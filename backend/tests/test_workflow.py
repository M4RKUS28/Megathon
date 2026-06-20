import asyncio

from app.config import Settings
from app.db import init_db
from app.devin import FakeDevinClient
from app.repository import create_course, get_latest_hosted_output, list_assets, list_devin_jobs, list_generated_prompts
from app.schemas import CourseCreate
from app.workflow import approve_plan, create_plan_for_course, run_autonomous_pipeline, run_preflight


def make_settings(tmp_path) -> Settings:
    return Settings(
        devin_api_key="cog_test",
        devin_api_base_url="https://api.devin.ai",
        devin_org_id="org-test",
        devin_project_id="project-test",
        devin_repo_url="https://github.com/example/courseforge-devin",
        devin_default_branch="main",
        database_url=f"sqlite:///{tmp_path / 'courseforge-test.db'}",
        testing=True,
        poll_interval_seconds=1,
        poll_timeout_seconds=5,
    )


def demo_payload() -> dict:
    return CourseCreate(
        title="Workplace Safety and Incident Reporting",
        description="Create a workplace safety onboarding course for warehouse employees.",
        target_audience="New warehouse employees",
        language="English",
        difficulty="Beginner",
        desired_duration_minutes=45,
        company_context="Logistics company with warehouse shifts, forklifts, picking zones, safety supervisors, incident reports, and mandatory PPE.",
        compliance_requirements="Every employee must pass each chapter quiz with at least 80 percent.",
    ).model_dump()


def test_preflight_fails_closed_without_real_credentials() -> None:
    settings = Settings(
        devin_api_key="",
        devin_api_base_url="https://api.devin.ai",
        devin_org_id="org-test",
        devin_project_id="project-test",
        devin_repo_url="https://github.com/example/courseforge-devin",
        devin_default_branch="main",
        testing=False,
    )

    result = asyncio.run(run_preflight(settings=settings))

    assert result["ok"] is False
    assert "DEVIN_API_KEY" in result["error"]


def test_testing_pipeline_uses_fake_devin_only(tmp_path, monkeypatch) -> None:
    settings = make_settings(tmp_path)
    monkeypatch.setenv("DATABASE_URL", settings.database_url)
    monkeypatch.setenv("TESTING", "true")
    init_db(settings)
    course = create_course(demo_payload())

    create_plan_for_course(course["id"])
    approve_plan(course["id"])
    asyncio.run(run_autonomous_pipeline(course["id"], settings=settings, client=FakeDevinClient()))

    jobs = list_devin_jobs(course["id"])
    prompts = list_generated_prompts(course["id"])
    assets = list_assets(course["id"])
    hosted = get_latest_hosted_output(course["id"])

    assert [job["phase"] for job in jobs] == ["implementation", "asset_integration", "qa"]
    assert all(job["devin_session_id"] for job in jobs)
    assert all(job["commit_sha"] for job in jobs)
    assert len(prompts) == 3
    assert assets and all(asset["status"] == "ready" for asset in assets)
    assert hosted and hosted["course_url"].endswith("/generated-course")
