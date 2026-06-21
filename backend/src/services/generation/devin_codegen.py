"""Phase 3 — Devin Implementation Agent (per-course code generation).

When `COURSE_BUILD_USE_DEVIN` is enabled and the Devin API is configured, this
authors each course's OWN Vite/React/TS application from the Lastenheft by running
a real Devin coding session that returns the project source files as structured
output. The builder then writes those files, runs `npm run build`, and publishes
the resulting `dist/` (Phase 4). If Devin is unavailable or fails, the caller
falls back to the prebuilt `course-app-template` build.

Supports parallel chapter sessions: one Devin session per chapter, each producing
its chapter's components/pages, merged into a single project at the end.

We keep hosting under our control (MinIO) rather than asking Devin to host, so the
generated app stays sandboxed and embeddable.
"""

from __future__ import annotations

import asyncio
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
        "- Interactive mini-game block types (use where pedagogically appropriate):\n"
        "  * `matching_game`: a card-matching memory game. Data: {pairs: [{term, definition}]}. "
        "Render as a grid of face-down cards that flip on click; match a term to its definition.\n"
        "  * `sorting_challenge`: learners drag/reorder items into the correct sequence. "
        "Data: {prompt, items: string[], correctOrder: number[]}.\n"
        "  * `fill_in_blank`: interactive fill-in-the-blank sentences. Data: {sentences: "
        "[{text, blanks: [{position, answer, options: string[]}]}]}.\n"
        "  * `word_cloud`: visual word cloud of key terms. Data: {words: [{text, weight}]}.\n"
        "  These are in ADDITION to the existing block types (flashcards, dragdrop, scenario, "
        "chart, timeline, hotspot, accordion). Use a rich, varied mix.\n\n"
        "- Never produce thin or empty pages. Each page should feel substantial with multiple "
        "content blocks, visual richness, and at least one interactive or visual element.\n"
        "- Conversations are a SUPPORTING element, not the primary content format. Most content "
        "should be direct instruction with rich interactions. Use conversation blocks for "
        "soft-skill scenarios or dialogue-based learning, not as filler.\n"
        "- Charts should only be rendered when the data is real and meaningful. If chart data "
        "looks placeholder-like (generic labels like Q1/Q2/Q3/Q4, linearly increasing numbers), "
        "render it as a styled info card instead with a note that real metrics will be added.\n"
        "- Make the course FUN — use gamification elements like score tracking, completion "
        "celebrations (confetti, star ratings), and varied mini-games where pedagogically "
        "appropriate. Reward correct answers with satisfying animations.\n\n"
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
            on_created=on_session,
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


# ── Parallel chapter sessions ─────────────────────────────────────────────────

