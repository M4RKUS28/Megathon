# Course App Platform Contract

> Canonical specification of every rule a Devin-generated (or template-built)
> course application must follow to integrate with the Coursive platform.
> A machine-readable summary lives in
> `backend/src/services/generation/contract.py` for direct inclusion in Devin
> prompts.

---

## 1. Project Layout & Build

| Rule | Detail |
|---|---|
| **Stack** | Vite + React + TypeScript + Tailwind CSS. Optional: Framer Motion, Chart.js / react-chartjs-2, Recharts, React Flow. |
| **Entry point** | `index.html` at project root with `<div id="root">`. |
| **Build command** | `npm run build` must produce a `dist/` directory containing `index.html`. |
| **Base URL** | `vite.config.ts` must set `base: "./"` (relative) because the app is served under a versioned MinIO prefix. |
| **Required files** | `package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, and all `src/` source files. |
| **Forbidden output** | Never include `node_modules/`, `dist/`, or `.git/` in generated source. These are build artifacts handled by the platform. |

## 2. Runtime Data Files

The builder bakes two JSON files into `public/` before `npm run build`. Vite
copies them into `dist/` and the platform additionally writes them to the MinIO
prefix after the build, so they are always present at runtime.

| File | Location at runtime | Shape |
|---|---|---|
| **`course.json`** | `./course.json` (relative to `index.html`) | See [Course JSON Schema](#course-json-schema) below. |
| **`asset_map.json`** | `./asset_map.json` (relative to `index.html`) | `Record<string, string>` mapping `template_link` to resolved storage URL. |

Load both at startup via relative `fetch`:

```ts
const [course, assetMap] = await Promise.all([
  fetch("./course.json").then(r => r.json()),
  fetch("./asset_map.json").then(r => r.ok ? r.json() : {}).catch(() => ({})),
]);
```

## 3. Course JSON Schema

```ts
interface Course {
  title: string;
  description?: string;
  companyName?: string;
  primaryColor?: string;   // CSS color; may be a bare HSL triple
  language?: string;
  passing_pct?: number;     // default 80
  chapters: Chapter[];
}

interface Chapter {
  id: string;
  title: string;
  objective?: string;
  pages: Page[];
  quiz: Quiz;
}

interface Page {
  id: string;
  title?: string;
  blocks: Block[];
}

interface Block {
  type: string;           // see Block Types
  text?: string;
  items?: string[];
  asset?: string;         // template_link resolved via asset_map
  data?: Record<string, unknown>;
}

interface Quiz {
  passing_pct: number;    // default 80
  retryable: boolean;
  questions: QuizQuestion[];
}

