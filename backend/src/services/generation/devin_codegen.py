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

import asyncio
import json
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any

from src.config.settings import settings
from src.services.devin.client import DevinClient, DevinError
from src.services.generation.builder import BuildError, try_build_from_sources
from src.services.generation.contract import COURSE_APP_CONTRACT  # noqa: F401 (re-exported)

logger = logging.getLogger(__name__)

# Optional async callback used to surface granular progress to the frontend.
StepLogger = Callable[[str], Awaitable[None]]


async def _emit(on_step: StepLogger | None, message: str) -> None:
    """Best-effort progress emit; never let logging break the build."""
    if on_step is None:
        return
    try:
        await on_step(message)
    except Exception:  # noqa: BLE001 — progress logging is non-critical
        logger.debug("step logger raised for %r", message, exc_info=True)

# ---------------------------------------------------------------------------
# Structured-output JSON schema
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Required files and forbidden patterns
# ---------------------------------------------------------------------------
REQUIRED_FILES = {"package.json", "index.html"}
REQUIRED_PATH_PREFIXES = {"src/"}
FORBIDDEN_PATH_SEGMENTS = {"node_modules", "dist", ".git", ".env"}

# ---------------------------------------------------------------------------
# Master prompt
# ---------------------------------------------------------------------------
_MASTER_PROMPT = """\
# Role

You are the Coursive Implementation Agent.
Your ONLY job is to implement the provided Lastenheft as a **bespoke, \
interactive e-learning application**.

## What you must NOT do

- Do NOT plan or outline the course — the Lastenheft IS the plan.
- Do NOT rewrite, restructure, or summarise the curriculum.
- Do NOT fetch, download, or generate media assets — they are resolved at \
  runtime via `asset_map.json`.
- Do NOT host, deploy, or serve the application — hosting is handled by the \
  platform.
- Do NOT build a generic JSON renderer — build a **bespoke** app whose \
  components, layout, and interactions are tailored to THIS course's content.
- Do NOT make external API calls, embed API keys, or reference secrets.
- Do NOT include `node_modules/`, `dist/`, or `.env` files in your output.

---

# Platform contracts

## 1. Runtime data loading

The built app will be served with two sibling files in the same directory:

| File | Description |
|---|---|
| `course.json` | The Lastenheft (chapters, pages, blocks, quizzes) |
| `asset_map.json` | Maps `template_link` → absolute storage URL |

Load both at runtime from the same origin (e.g. `fetch("./course.json")`). \
Place copies in `public/` so Vite serves them during development.

## 2. Asset resolution

Every media reference in the Lastenheft uses a **template_link** \
(e.g. `/resources/images/01`). At runtime, resolve each template_link through \
`asset_map.json`:

```ts
const url = assetMap[block.asset] ?? block.asset;
```

Never hard-code asset URLs. Never fetch assets from external origins.

## 3. Chapter navigation

- Sidebar listing all chapters with title + lock/complete indicator.
- Chapters unlock sequentially: chapter N+1 is locked until chapter N's quiz \
  is passed.
- Visual progress bar (fraction of chapters completed).

## 4. Page progression

- Each chapter has multiple pages (from `chapter.pages`).
- Show page-step indicators (dots or progress bar).
- Back / Next navigation within the chapter.
- After the last page, transition to the chapter quiz.

## 5. Quiz gating (>=80%)

- Each chapter ends with a quiz (`chapter.quiz`).
- Require a passing score of `quiz.passing_pct` (default 80%).
- Below the threshold: show score, allow retry (if `quiz.retryable`).
- At or above the threshold: unlock the next chapter and update progress.

## 6. Progress postMessage events

Post progress to the embedding platform via `window.parent.postMessage`:

```ts
// On app load:
window.parent.postMessage({ type: "coursive:ready" }, "*");

// On every state change:
window.parent.postMessage({
  type: "coursive:progress",
  status: "in_progress" | "completed",
  progress_pct: number,    // 0–100
  current_chapter: number, // 0-based index
  current_page: number,    // 0-based index
  score: number | undefined,
  quiz_attempts: number,
}, "*");
```

## 7. Iframe-safe responsive UI

- The app runs inside an `<iframe>` — never call `window.top` or navigate \
  the parent.
- Fully responsive: must work from 320 px to 1920 px width.
- Use `min-h-screen` or `min-h-full`; never set a fixed viewport height.
- Respect the course's `primaryColor` for branding (buttons, accents, \
  progress).

## 8. Edit-selection protocol

Implement the "Edit with Devin" handshake so creators can select blocks \
for editing:

```ts
// Listen for select-mode toggle from parent:
window.addEventListener("message", (e) => {
  if (e.data?.type === "coursive:select-mode") {
    setSelectMode(e.data.enabled);
  }
});

// When user clicks a block in select mode:
window.parent.postMessage({
  type: "coursive:element-selected",
  blockId: "<chapter>.<page>.<block>",  // dot-separated indices
  text: "<visible text of the block>",
  blockType: "<block type>",
}, "*");
```

Show a visual indicator when select mode is active. Highlight hovered \
blocks; on click, send the message above and exit select mode.

---

# Interaction affordance palette

Build **bespoke** components for each block type in the Lastenheft. \
You MUST implement every block type that appears in the spec. Use the \
libraries below as appropriate — pick whichever best serves the content:

| Library | Use for |
|---|---|
| **Recharts** | Bar, line, pie, area, radar, composed charts |
| **React Flow** | Node-based diagrams, process flows, org charts |
| **Framer Motion** | Page transitions, reveal animations, micro-interactions |
| **Chart.js / react-chartjs-2** | Alternative charting if Recharts isn't ideal |
| **react-syntax-highlighter** | Code blocks with language-aware highlighting |

### Standard block types

Implement at least these interaction patterns (use them when the Lastenheft \
specifies the matching block type):

- **heading / paragraph / list / callout** — standard text rendering
- **image / video / audio** — media with asset_map resolution
- **dialogue** — chat-bubble conversation between personas
- **chart** — interactive chart from `block.data` (Recharts or Chart.js)
- **flashcards** — flip-card grid (front/back)
- **dragdrop** — drag-and-drop matching exercise
- **hotspot** — labelled interactive regions over an image
- **timeline** — chronological event display
- **accordion** — expandable/collapsible sections
- **scenario** — branching decision tree with outcomes
- **sortable** — drag-to-reorder ranking exercise
- **calculator** — formula-driven interactive calculator
- **simulation** — custom interactive simulation (interpret `block.data`)
- **code** — syntax-highlighted code block

If the Lastenheft contains a block type not listed here, implement it as a \
reasonable interactive component based on the data in `block.data`.

---

# Tech stack & project structure

| Requirement | Value |
|---|---|
| Bundler | **Vite** (latest 5.x) |
| Framework | **React 18** |
| Language | **TypeScript** (strict) |
| Styling | **Tailwind CSS 3** |
| Build command | `npm run build` → output to `dist/` |
| Entry point | `index.html` at project root |

### Required project files (minimum)

```
package.json
index.html
vite.config.ts
tsconfig.json
tailwind.config.js   (or .ts / .cjs)
postcss.config.js    (or .cjs)
src/
  main.tsx
  App.tsx
  index.css           (Tailwind directives)
  ... (components, hooks, types, utils)
public/
  course.json         (copy of the Lastenheft, for dev)
  asset_map.json      (copy of the asset map, for dev)
```

### Dependency constraints

- Include ONLY the dependencies you actually use.
- Allowed runtime deps: `react`, `react-dom`, `framer-motion`, `recharts`, \
  `reactflow`, `chart.js`, `react-chartjs-2`, `react-syntax-highlighter`.
- Do NOT add: Express, Next.js, Remix, server frameworks, database drivers, \
  HTTP clients (axios/fetch wrappers), or any package that makes network \
  requests.
- Pin dependencies to specific versions (e.g. `"^18.3.1"`), not `"latest"`.

---

# Output format

Return **structured output only**: a JSON object with a single `files` array.
Each element is `{ "path": "<relative-path>", "content": "<file-content>" }`.

- Use forward-slash relative paths (e.g. `src/App.tsx`, not `./src/App.tsx`).
- Every file needed to `npm install && npm run build` must be present.
- Do NOT include `node_modules/`, `dist/`, or any binary files.
- Do NOT include explanatory text, markdown, or commentary — ONLY the \
  structured JSON output.
"""


