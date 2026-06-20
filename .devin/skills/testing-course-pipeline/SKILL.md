---
name: testing-course-pipeline
description: Test the Coursive 5-phase course-generation pipeline (plan review approval gate, build/hosting, manager dashboard) end-to-end via the UI. Use when verifying course creation, the plan_review approval gate, per-course build/hosting, or LMS reporting changes.
---

# Testing the Coursive course pipeline

## Stack bring-up (local dev)
```bash
cd <repo-root>
cp .env.example .env            # local-dev passwords are fine as-is
docker compose up -d --build    # uses docker-compose.override.yml (dev: hot reload + exposed ports)
docker compose exec -T backend uv run alembic upgrade head
```
- App (via nginx): http://localhost  — backend API is proxied at `/api/v1/*`.
- Backend direct: http://localhost:8000 (paths are `/v1/...`, NOT `/api/v1/...`). OpenAPI at `/openapi.json`, health at `/health`.
- Keycloak: http://localhost:8080 — realm `app` is **auto-imported** from `keycloak/realm-app.json` (`start-dev --import-realm`). No manual realm setup needed.

## Seeded Keycloak users (realm `app`, client `app-frontend`, public + direct grant enabled)
| username | password | realm roles |
|---|---|---|
| admin | admin | user, admin |
| demo | demo | user, admin |
| creator | creator | user, course_creator |
| employee | employee | user |

- Course creation / `/courses` / `/team` require role `admin` or `course_creator` → use `creator` or `admin`.
- Roles come from the JWT `realm_access.roles` (`backend/src/core/auth.py`).