interface QuizQuestion {
  question: string;
  options: string[];
  answerIndex: number;
  explanation?: string;
}
```

## 4. Block Types

Every course renderer must handle each of these `block.type` values:

| Type | Data contract |
|---|---|
| `heading` | `block.text` |
| `paragraph` | `block.text` |
| `list` | `block.items: string[]` |
| `callout` | `block.text` (styled as a highlighted box) |
| `image` | `block.asset` (template_link), `block.text` (alt) |
| `video` | `block.asset` (template_link) |
| `audio` | `block.asset` (template_link) |
| `dialogue` | `block.data.turns: { speaker: string; text: string }[]` |
| `chart` | `block.data.chartType: "bar"|"line"|"pie"`, `block.data.labels: string[]`, `block.data.datasets: { label: string; data: number[] }[]`, `block.data.title?: string` |
| `flashcards` | `block.data.cards: { front: string; back: string }[]` |
| `dragdrop` | `block.data.pairs: { left: string; right: string }[]`, `block.data.prompt?: string` |
| `hotspot` | `block.data.asset?: string` (template_link), `block.data.spots: { x: number; y: number; label: string }[]` |
| `timeline` | `block.data.events: { date: string; text: string }[]` |
| `accordion` | `block.data.items: { title: string; body: string }[]` |
| `scenario` | `block.data.branches: { choice: string; outcome: string }[]`, `block.data.prompt?: string` |

Unknown types should gracefully fall back to rendering `block.text` if present.

## 5. Asset Map Behaviour

- The spec (Lastenheft) uses abstract `template_link` paths (e.g.
  `/resources/images/01`) as references in `block.asset` and `block.data.asset`.
- At build time the platform resolves each `template_link` to a storage URL and
  writes the result to `asset_map.json`.
- The course app **must** resolve assets through the map at runtime:

```ts
const resolve = (link?: string) => link ? assetMap[link] ?? link : undefined;
// Usage: <img src={resolve(block.asset)} />
```

- Never hard-code asset URLs. Always use the `template_link` reference and
  resolve through the map.

## 6. Progress Events (postMessage)

The course app runs inside an `<iframe>`. Communication with the host platform
uses `window.parent.postMessage` with a `coursive:` type prefix.

### 6.1 `coursive:ready` (app -> host)

Sent once on startup, immediately after the app mounts. The host may respond
with `coursive:init` containing saved learner state.

```ts
window.parent.postMessage({ type: "coursive:ready" }, "*");
```

### 6.2 `coursive:init` (host -> app)

Sent by the host in response to `coursive:ready`. Contains previously saved
progress so the course can resume where the learner left off.

```ts
{
  type: "coursive:init",
  state: {
    status: "in_progress" | "completed" | "not_started",
    progress_pct: number,
    current_chapter: number,
    score: number | null,
  }
}
```

### 6.3 `coursive:progress` (app -> host)

Sent whenever learner state changes (page navigation, quiz completion, etc.).
The host persists it via `POST /learning/...`.

```ts
window.parent.postMessage({
  type: "coursive:progress",
  status: "in_progress" | "completed",
  progress_pct: number,         // 0-100
  current_chapter: number,      // 0-indexed
  current_page: number,         // 0-indexed
  score?: number,               // average quiz score %
  quiz_attempts?: number,
  time_spent_seconds?: number,
  drop_off_point?: string,
  engagement_score?: number,
}, "*");
```

### 6.4 `coursive:select-mode` (host -> app)

Sent by the host to toggle element-selection mode for the "Edit with Devin"
flow.

```ts
{ type: "coursive:select-mode", enabled: boolean }
```

### 6.5 `coursive:element-selected` (app -> host)

Sent when the learner clicks a block while in select mode.

```ts
{
  type: "coursive:element-selected",
  blockId: "chapter.page.block",  // e.g. "0.2.1" (0-indexed triple)
  text: string,                   // human-readable block content
  blockType: string,              // the block's type field
}
```

## 7. Quiz Completion & Chapter Gating

| Rule | Detail |
|---|---|
| Every chapter **must** end with a quiz. | `chapter.quiz` is always present. |
| Passing threshold | `quiz.passing_pct` (default **80%**). |
| Score < passing | If `quiz.retryable` is `true`, allow retry (reset answers). |
| Score >= passing | Mark chapter passed, unlock the next chapter. |
| Sequential unlock | Chapters are locked until all preceding chapters are passed. |
| Course completion | All chapters passed. `coursive:progress` sends `status: "completed"`. |

## 8. Iframe Constraints

| Constraint | Detail |
|---|---|
| **Embedding** | The course app is always rendered inside an `<iframe>` by the Coursive platform. |
| **Origin** | The iframe loads from MinIO (same-origin or cross-origin depending on proxy config). All `postMessage` calls use `"*"` as target origin. |
| **Fullscreen** | The host provides a fullscreen toggle via the native Fullscreen API on the iframe wrapper. The course app does not need to implement its own. |
| **No navigation** | The app must be a single-page application. No router, no external links that navigate the iframe away. |
| **Sandbox** | The app must work within standard iframe security. No `document.cookie` access to parent, no `window.top` manipulation. |

## 9. Editor Selection Protocol

The "Edit with Devin" feature requires the course app to implement:

1. **Listen** for `coursive:select-mode` messages on `window` and toggle visual
   selection affordances (highlight blocks on hover, show selection prompt).
2. **On click** in select mode, post `coursive:element-selected` back to
   `window.parent` with:
   - `blockId`: `"${chapterIndex}.${pageIndex}.${blockIndex}"` (0-indexed).
   - `text`: human-readable summary of the block content.
   - `blockType`: the block's `type` field.
3. **Exit** select mode after the click (set `selectMode = false`).

The `blockId` triple is used server-side by the editor agent to locate and
rewrite exactly one block in the spec.

## 10. Branding

- `course.primaryColor` is applied as CSS custom property `--brand`.
- It may arrive as a bare Tailwind HSL triple (e.g. `"262 83% 58%"`). The app
  must normalize it to `hsl(262 83% 58%)` before use:

```ts
function normalizeBrand(value: string): string {
  const v = value.trim();
  if (/^\d{1,3}(\.\d+)?\s+\d{1,3}(\.\d+)?%\s+\d{1,3}(\.\d+)?%$/.test(v))
    return `hsl(${v})`;
  return v;
}
```

- `course.companyName` is displayed in the sidebar header.

## 11. Forbidden Behaviour

| Forbidden | Reason |
|---|---|
| **External API calls** | Course apps must be fully static. No fetch to third-party APIs at runtime (OpenAI, analytics, etc.). |
| **Secrets / API keys** | Never embed or reference API keys, tokens, or credentials. |
| **Self-hosting** | The platform hosts the `dist/` on MinIO. The app must not attempt to serve itself or redirect elsewhere. |
| **`node_modules/` or `dist/` in output** | These are build artifacts managed by the platform build pipeline. |
| **Server-side code** | No Express, no server endpoints. The output is a static SPA. |
| **External CDN imports** | All dependencies must be bundled via `npm`. No `<script src="https://cdn...">`. |
| **Parent frame manipulation** | No `window.top.location`, `document.referrer` abuse, or cookie exfiltration. |
| **Dynamic `<script>` injection** | No runtime script loading from external sources. |

---

## Appendix: Hosting Path

Courses are published to MinIO under a versioned prefix:

```
courses/{company_slug}/{course_id}/v{version}/
  index.html
  course.json
  asset_map.json
  assets/...        # Vite-bundled JS/CSS chunks
```

The platform embeds the course via:
```
/storage/courses/{company_slug}/{course_id}/v{version}/index.html
```

Each accepted edit produces a **new immutable version** (version bump + rebuild +
re-host). Preview builds use a per-edit prefix
(`{course_id}/preview/{edit_id}/`).
