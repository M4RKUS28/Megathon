"""Arq task entrypoints for the course-generation pipeline.

These are thin wrappers invoked by the worker; the real orchestration lives in
`pipeline.py` (added in the generation phase). Kept importable so the worker can
boot from the first commit.
"""

import logging

logger = logging.getLogger(__name__)


async def run_edit_job(ctx: dict, job_id: str) -> None:
    from src.services.generation.pipeline import process_edit_job

    await process_edit_job(job_id)


# ── 5-phase pipeline ─────────────────────────────────────────────────────────


async def run_plan_job(ctx: dict, job_id: str) -> None:
    from src.services.generation.pipeline import process_plan_job

    await process_plan_job(job_id)


async def run_spec_job(ctx: dict, job_id: str) -> None:
    from src.services.generation.pipeline import process_spec_job

    await process_spec_job(job_id)


async def run_build_job(ctx: dict, job_id: str) -> None:
    from src.services.generation.pipeline import process_build_job

    await process_build_job(job_id)
