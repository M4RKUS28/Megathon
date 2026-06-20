"""Course-generation orchestration, executed by the Arq worker.

Each entrypoint opens its own DB session (worker process), advances job/course
state, and persists results.
"""

import logging
import re
import uuid

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
        target_text = payload.get("target_text")

        try:
            # Phase-2-aware edit: rewrite the selected block (or the spec) and
            # re-render a real preview reusing the course's existing assets.
            from src.services.agents.editor import generate_edited_spec

            new_spec = await generate_edited_spec(
                course.spec, edit.prompt, edit.target_selector, target_text
            )
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
            job.result = {
                "spec": new_spec,
                "preview_index_url": preview["course_url"],
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
        await db.commit()

        try:
            snapshot = course.style_guide_snapshot or {}
            brief = snapshot.get("brief", {"title": course.title})
            company_name, _primary, _style = await _branding(db, course.company_id)

            plan = await generate_plan(brief, company_name)
            course.plan = plan.model_dump()
            course.status = COURSE_PLAN_REVIEW  # approval gate
            job.status = JOB_SUCCEEDED
            job.result = {"chapters": len(plan.chapters)}
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
            lastenheft = await generate_lastenheft(plan, company_name, primary)

            spec = lastenheft.model_dump()
            course.spec = spec
            course.asset_manifest = {"assets": spec.get("asset_manifest", [])}
            course.status = COURSE_SPEC_READY
            job.status = JOB_SUCCEEDED
            job.result = {
                "chapters": len(lastenheft.chapters),
                "assets": len(lastenheft.asset_manifest),
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
    """Phase 2.5 (assets) + Phase 3 (implementation) + Phase 4 (hosting)."""
    from src.services.generation.assets import fetch_assets, publish_asset_map

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

            # Phase 2.5 process A — resource fetch -> asset_map.json. After an
            # accepted edit we reuse the already-fetched assets (no re-generation).
            reuse = bool((job.payload or {}).get("reuse_assets")) and bool(course.asset_map)
            if reuse:
                asset_map = course.asset_map or {}
            else:
                asset_map = fetch_assets(manifest, prefix, primary)
            publish_asset_map(prefix, asset_map)

            # Phase 2.5 process B / Phase 3 — Devin authors the per-course app
            # (optional; falls back to the template build inside the builder).
            from src.services.generation.devin_codegen import generate_course_app

            devin_session_id, source_files = await generate_course_app(
                course.spec, asset_map
            )

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
            course.asset_map = asset_map
            course.dist_object_prefix = hosting["prefix"]
            course.course_url = hosting["course_url"]
            course.iframe_url = hosting["iframe_url"]
            course.status = COURSE_READY
            job.status = JOB_SUCCEEDED
            job.result = {
                "assets": len(asset_map),
                "built": hosting["built"],
                "course_url": hosting["course_url"],
                "iframe_url": hosting["iframe_url"],
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
