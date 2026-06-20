"""Phase 3 — Devin Implementation Agent (per-course code generation).

When `COURSE_BUILD_USE_DEVIN` is enabled and the Devin API is configured, this
authors each course's OWN Vite/React/TS application from the Lastenheft by running
a real Devin coding session that returns the project source files as structured
output. The builder then writes those files, runs `npm run build`, and publishes
the resulting `dist/` (Phase 4). If Devin is unavailable or fails, the caller
falls back to the prebuilt `course-app-template` build.

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
        "Vite + React + TypeScript single-page application that delivers the "
        "interactive course described by the Lastenheft below.\n\n"
        "The Lastenheft is the source of truth for the CONTENT and the RESOURCES "
        "(assets) — what each chapter teaches and which media it uses. It is NOT a "
        "rigid design spec. You have FULL creative freedom over the HOW: layout, "
        "navigation, styling, motion and the way each piece of content is presented. "
        "Design a polished, modern, in-depth course you would be proud of.\n\n"
        "Aim for a course that looks nothing like a 2010s PowerPoint (cut-out stock "
        "photos, walls of text, rigid layouts). Apply this design system:\n"
        "- Layout & hierarchy: generous whitespace so the design 'breathes'; a clear "
        "12-column grid with everything aligned; ONE main idea per screen; place content "
        "in soft Cards/containers (rounded corners, subtle shadows) rather than raw text "
        "on a background. The learner should grasp the screen's point in ~2 seconds.\n"
        "- Typography: max 2 font families — a distinctive display font for headings "
        "(e.g. Poppins/Montserrat/Playfair) and a highly legible body font (e.g. Inter/"
        "Open Sans). Strong size contrast (H1 ~32-40px, body 16-18px), line-height "
        "~1.5, and line length capped at ~70-80 chars.\n"
        "- Colour: follow the 60-30-10 rule — ~60% neutral background (off-white / very "
        "light grey), ~30% secondary (derived from the brand primaryColor), ~10% vivid "
        "accent reserved for CTAs/links/highlights. Use the course `primaryColor` as the "
        "brand. Never use pure black (#000) for text — use a very dark grey (~#1f2937).\n"
        "- Imagery: treat assets as authentic, meaningful visuals (no cheesy stock); keep "
        "icons/illustrations in ONE consistent family; visualise data as charts/timelines/"
        "infographics; you may apply a subtle brand-coloured overlay/duotone to images.\n"
        "- UI & micro-interactions: obvious clickable buttons with clear hover states; "
        "reward correct answers with a small animation (a green check popping in); use "
        "gentle fade-in / slide-up to reveal content in reading order — never chaotic "
        "fly-ins.\n"
        "- Accessibility: ensure strong text/background contrast (WCAG AA); never convey "
        "right/wrong by colour alone — always add an icon (check/cross) too.\n\n"
        "Requirements:\n"
        "- Use Vite, React, TypeScript, Tailwind. Add Framer Motion, "
        "Chart.js/Recharts, React Flow or any other libraries you need.\n"
        "- Cover ALL the content: every chapter, every page and every block. Treat each "
        "block's `type`/`text`/`items`/`data` as the content brief, not a fixed widget — "
        "render it faithfully but design it well. You may split, merge, enrich or add "
        "sections and interactions, and invent presentations for custom/unknown block "
        "types, as long as no content is lost. Never produce thin or short chapters.\n"
        "- Audio narration: most pages include an `audio` block. Render it as a clear, "
        "accessible 'Listen to this page' player (labelled, with play/pause) — its audio "
        "is the spoken version of the page. Make it easy to find but not distracting.\n"
        "- A chapter-end quiz is mandatory; require >=80% to unlock the next chapter, "
        "and allow retry below 80%.\n"
        "- Reference assets STRICTLY by their template_link (e.g. "
        '<img src="/resources/images/01" />); a build step maps them to real URLs '
        "via /asset_map.json which is loaded at runtime. Use every provided asset.\n"
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
    """Return (devin_session_id, file map) or (None, None) to use the template."""
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
    return session_id, files
