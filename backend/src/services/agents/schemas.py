"""Pydantic schemas for the agentic pipeline outputs.

These are the contracts between the planner agent (Phase 1), the script-writer
graph (Phase 2), the asset pipeline (Phase 2.5 A) and the implementation/builder
(Phase 2.5 B / Phase 3). They are also used for LLM structured output.

The Lastenheft (spec) is *not* a rigid renderer schema — it describes behaviour
and intent clearly enough for Devin to implement bespoke React components.

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

# A *suggested*, non-exhaustive palette of content/interaction types. The
# Lastenheft defines WHAT to teach and WHICH resources (assets) to use — it
# deliberately does NOT lock down the visual design. The implementation agent
# (and the per-course renderer) are free to use these, combine them, or invent
# richer custom types: `Block.type` is an open string and the renderer degrades
# gracefully for unknown types. Treat this list as inspiration, not a hard limit.
BLOCK_TYPES = [
    "heading",
    "paragraph",
    "list",
    "callout",
    "image",
    "video",
    "audio",
    "conversation",  # two personas talking: avatars left/right, click through each
    # speech bubble, every line narrated (per-bubble TTS). Ideal for behavioural /
    # soft-skill / "how to act" topics. data shape:
    #   personas: [{id, name, role, side: "left"|"right", avatar}]
    #   turns:    [{persona: <persona id>, text, audio: "/resources/audio/NN"}]
    # `avatar` is a stable seed/key for the local cartoon-avatar library (or an
    # asset link to a real image); each `turn.audio` is a unique TTS asset link.
    "dialogue",  # legacy alias for `conversation` (turns: [{speaker, text}])
    "chart",  # Chart.js interactive chart
    "flashcards",
    "dragdrop",
    "hotspot",
    "timeline",
    "accordion",
    "scenario",  # branching decision scenario
    "worked_example",  # step-by-step worked example
    "code",  # code block / live editor
    "embed",  # external embed (iframe / widget)
]


class AssetSpec(BaseModel):
    """An entry in the isolated asset manifest (Phase 2).

    No asset is fetched here — only the template link and the spec a resource-
    fetch agent (or generator) needs to produce the final binary. At build time
    the ``template_link`` is the *only* identifier the implementation code
    should reference; the asset pipeline resolves each link to a production
    ``storage_url`` in ``asset_map.json``.
    """

    template_link: str  # e.g. /resources/images/01
    type: str  # image | video | audio | chart | model | diagram
    dimensions: str = "16:9"  # aspect ratio or WxH (e.g. "16:9", "800x450")
    description: str = ""  # detailed visual/audio brief for the generator
    purpose: str = ""  # function of the asset in the course
    alt_text: str = ""  # accessible alt text for screen readers
    style_hints: dict | None = None  # e.g. {"palette": "warm", "mood": "professional"}
    usage_context: str = ""  # where/how this asset appears (e.g. "hero image on intro page")
    # Optional TTS voice override for audio assets (e.g. distinct voices for the
    # two sides of a conversation). Falls back to the configured default voice.
    voice: str | None = None


class AssetNeed(BaseModel):
    """Per-page asset requirement (collected into the chapter-level manifest)."""

    template_link: str
    type: str  # image | video | audio | diagram
    description: str = ""  # detailed visual/audio brief for the asset generator


class Block(BaseModel):
    # Intentionally free-form: `type` is any string (see BLOCK_TYPES for a
    # suggested palette, but custom types are allowed). A block captures a unit
    # of CONTENT or a resource reference; the actual visual design is the
    # implementation agent's job, not the spec's.
    type: str
    text: str | None = None
    items: list[str] | None = None
    # Asset reference (template_link) resolved later via asset_map.
    asset: str | None = None
    # Free-form, type-specific configuration (chart data, dialogue turns,
    # dragdrop pairs, hotspot regions, scenario branches, ...).
    data: dict | None = None
    # ── Intent-level fields (guide Devin's bespoke React implementation) ──
    interaction_goal: str = ""  # what this interaction aims to achieve
    suggested_interaction: str = ""  # implementation hint, e.g. "animate bar chart on scroll"
    required_behavior: str = ""  # what the block MUST do behaviourally
    feedback_behavior: str = ""  # how the block responds to user actions
    success_criterion: str = ""  # how to tell the learner succeeded
    worked_example: dict | None = None  # step-by-step worked example or scenario data


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
    estimated_minutes: int = 0  # time budget for this page (0 = unspecified)


class QuizQuestion(BaseModel):
    question: str
    options: list[str]
    answerIndex: int
    explanation: str = ""
    bloom_level: str = ""  # Bloom's taxonomy level, e.g. "apply"
    learning_point_ref: str = ""  # links to a chapter learning point


class Quiz(BaseModel):
    passing_pct: int = 80
    retryable: bool = True
    questions: list[QuizQuestion] = Field(default_factory=list)
    assessment_id: str = ""  # stable id for analytics linkage
    chapter_ref: str = ""  # which chapter this quiz assesses
    competency_assessed: str = ""  # competency being measured


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
    learning_points: list[str] = Field(default_factory=list)
    estimated_minutes: int = 0  # time budget (0 = unspecified)
    competency: str = ""  # competency this chapter targets
    bloom_level: str = ""  # Bloom's taxonomy level
    assessment_requirements: AssessmentRequirement = Field(
        default_factory=AssessmentRequirement
    )


class StyleGuide(BaseModel):
    """Course-level style and branding hints for the implementation agent."""

    font_heading: str = ""  # e.g. "Inter"
    font_body: str = ""
    accent_color: str = ""  # secondary accent
    tone: str = ""  # e.g. "friendly and professional"
    illustration_style: str = ""  # e.g. "flat vector", "3d isometric"
    layout_preference: str = ""  # e.g. "single-column", "magazine"
    extras: dict | None = None  # open-ended overrides


class Lastenheft(BaseModel):
    """The full course specification handed to the implementation agent.

    This schema describes *behaviour and intent*, not pixel-level layout.
    It should contain enough detail for Devin to build a bespoke React app
    without follow-up questions.
    """

    title: str
    description: str = ""
    companyName: str = "Coursive"
    primaryColor: str = "#5145E5"
    language: str = "en"
    passing_pct: int = 80
    chapters: list[SpecChapter] = Field(default_factory=list)
    asset_manifest: list[AssetSpec] = Field(default_factory=list)
    # ── New top-level fields (all optional for backward compat) ──
    target_audience: str = ""
    difficulty: str = ""
    estimated_minutes: int = 0  # total course time budget
    style_guide: StyleGuide = Field(default_factory=StyleGuide)
