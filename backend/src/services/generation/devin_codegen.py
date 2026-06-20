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
from collections.abc import Awaitable, Callable
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
        "- Mandatory subagent workflow: use a separate subagent for EVERY chapter. Each "
        "chapter subagent must plan and implement its chapter's screens, interactions, "
        "quiz, media usage and accessibility details, then integrate that chapter into "
        "the final shared app. Do not skip subagents for short or simple chapters.\n"
        "- Audio narration: most pages include an `audio` block. Render it as a clear, "
        "accessible 'Listen to this page' player (labelled, with play/pause) — its audio "
        "is the spoken version of the page. Every audio block with `text` must also expose "
        "that spoken text through a small transcript/info button that opens a readable pop-up "
        "or panel. Make it easy to find but not distracting.\n"
        "- Never hide essential learning content in audio-only narration. If the spec has a "
        "heading, method name, process step or concrete example in `text`, `items` or `data`, "
        "render it visibly somewhere on the page, even if the audio transcript repeats it.\n"
        "- Conversation blocks (`type: \"conversation\"`, used heavily for behavioural / "
        "soft-skill topics): render an immersive two-character scene — one persona on the "
        "LEFT, one on the RIGHT, each shown as a friendly cartoon-style avatar. `data."
        "personas` is [{id,name,role,side,avatar}] and `data.turns` is [{persona,text,audio}]. "
        "Reveal ONE speech bubble at a time on the speaking persona's side; the learner clicks "
        "to advance, and each revealed turn AUTO-PLAYS its `audio` template_link (with a replay "
        "button). Highlight the active speaker and dim the other. Derive a stable cartoon "
        "avatar from each persona's `avatar` key (consistent face per persona). This is a "
        "signature interaction — make it polished and emotionally engaging.\n"
        "- Minigames (`type: \"minigame\"`): build them as polished, animated, *scored* games "
        "with instant feedback — not static quizzes. `data.game` is the kind: `quiz` (game-show "
        "multiple-choice with a score + explanations), `order` (drag/reorder shuffled steps into "
        "the correct sequence), `sort` (drag items into the correct category buckets), `memory` "
        "(flip-card matching pairs); the kind's config lives in `data`. Use real drag-and-drop, "
        "a visible score, celebratory micro-animations on success (confetti / a check popping "
        "in) and a replay button; invent richer games for custom kinds. Make them fun.\n"
        "- A chapter-end quiz is mandatory; require >=80% to unlock the next chapter, "
        "and allow retry below 80%. Do not render all quiz questions as one long page: "
        "use question tabs/steps with one active question at a time, numbered tabs for "
        "navigation, and clear Previous/Next/Submit controls.\n"
        "- Reference assets STRICTLY by their template_link (e.g. "
        '<img src="/resources/images/01" />); a build step maps them to real URLs '
        "via /asset_map.json which is loaded at runtime. Use every provided asset.\n"
        "- The app must build to static files with `npm run build` (output dir dist/). "
        "Read /course.json and /asset_map.json from the public/ root at runtime.\n"
        "- Before providing final structured output, run the course locally, click through "
        "every chapter page and each chapter-end quiz tab, verify media/transcript controls "
        "and minigames render, and fix any console/runtime/build errors you find. Include only "
        "source files after this validation passes.\n"
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
    spec: dict,
    asset_map: dict,
    on_session: Callable[[dict], Awaitable[None]] | None = None,
) -> tuple[str | None, dict[str, str] | None]:
    """Return (devin_session_id, file map) or (None, None) to use the template.

    `on_session` is awaited with the create-session response the moment the Devin
    session is created (before its long build wait), so the pipeline can persist
    the id/url and surface a live link to the session in the UI.

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
            on_created=on_session,
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