def _build_prompt(spec: dict, asset_map: dict) -> str:
    """Assemble the full prompt: master instructions + serialised Lastenheft."""
    course = {k: v for k, v in spec.items() if k != "asset_manifest"}
    manifest = spec.get("asset_manifest", [])
    return (
        f"{_MASTER_PROMPT}\n"
        "---\n\n"
        f"# Lastenheft (course.json)\n\n"
        f"```json\n{json.dumps(course, ensure_ascii=False)[:120_000]}\n```\n\n"
        f"# Asset manifest\n\n"
        f"```json\n{json.dumps(manifest, ensure_ascii=False)[:30_000]}\n```\n\n"
        f"# Asset map (asset_map.json)\n\n"
        f"```json\n{json.dumps(asset_map, ensure_ascii=False)[:20_000]}\n```\n"
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


_PATH_TRAVERSAL_RE = re.compile(r"(^|/)\.\.(/|$)")


def _validate_files(output: dict) -> dict[str, str] | None:
    """Validate and normalise Devin's structured output into a file map.

    Returns a ``{path: content}`` dict or ``None`` when the output is
    unusable (missing critical files, suspicious paths, etc.).
    """
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

        # Normalise: strip leading "./" prefix and leading slashes.
        norm = path
        while norm.startswith("./"):
            norm = norm[2:]
        norm = norm.lstrip("/")
        if not norm:
            logger.warning("skipping empty generated path")
            continue

        # Reject path traversal.
        if _PATH_TRAVERSAL_RE.search(norm):
            logger.warning("skipping path-traversal generated path: %s", path)
            continue

        # Reject forbidden segments (node_modules, dist, .env, .git).
        parts = norm.split("/")
        if any(seg in FORBIDDEN_PATH_SEGMENTS for seg in parts):
            logger.warning("skipping forbidden generated path: %s", path)
            continue

        result[norm] = content

    # --- Required-file checks ---
    missing = REQUIRED_FILES - result.keys()
    if missing:
        logger.warning("Devin output missing required files %s; rejecting", missing)
        return None

    # At least one file under src/ must exist.
    has_src = any(p.startswith(prefix) for p in result for prefix in REQUIRED_PATH_PREFIXES)
    if not has_src:
        logger.warning("Devin output has no files under src/; rejecting")
        return None

    # package.json must be parseable and contain a build script.
    try:
        pkg = json.loads(result["package.json"])
        scripts = pkg.get("scripts", {})
        if "build" not in scripts:
            logger.warning("package.json has no 'build' script; rejecting")
            return None
    except (json.JSONDecodeError, TypeError):
        logger.warning("package.json is not valid JSON; rejecting")
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


# ---------------------------------------------------------------------------
# Per-page code generation (one Devin session per page)
# ---------------------------------------------------------------------------

# Structured output for a single bespoke page component file.
PAGE_FILE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["content"],
    "properties": {"content": {"type": "string"}},
}

