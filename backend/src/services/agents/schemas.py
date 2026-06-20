"""Pydantic schemas for the agentic pipeline outputs.

These are the contracts between the planner agent (Phase 1), the script-writer
graph (Phase 2), the asset pipeline (Phase 2.5 A) and the implementation/builder
(Phase 2.5 B / Phase 3). They are also used for LLM structured output.

The Page schema carries a rich implementation brief so that Devin (or any
coding agent) can build every page without follow-up questions. Each page
specifies learning goals, concrete content, learner actions, UI treatment,
worked examples, interactions, behaviours, feedback, success criteria, and
asset needs.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ── Phase 1 — Course Plan (approval gate) ────────────────────────────────────


class KnowledgeHit(BaseModel):
    """A piece of company knowledge the planner agent surfaced via its tools."""

    tool: str
    query: str
    summary: str


class PlanChapter(BaseModel):
    id: str
    title: str
    objective: str = ""
    competency: str = ""
    estimated_minutes: int = 10
    key_points: list[str] = Field(default_factory=list)
    # Bloom's taxonomy level targeted by the chapter.
    bloom_level: str = "understand"


class CoursePlan(BaseModel):
    title: str
    description: str = ""
    language: str = "en"
    difficulty: str = "beginner"
    audience: str = "new employees"
    estimated_minutes: int = 60
    objectives: list[str] = Field(default_factory=list)
    competencies: list[str] = Field(default_factory=list)
    mandatory_topics: list[str] = Field(default_factory=list)
    compliance_requirements: list[str] = Field(default_factory=list)
    knowledge_sources: list[KnowledgeHit] = Field(default_factory=list)
    chapters: list[PlanChapter] = Field(default_factory=list)


# ── Phase 2 — Lastenheft (full interactive spec) ─────────────────────────────

# Rich, implementation-ready block/interaction types. The renderer (per-course
# Vite app) implements one component per type.
BLOCK_TYPES = [
    "heading",
    "paragraph",
    "list",
    "callout",
    "image",
    "video",
    "audio",
    "dialogue",  # speech-bubble conversation between personas
    "chart",  # Chart.js interactive chart
    "flashcards",
    "dragdrop",
    "hotspot",
    "timeline",
    "accordion",
    "scenario",  # branching decision scenario
]


class AssetSpec(BaseModel):
    """An entry in the isolated asset manifest (Phase 2). No asset is fetched
    here — only the template link and the spec a fetch agent / generator needs."""

    template_link: str  # e.g. /resources/images/01
    type: str  # image | video | audio | chart | model | diagram
    dimensions: str = "16:9"  # aspect ratio or WxH
    description: str = ""  # detailed visual/audio brief
    purpose: str = ""  # function in the course


class AssetNeed(BaseModel):
    """Per-page asset requirement (collected into the chapter-level manifest)."""

    template_link: str
    type: str  # image | video | audio | diagram
    description: str = ""  # detailed visual/audio brief for the asset generator


class Block(BaseModel):
    type: str
    text: str | None = None
    items: list[str] | None = None
    # Asset reference (template_link) resolved later via asset_map.
    asset: str | None = None
    # Free-form, type-specific configuration (chart data, dialogue turns,
    # dragdrop pairs, hotspot regions, scenario branches, ...).
    data: dict | None = None


class Page(BaseModel):
    id: str
    title: str = ""
    # ── rich implementation brief (consumed by Devin) ─────────────────────
    learning_goal: str = ""  # what the learner can do after this page
    content_goals: list[str] = Field(default_factory=list)  # concrete topics
    learner_action: str = ""  # what the learner DOES on this page
    ui_treatment: str = ""  # expected visual layout / component style
    worked_example: str = ""  # a concrete, named scenario or example
    recommended_interaction: str = ""  # which interaction type(s) and why
    required_behavior: str = ""  # what the React component MUST do
    feedback_behavior: str = ""  # how the page responds to learner input
    success_criterion: str = ""  # observable proof this page works
    # ── implementation payload ────────────────────────────────────────────
    blocks: list[Block] = Field(default_factory=list)
    asset_needs: list[AssetNeed] = Field(default_factory=list)


class QuizQuestion(BaseModel):
    question: str
    options: list[str]
    answerIndex: int
    explanation: str = ""


class Quiz(BaseModel):
    passing_pct: int = 80
    retryable: bool = True
    questions: list[QuizQuestion] = Field(default_factory=list)


class AssessmentRequirement(BaseModel):
    """Specification for a chapter's assessment, separate from content."""

    tested_goals: list[str] = Field(default_factory=list)
    question_types: list[str] = Field(default_factory=list)
    misconceptions_to_probe: list[str] = Field(default_factory=list)
    minimum_questions: int = 3
    passing_pct: int = 80
    feedback_on_wrong: str = ""


class SpecChapter(BaseModel):
    id: str
    title: str
    objective: str = ""
    pages: list[Page] = Field(default_factory=list)
    quiz: Quiz = Field(default_factory=Quiz)
    assessment_requirements: AssessmentRequirement = Field(
        default_factory=AssessmentRequirement
    )


class Lastenheft(BaseModel):
    """The full course specification handed to the implementation agent."""

    title: str
    description: str = ""
    companyName: str = "Coursive"
    primaryColor: str = "#5145E5"
    language: str = "en"
    passing_pct: int = 80
    chapters: list[SpecChapter] = Field(default_factory=list)
    asset_manifest: list[AssetSpec] = Field(default_factory=list)
