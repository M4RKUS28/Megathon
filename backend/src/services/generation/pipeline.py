"""Course-generation orchestration, executed by the Arq worker.

Each entrypoint opens its own DB session (worker process), advances job/course
state, and persists results.
"""

import asyncio
import logging
import re
import uuid
from collections import Counter
from typing import Any

from sqlalchemy import select

from src.db.crud.company import get_company
from src.db.crud.course import get_course_by_id, get_job
from src.db.database import AsyncSessionLocal
from src.db.models.company import CompanyBranding
from src.db.models.course import (
    COURSE_AUTHORING,
    COURSE_BUILDING,
    COURSE_FAILED,
    COURSE_PLAN_REVIEW,
    COURSE_READY,
    COURSE_SPEC_READY,
    JOB_BUILD,
    JOB_FAILED,
    JOB_RUNNING,
    JOB_SUCCEEDED,
    EditRequest,
)
from src.services.generation.builder import publish_built_course

logger = logging.getLogger(__name__)

_HSL_TRIPLE = re.compile(
    r"^\d{1,3}(?:\.\d+)?\s+\d{1,3}(?:\.\d+)?%\s+\d{1,3}(?:\.\d+)?%$"
)


def _css_color(value: str | None) -> str:
    """Normalize a brand color into a valid standalone CSS color.

    Branding stores the primary color as a Tailwind HSL triple (e.g.
    ``"262 83% 58%"``) so the main app can use it as ``hsl(var(--primary))``.
    Per-course artifacts instead use the color directly as ``var(--brand)``,
    where a bare triple is invalid CSS and renders transparent (invisible
    buttons). Wrap bare triples in ``hsl()``; leave hex/rgb/named colors as-is.
    """
    v = (value or "").strip()
    if not v:
        return "#5145E5"
    if _HSL_TRIPLE.match(v):
        return f"hsl({v})"
    return v


async def _branding(db, company_id: uuid.UUID) -> tuple[str, str, dict]:
    company = await get_company(db, company_id)
    company_name = company.name if company else "Coursive"
    result = await db.execute(
        select(CompanyBranding).where(CompanyBranding.company_id == company_id)
    )
    branding = result.scalar_one_or_none()
    primary = _css_color(branding.primary_color if branding else None)
    style_guide = (branding.style_guide if branding else {}) or {}
    return company_name, primary, style_guide