_PAGE_PROMPT = """\
# Role

You are the Coursive Page Component Agent. Author ONE bespoke, interactive
React + TypeScript component that renders a SINGLE page of an e-learning course.
The surrounding app shell (navigation, chapter unlocking, quizzes, progress,
asset loading, branding) ALREADY EXISTS — you implement only this one page.

## Output

Return structured output: a JSON object `{ "content": "<file-content>" }`
containing the COMPLETE source of one TypeScript React module. No markdown, no
commentary — only the structured JSON.

## Hard contract (do not deviate)

- The module MUST `export default` a single React function component.
- Its props are EXACTLY:

```ts
import type { ComponentType } from "react";
import type { AssetMap, Page } from "../types";

interface PageComponentProps {
  page: Page;            // this page's data (title, blocks, ...)
  resolve: (link?: string) => string | undefined;  // template_link -> URL
  assetMap: AssetMap;
}
```

- Import the `Page`/`Block`/`AssetMap` types from `"../types"`. Do NOT redefine them.
- Resolve every media/image reference through `resolve(block.asset)` — never
  hard-code or fetch external URLs.
- Render ALL of the page's textual prose: iterate the page's `paragraph`,
  `heading`, `list`, and `callout` blocks and show their full text. Do NOT
  summarise or drop content — every paragraph must appear.
- Build bespoke, attractive interactive UI for the page's interaction blocks
  (dialogue, chart, flashcards, dragdrop, hotspot, timeline, accordion,
  scenario, ...) using the page `blocks[*].data`.
- Use the course's brand color via the CSS variable `var(--brand)` for accents.
- Fully responsive (320px–1920px). The app runs in an iframe; never touch
  `window.top` or `window.parent` navigation.

## Allowed dependencies ONLY (already installed — do NOT add others)

`react`, `react-dom`, `framer-motion`, `chart.js`, `react-chartjs-2`, plus
Tailwind CSS utility classes and inline SVG. You may NOT import any other
package (no recharts, no reactflow, no syntax highlighters, no network libs).

## Quality

- TypeScript strict: fully typed, no `any`, no unused imports/vars (the project
  runs `tsc -b` and will fail the build on errors).
- Self-contained: the whole component lives in this one file.
"""


