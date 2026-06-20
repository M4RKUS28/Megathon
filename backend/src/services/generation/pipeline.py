"""Course-generation orchestration.

The full Devin-API pipeline is implemented in the generation phase. These
entrypoints are referenced by the Arq worker tasks; until the pipeline lands
they are inert no-ops so the worker can boot and accept jobs.
"""

import logging

logger = logging.getLogger(__name__)


async def process_concept_job(job_id: str) -> None:
    logger.info("process_concept_job(%s) — pipeline not yet implemented", job_id)


async def process_generate_job(job_id: str) -> None:
    logger.info("process_generate_job(%s) — pipeline not yet implemented", job_id)


async def process_edit_job(job_id: str) -> None:
    logger.info("process_edit_job(%s) — pipeline not yet implemented", job_id)