async def process_edit_job(job_id: str) -> None:
    async with AsyncSessionLocal() as db:
        job = await get_job(db, uuid.UUID(job_id))
        if job is None:
            logger.error("edit job %s not found", job_id)
            return
        payload = job.payload or {}
        edit_id = payload.get("edit_request_id")
        result = await db.execute(select(EditRequest).where(EditRequest.id == uuid.UUID(edit_id)))
        edit = result.scalar_one_or_none()
        course = await get_course_by_id(db, job.course_id)
        if edit is None or course is None or course.spec is None:
            job.status = JOB_FAILED
            job.error = "edit request / course / spec missing"
            await db.commit()
            return

        job.status = JOB_RUNNING
        job.attempts += 1
        edit.status = "running"
        await db.commit()

        company = await get_company(db, course.company_id)
        slug = company.slug if company else "tenant"
        company_name = company.name if company else None
        target_text = payload.get("target_text")

        # Extract context for the hybrid tiered editor.
        plan = course.plan or {}
        plan_summary = plan.get("description") or plan.get("title")
        plan_audience = plan.get("audience")
        plan_compliance = plan.get("compliance_requirements") or []

        # Collect recent edit history for conversation threading.
        from sqlalchemy import select as sa_select

        prev_edits_result = await db.execute(
            sa_select(EditRequest)
            .where(EditRequest.course_id == course.id)
            .where(EditRequest.id != edit.id)
            .order_by(EditRequest.created_at.desc())
            .limit(10)
        )
        edit_history = [
            {"prompt": e.prompt, "status": e.status}
            for e in prev_edits_result.scalars().all()
        ]

        try:
            from src.services.agents.editor import generate_edited_spec

            edit_result = await generate_edited_spec(
                course.spec,
                edit.prompt,
                edit.target_selector,
                target_text,
                company_name=company_name,
                plan_summary=plan_summary,
                compliance_requirements=plan_compliance,
                audience=plan_audience,
                edit_history=edit_history or None,
            )
            new_spec = edit_result.new_spec

            if edit_result.devin_session_id:
                edit.devin_session_id = edit_result.devin_session_id

            preview = publish_built_course(
                slug,
                f"{course.id}/preview/{edit.id}",
                course.version,
                new_spec,
                course.asset_map or {},
            )
            edit.preview_object_prefix = preview["prefix"]
            edit.status = "preview_ready"
            job.status = JOB_SUCCEEDED

            diff_data = None
            if edit_result.diff:
                diff_data = {
                    "summary": edit_result.diff.summary,
                    "blocks": [
                        {
                            "location": f"{d.chapter}.{d.page}.{d.block}",
                            "action": d.action,
                            "old_type": d.old_type,
                            "new_type": d.new_type,
                        }
                        for d in edit_result.diff.changed
                    ],
                }

            job.result = {
                "spec": new_spec,
                "preview_index_url": preview["course_url"],
                "edit_tier": edit_result.edit_tier,
                "diff": diff_data,
                "validation_warnings": edit_result.validation_warnings,
                "devin_session_id": edit_result.devin_session_id,
            }
            await db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.exception("edit job %s failed", job_id)
            job.status = JOB_FAILED
            job.error = str(exc)
            edit.status = "failed"
            await db.commit()


# ── 5-phase pipeline ─────────────────────────────────────────────────────────


