from __future__ import annotations

import asyncio
from typing import Any

from .assets import build_asset_map
from .config import Settings, get_settings
from .devin import DevinClient, get_devin_client
from .planner import apply_chapter_edits, generate_course_plan
from .prompts import asset_integration_prompt, implementation_prompt, qa_prompt
from .repository import (
    create_devin_job,
    get_course,
    get_devin_job,
    get_latest_plan,
    get_latest_spec,
    list_assets,
    mark_plan_approved,
    replace_assets_from_manifest,
    save_devin_event,
    save_generated_prompt,
    save_hosted_output,
    save_plan,
    save_qa_result,
    save_spec,
    update_asset_map,
    update_course_status,
    update_devin_job,
)
from .schemas import CourseCreate
from .specs import build_course_spec
from .timeutils import now_iso


TERMINAL_STATUSES = {"exit", "error"}


async def run_preflight(settings: Settings | None = None, client: DevinClient | None = None, prepare_repository: bool = False) -> dict[str, Any]:
    settings = settings or get_settings()
    client = client or get_devin_client(settings)
    try:
        return await client.preflight(prepare_repository=prepare_repository)
    except Exception as exc:
        return {"ok": False, "mode": "real" if not settings.testing else "testing_fake", "checks": {}, "error": str(exc)}


def create_plan_for_course(course_id: str) -> dict:
    course = get_course(course_id)
    if not course:
        raise ValueError("Course not found")
    plan = generate_course_plan(CourseCreate(**course))
    return save_plan(course_id, plan, "draft")


def approve_plan(course_id: str, chapter_edits: list[dict] | None = None) -> dict:
    course = get_course(course_id)
    latest_plan = get_latest_plan(course_id)
    if not course or not latest_plan:
        raise ValueError("Course or plan not found")
    plan = apply_chapter_edits(latest_plan["plan"], chapter_edits)
    mark_plan_approved(latest_plan["id"], plan)
    spec_markdown, spec, asset_manifest = build_course_spec(course, plan)
    saved_spec = save_spec(course_id, spec_markdown, spec, asset_manifest)
    replace_assets_from_manifest(course_id, asset_manifest)
    update_course_status(course_id, "approved", approved=True)
    return {"course": course, "plan": plan, "spec": saved_spec}


def _extract_structured(payload: dict[str, Any]) -> dict[str, Any]:
    structured = payload.get("structured_output") or {}
    if not isinstance(structured, dict):
        return {}
    return structured


def _branch_commit_pr(payload: dict[str, Any]) -> tuple[str | None, str | None, str | None, str | None]:
    structured = _extract_structured(payload)
    pr_url = structured.get("pr_url")
    if not pr_url:
        for pr in payload.get("pull_requests") or []:
            if pr.get("pr_url"):
                pr_url = pr["pr_url"]
                break
    return structured.get("branch"), structured.get("commit_sha"), pr_url, structured.get("summary") or structured.get("qa_notes")


async def launch_devin_phase(course_id: str, phase: str, prompt: str, settings: Settings, client: DevinClient) -> dict:
    save_generated_prompt(course_id, phase, prompt)
    job = create_devin_job(course_id, phase, prompt)
    save_devin_event(course_id, job["id"], "job_queued", "queued", f"{phase} Devin job queued", {})
    try:
        response = await client.create_session(title=f"CourseForge Devin: {phase}", prompt=prompt, tags=["courseforge-devin", phase, course_id])
        branch, commit_sha, pr_url, summary = _branch_commit_pr(response)
        update_devin_job(
            job["id"],
            devin_session_id=response.get("session_id"),
            devin_job_id=response.get("session_id"),
            status=response.get("status", "created"),
            branch=branch,
            commit_sha=commit_sha,
            pr_url=pr_url,
            transcript_summary=summary,
            raw_status_payload=response,
        )
        save_devin_event(course_id, job["id"], "job_created", response.get("status", "created"), f"{phase} Devin session created", response)
        job = get_devin_job(job["id"]) or job
        if response.get("status") in TERMINAL_STATUSES or response.get("status_detail") == "finished":
            update_devin_job(job["id"], status=response.get("status", "exit"), completed_at=now_iso())
            return get_devin_job(job["id"]) or job
        return await poll_devin_job(course_id, job["id"], settings, client)
    except Exception as exc:
        update_devin_job(job["id"], status="error", error=str(exc), completed_at=now_iso())
        save_devin_event(course_id, job["id"], "job_error", "error", str(exc), {})
        raise


