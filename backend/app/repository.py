from __future__ import annotations

import uuid
from typing import Any

from .db import db, dumps_json, loads_json, row_to_dict, rows_to_dicts
from .timeutils import now_iso


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def create_course(payload: dict) -> dict:
    course_id = new_id("course")
    now = now_iso()
    with db() as conn:
        conn.execute(
            """
            INSERT INTO courses (
              id, title, description, target_audience, language, difficulty,
              desired_duration_minutes, company_context, compliance_requirements,
              source_material, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                course_id,
                payload["title"],
                payload["description"],
                payload["target_audience"],
                payload["language"],
                payload["difficulty"],
                payload["desired_duration_minutes"],
                payload["company_context"],
                payload["compliance_requirements"],
                payload.get("source_material"),
                "draft",
                now,
                now,
            ),
        )
    return get_course(course_id) or {}


def list_courses() -> list[dict]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM courses ORDER BY created_at DESC").fetchall()
    return rows_to_dicts(rows)


def get_course(course_id: str) -> dict | None:
    with db() as conn:
        row = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
    return row_to_dict(row)


def update_course_status(course_id: str, status: str, approved: bool = False) -> None:
    now = now_iso()
    with db() as conn:
        if approved:
            conn.execute("UPDATE courses SET status = ?, updated_at = ?, approved_at = ? WHERE id = ?", (status, now, now, course_id))
        else:
            conn.execute("UPDATE courses SET status = ?, updated_at = ? WHERE id = ?", (status, now, course_id))


def save_plan(course_id: str, plan: dict, status: str) -> dict:
    plan_id = new_id("plan")
    now = now_iso()
    with db() as conn:
        conn.execute(
            "INSERT INTO course_plans (id, course_id, plan_json, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (plan_id, course_id, dumps_json(plan), status, now, now),
        )
        conn.execute("UPDATE courses SET status = ?, updated_at = ? WHERE id = ?", ("awaiting_approval", now, course_id))
    return get_latest_plan(course_id) or {}


def get_latest_plan(course_id: str) -> dict | None:
    with db() as conn:
        row = conn.execute("SELECT * FROM course_plans WHERE course_id = ? ORDER BY created_at DESC LIMIT 1", (course_id,)).fetchone()
    data = row_to_dict(row)
    if data:
        data["plan"] = loads_json(data.pop("plan_json"), {})
    return data


def mark_plan_approved(plan_id: str, plan: dict) -> None:
    now = now_iso()
    with db() as conn:
        conn.execute("UPDATE course_plans SET status = ?, plan_json = ?, updated_at = ? WHERE id = ?", ("approved", dumps_json(plan), now, plan_id))


def save_spec(course_id: str, spec_markdown: str, spec: dict, asset_manifest: list[dict]) -> dict:
    spec_id = new_id("spec")
    now = now_iso()
    with db() as conn:
        conn.execute(
            "INSERT INTO course_specs (id, course_id, spec_markdown, spec_json, asset_manifest_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (spec_id, course_id, spec_markdown, dumps_json(spec), dumps_json(asset_manifest), now),
        )
    return get_latest_spec(course_id) or {}


def get_latest_spec(course_id: str) -> dict | None:
    with db() as conn:
        row = conn.execute("SELECT * FROM course_specs WHERE course_id = ? ORDER BY created_at DESC LIMIT 1", (course_id,)).fetchone()
    data = row_to_dict(row)
    if data:
        data["spec"] = loads_json(data.pop("spec_json"), {})
        data["asset_manifest"] = loads_json(data.pop("asset_manifest_json"), [])
    return data


def replace_assets_from_manifest(course_id: str, asset_manifest: list[dict]) -> None:
    now = now_iso()
    with db() as conn:
        conn.execute("DELETE FROM assets WHERE course_id = ?", (course_id,))
        for asset in asset_manifest:
            conn.execute(
                """
                INSERT INTO assets (
                  id, course_id, template_link, type, dimensions, description, purpose,
                  status, final_url, validation_result, source, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("asset"),
                    course_id,
                    asset["template_link"],
                    asset["type"],
                    asset["dimensions"],
                    asset["description"],
                    asset["purpose"],
                    "pending",
                    None,
                    None,
                    None,
                    now,
                    now,
                ),
            )


