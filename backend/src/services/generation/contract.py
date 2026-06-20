"""Coursive course-app platform contract.

Machine-readable summary of every rule a Devin-generated (or template-built)
course application must follow. Import ``COURSE_APP_CONTRACT`` to inject the
full contract text into a Devin prompt so the agent has stable integration
rules without relying on out-of-band documentation.

The authoritative human-readable version lives in ``docs/COURSE_APP_CONTRACT.md``.
"""

COURSE_APP_CONTRACT: str = """\
=== Coursive Course-App Platform Contract ===

PROJECT
- Stack: Vite + React + TypeScript + Tailwind CSS. Optional: Framer Motion, \
Chart.js/react-chartjs-2.
- Entry: index.html with <div id="root">.
- Build: `npm run build` -> dist/index.html.  vite.config.ts: base: "./".
- Include: package.json, vite.config.ts, tsconfig.json, index.html, src/*.
- NEVER include node_modules/, dist/, or .git/.

RUNTIME DATA
- ./course.json  — course structure (chapters, pages, blocks, quizzes).
- ./asset_map.json — Record<template_link, storage_url>.
  Load both via relative fetch() on startup.

BLOCK TYPES (block.type)
heading (text), paragraph (text), list (items[]), callout (text),
image (asset, text=alt), video (asset), audio (asset),
dialogue (data.turns[]{speaker,text}),
chart (data.chartType bar|line|pie, data.labels[], data.datasets[]{label,data[]}),
flashcards (data.cards[]{front,back}),
dragdrop (data.pairs[]{left,right}, data.prompt?),
hotspot (data.asset?, data.spots[]{x,y,label}),
timeline (data.events[]{date,text}),
accordion (data.items[]{title,body}),
scenario (data.branches[]{choice,outcome}, data.prompt?).
Unknown types: render block.text if present.

ASSET MAP
- Spec uses abstract template_link paths (e.g. /resources/images/01).
- Resolve at runtime: assetMap[link] ?? link.
- Never hard-code asset URLs.

POSTMESSAGE PROTOCOL (coursive: prefix)
1. App -> Host:  { type: "coursive:ready" }              on mount.
2. Host -> App:  { type: "coursive:init", state }         saved progress.
3. App -> Host:  { type: "coursive:progress", status, progress_pct, \
current_chapter, current_page, score?, quiz_attempts? }   on state change.
4. Host -> App:  { type: "coursive:select-mode", enabled } toggle edit selection.
5. App -> Host:  { type: "coursive:element-selected", blockId, text, blockType }
   blockId = "chapter.page.block" (0-indexed triple).

QUIZ GATING
- Every chapter ends with a quiz (chapter.quiz).
- Passing: quiz.passing_pct (default 80%).
- Below passing + retryable: allow retry. At/above: unlock next chapter.
- Chapters sequential: locked until all preceding chapters passed.
- All passed -> status "completed".

BRANDING
- course.primaryColor -> CSS --brand.  May be bare HSL triple; wrap in hsl().
- course.companyName -> sidebar header.

IFRAME CONSTRAINTS
- App runs inside <iframe>. Single-page, no router/external navigation.
- Fullscreen provided by host. No parent-frame manipulation.

EDITOR SELECTION PROTOCOL
1. Listen for coursive:select-mode; highlight blocks on hover.
2. On click: post coursive:element-selected with blockId, text, blockType.
3. Exit select mode after click.

FORBIDDEN
- External API calls at runtime (no fetch to third-party services).
- Secrets, API keys, tokens, credentials.
- Self-hosting / redirects (platform hosts dist/ on MinIO).
- node_modules/ or dist/ in generated source.
- Server-side code (Express, etc.). Output is a static SPA.
- External CDN <script> imports; bundle everything via npm.
- Parent-frame manipulation (window.top, cookie exfiltration).
- Dynamic external <script> injection.
"""
