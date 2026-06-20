# Coursive

-----DEMO LINK-----

**Coursive** is a white-label platform that turns a short course brief into a fully
interactive, hosted e-learning course using a multi-agent generation pipeline, and then
delivers it to learners as an LMS (assignments, progress tracking, quizzes, reporting).

A course creator describes what they want → an agentic pipeline plans the course, writes a
detailed spec (*Lastenheft*), fetches/generates media assets, builds a per-course web app and
hosts it → managers assign it to employees → learners take it chapter-by-chapter with
end-of-chapter quiz gates → managers see progress and compliance reporting.

It is built on a single Docker Compose stack: **React + FastAPI + PostgreSQL + Keycloak +
MinIO + Redis (Arq worker)**, routed by Traefik in production and Nginx for local dev.

---

## Table of contents

- [Architecture overview](#architecture-overview)
- [The 5-phase generation pipeline](#the-5-phase-generation-pipeline)
- [Edit with Devin](#edit-with-devin)
- [Course delivery & LMS](#course-delivery--lms)
- [Tech stack](#tech-stack)
- [Project structure](#project-structure)
- [Services & ports](#services--ports)
- [Getting started](#getting-started)
- [Configuration (providers & secrets)](#configuration-providers--secrets)
- [Feature status](#feature-status)
- [Roadmap / TODO](#roadmap--todo)
- [Development](#development)

---

## Architecture overview

```
                       ┌──────────────┐      REST       ┌───────────────┐
   Browser (SPA) ──────▶   Proxy :80  ├────────────────▶│  FastAPI :8000 │
   React + Vite        └──────┬───────┘                 └───────┬────────┘
                              │ /storage/* (hosted courses)     │ enqueue
                              ▼                                  ▼
                       ┌──────────────┐                  ┌───────────────┐
                       │  MinIO (S3)  │◀─── publish ─────│  Arq worker   │
                       │  course dist │                  │  (pipeline)   │
                       └──────────────┘                  └───────┬───────┘
                                                                 │ calls
        Auth: Keycloak (OIDC/PKCE)   DB: PostgreSQL    Queue: Redis
                                                                 ▼
                       Gemini · Nano-Banana · Gemini TTS · PixVerse · Cala MCP · Devin
```

- **Frontend** (`frontend/`) — the Coursive SPA: dashboards, course creation, plan review,
  the "Edit with Devin" panel, learner course player, manager reporting.
- **Backend** (`backend/`) — FastAPI API + an **Arq worker** that runs the long-running
  generation pipeline asynchronously. Course/job state lives in PostgreSQL.
- **Generated courses** are static web apps (per-course Vite build, or a deterministic
  inline-HTML fallback renderer) published to **MinIO** under a versioned prefix
  (`courses/<tenant>/<courseId>/v<n>/index.html`) and embedded in the platform via `<iframe>`.

A course is **not** a single shared renderer with a JSON file — each course version is built and
hosted as its own artifact, so accepted edits produce a new immutable version.

---

## The 5-phase generation pipeline

Implemented in `backend/src/services/generation/pipeline.py` and `backend/src/services/agents/`.
Each phase is an Arq job that advances `course.status`.

| Phase | Job | Status | What happens |
|---|---|---|---|
| **1 — Planner** | `plan` | `planning` → `plan_review` | A LangGraph ReAct agent (Gemini) analyses the brief and calls **company-knowledge tools** (Cala MCP / RAG / SOP / compliance / policy / wiki / PDF / Google) to produce a `CoursePlan` (chapters, objectives, Bloom levels, compliance, duration). Then it **pauses at an approval gate**. |
| **Approval gate** | — | `plan_review` | The creator reviews/edits the plan in the UI (add/remove/reorder chapters, edit objectives & duration) and approves. Generation does **not** continue without approval. |
| **2 — Script writer** | `spec` | `authoring` → `spec_ready` | A second agent expands the approved plan into a full **Lastenheft (spec)**: multi-page chapters, rich interactions (dialogue, drag-drop, hotspots, charts, scenarios, flashcards, timelines…), an end-of-chapter quiz (≥80% gate + retry), and an **isolated asset manifest** of `template_link`s with detailed specs. |
| **2.5 / 3 — Assets + build** | `build` | `building` → `ready` | **Process A:** resource-fetch agents resolve each `template_link` to a real `storage_url` (`asset_map.json`). **Process B:** a per-course Vite/React/TS app is built (optionally authored by a real Devin session) with `course.json` + `asset_map.json` baked in, `npm run build`, then published. |
| **4 — Hosting** | (part of `build`) | `ready` | The built `dist/` is published to MinIO; `course_url` / `iframe_url` are stored on the course. |
| **5 — LMS & reporting** | runtime | — | Assignments, enrollments, progress/quiz tracking, manager dashboards, SCORM/xAPI export. |

**Offline-first:** every LLM/provider step has a deterministic fallback. Without any API keys
the whole pipeline still runs end-to-end (placeholder plan, placeholder Lastenheft, branded-SVG
assets, inline-HTML renderer), which is why a no-key run completes in milliseconds.

---

## Edit with Devin

On a built (`ready`) course the creator can select any block in the preview and request a
change in natural language:

1. **Select** — clicking "Select element to edit" posts `coursive:select-mode` into the course
   iframe; the renderer highlights blocks and posts back `coursive:element-selected`
   (`blockId` = `chapter.page.block`, text, type).
2. **Request edit** — `POST /courses/{id}/edits` enqueues an edit job. `generate_edited_spec`
   (`backend/src/services/agents/editor.py`) rewrites **only the selected block** (or the whole
   spec) via Gemini, with a deterministic local fallback.
3. **Preview** — a real build of the edited spec is published under a per-edit prefix,
   **reusing the existing assets**, and shown as a preview link (status `preview_ready`).
4. **Accept / Reject** — Accept promotes the edited spec, bumps `course.version`, and rebuilds &
   re-hosts the course as a new production version (assets reused). Reject discards the preview.

> ⚠️ The select/edit handshake is baked into each course's hosted renderer **at build time**.
> Courses built before this feature was added keep their old renderer and need a rebuild to gain
> element selection; newly created/rebuilt courses get it automatically.

---

## Course delivery & LMS

- **Roles** (`backend/src/db/models/org.py`, mirrored from Keycloak realm roles):
  `admin`, `course_creator`, `user` (learner). Managers are modelled via department/manager
  relationships for team reporting.
- **Assignment** — creators/managers assign courses to users or whole departments.
- **Learner player** (`frontend/src/pages/CoursePlayer.tsx`) — chapter-by-chapter, page-by-page
  navigation; an end-of-chapter quiz must be passed (≥80%) to unlock the next chapter; progress
  is reported back via `coursive:progress` postMessage → `POST /learning/...`.
- **Fullscreen** — both the creator preview and the learner player have a Fullscreen toggle
  (native Fullscreen API, `frontend/src/hooks/useFullscreen.ts`).
- **Reporting** — manager dashboard + progress report (status, progress %, score per learner).
- **Standards** — SCORM 1.2 / SCORM 2004 / xAPI export helpers in
  `backend/src/services/standards.py`.

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, TypeScript, Tailwind CSS, shadcn/ui, React Router, TanStack Query |
| Auth (client) | keycloak-js (OIDC / PKCE) |
| Backend | FastAPI, Python 3.12, uv |
| Async jobs | Arq worker on Redis |
| Agents | LangGraph + LangChain, Google Gemini |
| ORM / migrations | SQLAlchemy 2.0 async, Alembic |
| Database | PostgreSQL 16 |
| Object storage | MinIO (S3-compatible) |
| Auth server | Keycloak 24 |
| Proxy | Traefik (prod), Nginx (dev) |
| Media providers | Gemini (Nano-Banana image + TTS audio), PixVerse (image/video) |
| Knowledge | Cala MCP (company knowledge) |
| Code-gen | Devin v3 API (per-course app authoring, optional) |

---

## Project structure

```
.
├── docker-compose.yml               # symlink to deploy/docker-compose.yml
├── docker-compose.override.yml      # symlink to deploy/docker-compose.override.yml
├── .env.example
├── deploy/                          # canonical Compose files + production deploy script
│   ├── docker-compose.yml           # local/default Compose
│   ├── docker-compose.override.yml  # dev (hot reload, exposed ports)
│   ├── docker-compose.prod.yml      # production Traefik labels + image deployment
│   └── deploy.sh                    # pull images and run production Compose
├── .github/workflows/prod-build.yml # CI: build frontend + course template + docker images
├── nginx/                           # local dev gateway config
│   ├── nginx.conf
│   └── conf.d/
│       └── dev.conf                 # dev routing
├── keycloak/                        # realm theme
├── postgres/                        # init scripts
├── backend/
│   ├── alembic/                     # migrations (incl. a1b2c3d4e5f6 five-phase pipeline)
│   └── src/
│       ├── main.py
│       ├── config/settings.py       # all env vars (providers, keys, models)
│       ├── core/                    # auth, tenant/roles, exceptions
│       ├── db/                      # models, crud, database, minio, seed
│       ├── api/v1/                  # routers, schemas, endpoints
│       │   └── endpoints/           # courses, learning, reporting, people, companies, …
│       └── services/
│           ├── agents/              # ── pipeline brains ──
│           │   ├── planner.py       # Phase 1 LangGraph ReAct planner
│           │   ├── script_writer.py # Phase 2 Lastenheft generator
│           │   ├── editor.py        # Edit-with-Devin spec editor
│           │   ├── knowledge.py     # CompanyKnowledge interface + placeholder
│           │   ├── cala.py          # Cala MCP knowledge provider
│           │   ├── llm.py           # Gemini client + availability
│           │   ├── fallback.py      # deterministic offline plan/spec
│           │   └── schemas.py       # CoursePlan, Lastenheft, AssetSpec, …
│           ├── generation/
│           │   ├── pipeline.py      # Arq job orchestration (all phases)
│           │   ├── builder.py       # per-course Vite build + publish to MinIO
│           │   ├── assets.py        # asset fetch/publish, providers base
│           │   ├── devin_codegen.py # Phase 3 Devin code-gen (optional)
│           │   └── providers/       # gemini_media, pixverse, composite
│           ├── devin/client.py      # Devin v3 API client
│           ├── queue/               # Arq pool + worker
│           └── standards.py         # SCORM / xAPI export
├── course-app-template/             # per-course Vite/React renderer (built per course)
└── frontend/
    ├── Dockerfile
    ├── server.mjs                   # production static file server
    ├── public/
    │   └── silent-check-sso.html    # Keycloak silent SSO
    └── src/
        ├── pages/                   # CourseDetail, CoursePlayer, MyLearning, ManagerDashboard, …
        ├── hooks/                   # useCourses, useLearning, useFullscreen, …
        ├── components/              # Layout, ProtectedRoute, RoleRoute, CourseAssignPanel, …
        └── lib/                     # auth, api, query-client
```

---

## Services & ports

| Service | Internal | Exposed (dev) |
|---|---|---|
| Nginx | 80 | 80 |
| Frontend (Vite) | 5173 | 5173 |
| Backend (FastAPI) | 8000 | 8000 |
| Arq worker | — | — |
| Keycloak | 8080 | 8080 |
| PostgreSQL | 5432 | 5432 |
| Redis | 6379 | 6379 |
| MinIO API / Console | 9000 / 9001 | 9000 / 9001 |

Local development uses the Compose `nginx` service for the one-command laptop setup, including
hosted courses at `/storage/courses/<tenant>/<courseId>/v<n>/index.html`.

In production all traffic goes through the host Traefik instance.

---

## Traefik routing (prod)

```
<server-ip>/api/*       →  backend:8000  (strip /api)
<server-ip>/auth/*      →  keycloak:8080
<server-ip>/storage/*   →  minio:9000    (strip /storage)
<server-ip>/            →  frontend:4173 (SPA fallback)
```

---

## Getting started

```bash
cp .env.example .env
# edit .env — set passwords, secrets, local dev domains, and provider keys if needed

# Dev (hot reload, exposed ports)
docker compose up

# Production
./deploy/deploy.sh
```

First run:

1. Keycloak realm `app` + client `app-frontend` are provisioned via the bundled realm config.
2. Apply migrations: `docker compose exec backend uv run alembic upgrade head`
3. Seed demo data (tenant + users) if needed: `docker compose exec backend uv run python -m src.db.seed`
4. Log in as the seeded creator (`creator` / `creator`) and create a course.

Without provider keys the pipeline runs fully in offline/fallback mode.

---

## Configuration (providers & secrets)

All settings live in `backend/src/config/settings.py` (env via `.env`). Everything is optional;
each provider degrades to a deterministic fallback when unset.

| Capability | Env vars | Fallback if unset |
|---|---|---|
| Agentic planner + script writer | `GEMINI_API_KEY`, `GEMINI_MODEL` (`gemini-3.5-flash`) | deterministic plan/Lastenheft |
| Image generation (Nano-Banana) | `GEMINI_API_KEY`, `GEMINI_IMAGE_MODEL` (`gemini-3.1-flash-image`) | branded SVG placeholder |
| Audio narration (Gemini TTS) | `GEMINI_API_KEY`, `GEMINI_TTS_MODEL` (`gemini-3.1-flash-tts-preview`), `GEMINI_TTS_VOICE` | no audio / placeholder |
| Image/video generation (PixVerse) | `PIXVERSE_API_KEY` (`PIX_VERSE`) | branded SVG placeholder |
| Company knowledge (Cala MCP) | `CALA_MCP_URL`, `CALA_API_KEY` (`CALA`) | placeholder knowledge snippets |
| Per-course code-gen (Devin) | `DEVIN_API_KEY` (`DEVIN`), `COURSE_BUILD_USE_DEVIN=true`, `DEVIN_ORG_ID` | template-based Vite build |
| Asset provider selection | `ASSET_IMAGE_PROVIDER` / `ASSET_VIDEO_PROVIDER` / `ASSET_AUDIO_PROVIDER` (`auto`/…/`placeholder`) | `auto` |

> **Important:** keys must reach the **worker** container (not only the backend). They are wired
> through `x-backend-env` in the compose files. Do not commit real keys.

---

## Feature status

### ✅ Working

- 5-phase pipeline end-to-end with approval gate (offline fallbacks for every step).
- LangGraph planner agent with company-knowledge **tools** (Gemini); verified live.
- Script writer producing multi-page chapters + end-of-chapter quiz (≥80% gate, retry,
  sequential unlock) + isolated asset manifest.
- Per-course Vite build + MinIO hosting; inline-HTML fallback renderer.
- **Nano-Banana image generation** and **Gemini TTS** — verified live (real PNG/WAV in courses).
- **Edit with Devin**: element selection handshake, block-targeted spec edit, real preview with
  asset reuse, accept → versioned rebuild/rehost. Verified end-to-end.
- Fullscreen course view (creator preview + learner player).
- LMS: assignment, learner player with progress/quiz tracking, manager reporting, SCORM/xAPI export.
- Multi-tenant white-label (company branding, primary color, style guide).

### 🟡 Implemented but not yet verified live (no keys in CI/session)

- **Cala MCP** knowledge client (real MCP handshake) — runs on placeholder until `CALA_MCP_URL` set.
- **PixVerse** image/video — falls back to SVG until `PIXVERSE_API_KEY` set; endpoint paths may
  need adjustment per plan.
- **Devin per-course code-gen** — gated behind `COURSE_BUILD_USE_DEVIN`; template build used otherwise.

### ❌ Not yet implemented

- Real Google Search / Unsplash / Pexels stock-image fetch (manifest entries currently route to
  generative providers or placeholders).
- Resource-fetch agents are sequential helpers, not the described **parallel** multi-agent fetch.
- Asset validator stage (dimension/format validation before publish).
- SCORM/xAPI: export helpers exist, but no LRS ingestion / webhook delivery.
- Quiz analytics beyond pass/score (drop-off points, engagement score, certificates) are partial.

---

## Roadmap / TODO

1. Wire and live-verify Cala MCP, PixVerse, and Devin code-gen with real credentials.
2. Add stock-image providers (Unsplash/Pexels/Google Images) and an asset validator stage.
3. Parallelise the asset-fetch agents (true Phase 2.5 process-A concurrency).
4. Richer learner analytics (engagement score, drop-off, certificates) + manager compliance views.
5. LRS/webhook delivery for xAPI; SCORM package export (zip) for external LMS import.
6. Auto-rebuild existing courses to upgrade their hosted renderer when the renderer changes.

---

## Development

```bash
# Backend lint + tests
cd backend && uv run ruff check . && uv run pytest

# Frontend typecheck + build
cd frontend && npm run build

# Course renderer template
cd course-app-template && npm run build
```

**Adding an API route:** model (`db/models/`) → register in `db/models/__init__.py` → CRUD
(`db/crud/`) → service (`services/`) → schema (`api/v1/schemas/`) → endpoint
(`api/v1/endpoints/`) registered in `api/v1/router.py` → migration
(`uv run alembic revision --autogenerate -m "..."` then `upgrade head`).

hi matthias here
