"""Offline-pipeline unit tests (no DB / no network / no LLM key required)."""

from src.services.agents.editor import (
    EditResult,
    classify_edit_complexity,
    compute_edit_diff,
    generate_edited_spec,
    validate_edited_spec,
)
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


def test_static_fallback_supports_edit_selection_handshake():
    plan = fallback_plan(BRIEF, "Acme")
    spec = fallback_lastenheft(plan, "Acme", "#abcdef").model_dump()
    spec.pop("asset_manifest", None)
    html = _static_fallback_html(spec)
    # The renderer must implement the "Edit with Devin" element-selection protocol.
    assert "coursive:select-mode" in html
    assert "coursive:element-selected" in html


async def test_edit_block_only_changes_selected_block_offline():
    plan = fallback_plan(BRIEF, "Acme")
    spec = fallback_lastenheft(plan, "Acme", "#abcdef").model_dump()
    before = spec["chapters"][0]["pages"][0]["blocks"][0]
    result = await generate_edited_spec(
        spec, "make it friendlier", "0.0.0", before.get("text")
    )
    assert isinstance(result, EditResult)
    new_spec = result.new_spec
    # Same shape, only the targeted block changed.
    assert len(new_spec["chapters"]) == len(spec["chapters"])
    after = new_spec["chapters"][0]["pages"][0]["blocks"][0]
    assert after != before
    # An untouched block is preserved.
    assert (
        new_spec["chapters"][-1]["pages"][-1]["blocks"][-1]
        == spec["chapters"][-1]["pages"][-1]["blocks"][-1]
    )
    # EditResult contains metadata.
    assert result.edit_tier == "simple"
    assert result.diff is not None
    assert result.diff.summary  # non-empty summary


async def test_edit_without_selector_applies_spec_level_change_offline():
    plan = fallback_plan(BRIEF, "Acme")
    spec = fallback_lastenheft(plan, "Acme", "#abcdef").model_dump()
    result = await generate_edited_spec(spec, "add a safety reminder", None, None)
    assert isinstance(result, EditResult)
    assert Lastenheft(**result.new_spec).chapters
    assert result.new_spec != spec
    # Spec-level edits without selector are always complex.
    assert result.edit_tier == "complex"


# ── Classifier tests ─────────────────────────────────────────────────────────

def test_classify_edit_complexity_simple_cases():
    assert classify_edit_complexity("make it friendlier", "0.0.0") == "simple"
    assert classify_edit_complexity("add an example", "0.0.0") == "simple"
    assert classify_edit_complexity("fix a typo", "0.0.0") == "simple"
    assert classify_edit_complexity("rephrase this paragraph", "1.2.3") == "simple"
    assert classify_edit_complexity("short instruction", "0.0.0") == "simple"


def test_classify_edit_complexity_complex_cases():
    assert classify_edit_complexity("anything", None) == "complex"
    assert classify_edit_complexity("add chapter about safety", "0.0.0") == "complex"
    assert classify_edit_complexity("restructure the course", "0.0.0") == "complex"
    assert classify_edit_complexity("update quiz questions", "0.0.0") == "complex"
    assert classify_edit_complexity("add compliance regulation note", "0.0.0") == "complex"


# ── Diff tracking tests ──────────────────────────────────────────────────────

def test_compute_edit_diff_detects_changes():
    old = {"chapters": [{"pages": [{"blocks": [{"type": "paragraph", "text": "old"}]}]}]}
    new = {"chapters": [{"pages": [{"blocks": [{"type": "paragraph", "text": "new"}]}]}]}
    diff = compute_edit_diff(old, new)
    assert len(diff.changed) == 1
    assert diff.changed[0].action == "changed"
    assert "1 block(s) changed" in diff.summary


def test_compute_edit_diff_detects_added_blocks():
    old = {"chapters": [{"pages": [{"blocks": [{"type": "paragraph", "text": "a"}]}]}]}
    new = {"chapters": [{"pages": [{"blocks": [
        {"type": "paragraph", "text": "a"},
        {"type": "callout", "text": "new"}
    ]}]}]}
    diff = compute_edit_diff(old, new)
    added = [d for d in diff.changed if d.action == "added"]
    assert len(added) == 1
    assert "1 block(s) added" in diff.summary


# ── Validation tests ─────────────────────────────────────────────────────────

def test_validate_edited_spec_catches_quiz_issues():
    spec = {"chapters": [{
        "pages": [{"blocks": [{"type": "paragraph", "text": "test"}]}],
        "quiz": {
            "passing_pct": 150,
            "questions": [{
                "question": "test?",
                "options": ["a", "b"],
                "answerIndex": 5
            }]
        }
    }]}
    warnings = validate_edited_spec(spec)
    assert any("passing_pct" in w for w in warnings)
    assert any("answerIndex" in w for w in warnings)


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