def _page_prompt(course: dict, chapter: dict, page: dict, primary_color: str) -> str:
    """Prompt for authoring a single page's bespoke component."""
    ctx = {
        "courseTitle": course.get("title", ""),
        "primaryColor": primary_color,
        "chapterTitle": chapter.get("title", ""),
        "chapterObjective": chapter.get("objective", ""),
    }
    return (
        f"{_PAGE_PROMPT}\n---\n\n"
        f"# Context\n\n```json\n{json.dumps(ctx, ensure_ascii=False)}\n```\n\n"
        f"# Page to implement (page.json)\n\n"
        f"```json\n{json.dumps(page, ensure_ascii=False)[:60_000]}\n```\n"
    )


def _safe_component_name(chapter_idx: int, page_idx: int) -> str:
    return f"Page_{chapter_idx}_{page_idx}"


def _load_template_files() -> dict[str, str]:
    """Read the course-app-template into a {relpath: content} file map."""
    from src.services.generation.builder import _app_template_dir

    template = _app_template_dir()
    if template is None:
        return {}
    skip_dirs = {"node_modules", "dist", ".git"}
    files: dict[str, str] = {}
    for path in template.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(template)
        if any(part in skip_dirs for part in rel.parts):
            continue
        try:
            files[str(rel).replace("\\", "/")] = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # skip binaries / unreadable files
    return files


def _registry_source(entries: list[tuple[str, str]]) -> str:
    """Generate src/pages/registry.tsx wiring every authored page component.

    ``entries`` is a list of (key, component_name) where key is "<c>.<p>" and
    the module lives at src/pages/<component_name>.tsx.
    """
    imports = "\n".join(
        f'import {name} from "./{name}";' for _key, name in entries
    )
    mapping = "\n".join(f'  "{key}": {name},' for key, name in entries)
    return (
        'import type { ComponentType } from "react";\n'
        'import type { AssetMap, Page } from "../types";\n'
        f"{imports}\n\n"
        "export interface PageComponentProps {\n"
        "  page: Page;\n"
        "  resolve: (link?: string) => string | undefined;\n"
        "  assetMap: AssetMap;\n"
        "}\n\n"
        "export const pageComponents: "
        "Record<string, ComponentType<PageComponentProps>> = {\n"
        f"{mapping}\n"
        "};\n"
    )


async def _generate_one_page(
    client: DevinClient,
    course: dict,
    chapter: dict,
    page: dict,
    chapter_idx: int,
    page_idx: int,
    primary_color: str,
    sem: asyncio.Semaphore,
    on_step: StepLogger | None,
    total_pages: int,
    counter: dict[str, int],
) -> tuple[str, str, str, str, str] | None:
    """Author one page component. Returns (key, name, path, content, session_id) or None."""
    name = _safe_component_name(chapter_idx, page_idx)
    key = f"{chapter_idx}.{page_idx}"
    async with sem:
        try:
            session_id, output = await client.run(
                _page_prompt(course, chapter, page, primary_color),
                structured_output_schema=PAGE_FILE_SCHEMA,
                title=(
                    f"Course page {chapter_idx + 1}.{page_idx + 1}: "
                    f"{page.get('title', '')[:60]}"
                ),
                tags=["coursive", "course-page"],
            )
        except DevinError as exc:
            logger.warning("page %s session failed: %s", key, exc)
            return None
    content = output.get("content") if isinstance(output, dict) else None
    counter["done"] += 1
    await _emit(
        on_step,
        f"Authored page {counter['done']}/{total_pages} "
        f"(ch{chapter_idx + 1}.{page_idx + 1})",
    )
    if not isinstance(content, str) or "export default" not in content:
        logger.warning("page %s returned no usable component", key)
        return None
    return key, name, f"src/pages/{name}.tsx", content, session_id


