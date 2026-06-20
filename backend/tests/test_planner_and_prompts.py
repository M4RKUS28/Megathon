from app.config import Settings
from app.planner import generate_course_plan
from app.prompts import implementation_prompt
from app.schemas import CourseCreate
from app.specs import build_course_spec


def demo_request() -> CourseCreate:
    return CourseCreate(
        title="Workplace Safety and Incident Reporting",
        description="Create a workplace safety onboarding course for warehouse employees.",
        target_audience="New warehouse employees",
        language="English",
        difficulty="Beginner",
        desired_duration_minutes=45,
        company_context="Logistics company with warehouse shifts, forklifts, picking zones, safety supervisors, incident reports, and mandatory PPE.",
        compliance_requirements="Every employee must pass each chapter quiz with at least 80 percent.",
    )


def test_plan_duration_and_learning_requirements() -> None:
    plan = generate_course_plan(demo_request())

    assert sum(chapter["duration_minutes"] for chapter in plan["chapters"]) == 45
    assert "Bloom's taxonomy" in plan["learning_principles"]
    assert "RAG retrieval" in plan["company_knowledge_placeholders"]
    assert all(chapter["quiz"]["passing_threshold_percent"] == 80 for chapter in plan["chapters"])


def test_implementation_prompt_contains_real_devin_workload() -> None:
    request = demo_request()
    course = {
        "title": request.title,
        "description": request.description,
        "target_audience": request.target_audience,
        "language": request.language,
        "difficulty": request.difficulty,
        "desired_duration_minutes": request.desired_duration_minutes,
        "company_context": request.company_context,
        "compliance_requirements": request.compliance_requirements,
    }
    plan = generate_course_plan(request)
    _, spec, asset_manifest = build_course_spec(course, plan)
    settings = Settings(
        devin_api_key="cog_test",
        devin_api_base_url="https://api.devin.ai",
        devin_org_id="org-test",
        devin_project_id="project-test",
        devin_repo_url="https://github.com/example/courseforge-devin",
        devin_default_branch="main",
        testing=True,
    )

    prompt = implementation_prompt(course, plan, spec, asset_manifest, settings)

    assert "https://github.com/example/courseforge-devin" in prompt
    assert "standalone Vite + React + TypeScript" in prompt
    assert "80 percent pass threshold" in prompt
    assert "/resources/images/img_001" in prompt
    assert "commit SHA" in prompt
