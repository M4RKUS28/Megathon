"""Offline-pipeline unit tests (no DB / no network / no LLM key required)."""

from src.services.agents.editor import generate_edited_spec
from src.services.agents.fallback import fallback_lastenheft, fallback_plan
from src.services.agents.planner import generate_plan
from src.services.agents.schemas import (
    Block,
    CoursePlan,
    Lastenheft,
    Page,
    Quiz,
    QuizQuestion,
    SpecChapter,
    StyleGuide,
)
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
        assert len(ch.quiz.questions) >= 3
        for q in ch.quiz.questions:
            assert 0 <= q.answerIndex < len(q.options)

    # Asset manifest is isolated and well-formed.
    assert spec.asset_manifest
    for a in spec.asset_manifest:
        assert a.template_link.startswith("/resources/")
        assert a.type and a.description and a.purpose


def test_fallback_lastenheft_populates_new_schema_fields():
    """Verify the fallback produces the upgraded Lastenheft fields."""
    plan = fallback_plan(BRIEF, "Acme")
    spec = fallback_lastenheft(plan, "Acme", "#aabbcc")

    # Top-level new fields
    assert spec.target_audience == plan.audience
    assert spec.difficulty == plan.difficulty
    assert spec.estimated_minutes == plan.estimated_minutes
    assert spec.style_guide.tone

    for ch in spec.chapters:
        # Chapter-level
        assert ch.learning_points
        assert ch.estimated_minutes > 0
        assert ch.competency
        assert ch.bloom_level
        # Quiz linkage
        assert ch.quiz.assessment_id
        assert ch.quiz.chapter_ref == ch.id
        assert ch.quiz.competency_assessed
        for q in ch.quiz.questions:
            assert q.bloom_level
            assert q.learning_point_ref

        # Page-level
        for page in ch.pages:
            assert page.content_goal
            assert page.learner_action
            assert page.ui_treatment
            assert page.estimated_minutes > 0

        # Block-level intent fields (at least some blocks should have them)
        blocks_with_goal = [
            b for p in ch.pages for b in p.blocks if b.interaction_goal
        ]
        assert blocks_with_goal, "at least one block per chapter should have interaction_goal"

    # Asset alt_text
    for a in spec.asset_manifest:
        assert a.alt_text


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


def test_fallback_pages_have_rich_implementation_brief():
    """Every page in the fallback Lastenheft must carry the full implementation
    brief fields so Devin can build without follow-up questions."""
    plan = fallback_plan(BRIEF, "Acme")
    spec = fallback_lastenheft(plan, "Acme", "#123456")
    for ch in spec.chapters:
        for page in ch.pages:
            assert page.learning_goal, f"{page.id} missing learning_goal"
            assert page.content_goals, f"{page.id} missing content_goals"
            assert len(page.content_goals) >= 2, f"{page.id} needs >=2 content_goals"
            assert page.learner_action, f"{page.id} missing learner_action"
            assert page.ui_treatment, f"{page.id} missing ui_treatment"
            assert page.worked_example, f"{page.id} missing worked_example"
            assert page.recommended_interaction, f"{page.id} missing recommended_interaction"
            assert page.required_behavior, f"{page.id} missing required_behavior"
            assert page.feedback_behavior, f"{page.id} missing feedback_behavior"
            assert page.success_criterion, f"{page.id} missing success_criterion"


def test_fallback_chapters_have_assessment_requirements():
    """Each chapter must carry assessment_requirements separate from the quiz."""
    plan = fallback_plan(BRIEF, "Acme")
    spec = fallback_lastenheft(plan, "Acme", "#123456")
    for ch in spec.chapters:
        ar = ch.assessment_requirements
        assert ar.tested_goals, f"{ch.id} missing tested_goals"
        assert ar.question_types, f"{ch.id} missing question_types"
        assert ar.misconceptions_to_probe, f"{ch.id} missing misconceptions_to_probe"
        assert ar.minimum_questions >= 3
        assert ar.passing_pct == 80
        assert ar.feedback_on_wrong, f"{ch.id} missing feedback_on_wrong"


def test_fallback_pages_have_asset_needs_with_template_links():
    """Pages that use media blocks must declare asset_needs entries."""
    plan = fallback_plan(BRIEF, "Acme")
    spec = fallback_lastenheft(plan, "Acme", "#123456")
    pages_with_media = [
        page
        for ch in spec.chapters
        for page in ch.pages
        if any(b.asset for b in page.blocks)
    ]
    assert pages_with_media, "at least some pages should have media blocks"
    for page in pages_with_media:
        assert page.asset_needs, f"{page.id} has media blocks but no asset_needs"
        for need in page.asset_needs:
            assert need.template_link.startswith("/resources/")
            assert need.type
            assert need.description


def test_fallback_quiz_questions_are_scenario_based():
    """Quiz questions must test application, not trivial recall."""
    plan = fallback_plan(BRIEF, "Acme")
    spec = fallback_lastenheft(plan, "Acme", "#123456")
    for ch in spec.chapters:
        for q in ch.quiz.questions:
            # No joke distractors
            lowered = [o.lower() for o in q.options]
            assert "office snacks" not in lowered
            assert "parking" not in lowered
            # Explanation must be non-empty
            assert q.explanation


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
    new_spec = await generate_edited_spec(
        spec, "make it friendlier", "0.0.0", before.get("text")
    )
    # Same shape, only the targeted block changed.
    assert len(new_spec["chapters"]) == len(spec["chapters"])
    after = new_spec["chapters"][0]["pages"][0]["blocks"][0]
    assert after != before
    # An untouched block is preserved.
    assert (
        new_spec["chapters"][-1]["pages"][-1]["blocks"][-1]
        == spec["chapters"][-1]["pages"][-1]["blocks"][-1]
    )


