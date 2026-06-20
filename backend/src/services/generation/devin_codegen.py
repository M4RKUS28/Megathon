"""Phase 3 — Devin Implementation Agent (per-course code generation).

Build-mode resolution (``COURSE_BUILD_MODE``, default ``auto``):

- **auto** — use Devin when ``DEVIN_API_KEY`` + ``DEVIN_ORG_ID`` are present,
  otherwise fall back transparently to the local template build.
- **devin** — always attempt Devin; still falls back to template on failure
  (pipeline never hard-fails due to code-gen).
- **template** — skip Devin entirely, always use the prebuilt template.

The legacy env var ``COURSE_BUILD_USE_DEVIN=true`` is treated as ``devin`` mode.

We keep hosting under our control (MinIO) rather than asking Devin to host, so the
generated app stays sandboxed and embeddable.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.config.settings import settings
from src.services.devin.client import DevinClient, DevinError

logger = logging.getLogger(__name__)

# Structured output: a flat map of project files. Constrained so the session must
# return enough to `npm install && npm run build` into a static dist/.
COURSE_APP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["files"],
    "properties": {
        "files": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["path", "content"],
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
            },
        }
    },
}


def _build_prompt(spec: dict, asset_map: dict) -> str:
    course = {k: v for k, v in spec.items() if k != "asset_manifest"}
    return (
        "You are the Devin Implementation Agent. Build a COMPLETE, self-contained "
        "Vite + React + TypeScript single-page application that renders the "
        "interactive course described by the Lastenheft below.\n\n"
        "Requirements:\n"
        "- Use Vite, React, TypeScript, Tailwind. You may add Framer Motion, "
        "Chart.js/Recharts, React Flow as needed for the interactions.\n"
        "- Implement every chapter, page and block type (heading, paragraph, list, "
        "callout, image, video, audio, dialogue, chart, flashcards, dragdrop, "
        "hotspot, timeline, accordion, scenario).\n"
        "- A chapter-end quiz is mandatory; require >=80% to unlock the next chapter, "
        "and allow retry below 80%.\n"
        "- Reference assets STRICTLY by their template_link (e.g. "
        '<img src="/resources/images/01" />); a build step maps them to real URLs '
        "via /asset_map.json which is loaded at runtime.\n"
        "- The app must build to static files with `npm run build` (output dir dist/). "
        "Read /course.json and /asset_map.json from the public/ root at runtime.\n"
        "- Include package.json, vite.config.ts, tsconfig.json, index.html, and all "
        "src/ files. Do not include node_modules or dist.\n\n"
        "Return ONLY structured output: a `files` array of {path, content} covering "
        "the whole project. Use forward-slash relative paths.\n\n"
        f"=== Lastenheft (course.json) ===\n{json.dumps(course)[:120000]}\n\n"
        f"=== asset_map.json ===\n{json.dumps(asset_map)[:20000]}\n"
    )


def _validate_files(output: dict) -> dict[str, str] | None:
    files = output.get("files") if isinstance(output, dict) else None
    if not isinstance(files, list) or not files:
        return None
    result: dict[str, str] = {}
    for entry in files:
        if not isinstance(entry, dict):
            continue
        path = entry.get("path")
        content = entry.get("content")
        if not isinstance(path, str) or not isinstance(content, str):
            continue
        # Reject path traversal / absolute paths.
        norm = path.lstrip("/")
        if ".." in norm.split("/") or not norm:
            logger.warning("skipping unsafe generated path: %s", path)
            continue
        result[norm] = content
    if "package.json" not in result:
        logger.warning("Devin output missing package.json; rejecting")
        return None
    return result


async def generate_course_app(
    spec: dict, asset_map: dict
) -> tuple[str | None, dict[str, str] | None]:
    """Return (devin_session_id, file map) or (None, None) to use the template.

    Mode resolution:
    - template: immediately return (None, None).
    - auto: use Devin only when credentials are configured; skip silently otherwise.
    - devin: always attempt Devin; warn loudly on misconfiguration but still fall
      back to avoid breaking the pipeline.
    """
    mode = settings.course_build_mode

    if mode == "template":
        return None, None

    client = DevinClient()
    if not client.enabled:
        if mode == "devin":
            logger.warning(
                "COURSE_BUILD_MODE=devin but Devin API not configured "
                "(missing DEVIN_API_KEY/DEVIN_ORG_ID); falling back to template"
            )
        else:
            logger.debug("Devin API not configured; using template (auto mode)")
        return None, None

    logger.info("Using Devin code-gen for course app (mode=%s)", mode)

    try:
        session_id, output = await client.run(
            _build_prompt(spec, asset_map),
            structured_output_schema=COURSE_APP_SCHEMA,
            title=f"Course app: {spec.get('title', 'course')}",
            tags=["coursive", "course-app"],
        )
    except DevinError as exc:
        logger.warning("Devin course-app generation failed (%s); falling back to template", exc)
        return None, None

    files = _validate_files(output)
    if not files:
        logger.warning("Devin returned no usable project files; falling back to template")
        return session_id, None
    logger.info("Devin authored %d project files for the course app", len(files))
    return session_id, files
