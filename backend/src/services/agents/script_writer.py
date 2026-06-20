"""Phase 2 — Course Script Writer.

A small LangGraph state graph that turns the *approved* Course Plan into a full
Lastenheft (interactive spec) plus an isolated asset manifest:

    design_interactions  ->  build_manifest  ->  (Lastenheft)

`design_interactions` writes implementation-ready pages with rich interactions
(dialogue, dragdrop, flashcards, charts, hotspots, scenarios, ...) and end-of-
chapter quizzes (80% gate, retryable). `build_manifest` collects every asset the
spec references into the isolated manifest (template_link + specs only — no asset
is fetched in this phase).

Falls back to the deterministic Lastenheft generator when Gemini is unavailable.
"""

from __future__ import annotations

import logging
from typing import TypedDict

from pydantic import BaseModel, Field

from .fallback import fallback_lastenheft
from .llm import gemini_available, get_chat_model
from .schemas import AssetSpec, CoursePlan, Lastenheft, SpecChapter, StyleGuide

logger = logging.getLogger(__name__)

SCRIPT_SYSTEM = """You are a senior interactive learning designer. Turn the approved course
plan into an implementation-ready Lastenheft (spec) for a bespoke Vite/React course app
that a coding agent (Devin) will build from scratch.

The spec describes *behaviour and intent* — NOT a rigid renderer schema. Be specific enough
that Devin can implement each interaction without follow-up questions.

Rules:
- The course must NEVER be plain text. Each topic block is supported by media or an interaction.
- Split EVERY chapter into MULTIPLE pages (at least 3, ideally 3-5). Each `page` is one
  digestible screen the learner steps through one at a time (e.g. "Introduction",
  "Key concepts", "Apply it", "Recap"). NEVER put a whole chapter on a single page, and never
  put the quiz inside a content page.
- Give each page 2-4 blocks and a short, descriptive page `title`. Use a rich mix of block
  types across the pages: heading, paragraph, list, callout, image, video, audio,
  dialogue (speech-bubble conversation), chart (Chart.js), flashcards, dragdrop, hotspot,
  timeline, accordion, scenario (branching), worked_example. Favour many visualisations and
  conversations.
- For every visual/media block set `asset` to a UNIQUE template link like
  "/resources/images/01", "/resources/videos/02", "/resources/audio/03". Do NOT invent URLs.
- Describe interactions precisely via the `data` field so a coding agent can implement them
  without questions (e.g. chart: chartType/labels/datasets; dragdrop: pairs; dialogue: turns;
  scenario: branches).

Chapter-level fields (populate for EVERY chapter):
  - `learning_points`: concrete things the learner will know/be able to do after this chapter.
  - `estimated_minutes`: realistic time budget.
  - `competency`: the competency this chapter targets.
  - `bloom_level`: Bloom's taxonomy level (remember/understand/apply/analyze/evaluate/create).

Page-level fields (populate for EVERY page):
  - `content_goal`: what this page aims to teach or achieve.
  - `learner_action`: what the learner should *do* on this page.
  - `ui_treatment`: visual/layout hint (e.g. "hero splash", "two-column sidebar", "immersive
    scenario"). This guides Devin's React implementation — be creative, not generic.
  - `estimated_minutes`: time budget for this page.

Block-level intent fields (populate where the block has interaction or media):
  - `interaction_goal`: what this interaction aims to achieve pedagogically.
  - `suggested_interaction`: implementation hint (e.g. "animate bars on scroll").
  - `required_behavior`: what the block MUST do behaviourally.
  - `feedback_behavior`: how the block responds to user actions.
  - `success_criterion`: how to tell the learner succeeded.
  - `worked_example`: optional step-by-step worked example data.

Quiz fields:
- Each chapter ends with ONE quiz (shown only after the last page):
  passing_pct=80, retryable=true, 3-5 multiple-choice questions with the correct answerIndex
  and an explanation. Learners must score >=80% to unlock the next chapter.
- Set `assessment_id` (stable id), `chapter_ref` (chapter id), `competency_assessed`.
- On each question set `bloom_level` and `learning_point_ref` (links to a chapter
  learning_point).

Return structured output: a list of chapters covering EVERY chapter in the plan, in order."""