async def _generate_course_app_per_page(
    spec: dict, asset_map: dict, on_step: StepLogger | None
) -> tuple[str | None, dict[str, str] | None]:
    """Author each page in its own Devin session; assemble onto the template shell."""
    files = _load_template_files()
    if not files:
        logger.warning("course-app-template not found; cannot use per-page mode")
        return None, None

    course, amap = _derive_course_data(spec, asset_map)
    primary_color = str(course.get("primaryColor", "#5145E5"))
    chapters = course.get("chapters", [])

    jobs: list[tuple[dict, dict, int, int]] = []
    for c_idx, chapter in enumerate(chapters):
        for p_idx, page in enumerate(chapter.get("pages", [])):
            jobs.append((chapter, page, c_idx, p_idx))

    total_pages = len(jobs)
    if total_pages == 0:
        logger.warning("spec has no pages; cannot use per-page mode")
        return None, None

    client = DevinClient()
    sem = asyncio.Semaphore(max(1, settings.course_build_page_concurrency))
    counter = {"done": 0}
    await _emit(
        on_step,
        f"Authoring {total_pages} page components in parallel "
        f"(one Devin session each)…",
    )

    results = await asyncio.gather(
        *(
            _generate_one_page(
                client, course, chapter, page, c_idx, p_idx, primary_color,
                sem, on_step, total_pages, counter,
            )
            for (chapter, page, c_idx, p_idx) in jobs
        )
    )

    entries: list[tuple[str, str]] = []
    primary_session: str | None = None
    for res in results:
        if res is None:
            continue
        key, name, path, content, session_id = res
        files[path] = content
        entries.append((key, name))
        if primary_session is None:
            primary_session = session_id

    files["src/pages/registry.tsx"] = _registry_source(entries)
    await _emit(
        on_step,
        f"Assembling app — {len(entries)}/{total_pages} bespoke pages, "
        f"{total_pages - len(entries)} via fallback renderer",
    )

    # ── build-validate-repair loop on the assembled app ────────────────────
    max_retries = settings.course_build_repair_max_retries
    for attempt in range(1, max_retries + 2):
        try:
            await _emit(
                on_step,
                "Building course app"
                + (f" (repair attempt {attempt - 1})" if attempt > 1 else "")
                + "…",
            )
            await asyncio.to_thread(try_build_from_sources, files, course, amap)
            await _emit(on_step, "Course app built successfully")
            return primary_session, files
        except BuildError as exc:
            logger.warning(
                "per-page build attempt %d/%d failed: %s",
                attempt, max_retries + 1, exc,
            )
            if attempt > max_retries:
                await _emit(on_step, "Build failed after repairs; using template")
                return primary_session, None
            await _emit(on_step, f"Build failed — repairing (attempt {attempt})…")
            repaired = await _request_repair(
                client, exc.logs, files, spec, asset_map, attempt
            )
            if repaired is None:
                return primary_session, None
            files = repaired
    return primary_session, None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def generate_course_app(
    spec: dict, asset_map: dict, on_step: StepLogger | None = None
) -> tuple[str | None, dict[str, str] | None]:
    """Return (devin_session_id, file map) or (None, None) to use the template.

    Mode resolution:
    - template: immediately return (None, None).
    - auto: use Devin only when credentials are configured; skip silently otherwise.
    - devin: always attempt Devin; warn loudly on misconfiguration but still fall
      back to avoid breaking the pipeline.

    When the initial Devin output fails to build, a repair loop sends the exact
    error logs back to Devin up to ``settings.course_build_repair_max_retries``
    times. If all attempts fail the caller falls back to the template build.
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

    # Per-page mode: author each page in its own parallel Devin session on the
    # fixed template shell. Falls back to the single-session path below if the
    # template is unavailable or no pages were authored.
    if settings.course_build_per_page:
        session_id, files = await _generate_course_app_per_page(spec, asset_map, on_step)
        if files is not None:
            return session_id, files
        logger.info("per-page code-gen produced no build; trying single-session path")

    await _emit(on_step, "Authoring the full course app (single Devin session)…")
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
