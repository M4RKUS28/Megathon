"""Phase 3 — Devin Implementation Agent (per-course code generation).

When `COURSE_BUILD_USE_DEVIN` is enabled and the Devin API is configured, this
authors each course's OWN Vite/React/TS application from the Lastenheft by running
a real Devin coding session that returns the project source files as structured
output. The builder then writes those files, runs `npm run build`, and publishes
the resulting `dist/` (Phase 4). If Devin is unavailable or fails, the caller
falls back to the prebuilt `course-app-template` build.

A **build-validate-repair loop** tries the generated files, and — on build,
typecheck, lint or test failure — sends the exact error logs back to Devin for a
repair attempt (up to ``settings.course_build_repair_max_retries`` iterations).
Only when every attempt is exhausted does the caller fall back to the template.

We keep hosting under our control (MinIO) rather than asking Devin to host, so the
generated app stays sandboxed and embeddable.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.config.settings import settings
from src.services.devin.client import DevinClient, DevinError
from src.services.generation.builder import BuildError, try_build_from_sources

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


def _repair_prompt(
    error_logs: str,
    source_files: dict[str, str],
    spec: dict,
    asset_map: dict,
) -> str:
    """Build a concise repair prompt with exact error logs and current files."""
    file_listing = "\n".join(
        f"  {path} ({len(content)} chars)" for path, content in sorted(source_files.items())
    )
    # Truncate logs to keep the prompt within reasonable bounds.
    truncated_logs = error_logs[:12000]

    course = {k: v for k, v in spec.items() if k != "asset_manifest"}
    return (
        "You are the Devin Repair Agent. The course application you previously "
        "generated failed to build/typecheck/lint/test. Your task is to fix ONLY "
        "the implementation and build issues.\n\n"
        "STRICT RULES:\n"
        "- Fix ONLY implementation errors, type errors, build configuration, and "
        "missing/incorrect imports.\n"
        "- Do NOT change the curriculum, educational content, quiz questions, "
        "passing thresholds (>=80%), block types, chapter/page structure, or any "
        "pedagogical content.\n"
        "- Do NOT change the platform contracts: the app must read /course.json "
        "and /asset_map.json from public/ at runtime, reference assets by "
        "template_link, and build to dist/ via `npm run build`.\n"
        "- Return the COMPLETE corrected file map (every file, not just changed "
        "ones).\n\n"
        f"=== BUILD ERROR LOGS ===\n{truncated_logs}\n\n"
        f"=== CURRENT FILES ===\n{file_listing}\n\n"
        "=== FILE CONTENTS ===\n"
        + "\n".join(
            f"--- {path} ---\n{content[:8000]}"
            for path, content in sorted(source_files.items())
        )[:100000]
        + "\n\n"
        f"=== Lastenheft (course.json, for reference only — do NOT modify) ===\n"
        f"{json.dumps(course)[:40000]}\n\n"
        f"=== asset_map.json (for reference only) ===\n"
        f"{json.dumps(asset_map)[:10000]}\n"
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


async def _request_repair(
    client: DevinClient,
    error_logs: str,
    source_files: dict[str, str],
    spec: dict,
    asset_map: dict,
    attempt: int,
) -> dict[str, str] | None:
    """Send a repair prompt to Devin and return the corrected file map."""
    prompt = _repair_prompt(error_logs, source_files, spec, asset_map)
    try:
        _session_id, output = await client.run(
            prompt,
            structured_output_schema=COURSE_APP_SCHEMA,
            title=f"Repair course app (attempt {attempt}): {spec.get('title', 'course')}",
            tags=["coursive", "course-app", "repair"],
        )
    except DevinError as exc:
        logger.warning("Devin repair session failed (%s)", exc)
        return None

    repaired = _validate_files(output)
    if not repaired:
        logger.warning("Devin repair returned no usable project files")
        return None
    logger.info("Devin repair returned %d files (attempt %d)", len(repaired), attempt)
    return repaired


def _derive_course_data(spec: dict, asset_map: dict) -> tuple[dict, dict]:
    """Derive runtime course dict and ensure asset_map is a dict."""
    course = {k: v for k, v in spec.items() if k != "asset_manifest"}
    course.setdefault("chapters", [])
    return course, asset_map or {}


async def generate_course_app(
    spec: dict, asset_map: dict
) -> tuple[str | None, dict[str, str] | None]:
    """Return (devin_session_id, file map) or (None, None) to use the template.

    When the initial Devin output fails to build, a repair loop sends the exact
    error logs back to Devin up to ``settings.course_build_repair_max_retries``
    times. If all attempts fail the caller falls back to the template build.
    """
    if not settings.course_build_use_devin:
        return None, None
    client = DevinClient()
    if not client.enabled:
        logger.info("COURSE_BUILD_USE_DEVIN set but Devin API not configured; using template")
        return None, None

    try:
        session_id, output = await client.run(
            _build_prompt(spec, asset_map),
            structured_output_schema=COURSE_APP_SCHEMA,
            title=f"Course app: {spec.get('title', 'course')}",
            tags=["coursive", "course-app"],
        )
    except DevinError as exc:
        logger.warning("Devin course-app generation failed (%s); using template", exc)
        return None, None

    files = _validate_files(output)
    if not files:
        logger.warning("Devin returned no usable project files; using template")
        return session_id, None
    logger.info("Devin authored %d project files for the course app", len(files))

    # ── build-validate-repair loop ─────────────────────────────────────────
    course, amap = _derive_course_data(spec, asset_map)
    max_retries = settings.course_build_repair_max_retries

    for attempt in range(1, max_retries + 2):  # attempt 1 = initial, 2..N+1 = repairs
        try:
            try_build_from_sources(files, course, amap)
            logger.info(
                "Devin-generated build succeeded (attempt %d/%d)",
                attempt,
                max_retries + 1,
            )
            return session_id, files
        except BuildError as exc:
            logger.warning(
                "Devin build attempt %d/%d failed: %s",
                attempt,
                max_retries + 1,
                exc,
            )
            if attempt > max_retries:
                logger.warning(
                    "All %d repair attempts exhausted; falling back to template",
                    max_retries,
                )
                return session_id, None

            repaired = await _request_repair(
                client, exc.logs, files, spec, asset_map, attempt
            )
            if repaired is None:
                logger.warning("Repair attempt %d returned nothing; giving up", attempt)
                return session_id, None
            files = repaired

    # Should not be reached, but satisfy the type checker.
    return session_id, None
