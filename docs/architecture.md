# Architecture Notes

CourseForge Devin is a monorepo with a FastAPI backend and Vite React frontend.

## Backend

The backend owns workflow state, SQLite persistence, prompt generation, Devin API calls, asset mapping, and reporting stubs.

Key modules:

- `app/devin.py`: real Devin API v3 client and `TESTING=true` fake adapter.
- `app/workflow.py`: approval gate, pipeline orchestration, Devin phase launch, polling.
- `app/planner.py`: deterministic course plan generation.
- `app/specs.py`: Lastenheft/spec and asset manifest generation.
- `app/prompts.py`: implementation, asset integration, and QA prompts.
- `app/repository.py`: SQLite persistence functions.

## Persistence

SQLite tables cover:

- courses
- course_plans
- course_specs
- assets
- devin_jobs
- devin_events
- generated_prompts
- qa_results
- hosted_outputs
- lms_progress

## Runtime Flow

1. User creates a course request.
2. Backend generates a structured plan.
3. User approves the plan.
4. Backend runs real Devin preflight and refuses launch if it fails.
5. Backend writes the Lastenheft and asset manifest.
6. Backend launches the real Devin implementation session.
7. Local asset worker maps template links to deterministic local URLs.
8. Backend launches the real Devin asset integration session.
9. Backend launches the real Devin QA/fix session.
10. Hosting and LMS/reporting records are stored.
11. Evidence Ledger exposes the full audit trail.

## Fail-Closed Behavior

`TESTING=false` selects `RealDevinClient`. Approval and manual launch call preflight first. Missing env vars, a non-`cog_` key, unreachable API, org mismatch, or invisible repo stops the pipeline before any course automation begins.

`TESTING=true` selects `FakeDevinClient` and is intended only for automated tests.