## Fast API smoke (de-risk before recording)
Direct grant is enabled, so you can drive the whole pipeline headless:
```bash
TOKEN=$(curl -s -X POST http://localhost:8080/realms/app/protocol/openid-connect/token \
  -d client_id=app-frontend -d username=creator -d password=creator -d grant_type=password \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
# create -> returns id, status "planning"
curl -s -X POST http://localhost/api/v1/courses -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"title":"X","description":"d","brief":{"audience":"staff","goals":"g","tone":"friendly","duration":"4 chapters","topics":["a","b","c"]}}'
# poll GET /api/v1/courses/{id} until status == "plan_review"
# approve: POST /api/v1/courses/{id}/plan/approve  body {"plan": null}  (or an edited plan dict)
# poll until status == "ready"; host_url = /storage/courses/acme/{id}/v1/index.html (curl -> 200)
```
NOTE: through nginx use `/api/v1/...`; hitting backend `:8000/api/v1/...` returns 404 (it's `:8000/v1/...`).

## Pipeline runs offline by default
With no `GEMINI_API_KEY`, the planner/script-writer use deterministic fallbacks (`backend/src/services/agents/fallback.py`), so the full flow `planning → plan_review → authoring → ready` works without any LLM key — good for deterministic tests. Set `GEMINI_API_KEY` in `.env` to exercise the real LangGraph agents. Pipeline jobs run in the `worker` container (Arq + Redis); `docker compose logs worker` to debug.

## Validating real provider assets (Nano-Banana / Gemini TTS / PixVerse / Cala / Devin)
With `GEMINI_API_KEY` set + `ASSET_*_PROVIDER=auto`, the asset pipeline emits real media
instead of branded SVG placeholders. The key adversarial signal lives in `asset_map.json`:
images → `.png`, audio → `.wav`; only unconfigured types (video/diagram when PixVerse is
absent) stay `.svg`.
```bash
# after a course reaches ready, inspect the asset extensions
curl -s http://localhost/api/v1/courses/$CID -H "Authorization: Bearer $TOKEN" | python3 -c "
import sys,json;from collections import Counter
am=json.load(sys.stdin)['asset_map']
print(Counter(v.rsplit('.',1)[-1] for v in am.values()))"
# download a sample and verify bytes (don't trust the extension alone)
#  PNG: first 8 bytes == \x89PNG\r\n\x1a\n ; WAV: b[:4]==RIFF and b[8:12]==WAVE (wave module -> 24kHz)
```
- Real Nano-Banana images are `1024x1024` RGB PNGs (~0.9-1.3 MB). A flat solid-color card
  with centered description text = the SVG fallback (provider NOT engaged).
- The static-fallback renderer resolves `block.asset` (e.g. `/resources/images/00`) via
  `asset_map.json` → `<img src>` (`backend/src/services/generation/static_fallback.html`),
  so real images show up in the hosted `index.html` even when `built:false` (npm build skipped).
- `built:false` in the build-job result just means the per-course Vite/Devin build was
  skipped and the static renderer was used — assets still render. Don't read it as failure.
- **CRITICAL compose gotcha:** provider keys must be in `x-backend-env` in the base
  `docker-compose.yml` (not only the override), or the **worker** never sees them and always
  falls back. Verify with `docker compose exec worker env | grep GEMINI`.
- Cala MCP / PixVerse / Devin need `CALA` / `PIX_VERSE` / `DEVIN` secrets; these may not be
  present in the runner env even if added as repo secrets — they degrade to fallback, so
  treat them as unit-tested-only unless the keys are actually injected into the worker.
- Real Gemini planner takes ~20-40 s (vs ~0.01 s fallback); real image/audio gen pushes the
  build phase to several minutes. Poll, don't assume a hang.

### Real Gemini plan vs fallback — the reliable adversarial signals
The planner falls back **silently** on any agent exception (`planner.py` try/except), so a
"plan_review" status alone does NOT prove the real LLM ran. Distinguish via:
- **Compliance requirements card** in the plan_review UI: `fallback_plan` hardcodes
  `compliance_requirements=[]` (`fallback.py`) and the UI only renders that card when non-empty
  (`CourseDetail.tsx`). For a compliance/regulation brief, a real Gemini plan populates it
  (e.g. "FCPA", "UK Bribery Act 2010") — fallback shows no card. Strongest single signal.
- **Chapter titles/objectives**: fallback chapters are the **verbatim** `brief.topics` with
  objective text of the exact form "Understand {topic} as it applies to {audience}." and key
  points "Why {topic} matters at {company}". Real Gemini reworks/reorders/adds chapters and
  writes specific objectives. (So a brief with N topics yielding exactly N verbatim-titled
  chapters + templated objectives ⇒ fallback.)
- **`knowledge_sources`** is `[]` in fallback, populated (tool/query/summary entries) when the
  ReAct agent actually ran — check `GET /api/v1/courses/{id}` `.plan.knowledge_sources`.
- **Worker log**: real success = `plan ready for course <id>`; fallback/agent failure logs
  `using fallback` / `planner agent failed` / a Gemini `thought_signature` 400.

### Gemini 3 model gotcha (thought_signature)
`GEMINI_MODEL=gemini-3.5-flash` is a **Gemini 3** model, which requires `thought_signature`
to be replayed on every multi-turn function call. The planner is a tool-using ReAct agent, so
on `langchain-google-genai` 2.x it 400s on turn 2 (`Function call is missing a thought_signature
…`) and silently falls back — every course came out as the deterministic plan. Fixed by bumping
to `langchain-google-genai>=4.2` (+ `langgraph` 1.x, `langchain-core` 1.x). The script-writer
uses single-turn `with_structured_output`, so it was unaffected — only the planner broke.
If the planner always falls back despite a valid key, check the model name vs the lib version.

## UI flow (status transitions are the key signal)
1. `/courses` → "New course" → fill Title/Audience/Goals/Key topics → "Draft with Devin".
2. Lands on `/courses/{id}`; status badge → **Plan review** (amber). The `PlanReview` component (`frontend/src/pages/CourseDetail.tsx`) shows editable objectives/duration and a chapters list (rename, Add chapter, up/down reorder, trash delete). (To prove the *real* planner ran vs the silent fallback, use the signals in "Real Gemini plan vs fallback" above — not just the presence of chapters.)
3. "Approve & generate course" → `POST .../plan/approve` → status goes Authoring/Building → **Ready**. The Preview iframe renders the hosted course; edited chapter titles persist into it. Generation log lists plan/spec/build = Succeeded.
4. `/team` → manager dashboard: 5 stat cards + members table. Empty ("No direct reports yet.") unless the logged-in user manages direct reports — that empty state is correct, not a bug.

## Gotchas
- The chapters shown at plan_review come from `brief.topics`; pass distinct topics so you can assert they appear (a static template would show generic chapters instead).
- `creator` has no direct reports, so the team dashboard is all zeros — expected. To show populated data you'd need a manager→reports hierarchy.
- Migration `a1b2c3d4e5f6` adds course columns (plan/spec/asset_manifest/asset_map/course_url/iframe_url) and enrollment tracking columns; run `alembic upgrade head` or the pages 500.

## Devin Secrets Needed
- `GEMINI_API_KEY` (repo-scoped) — drives the real LangGraph planner/script-writer AND the
  Nano-Banana image + Gemini-TTS audio providers. Tests pass without it via fallbacks, but
  real-asset validation needs it.
- `CALA` / `PIX_VERSE` / `DEVIN` (repo-scoped) — for Cala MCP, PixVerse image/video, and Devin
  code-gen respectively. Often NOT visible in the runner env; without them those providers
  stay on fallback (unit-tested only).