# Schema for chapter sessions: each returns only its chapter's src/ files.
CHAPTER_APP_SCHEMA: dict[str, Any] = {
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


def _build_skeleton_prompt(spec: dict) -> str:
    """Build the shared skeleton prompt: package.json, router, layout, shared types.

    This prompt creates the project scaffolding that all chapter sessions depend on.
    """
    course_meta = {
        "title": spec.get("title"),
        "primaryColor": spec.get("primaryColor"),
        "chapters": [
            {"id": ch.get("id"), "title": ch.get("title")}
            for ch in spec.get("chapters", [])
        ],
    }
    return (
        "You are the Devin Skeleton Agent. Create ONLY the shared project scaffolding "
        "for a Vite + React + TypeScript + Tailwind course application. Individual "
        "chapter content will be built by separate agents and merged in later.\n\n"
        "Create these files:\n"
        "- package.json (with vite, react, react-dom, react-router-dom, typescript, "
        "tailwindcss, framer-motion, recharts, @dnd-kit/core, @dnd-kit/sortable)\n"
        "- vite.config.ts\n"
        "- tsconfig.json\n"
        "- tailwind.config.ts (with the course primaryColor as brand)\n"
        "- index.html\n"
        "- src/main.tsx (mounts <App/>)\n"
        "- src/App.tsx (React Router with lazy routes for each chapter)\n"
        "- src/types.ts (shared TypeScript interfaces: Chapter, Page, Block, Asset)\n"
        "- src/hooks/useAssetMap.ts (loads /asset_map.json, resolves template_links)\n"
        "- src/hooks/useCourse.ts (loads /course.json)\n"
        "- src/components/Layout.tsx (sidebar/nav shell with chapter navigation)\n"
        "- src/components/AudioPlayer.tsx (reusable audio player with transcript)\n"
        "- src/components/QuizGate.tsx (chapter-end quiz requiring >=80%)\n"
        "- src/components/ProgressBar.tsx\n"
        "- src/styles/globals.css (Tailwind directives + brand variables)\n\n"
        "The router should expect each chapter's pages at:\n"
        "  src/chapters/<chapter_id>/index.tsx\n\n"
        "Return ONLY structured output: a `files` array of {path, content}.\n\n"
        f"=== Course metadata ===\n{json.dumps(course_meta)}\n"
    )


def _build_chapter_prompt(spec: dict, chapter: dict, chapter_index: int) -> str:
    """Build a prompt for a single chapter's Devin session."""
    course_meta = {
        "title": spec.get("title"),
        "primaryColor": spec.get("primaryColor"),
        "totalChapters": len(spec.get("chapters", [])),
    }
    chapter_id = chapter.get("id", f"chapter-{chapter_index + 1}")
    return (
        f"You are the Devin Chapter Agent for chapter {chapter_index + 1}. Build ONLY "
        f"the React components for this single chapter of an interactive course.\n\n"
        "The chapter will be integrated into a shared Vite + React + TypeScript + "
        "Tailwind project. Your files will be placed under:\n"
        f"  src/chapters/{chapter_id}/\n\n"
        "Requirements:\n"
        "- Create src/chapters/{chapter_id}/index.tsx as the chapter's entry component\n"
        "- Create sub-components for each page and block type in the chapter\n"
        "- Cover ALL pages and ALL blocks in the chapter spec faithfully\n"
        "- Audio blocks: render as accessible 'Listen' player with transcript toggle\n"
        "- Conversation blocks: two-persona scene with speech bubbles, auto-advance\n"
        "- Minigame blocks: polished, animated, scored games with drag-and-drop\n"
        "- End the chapter with a quiz gate (>=80% to pass, retry below 80%)\n"
        "- Reference assets by template_link (e.g. /resources/images/01)\n"
        "- Import shared hooks from '../../hooks/useAssetMap' and '../../hooks/useCourse'\n"
        "- Import shared components from '../../components/AudioPlayer' etc.\n"
        "- Use Tailwind, Framer Motion for animations\n"
        "- Apply the 60-30-10 color rule with the brand primaryColor\n"
        "- Make it visually polished, modern, and accessible (WCAG AA)\n\n"
        "Return ONLY structured output: a `files` array of {path, content}.\n"
        f"All paths should be relative (e.g. src/chapters/{chapter_id}/index.tsx).\n\n"
        f"=== Course metadata ===\n{json.dumps(course_meta)}\n\n"
        f"=== Chapter spec ===\n{json.dumps(chapter)[:80000]}\n"
    )


def _merge_chapter_files(
    skeleton_files: dict[str, str],
    chapter_outputs: list[tuple[int, dict[str, str]]],
) -> dict[str, str]:
    """Merge skeleton + all chapter file maps into a single project."""
    merged = dict(skeleton_files)
    for _idx, chapter_files in sorted(chapter_outputs, key=lambda x: x[0]):
        for path, content in chapter_files.items():
            norm = path.lstrip("/")
            if ".." in norm.split("/") or not norm:
                continue
            merged[norm] = content
    return merged


async def generate_course_app_parallel(
    spec: dict,
    asset_map: dict,
    on_session: Callable[[dict], Awaitable[None]] | None = None,
    on_chapter_session: Callable[[int, str, dict], Awaitable[None]] | None = None,
) -> tuple[str | None, dict[str, str] | None, list[dict] | None]:
    """Parallel chapter generation: one Devin session per chapter.

    Returns (primary_session_id, merged_file_map, chapter_sessions_info) or
    (None, None, None) to fall back to template/single-session approach.

    `on_session` is called for the skeleton session.
    `on_chapter_session` is called for each chapter session with
    (chapter_index, chapter_title, created_response).
    """
    if not settings.course_build_use_devin or not settings.course_build_parallel_chapters:
        return None, None, None

    client = DevinClient()
    if not client.enabled:
        logger.info("Parallel chapters: Devin API not configured; skipping")
        return None, None, None

    chapters = spec.get("chapters", [])
    if not chapters:
        logger.warning("Parallel chapters: no chapters in spec; skipping")
        return None, None, None

    logger.info("Starting parallel chapter generation: %d chapters", len(chapters))
    chapter_sessions: list[dict] = []

    try:
        # Step 1: Create the skeleton session
        skeleton_session_id: str | None = None

        async def _on_skeleton_created(created: dict) -> None:
            nonlocal skeleton_session_id
            skeleton_session_id = created.get("session_id")
            if on_session:
                await on_session(created)

        skeleton_id, skeleton_output = await client.run(
            _build_skeleton_prompt(spec),
            structured_output_schema=CHAPTER_APP_SCHEMA,
            title=f"Skeleton: {spec.get('title', 'course')}",
            tags=["coursive", "course-app", "skeleton"],
            on_created=_on_skeleton_created,
        )
        skeleton_files = _validate_files(skeleton_output)
        if not skeleton_files:
            logger.warning("Skeleton session returned no usable files; falling back")
            return skeleton_id, None, None

        logger.info("Skeleton session %s produced %d files", skeleton_id, len(skeleton_files))

        # Step 2: Spawn one Devin session per chapter in parallel
        async def _run_chapter(
            index: int, chapter: dict,
        ) -> tuple[int, dict[str, str] | None, dict]:
            chapter_title = chapter.get("title", f"Chapter {index + 1}")
            chapter_id = chapter.get("id", f"chapter-{index + 1}")
            session_info: dict[str, Any] = {
                "chapter": chapter_title,
                "chapter_id": chapter_id,
                "chapter_index": index,
                "session_id": None,
                "status": "pending",
            }

            async def _on_ch_created(created: dict) -> None:
                session_info["session_id"] = created.get("session_id")
                session_info["status"] = "running"
                session_info["url"] = created.get("url")
                if on_chapter_session:
                    await on_chapter_session(index, chapter_title, created)

            try:
                ch_session_id, ch_output = await client.run(
                    _build_chapter_prompt(spec, chapter, index),
                    structured_output_schema=CHAPTER_APP_SCHEMA,
                    title=f"Ch{index + 1}: {chapter_title[:40]}",
                    tags=["coursive", "course-app", "chapter", f"ch-{index + 1}"],
                    on_created=_on_ch_created,
                )
                session_info["session_id"] = ch_session_id
                ch_files = _validate_chapter_files(ch_output)
                if ch_files:
                    session_info["status"] = "done"
                    session_info["files_count"] = len(ch_files)
                    return index, ch_files, session_info
                else:
                    session_info["status"] = "failed"
                    session_info["error"] = "no usable files returned"
                    return index, None, session_info
            except DevinError as exc:
                session_info["status"] = "failed"
                session_info["error"] = str(exc)
                logger.warning("Chapter %d session failed: %s", index + 1, exc)
                return index, None, session_info

        tasks = [_run_chapter(i, ch) for i, ch in enumerate(chapters)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect results
        chapter_outputs: list[tuple[int, dict[str, str]]] = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning("Chapter task raised exception: %s", result)
                continue
            index, files, info = result
            chapter_sessions.append(info)
            if files:
                chapter_outputs.append((index, files))

        if not chapter_outputs:
            logger.warning("No chapter sessions produced files; falling back")
            return skeleton_id, None, chapter_sessions

        logger.info(
            "Parallel chapters: %d/%d succeeded",
            len(chapter_outputs),
            len(chapters),
        )

        # Step 3: Merge skeleton + chapter files
        merged = _merge_chapter_files(skeleton_files, chapter_outputs)
        if "package.json" not in merged:
            logger.warning("Merged project missing package.json; falling back")
            return skeleton_id, None, chapter_sessions

        logger.info(
            "Parallel generation complete: %d total files from skeleton + %d chapters",
            len(merged),
            len(chapter_outputs),
        )
        return skeleton_id, merged, chapter_sessions

    except DevinError as exc:
        logger.warning("Parallel chapter generation failed (%s); falling back", exc)
        return None, None, chapter_sessions
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error in parallel chapter generation: %s", exc)
        return None, None, chapter_sessions


def _validate_chapter_files(output: dict) -> dict[str, str] | None:
    """Validate chapter session output (less strict than full project validation)."""
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
        norm = path.lstrip("/")
        if ".." in norm.split("/") or not norm:
            logger.warning("skipping unsafe chapter path: %s", path)
            continue
        result[norm] = content
    return result if result else None
