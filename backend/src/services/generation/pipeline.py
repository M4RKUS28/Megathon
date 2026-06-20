"""Course-generation orchestration, executed by the Arq worker.

Each entrypoint opens its own DB session (worker process), advances job/course
state, and persists results.
"""

import logging
import uuid

from sqlalchemy import select

from src.db.crud.company import get_company
from src.db.crud.course import get_course_by_id, get_job
from src.db.database import AsyncSessionLocal
from src.db.models.company import CompanyBranding
from src.db.models.course import (
    COURSE_CONCEPT_READY,
    COURSE_FAILED,
    COURSE_GENERATING,
    COURSE_READY,
    JOB_FAILED,
    JOB_RUNNING,
    JOB_SUCCEEDED,
    EditRequest,
)
from src.services.generation.builder import index_url, publish_course
from src.services.generation.concept import generate_concept, generate_edited_concept

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

        try:
            snapshot = course.style_guide_snapshot or {}
            brief = snapshot.get("brief", {"title": course.title})
            company_name, primary, style_guide = await _branding(db, course.company_id)

            session_id, concept = await generate_concept(
                brief, style_guide, company_name, primary
            )

            course.concept = concept
            course.devin_session_id = session_id
            course.status = COURSE_CONCEPT_READY
            job.status = JOB_SUCCEEDED
            job.devin_session_id = session_id
            job.result = {"chapters": len(concept.get("chapters", []))}
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

        try:
            company = await get_company(db, course.company_id)
            slug = company.slug if company else "tenant"
            prefix = publish_course(slug, str(course.id), course.version, course.concept)

            course.dist_object_prefix = prefix
            course.status = COURSE_READY
            job.status = JOB_SUCCEEDED
            job.result = {"prefix": prefix, "index_url": index_url(prefix)}
            await db.commit()
            logger.info("course %s built at %s", course.id, prefix)
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

        try:
            session_id, new_concept = await generate_edited_concept(
                course.concept, edit.prompt, payload.get("target_text")
            )
            company = await get_company(db, course.company_id)
            slug = company.slug if company else "tenant"
            # Publish the proposed version under a per-edit preview path.
            preview_prefix = publish_course(
                slug, f"{course.id}/preview/{edit.id}", course.version, new_concept
            )

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
