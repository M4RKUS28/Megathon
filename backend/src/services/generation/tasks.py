"""Arq task entrypoints for the course-generation pipeline.

These are thin wrappers invoked by the worker; the real orchestration lives in
`pipeline.py` (added in the generation phase). Kept importable so the worker can
boot from the first commit.
"""

import logging

logger = logging.getLogger(__name__)


async def run_concept_job(ctx: dict, job_id: str) -> None:
    from src.services.generation.pipeline import process_concept_job

    await process_concept_job(job_id)


async def run_generate_job(ctx: dict, job_id: str) -> None:
    from src.services.generation.pipeline import process_generate_job

    await process_generate_job(job_id)


async def run_edit_job(ctx: dict, job_id: str) -> None:
    from src.services.generation.pipeline import process_edit_job

    await process_edit_job(job_id)
