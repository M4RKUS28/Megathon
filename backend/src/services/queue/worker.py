"""Arq worker process.

Run with: `uv run arq src.services.queue.worker.WorkerSettings`

Generation tasks (concept / generate / edit) are registered here. The concrete
task implementations live in `src.services.generation.tasks`.
"""

import logging

from src.config.settings import settings
from src.services.generation.tasks import (
    run_build_job,
    run_concept_job,
    run_edit_job,
    run_generate_job,
    run_plan_job,
    run_spec_job,
)
from src.services.queue.pool import redis_settings

logging.basicConfig(level=settings.log_level)


async def ping(ctx: dict) -> str:
    return "pong"


class WorkerSettings:
    functions = [
        run_concept_job,
        run_generate_job,
        run_edit_job,
        run_plan_job,
        run_spec_job,
        run_build_job,
        ping,
    ]
    redis_settings = redis_settings()
    max_jobs = 4
    job_timeout = 60 * 60  # course generation can take many minutes