async def poll_devin_job(course_id: str, job_id: str, settings: Settings, client: DevinClient) -> dict:
    started = asyncio.get_event_loop().time()
    while True:
        job = get_devin_job(job_id)
        if not job or not job.get("devin_session_id"):
            raise ValueError("Cannot poll Devin job without a session id")
        payload = await client.get_session(job["devin_session_id"])
        messages = await client.list_messages(job["devin_session_id"])
        branch, commit_sha, pr_url, summary = _branch_commit_pr(payload)
        if not summary:
            items = messages.get("items") or []
            summary = items[-1]["message"] if items else None
        status = payload.get("status", "unknown")
        completed = status in TERMINAL_STATUSES or payload.get("status_detail") == "finished"
        update_devin_job(
            job_id,
            status=status,
            branch=branch,
            commit_sha=commit_sha,
            pr_url=pr_url,
            transcript_summary=summary,
            raw_status_payload={"session": payload, "messages": messages},
            completed_at=now_iso() if completed else None,
        )
        save_devin_event(course_id, job_id, "job_polled", status, summary or "Polled Devin status", {"session": payload, "messages": messages})
        if completed:
            return get_devin_job(job_id) or job
        if asyncio.get_event_loop().time() - started > settings.poll_timeout_seconds:
            update_devin_job(job_id, status="error", error="Polling timed out", completed_at=now_iso())
            raise TimeoutError("Devin polling timed out")
        await asyncio.sleep(max(1, settings.poll_interval_seconds))


async def run_autonomous_pipeline(course_id: str, settings: Settings | None = None, client: DevinClient | None = None) -> None:
    settings = settings or get_settings()
    client = client or get_devin_client(settings)
    course = get_course(course_id)
    plan_record = get_latest_plan(course_id)
    spec_record = get_latest_spec(course_id)
    if not course or not plan_record or not spec_record:
        raise ValueError("Course must be approved with a plan and spec before launching Devin")

    update_course_status(course_id, "devin_implementation_running")
    impl_prompt = implementation_prompt(course, plan_record["plan"], spec_record["spec"], spec_record["asset_manifest"], settings)
    await launch_devin_phase(course_id, "implementation", impl_prompt, settings, client)

    asset_map = build_asset_map(spec_record["asset_manifest"])
    update_asset_map(course_id, asset_map)
    save_devin_event(course_id, None, "asset_worker_completed", "ready", "Local asset map generated", {"asset_map": asset_map})

    update_course_status(course_id, "devin_asset_integration_running")
    integration_prompt = asset_integration_prompt(course, asset_map, settings)
    await launch_devin_phase(course_id, "asset_integration", integration_prompt, settings, client)

    update_course_status(course_id, "devin_qa_running")
    qa_job = await launch_devin_phase(course_id, "qa", qa_prompt(course, settings), settings, client)
    save_qa_result(course_id, qa_job.get("status", "unknown"), qa_job.get("raw_status_payload") or {})
    save_hosted_output(course_id)
    update_course_status(course_id, "ready_for_demo")


async def launch_manual_phase(course_id: str, phase: str, settings: Settings | None = None, client: DevinClient | None = None) -> dict:
    settings = settings or get_settings()
    client = client or get_devin_client(settings)
    course = get_course(course_id)
    plan_record = get_latest_plan(course_id)
    spec_record = get_latest_spec(course_id)
    if not course or not plan_record:
        raise ValueError("Course and plan required")
    if phase == "implementation":
        if not spec_record:
            raise ValueError("Spec required for implementation")
        prompt = implementation_prompt(course, plan_record["plan"], spec_record["spec"], spec_record["asset_manifest"], settings)
    elif phase == "asset_integration":
        asset_map = [
            {
                "template_link": asset["template_link"],
                "status": asset["status"],
                "final_url": asset["final_url"],
                "validation_result": asset["validation_result"],
                "source": asset["source"],
                "updated_at": asset["updated_at"],
            }
            for asset in list_assets(course_id)
        ]
        prompt = asset_integration_prompt(course, asset_map, settings)
    elif phase == "qa":
        prompt = qa_prompt(course, settings)
    else:
        raise ValueError(f"Unsupported phase {phase}")
    return await launch_devin_phase(course_id, phase, prompt, settings, client)