async def test_edit_without_selector_applies_spec_level_change_offline():
    plan = fallback_plan(BRIEF, "Acme")
    spec = fallback_lastenheft(plan, "Acme", "#abcdef").model_dump()
    new_spec = await generate_edited_spec(spec, "add a safety reminder", None, None)
    assert Lastenheft(**new_spec).chapters
    assert new_spec != spec


# ── Backward compatibility: old-shape specs (no new fields) still validate ───


def test_old_shape_spec_still_validates():
    """A Lastenheft dict without the new optional fields must still parse."""
    old_spec = {
        "title": "Legacy Course",
        "description": "desc",
        "companyName": "Acme",
        "primaryColor": "#000",
        "language": "en",
        "passing_pct": 80,
        "chapters": [
            {
                "id": "ch1",
                "title": "Intro",
                "objective": "Learn basics",
                "pages": [
                    {
                        "id": "p1",
                        "title": "Page 1",
                        "blocks": [{"type": "paragraph", "text": "Hello"}],
                    }
                ],
                "quiz": {
                    "passing_pct": 80,
                    "retryable": True,
                    "questions": [
                        {
                            "question": "Q?",
                            "options": ["A", "B"],
                            "answerIndex": 0,
                        }
                    ],
                },
            }
        ],
        "asset_manifest": [],
    }
    lh = Lastenheft(**old_spec)
    assert lh.chapters[0].learning_points == []
    assert lh.chapters[0].estimated_minutes == 0
    assert lh.chapters[0].pages[0].content_goal == ""
    assert lh.chapters[0].pages[0].blocks[0].interaction_goal == ""
    assert lh.chapters[0].quiz.assessment_id == ""
    assert lh.style_guide.tone == ""
    assert lh.target_audience == ""
    assert lh.estimated_minutes == 0


def test_new_shape_spec_validates():
    """A Lastenheft with all new fields filled in must also parse."""
    lh = Lastenheft(
        title="Modern Course",
        target_audience="engineers",
        difficulty="intermediate",
        estimated_minutes=45,
        style_guide=StyleGuide(
            font_heading="Inter",
            font_body="Source Sans Pro",
            accent_color="#FF6600",
            tone="technical yet approachable",
            illustration_style="flat vector",
            layout_preference="magazine",
        ),
        chapters=[
            SpecChapter(
                id="ch1",
                title="Getting Started",
                objective="Onboard",
                learning_points=["Set up dev env", "Run first test"],
                estimated_minutes=15,
                competency="Developer Onboarding",
                bloom_level="apply",
                pages=[
                    Page(
                        id="p1",
                        title="Setup",
                        content_goal="Walk through env setup",
                        learner_action="Follow along in terminal",
                        ui_treatment="split-screen: instructions left, terminal right",
                        estimated_minutes=5,
                        blocks=[
                            Block(
                                type="worked_example",
                                text="Setting up your environment",
                                interaction_goal="Guide through first-run setup",
                                suggested_interaction="Step-by-step reveal with copy buttons",
                                required_behavior="Steps revealed one at a time",
                                feedback_behavior="Checkmark after each step is expanded",
                                success_criterion="All steps viewed",
                                worked_example={
                                    "steps": [
                                        {"title": "Clone repo", "code": "git clone ..."},
                                        {"title": "Install deps", "code": "npm install"},
                                    ]
                                },
                            )
                        ],
                    )
                ],
                quiz=Quiz(
                    passing_pct=80,
                    retryable=True,
                    assessment_id="quiz-ch1",
                    chapter_ref="ch1",
                    competency_assessed="Developer Onboarding",
                    questions=[
                        QuizQuestion(
                            question="First step?",
                            options=["Clone", "Deploy", "Delete"],
                            answerIndex=0,
                            bloom_level="remember",
                            learning_point_ref="Set up dev env",
                        )
                    ],
                ),
            )
        ],
    )
    assert lh.style_guide.font_heading == "Inter"
    ch = lh.chapters[0]
    assert ch.learning_points == ["Set up dev env", "Run first test"]
    assert ch.bloom_level == "apply"
    page = ch.pages[0]
    assert page.ui_treatment == "split-screen: instructions left, terminal right"
    block = page.blocks[0]
    assert block.worked_example is not None
    assert block.success_criterion == "All steps viewed"
    assert ch.quiz.assessment_id == "quiz-ch1"
    assert ch.quiz.questions[0].learning_point_ref == "Set up dev env"


def test_round_trip_old_spec_through_model_dump():
    """model_dump then re-parse must be identity for old-shape specs."""
    plan = fallback_plan(BRIEF, "Acme")
    spec = fallback_lastenheft(plan, "Acme", "#abcdef")
    dumped = spec.model_dump()
    reparsed = Lastenheft(**dumped)
    assert reparsed == spec


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
