from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .assets import asset_interfaces
from .config import get_settings
from .db import init_db
from .repository import (
    create_course,
    evidence_ledger,
    full_course_state,
    get_course,
    list_assets,
    list_courses,
    list_devin_jobs,
    reporting,
    save_devin_event,
)
from .schemas import CourseCreate, LaunchDevinPhase, PlanApproval
from .workflow import approve_plan, create_plan_for_course, launch_manual_phase, run_autonomous_pipeline, run_preflight


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="CourseForge Devin API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    settings = get_settings()
    return {"ok": True, "service": "courseforge-devin", "testing": settings.testing}


@app.get("/api/devin/preflight")
async def devin_preflight(prepare_repository: bool = False) -> dict:
    result = await run_preflight(prepare_repository=prepare_repository)
    return result


@app.post("/api/courses")
async def create_course_endpoint(payload: CourseCreate) -> dict:
    return create_course(payload.model_dump())


@app.get("/api/courses")
async def list_courses_endpoint() -> list[dict]:
    return list_courses()


@app.get("/api/courses/{course_id}")
async def get_course_endpoint(course_id: str) -> dict:
    state = full_course_state(course_id)
    if not state:
        raise HTTPException(status_code=404, detail="Course not found")
    return state


@app.post("/api/courses/{course_id}/plan")
async def plan_course_endpoint(course_id: str) -> dict:
    if not get_course(course_id):
        raise HTTPException(status_code=404, detail="Course not found")
    return create_plan_for_course(course_id)


@app.post("/api/courses/{course_id}/approve")
async def approve_course_endpoint(course_id: str, payload: PlanApproval, background_tasks: BackgroundTasks) -> dict:
    preflight = await run_preflight(prepare_repository=True)
    if not preflight.get("ok"):
        save_devin_event(course_id, None, "preflight_failed", "error", preflight.get("error") or "Devin preflight failed", preflight)
        raise HTTPException(status_code=409, detail={"message": "Real Devin preflight failed. Pipeline refused to start.", "preflight": preflight})
    if not get_course(course_id):
        raise HTTPException(status_code=404, detail="Course not found")
    result = approve_plan(course_id, [item.model_dump() for item in payload.chapters] if payload.chapters else None)
    save_devin_event(course_id, None, "preflight_passed", "ok", "Real Devin preflight passed before launch", preflight)
    background_tasks.add_task(run_autonomous_pipeline, course_id)
    return {"ok": True, "message": "Approved. Autonomous Devin pipeline started.", "preflight": preflight, "result": result}


@app.post("/api/courses/{course_id}/devin/launch")
async def launch_devin_endpoint(course_id: str, payload: LaunchDevinPhase) -> dict:
    preflight = await run_preflight(prepare_repository=True)
    if not preflight.get("ok"):
        raise HTTPException(status_code=409, detail={"message": "Real Devin preflight failed. Manual launch refused.", "preflight": preflight})
    try:
        return await launch_manual_phase(course_id, payload.phase)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/courses/{course_id}/devin/jobs")
async def list_devin_jobs_endpoint(course_id: str) -> list[dict]:
    if not get_course(course_id):
        raise HTTPException(status_code=404, detail="Course not found")
    return list_devin_jobs(course_id)


@app.get("/api/courses/{course_id}/evidence")
async def evidence_endpoint(course_id: str) -> dict:
    ledger = evidence_ledger(course_id)
    if not ledger:
        raise HTTPException(status_code=404, detail="Course not found")
    ledger["asset_provider_interfaces"] = asset_interfaces()
    return ledger


@app.get("/api/courses/{course_id}/assets")
async def assets_endpoint(course_id: str) -> dict:
    if not get_course(course_id):
        raise HTTPException(status_code=404, detail="Course not found")
    return {"assets": list_assets(course_id), "interfaces": asset_interfaces()}


@app.get("/api/courses/{course_id}/reporting")
async def reporting_endpoint(course_id: str) -> dict:
    if not get_course(course_id):
        raise HTTPException(status_code=404, detail="Course not found")
    return reporting(course_id)