class _ChaptersOut(BaseModel):
    chapters: list[SpecChapter] = Field(default_factory=list)


class _State(TypedDict, total=False):
    plan: CoursePlan
    company_name: str
    primary_color: str
    chapters: list[SpecChapter]
    asset_manifest: list[AssetSpec]
    lastenheft: Lastenheft


def _plan_text(plan: CoursePlan) -> str:
    lines = [f"Title: {plan.title}", f"Audience: {plan.audience}", f"Language: {plan.language}"]
    if plan.objectives:
        lines.append("Objectives:\n" + "\n".join(f"- {o}" for o in plan.objectives))
    if plan.compliance_requirements:
        lines.append(
            "Compliance:\n" + "\n".join(f"- {c}" for c in plan.compliance_requirements)
        )
    lines.append("Chapters:")
    for c in plan.chapters:
        kp = "; ".join(c.key_points)
        lines.append(f"- [{c.id}] {c.title} — {c.objective} (key points: {kp})")
    return "\n".join(lines)


async def _design_interactions(state: _State) -> _State:
    plan = state["plan"]
    model = get_chat_model(temperature=0.5).with_structured_output(_ChaptersOut)
    out: _ChaptersOut = await model.ainvoke(
        [("system", SCRIPT_SYSTEM), ("user", _plan_text(plan))]
    )
    chapters = out.chapters or []
    if not chapters:
        raise RuntimeError("script writer produced no chapters")
    return {"chapters": chapters}


def _build_manifest(state: _State) -> _State:
    """Collect every referenced asset into the isolated manifest (dedup by link)."""
    manifest: dict[str, AssetSpec] = {}
    for ch in state["chapters"]:
        for page in ch.pages:
            for block in page.blocks:
                link = block.asset
                if not link or link in manifest:
                    continue
                atype = block.type if block.type in {"image", "video", "audio"} else "image"
                if block.type == "chart":
                    atype = "diagram"
                manifest[link] = AssetSpec(
                    template_link=link,
                    type=atype,
                    dimensions="16:9",
                    description=(block.text or ch.title or "Course asset").strip(),
                    purpose=f"{block.type} in chapter '{ch.title}'",
                )
    return {"asset_manifest": list(manifest.values())}


def _assemble(state: _State) -> _State:
    plan = state["plan"]
    return {
        "lastenheft": Lastenheft(
            title=plan.title,
            description=plan.description,
            companyName=state["company_name"],
            primaryColor=state["primary_color"],
            language=plan.language,
            passing_pct=80,
            chapters=state["chapters"],
            asset_manifest=state["asset_manifest"],
            target_audience=plan.audience,
            difficulty=plan.difficulty,
            estimated_minutes=plan.estimated_minutes,
            style_guide=StyleGuide(tone="friendly and professional"),
        )
    }


def _build_graph():
    from langgraph.graph import END, START, StateGraph

    g = StateGraph(_State)
    g.add_node("design_interactions", _design_interactions)
    g.add_node("build_manifest", _build_manifest)
    g.add_node("assemble", _assemble)
    g.add_edge(START, "design_interactions")
    g.add_edge("design_interactions", "build_manifest")
    g.add_edge("build_manifest", "assemble")
    g.add_edge("assemble", END)
    return g.compile()


async def generate_lastenheft(
    plan: CoursePlan, company_name: str, primary_color: str
) -> Lastenheft:
    """Run the script-writer graph (or deterministic fallback)."""
    if not gemini_available():
        logger.info("GEMINI_API_KEY not set — using deterministic Lastenheft fallback")
        return fallback_lastenheft(plan, company_name, primary_color)
    try:
        graph = _build_graph()
        result = await graph.ainvoke(
            {"plan": plan, "company_name": company_name, "primary_color": primary_color}
        )
        lh = result.get("lastenheft")
        if isinstance(lh, Lastenheft) and lh.chapters:
            return lh
        logger.warning("script writer returned no usable Lastenheft; using fallback")
    except Exception as exc:  # noqa: BLE001
        logger.warning("script writer graph failed (%s); using fallback", exc)
    return fallback_lastenheft(plan, company_name, primary_color)
