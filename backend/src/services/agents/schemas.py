"""Pydantic schemas for the agentic pipeline outputs.

These are the contracts between the planner agent (Phase 1), the script-writer
graph (Phase 2), the asset pipeline (Phase 2.5 A) and the implementation/builder
(Phase 2.5 B / Phase 3). They are also used for LLM structured output.

The Lastenheft (spec) is *not* a rigid renderer schema — it describes behaviour
and intent clearly enough for Devin to implement bespoke React components.
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
# Vite app) implements one component per type.  Devin may invent additional
# types when building bespoke React — this list is advisory, not exhaustive.
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
    "worked_example",  # step-by-step worked example
    "code",  # code block / live editor
    "embed",  # external embed (iframe / widget)
]


class AssetSpec(BaseModel):
    """An entry in the isolated asset manifest (Phase 2). No asset is fetched
    here — only the template link and the spec a fetch agent / generator needs."""

    template_link: str  # e.g. /resources/images/01
    type: str  # image | video | audio | chart | model | diagram
    dimensions: str = "16:9"  # aspect ratio or WxH
    description: str = ""  # detailed visual/audio brief
    purpose: str = ""  # function in the course
    alt_text: str = ""  # accessibility alt text
    style_hints: dict | None = None  # e.g. {"palette": "warm", "mood": "professional"}


class Block(BaseModel):
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
    blocks: list[Block] = Field(default_factory=list)
    content_goal: str = ""  # what this page aims to teach or achieve
    learner_action: str = ""  # what the learner should *do* on this page
    ui_treatment: str = ""  # visual hint, e.g. "hero splash", "two-column sidebar"
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