async def process_plan_job(job_id: str) -> None:
    """Phase 1 — run the planner agent; pause at the approval gate."""
    from src.services.agents.planner import generate_plan

    async with AsyncSessionLocal() as db:
        job = await get_job(db, uuid.UUID(job_id))
        if job is None:
            logger.error("plan job %s not found", job_id)
            return
        course = await get_course_by_id(db, job.course_id)
        if course is None:
            job.status = JOB_FAILED
            job.error = "course not found"
            await db.commit()
            return

        job.status = JOB_RUNNING
        job.attempts += 1
        job.result = {
            "tasks": [{"id": "plan-generate", "name": "Generate course plan", "service": "gemini", "status": "running"}],
        }
        await db.commit()

        try:
            snapshot = course.style_guide_snapshot or {}
            brief = snapshot.get("brief", {"title": course.title})
            company_name, _primary, _style = await _branding(db, course.company_id)

            plan = await generate_plan(brief, company_name)
            course.plan = plan.model_dump()
            course.status = COURSE_PLAN_REVIEW  # approval gate
            job.status = JOB_SUCCEEDED
            job.result = {
                "chapters": len(plan.chapters),
                "tasks": [{"id": "plan-generate", "name": "Generate course plan", "service": "gemini", "status": "done"}],
            }
            await db.commit()
            logger.info("plan ready for course %s (awaiting approval)", course.id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("plan job %s failed", job_id)
            job.status = JOB_FAILED
            job.error = str(exc)
            course.status = COURSE_FAILED
            await db.commit()


async def process_spec_job(job_id: str) -> None:
    """Phase 2 — script writer produces the Lastenheft + asset manifest, then
    automatically enqueues the build job (Phase 2.5/3/4)."""
    from src.services.agents.schemas import CoursePlan
    from src.services.agents.script_writer import generate_lastenheft
    from src.services.queue.pool import get_pool

    async with AsyncSessionLocal() as db:
        job = await get_job(db, uuid.UUID(job_id))
        if job is None:
            logger.error("spec job %s not found", job_id)
            return
        course = await get_course_by_id(db, job.course_id)
        if course is None or course.plan is None:
            job.status = JOB_FAILED
            job.error = "course or approved plan missing"
            await db.commit()
            return

        job.status = JOB_RUNNING
        job.attempts += 1
        course.status = COURSE_AUTHORING
        await db.commit()

        try:
            company_name, primary, _style = await _branding(db, course.company_id)
            plan = CoursePlan(**course.plan)

            # Build per-chapter task entries for spec phase
            spec_tasks = [
                {"id": f"spec-ch-{i+1}", "name": f"Write script: {ch.title}", "service": "gemini", "status": "running"}
                for i, ch in enumerate(plan.chapters)
            ]
            job.result = {"tasks": spec_tasks}
            await db.commit()

            lastenheft = await generate_lastenheft(plan, company_name, primary)

            spec = lastenheft.model_dump()
            course.spec = spec
            course.asset_manifest = {"assets": spec.get("asset_manifest", [])}
            course.status = COURSE_SPEC_READY
            job.status = JOB_SUCCEEDED
            # Mark all spec tasks as done
            for t in spec_tasks:
                t["status"] = "done"
            job.result = {
                "chapters": len(lastenheft.chapters),
                "assets": len(lastenheft.asset_manifest),
                "tasks": spec_tasks,
            }

            build_job = await _create_followup_job(db, course, JOB_BUILD)
            await db.commit()

            pool = await get_pool()
            await pool.enqueue_job("run_build_job", str(build_job.id))
            logger.info("spec ready for course %s; build enqueued", course.id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("spec job %s failed", job_id)
            job.status = JOB_FAILED
            job.error = str(exc)
            course.status = COURSE_FAILED
            await db.commit()


async def process_build_job(job_id: str) -> None:
    """Phase 2.5 (assets) + Phase 3 (implementation) + Phase 4 (hosting).

    Asset generation and Devin codegen run IN PARALLEL. The Devin session starts
    immediately with an empty asset_map (it uses template_link references during
    development). The real asset_map is only needed at the final publish step.

    If `COURSE_BUILD_PARALLEL_CHAPTERS` is enabled, multiple Devin sessions are
    spawned (one per chapter) instead of a single monolithic session.
    """
    from src.services.generation.assets import AssetProgress, fetch_assets, publish_asset_map

    async with AsyncSessionLocal() as db:
        job = await get_job(db, uuid.UUID(job_id))
        if job is None:
            logger.error("build job %s not found", job_id)
            return
        course = await get_course_by_id(db, job.course_id)
        if course is None or course.spec is None:
            job.status = JOB_FAILED
            job.error = "course or spec missing"
            await db.commit()
            return

        job.status = JOB_RUNNING
        job.attempts += 1
        course.status = COURSE_BUILDING
        await db.commit()

        try:
            company = await get_company(db, course.company_id)
            slug = company.slug if company else "tenant"
            _name, primary, _style = await _branding(db, course.company_id)

            from src.services.generation.builder import course_prefix

            prefix = course_prefix(slug, str(course.id), course.version)
            manifest = (course.asset_manifest or {}).get("assets", [])
            manifest_by_type = Counter((a or {}).get("type", "unknown") for a in manifest)
            logger.info(
                "build job %s asset manifest: course=%s prefix=%s total=%d by_type=%s",
                job_id,
                course.id,
                prefix,
                len(manifest),
                dict(sorted(manifest_by_type.items())),
            )

            # ── Initialize parallel_status tracking ──────────────────────────
            parallel_status: dict[str, Any] = {
                "assets": {
                    "status": "running",
                    "progress": {"total": len(manifest), "completed": 0},
                },
                "codegen": {"status": "running", "sessions": []},
            }

            # ── Build per-asset task entries for the expandable list ──────────
            def _service_for_asset_type(atype: str) -> str:
                if atype in ("audio", "narration"):
                    return "gemini-tts"
                if atype == "video":
                    return "pixverse"
                return "gemini-imagen"

            build_tasks: list[dict[str, str]] = []
            for i, a in enumerate(manifest):
                atype = (a or {}).get("type", "unknown")
                purpose = (a or {}).get("purpose", atype)[:40]
                build_tasks.append({
                    "id": f"asset-{i}",
                    "name": f"Generate {atype}: {purpose}",
                    "service": _service_for_asset_type(atype),
                    "status": "running",
                })
            # Codegen task placeholder
            build_tasks.append({
                "id": "codegen-main",
                "name": "Build course application",
                "service": "devin",
                "status": "running",
            })

            job.result = {**(job.result or {}), "parallel_status": parallel_status, "tasks": build_tasks}
            await db.commit()

            # ── Phase 2.5 process A — asset generation (may be reused) ───────
            reuse = bool((job.payload or {}).get("reuse_assets")) and bool(course.asset_map)

            async def _fetch_assets_async() -> dict[str, str]:
                if reuse:
                    logger.info(
                        "build job %s reusing existing asset_map: mapped=%d",
                        job_id,
                        len(course.asset_map or {}),
                    )
                    return course.asset_map or {}

                def _on_asset_progress(progress: AssetProgress) -> None:
                    parallel_status["assets"]["progress"] = progress.to_dict()
                    # Mark completed asset tasks
                    done_count = progress.completed + progress.failed
                    for i, t in enumerate(build_tasks):
                        if t["id"].startswith("asset-") and i < done_count:
                            t["status"] = "done"
                    job.result = {
                        **(job.result or {}),
                        "asset_progress": progress.to_dict(),
                        "parallel_status": parallel_status,
                        "tasks": build_tasks,
                    }

                # Use the new async fetch_assets with bounded concurrency
                result = await fetch_assets(
                    manifest, prefix, primary, on_progress=_on_asset_progress
                )
                return result

            # ── Phase 3 — Devin codegen (parallel with assets) ───────────────
            async def _on_devin_session(created: dict) -> None:
                session_id = created.get("session_id")
                if not session_id:
                    logger.warning("Devin create-session response missing session_id: %s", created)
                    return
                session_url = created.get("url")
                course.devin_session_id = session_id
                job.devin_session_id = session_id
                parallel_status["codegen"]["sessions"].append({
                    "chapter": "__main__",
                    "session_id": session_id,
                    "status": "running",
                })
                job.result = {
                    **(job.result or {}),
                    "devin_session_id": session_id,
                    "devin_session_url": session_url,
                    "devin_status": created.get("status"),
                    "parallel_status": parallel_status,
                }
                await db.commit()
                logger.info(
                    "devin session %s started for course %s (%s)",
                    session_id,
                    course.id,
                    session_url,
                )

            async def _on_chapter_session(index: int, title: str, created: dict) -> None:
                session_id = created.get("session_id")
                session_url = f"https://app.devin.ai/sessions/{session_id}" if session_id else None
                parallel_status["codegen"]["sessions"].append({
                    "chapter": title,
                    "session_id": session_id,
                    "status": "running",
                })
                # Add per-chapter task entry with Devin session link
                build_tasks.append({
                    "id": f"codegen-ch-{index+1}",
                    "name": f"Build chapter: {title}",
                    "service": "devin",
                    "status": "running",
                    "session_url": session_url,
                })
                job.result = {**(job.result or {}), "parallel_status": parallel_status, "tasks": build_tasks}
                await db.commit()
                logger.info(
                    "chapter %d (%s) devin session %s started for course %s",
                    index + 1,
                    title,
                    session_id,
                    course.id,
                )

            async def _run_codegen() -> tuple[str | None, dict[str, str] | None]:
                from src.config.settings import settings
                from src.services.generation.devin_codegen import (
                    generate_course_app,
                    generate_course_app_parallel,
                )

                # Try parallel chapter approach first

                if settings.course_build_parallel_chapters:
                    session_id, files, chapter_sessions = await generate_course_app_parallel(
                        course.spec,
                        {},  # empty asset_map — Devin uses template_links
                        on_session=_on_devin_session,
                        on_chapter_session=_on_chapter_session,
                    )
                    if files:
                        # Update chapter session statuses in parallel_status
                        if chapter_sessions:
                            parallel_status["codegen"]["sessions"] = [
                                {
                                    "chapter": s.get("chapter", ""),
                                    "session_id": s.get("session_id"),
                                    "status": s.get("status", "unknown"),
                                }
                                for s in chapter_sessions
                            ]
                        return session_id, files
                    logger.info("Parallel chapter approach failed; trying single session")

                # Fall back to single-session approach
                parallel_status["codegen"]["sessions"] = []
                return await generate_course_app(
                    course.spec,
                    {},  # empty asset_map — Devin uses template_links
                    on_session=_on_devin_session,
                )

            # ── Run assets + codegen IN PARALLEL ─────────────────────────────
            logger.info("build job %s: launching assets + codegen in parallel", job_id)
            asset_task = asyncio.create_task(_fetch_assets_async())
            codegen_task = asyncio.create_task(_run_codegen())

            # Wait for both to complete
            asset_map, (devin_session_id, source_files) = await asyncio.gather(
                asset_task, codegen_task
            )

            # ── Update parallel_status after both complete ───────────────────
            mapped_audio = sum(1 for key in asset_map if "/audio/" in key)
            expected_audio = manifest_by_type.get("audio", 0)
            logger.info(
                "build job %s asset_map ready: mapped=%d audio=%d/%d",
                job_id,
                len(asset_map),
                mapped_audio,
                expected_audio,
            )

            parallel_status["assets"] = {
                "status": "done",
                "progress": {"total": len(manifest), "completed": len(asset_map)},
            }
            parallel_status["codegen"]["status"] = "done"
            # Update individual session statuses
            for s in parallel_status["codegen"]["sessions"]:
                if s.get("status") == "running":
                    s["status"] = "done"
            # Mark all build tasks as done
            for t in build_tasks:
                if t["status"] == "running":
                    t["status"] = "done"
            job.result = {**(job.result or {}), "parallel_status": parallel_status, "tasks": build_tasks}
            await db.commit()

            # Publish the final asset_map now that assets are ready
            await publish_asset_map(prefix, asset_map)

            # Phase 3 + 4 — build per-course app and host it
            hosting = publish_built_course(
                slug,
                str(course.id),
                course.version,
                course.spec,
                asset_map,
                source_files=source_files,
            )

            if devin_session_id:
                job.devin_session_id = devin_session_id
                course.devin_session_id = devin_session_id
            course.asset_map = asset_map
            course.dist_object_prefix = hosting["prefix"]
            course.course_url = hosting["course_url"]
            course.iframe_url = hosting["iframe_url"]
            course.status = COURSE_READY
            job.status = JOB_SUCCEEDED
            # Add final hosting task
            build_tasks.append({
                "id": "hosting",
                "name": "Deploy course app",
                "service": "internal",
                "status": "done",
            })
            job.result = {
                "assets": len(asset_map),
                "built": hosting["built"],
                "course_url": hosting["course_url"],
                "iframe_url": hosting["iframe_url"],
                "devin_session_id": devin_session_id,
                "devin_session_url": (job.result or {}).get("devin_session_url"),
                "asset_progress": (job.result or {}).get("asset_progress"),
                "parallel_status": parallel_status,
                "tasks": build_tasks,
            }
            await db.commit()
            logger.info("course %s built & hosted at %s", course.id, hosting["prefix"])
        except Exception as exc:  # noqa: BLE001
            logger.exception("build job %s failed", job_id)
            job.status = JOB_FAILED
            job.error = str(exc)
            course.status = COURSE_FAILED
            await db.commit()


async def _create_followup_job(db, course, job_type: str):
    """Create a queued GenerationJob row for the next pipeline phase."""
    from src.db.crud.course import create_job

    return await create_job(db, course.id, course.company_id, job_type)
