"""Course-generation orchestration, executed by the Arq worker.

Each entrypoint opens its own DB session (worker process), advances job/course
state, emits live progress messages, runs the media pass, and persists results.
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from src.db.crud.company import get_company
from src.db.crud.course import get_course_by_id, get_job
from src.db.database import AsyncSessionLocal
from src.db.models.company import CompanyBranding
from src.db.models.course import (
    COURSE_AUTHORING,
    COURSE_BUILDING,
    COURSE_CONCEPT_READY,
    COURSE_FAILED,
    COURSE_GENERATING,
    COURSE_PLAN_REVIEW,
    COURSE_READY,
    COURSE_SPEC_READY,
    JOB_BUILD,
    JOB_FAILED,
    JOB_RUNNING,
    JOB_SUCCEEDED,
    EditRequest,
    GenerationJob,
)
from src.services.generation.builder import (
    course_prefix,
    index_url,
    publish_built_course,
    publish_course,
)
from src.services.generation.concept import generate_concept, generate_edited_concept
from src.services.generation.media import generate_media_for_concept

logger = logging.getLogger(__name__)


async def _branding(db, company_id: uuid.UUID) -> tuple[str, str, dict]:
    company = await get_company(db, company_id)
    company_name = company.name if company else "Coursive"
    result = await db.execute(
        select(CompanyBranding).where(CompanyBranding.company_id == company_id)
    )
    branding = result.scalar_one_or_none()
    primary = (branding.primary_color if branding else None) or "#5145E5"
    style_guide = (branding.style_guide if branding else {}) or {}
    return company_name, primary, style_guide


async def _progress(db, job: GenerationJob, message: str, pct: int) -> None:
    """Append a live progress step to the job and commit so the UI can poll it."""
    steps = list((job.progress or {}).get("steps", []))
    steps.append({"message": message, "pct": pct})
    job.progress = {"pct": pct, "message": message, "steps": steps[-25:]}
    await db.commit()
    logger.info("job %s: %s (%s%%)", job.id, message, pct)


async def process_concept_job(job_id: str) -> None:
    async with AsyncSessionLocal() as db:
        job = await get_job(db, uuid.UUID(job_id))
        if job is None:
            logger.error("concept job %s not found", job_id)
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
        await _progress(db, job, "Reviewing your course brief…", 10)

        try:
            snapshot = course.style_guide_snapshot or {}
            brief = snapshot.get("brief", {"title": course.title})
            company_name, primary, style_guide = await _branding(db, course.company_id)

            await _progress(db, job, "Devin is designing an interactive course…", 35)
            session_id, concept = await generate_concept(
                brief, style_guide, company_name, primary
            )

            n = len(concept.get("chapters", []))
            await _progress(db, job, f"Concept ready — {n} interactive chapters drafted.", 100)
            course.concept = concept
            course.devin_session_id = session_id
            course.status = COURSE_CONCEPT_READY
            job.status = JOB_SUCCEEDED
            job.devin_session_id = session_id
            job.result = {"chapters": n}
            await db.commit()
            logger.info("concept ready for course %s", course.id)
        except Exception as exc:  # noqa: BLE001 — surface failure into job/course state
            logger.exception("concept job %s failed", job_id)
            job.status = JOB_FAILED
            job.error = str(exc)
            course.status = COURSE_FAILED
            await db.commit()


async def process_generate_job(job_id: str) -> None:
    async with AsyncSessionLocal() as db:
        job = await get_job(db, uuid.UUID(job_id))
        if job is None:
            logger.error("generate job %s not found", job_id)
            return
        course = await get_course_by_id(db, job.course_id)
        if course is None or course.concept is None:
            job.status = JOB_FAILED
            job.error = "course or concept missing"
            await db.commit()
            return

        job.status = JOB_RUNNING
        job.attempts += 1
        course.status = COURSE_GENERATING
        await db.commit()
        await _progress(db, job, "Preparing the interactive build…", 5)

        try:
            company = await get_company(db, course.company_id)
            slug = company.slug if company else "tenant"
            prefix = course_prefix(slug, str(course.id), course.version)

            await _progress(db, job, "Generating images, narration and video…", 15)

            async def cb(message: str, pct: int) -> None:
                # Map media progress (0-100) into the 15-90 band.
                await _progress(db, job, message, 15 + int(pct * 0.75))

            concept = await generate_media_for_concept(course.concept, prefix, cb)
            course.concept = concept
            flag_modified(course, "concept")

            await _progress(db, job, "Building and publishing the course…", 92)
            published = publish_course(slug, str(course.id), course.version, concept)

            await _progress(db, job, "Course ready.", 100)
            course.dist_object_prefix = published
            course.status = COURSE_READY
            job.status = JOB_SUCCEEDED
            job.result = {"prefix": published, "index_url": index_url(published)}
            await db.commit()
            logger.info("course %s built at %s", course.id, published)
        except Exception as exc:  # noqa: BLE001
            logger.exception("generate job %s failed", job_id)
            job.status = JOB_FAILED
            job.error = str(exc)
            course.status = COURSE_FAILED
            await db.commit()


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
        if edit is None or course is None or course.concept is None:
            job.status = JOB_FAILED
            job.error = "edit request / course / concept missing"
            await db.commit()
            return

        job.status = JOB_RUNNING
        job.attempts += 1
        edit.status = "running"
        await db.commit()
        await _progress(db, job, "Devin is applying your edit…", 20)

        try:
            session_id, new_concept = await generate_edited_concept(
                course.concept, edit.prompt, payload.get("target_text")
            )
            company = await get_company(db, course.company_id)
            slug = company.slug if company else "tenant"
            preview_id = f"{course.id}/preview/{edit.id}"
            prefix = course_prefix(slug, preview_id, course.version)

            await _progress(db, job, "Refreshing media for changed sections…", 55)

            async def cb(message: str, pct: int) -> None:
                await _progress(db, job, message, 55 + int(pct * 0.35))

            new_concept = await generate_media_for_concept(new_concept, prefix, cb)

            await _progress(db, job, "Publishing preview…", 92)
            preview_prefix = publish_course(slug, preview_id, course.version, new_concept)

            await _progress(db, job, "Preview ready.", 100)
            edit.devin_session_id = session_id
            edit.preview_object_prefix = preview_prefix
            edit.status = "preview_ready"
            job.status = JOB_SUCCEEDED
            job.devin_session_id = session_id
            job.result = {
                "concept": new_concept,
                "preview_index_url": index_url(preview_prefix),
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

            # Phase 2.5 process A — resource fetch -> asset_map.json
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
