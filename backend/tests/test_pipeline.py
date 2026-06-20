"""Offline-pipeline unit tests (no DB / no network / no LLM key required)."""

from src.services.agents.fallback import fallback_lastenheft, fallback_plan
from src.services.agents.planner import generate_plan
from src.services.agents.schemas import CoursePlan, Lastenheft
from src.services.agents.script_writer import generate_lastenheft
from src.services.generation.builder import _static_fallback_html
from src.services.standards import scorm_manifest, xapi_statement

BRIEF = {
    "title": "Workplace Safety Essentials",
    "audience": "warehouse staff",
    "goals": "reduce accidents",
    "language": "en",
    "difficulty": "beginner",
    "duration": "4 chapters",
    "topics": ["PPE", "hazard reporting", "emergency exits"],
}


def test_fallback_plan_is_valid():
    plan = fallback_plan(BRIEF, "Acme")
    assert isinstance(plan, CoursePlan)
    assert plan.chapters, "plan must have chapters"
    for ch in plan.chapters:
        assert ch.title
        assert ch.bloom_level
        assert ch.estimated_minutes > 0


async def test_generate_plan_offline_falls_back():
    plan = await generate_plan(BRIEF, "Acme")
    assert isinstance(plan, CoursePlan)
    assert len(plan.chapters) >= 1


def test_fallback_lastenheft_has_rich_blocks_and_quiz():
    plan = fallback_plan(BRIEF, "Acme")
    spec = fallback_lastenheft(plan, "Acme", "#123456")
    assert isinstance(spec, Lastenheft)
    assert spec.primaryColor == "#123456"
    assert spec.chapters

    block_types = {b.type for ch in spec.chapters for p in ch.pages for b in p.blocks}
    # Never plain text only: at least one non-paragraph interaction/media block.
    assert block_types - {"paragraph", "heading"}, block_types

    for ch in spec.chapters:
        assert ch.quiz.passing_pct == 80
        assert ch.quiz.questions
        for q in ch.quiz.questions:
            assert 0 <= q.answerIndex < len(q.options)

    # Asset manifest is isolated and well-formed.
    assert spec.asset_manifest
    for a in spec.asset_manifest:
        assert a.template_link.startswith("/resources/")
        assert a.type and a.description and a.purpose


def test_fallback_chapters_are_split_into_multiple_pages():
    plan = fallback_plan(BRIEF, "Acme")
    spec = fallback_lastenheft(plan, "Acme", "#123456")
    for ch in spec.chapters:
        # Each chapter is paged (not one long page) and the quiz is separate.
        assert len(ch.pages) >= 2, ch.id
        # Page ids are unique within a chapter and pages carry blocks + a title.
        assert len({p.id for p in ch.pages}) == len(ch.pages)
        for page in ch.pages:
            assert page.title
            assert page.blocks
        # The quiz lives on the chapter, never inside a content page.
        page_types = {b.type for p in ch.pages for b in p.blocks}
        assert "quiz" not in page_types


async def test_generate_lastenheft_offline_falls_back():
    plan = fallback_plan(BRIEF, "Acme")
    spec = await generate_lastenheft(plan, "Acme", "#5145E5")
    assert isinstance(spec, Lastenheft)
    assert spec.chapters


def test_static_fallback_html_renders():
    plan = fallback_plan(BRIEF, "Acme")
    spec = fallback_lastenheft(plan, "Acme", "#abcdef").model_dump()
    spec.pop("asset_manifest", None)
    html = _static_fallback_html(spec)
    assert "<html" in html
    assert "#abcdef" in html
    assert "__COURSE_DATA__" not in html
    assert spec["title"] in html


def test_scorm_manifest_valid():
    xml = scorm_manifest("abc-123", "Safety <Course>", version="2004")
    assert xml.startswith("<?xml")
    assert "COURSE-abc-123" in xml
    assert "Safety &lt;Course&gt;" in xml  # escaped
    assert "2004 4th Edition" in xml


def test_xapi_statement_structure():
    stmt = xapi_statement(
        "a@b.com",
        "Alice",
        "http://adlnet.gov/expapi/verbs/completed",
        "completed",
        "urn:course:1",
        "Safety",
        score_pct=90,
        completed=True,
    )
    assert stmt["actor"]["mbox"] == "mailto:a@b.com"
    assert stmt["verb"]["display"]["en-US"] == "completed"
    assert stmt["result"]["completion"] is True
    assert stmt["result"]["score"]["raw"] == 90
