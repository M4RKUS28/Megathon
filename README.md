# CourseForge Devin

CourseForge Devin is a full-stack hackathon product for the MEGATHON Cognition track. A company submits a course request, reviews a generated plan, approves it, and then the backend launches real Devin sessions through the official Devin API to implement, integrate assets, and QA the generated course app.

The production path is fail-closed. `TESTING=true` enables a fake Devin adapter for automated tests only. With `TESTING=false`, approval and manual Devin launch endpoints refuse to run until Devin preflight passes.

## Stack

- Frontend: Vite, React, TypeScript, Tailwind CSS
- Backend: FastAPI, Python, SQLite
- Background jobs: FastAPI background task plus asyncio polling
- Tests: pytest

## Setup

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd frontend
npm install
```

Fill `.env` with real Devin values:

```bash
DEVIN_API_KEY=cog_...
DEVIN_API_BASE_URL=https://api.devin.ai
DEVIN_ORG_ID=org-...
DEVIN_PROJECT_ID=...
DEVIN_REPO_URL=https://github.com/your-org/your-repo
DEVIN_DEFAULT_BRANCH=main
DATABASE_URL=sqlite:///./courseforge.db
TESTING=false
```

The service user key must be a Devin API v3 service-user key with permissions for `ReadAccountMeta`, repository read/indexing if you use prepare preflight, and organization session management.

## Run

Terminal 1:

```bash
source .venv/bin/activate
set -a && source .env && set +a
uvicorn backend.app.main:app --reload --port 8000
```

Terminal 2:

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`.

## Demo Flow

1. Open Dashboard and confirm Devin preflight status.
2. Go to New Course and use Seed Demo.
3. Create the course.
4. Generate the plan.
5. Review, edit, reorder, or adjust chapter durations.
6. Approve the plan.
7. The backend runs preflight with repository preparation, writes the Lastenheft and asset manifest, and starts the autonomous Devin pipeline.
8. Watch Pipeline for implementation, asset integration, QA, branch, commit, PR, and status metadata.
9. Open Evidence Ledger for the original request, approved plan, spec, assets, prompts, real Devin session IDs, status events, transcript summaries, commits, PR URLs, QA results, and hosting output.

## Backend API

- `GET /api/health`
- `GET /api/devin/preflight`
- `POST /api/courses`
- `GET /api/courses`
- `GET /api/courses/{course_id}`
- `POST /api/courses/{course_id}/plan`
- `POST /api/courses/{course_id}/approve`
- `POST /api/courses/{course_id}/devin/launch`
- `GET /api/courses/{course_id}/devin/jobs`
- `GET /api/courses/{course_id}/evidence`
- `GET /api/courses/{course_id}/assets`
- `GET /api/courses/{course_id}/reporting`

## Tests

```bash
source .venv/bin/activate
cd backend
pytest
```

The tests set `TESTING=true` and inject `FakeDevinClient`. That fake is not used in the production runtime path.

Frontend build:

```bash
cd frontend
npm run build
```

## Verifying Real Devin Work

The Evidence Ledger is at the `Evidence` tab in the UI and is backed by `GET /api/courses/{course_id}/evidence`.

Check:

- `devin_jobs[*].devin_session_id`
- `devin_jobs[*].branch`
- `devin_jobs[*].commit_sha`
- `devin_jobs[*].pr_url`
- `generated_prompts[*].prompt`
- `devin_events[*].payload`
- linked Devin session URLs inside raw status payloads

The judged demo should show real `devin-...` sessions and commits from Devin in the configured repo history.

## Why This Qualifies

CourseForge Devin does not use Devin as an inline coding assistant. Devin is the autonomous infrastructure layer. Human approval triggers API-created Devin sessions; the app stores Devin prompts, sessions, status payloads, branches, commits, PRs, transcript summaries, QA results, and exposes that evidence in a dedicated ledger.
