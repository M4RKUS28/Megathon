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
import re
from typing import Any

from src.config.settings import settings
from src.services.devin.client import DevinClient, DevinError
from src.services.generation.builder import BuildError, try_build_from_sources
from src.services.generation.contract import COURSE_APP_CONTRACT  # noqa: F401 (re-exported)

logger = logging.getLogger(__name__)

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

        # Normalise: strip leading "./" and "/".
        norm = path.lstrip("./")
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
# Public API
# ---------------------------------------------------------------------------


async def generate_course_app(
    spec: dict, asset_map: dict
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
