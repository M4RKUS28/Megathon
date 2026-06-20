"""Pydantic schemas for the agentic pipeline outputs.

These are the contracts between the planner agent (Phase 1), the script-writer
graph (Phase 2), the asset pipeline (Phase 2.5 A) and the implementation/builder
(Phase 2.5 B / Phase 3). They are also used for LLM structured output.
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
    # ── Phase-2 enrichment fields (guide the script writer) ──
    subtopics: list[str] = Field(default_factory=list)
    min_pages: int = 5
    suggested_interactions: list[str] = Field(default_factory=list)
    dialogue_appropriate: bool = False
    chart_appropriate: bool = False
    depth: str = "standard"


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
    # ── Content-style guidance for the script writer ──
    primary_format: str = "expository"
    content_density: str = "rich"
    style_notes: list[str] = Field(default_factory=list)


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
    "minigame",  # gamified, scored exercise with instant feedback. `data.game`
    # selects the kind (custom kinds allowed; the renderer degrades gracefully):
    #   quiz   -> {prompt?, questions: [{question, options, answerIndex, explanation?}]}
    #   order  -> {prompt?, steps: [str]}            (steps given in the CORRECT order)
    #   sort   -> {prompt?, categories: [str], items: [{text, category}]}
    #   memory -> {prompt?, pairs: [{a, b}]}         (flip-card matching)
]


class AssetSpec(BaseModel):
    """An entry in the isolated asset manifest (Phase 2). No asset is fetched
    here — only the template link and the spec a fetch agent / generator needs."""

    template_link: str  # e.g. /resources/images/01
    type: str  # image | video | audio | chart | model | diagram
    dimensions: str = "16:9"  # aspect ratio or WxH
    description: str = ""  # detailed visual/audio brief
    purpose: str = ""  # function in the course
    # Optional TTS voice override for audio assets (e.g. distinct voices for the
    # two sides of a conversation). Falls back to the configured default voice.
    voice: str | None = None


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


class Page(BaseModel):
    id: str
    title: str = ""
    blocks: list[Block] = Field(default_factory=list)


class QuizQuestion(BaseModel):
    question: str
    options: list[str]
    answerIndex: int
    explanation: str = ""


class Quiz(BaseModel):
    passing_pct: int = 80
    retryable: bool = True
    questions: list[QuizQuestion] = Field(default_factory=list)


class SpecChapter(BaseModel):
    id: str
    title: str
    objective: str = ""
    pages: list[Page] = Field(default_factory=list)
    quiz: Quiz = Field(default_factory=Quiz)


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