def update_asset_map(course_id: str, asset_map: list[dict]) -> None:
    with db() as conn:
        for item in asset_map:
            conn.execute(
                """
                UPDATE assets
                SET status = ?, final_url = ?, validation_result = ?, source = ?, updated_at = ?
                WHERE course_id = ? AND template_link = ?
                """,
                (
                    item["status"],
                    item["final_url"],
                    item["validation_result"],
                    item["source"],
                    item["updated_at"],
                    course_id,
                    item["template_link"],
                ),
            )


def list_assets(course_id: str) -> list[dict]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM assets WHERE course_id = ? ORDER BY template_link", (course_id,)).fetchall()
    return rows_to_dicts(rows)


def save_generated_prompt(course_id: str, phase: str, prompt: str) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO generated_prompts (id, course_id, phase, prompt, created_at) VALUES (?, ?, ?, ?, ?)",
            (new_id("prompt"), course_id, phase, prompt, now_iso()),
        )


def list_generated_prompts(course_id: str) -> list[dict]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM generated_prompts WHERE course_id = ? ORDER BY created_at", (course_id,)).fetchall()
    return rows_to_dicts(rows)


def create_devin_job(course_id: str, phase: str, prompt: str) -> dict:
    job_id = new_id("devinjob")
    now = now_iso()
    with db() as conn:
        conn.execute(
            """
            INSERT INTO devin_jobs (
              id, course_id, phase, prompt, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (job_id, course_id, phase, prompt, "queued", now, now),
        )
    return get_devin_job(job_id) or {}


def update_devin_job(job_id: str, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = now_iso()
    assignments = ", ".join(f"{key} = ?" for key in fields)
    values = [dumps_json(value) if key == "raw_status_payload" and not isinstance(value, str) else value for key, value in fields.items()]
    values.append(job_id)
    with db() as conn:
        conn.execute(f"UPDATE devin_jobs SET {assignments} WHERE id = ?", values)


def get_devin_job(job_id: str) -> dict | None:
    with db() as conn:
        row = conn.execute("SELECT * FROM devin_jobs WHERE id = ?", (job_id,)).fetchone()
    data = row_to_dict(row)
    if data and data.get("raw_status_payload"):
        data["raw_status_payload"] = loads_json(data["raw_status_payload"], {})
    return data


def list_devin_jobs(course_id: str) -> list[dict]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM devin_jobs WHERE course_id = ? ORDER BY created_at", (course_id,)).fetchall()
    jobs = rows_to_dicts(rows)
    for job in jobs:
        if job.get("raw_status_payload"):
            job["raw_status_payload"] = loads_json(job["raw_status_payload"], {})
    return jobs


def save_devin_event(course_id: str | None, devin_job_id: str | None, event_type: str, status: str, message: str, payload: Any) -> None:
    with db() as conn:
        conn.execute(
            """
            INSERT INTO devin_events (id, course_id, devin_job_id, event_type, status, message, payload, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (new_id("event"), course_id, devin_job_id, event_type, status, message, dumps_json(payload), now_iso()),
        )


def list_devin_events(course_id: str) -> list[dict]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM devin_events WHERE course_id = ? ORDER BY created_at", (course_id,)).fetchall()
    events = rows_to_dicts(rows)
    for event in events:
        event["payload"] = loads_json(event["payload"], {})
    return events


def save_qa_result(course_id: str, status: str, results: dict) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO qa_results (id, course_id, status, results_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (new_id("qa"), course_id, status, dumps_json(results), now_iso()),
        )


def list_qa_results(course_id: str) -> list[dict]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM qa_results WHERE course_id = ? ORDER BY created_at", (course_id,)).fetchall()
    results = rows_to_dicts(rows)
    for result in results:
        result["results"] = loads_json(result.pop("results_json"), {})
    return results


def save_hosted_output(course_id: str) -> dict:
    output_id = new_id("hosting")
    now = now_iso()
    payload = {
        "id": output_id,
        "course_id": course_id,
        "course_url": "http://localhost:5174/generated-course",
        "iframe_url": "http://localhost:5174/generated-course/embed",
        "created_at": now,
    }
    with db() as conn:
        conn.execute(
            "INSERT INTO hosted_outputs (id, course_id, course_url, iframe_url, created_at) VALUES (?, ?, ?, ?, ?)",
            (payload["id"], course_id, payload["course_url"], payload["iframe_url"], payload["created_at"]),
        )
    return payload


def get_latest_hosted_output(course_id: str) -> dict | None:
    with db() as conn:
        row = conn.execute("SELECT * FROM hosted_outputs WHERE course_id = ? ORDER BY created_at DESC LIMIT 1", (course_id,)).fetchone()
    return row_to_dict(row)


def ensure_lms_progress(course_id: str) -> None:
    now = now_iso()
    learners = [
        ("Avery Chen", "employee", 72, "in_progress", 86),
        ("Morgan Patel", "employee", 100, "certified", 91),
        ("Riley Gomez", "employee", 34, "at_risk", 62),
        ("Samira Vogel", "manager", 100, "manager_view", 89),
    ]
    with db() as conn:
        count = conn.execute("SELECT COUNT(*) AS count FROM lms_progress WHERE course_id = ?", (course_id,)).fetchone()["count"]
        if count:
            return
        for name, role, progress, status, score in learners:
            progress_json = {
                "course_progress_percent": progress,
                "chapter_completion": progress // 20,
                "page_progress": progress,
                "quiz_results": [{"chapter": 1, "score": score, "passed": score >= 80}],
                "time_spent_minutes": max(5, progress // 2),
                "retries": 1 if score < 80 else 0,
                "drop_off_point": "Chapter 3 scenario" if progress < 60 else None,
                "engagement_score": min(100, progress + 8),
                "certification_status": "certified" if status == "certified" else "not_certified",
                "scorm_1_2": "stub",
                "scorm_2004": "stub",
                "xapi_tincan": "stub",
                "rest_webhook_events": "stub",
            }
            conn.execute(
                """
                INSERT INTO lms_progress (id, course_id, learner_name, role, progress_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (new_id("lms"), course_id, name, role, dumps_json(progress_json), now, now),
            )


def reporting(course_id: str) -> dict:
    ensure_lms_progress(course_id)
    with db() as conn:
        rows = conn.execute("SELECT * FROM lms_progress WHERE course_id = ? ORDER BY learner_name", (course_id,)).fetchall()
    learners = rows_to_dicts(rows)
    for learner in learners:
        learner["progress"] = loads_json(learner.pop("progress_json"), {})
    employee_rows = [item for item in learners if item["role"] == "employee"]
    completed = [item for item in employee_rows if item["progress"]["course_progress_percent"] == 100]
    average_score = round(sum(item["progress"]["quiz_results"][0]["score"] for item in employee_rows) / max(1, len(employee_rows)), 1)
    return {
        "roles": ["administrator", "manager", "employee"],
        "assigned_courses": len(employee_rows),
        "open_courses": len(employee_rows) - len(completed),
        "completed_courses": len(completed),
        "average_score": average_score,
        "team_progress": learners,
        "compliance_status": "attention_required" if len(completed) < len(employee_rows) else "complete",
        "standards_stubs": ["SCORM 1.2", "SCORM 2004", "xAPI/TinCan", "REST webhook events"],
    }


def full_course_state(course_id: str) -> dict | None:
    course = get_course(course_id)
    if not course:
        return None
    return {
        "course": course,
        "plan": get_latest_plan(course_id),
        "spec": get_latest_spec(course_id),
        "assets": list_assets(course_id),
        "devin_jobs": list_devin_jobs(course_id),
        "devin_events": list_devin_events(course_id),
        "prompts": list_generated_prompts(course_id),
        "qa_results": list_qa_results(course_id),
        "hosted_output": get_latest_hosted_output(course_id),
    }


def evidence_ledger(course_id: str) -> dict | None:
    state = full_course_state(course_id)
    if not state:
        return None
    state["reporting"] = reporting(course_id)
    return state
