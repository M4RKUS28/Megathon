"""Publish a generated course to MinIO.

Each course is rendered by populating the prebuilt Vite course-template (which
loads `concept.json` at runtime) and uploading the static files to the public
`courses` bucket under a versioned prefix. Nginx proxies `/storage/courses/...`
so the platform can embed the result via iframe.
"""

import json
import logging
import mimetypes
import os
from pathlib import Path

from src.config.settings import settings
from src.db.minio import ensure_bucket_exists, public_object_url, put_bytes, put_file

logger = logging.getLogger(__name__)

# Repo-relative fallback for local runs where the image path doesn't exist.
_REPO_FALLBACK = Path(__file__).resolve().parents[4] / "courses-template" / "dist"


def _template_dist() -> Path:
    configured = Path(settings.course_template_dist)
    if configured.is_dir():
        return configured
    if _REPO_FALLBACK.is_dir():
        return _REPO_FALLBACK
    raise FileNotFoundError(
        f"Course template dist not found at {configured} or {_REPO_FALLBACK}. "
        "Build courses-template (npm run build) first."
    )


def course_prefix(company_slug: str, course_id: str, version: int) -> str:
    return f"{company_slug}/{course_id}/v{version}"


def index_url(prefix: str) -> str:
    return public_object_url(f"{prefix}/index.html", settings.courses_bucket)


def publish_course(company_slug: str, course_id: str, version: int, concept: dict) -> str:
    """Upload the template + concept.json under a versioned prefix; return prefix."""
    ensure_bucket_exists(settings.courses_bucket)
    dist = _template_dist()
    prefix = course_prefix(company_slug, course_id, version)

    for root, _dirs, files in os.walk(dist):
        for name in files:
            local = Path(root) / name
            rel = local.relative_to(dist).as_posix()
            content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
            put_file(str(local), f"{prefix}/{rel}", settings.courses_bucket, content_type)

    put_bytes(
        json.dumps(concept).encode("utf-8"),
        f"{prefix}/concept.json",
        settings.courses_bucket,
        "application/json",
    )
    logger.info("Published course %s v%s -> %s", course_id, version, prefix)
    return prefix
