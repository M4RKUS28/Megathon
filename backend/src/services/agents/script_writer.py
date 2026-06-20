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

import asyncio
import logging
from typing import TypedDict

from langchain_core.messages import AIMessage
from langchain_core.output_parsers import PydanticOutputParser

from .fallback import fallback_lastenheft
from .llm import gemini_available, get_chat_model
from .schemas import (
    AssetSpec,
    CoursePlan,
    Lastenheft,
    PlanChapter,
    SpecChapter,
    StyleGuide,
)

logger = logging.getLogger(__name__)

# Gemini's function-calling structured output silently returns empty nested
# arrays for this deeply nested schema (pages/blocks/asset_needs/quiz come back
# []). We instead prompt for raw JSON and parse it, which populates reliably.
_CHAPTER_PARSER = PydanticOutputParser(pydantic_object=SpecChapter)

SCRIPT_SYSTEM = """You are a senior interactive learning designer creating an implementation-
ready Lastenheft (specification) for a bespoke Vite/React course app. A coding agent (Devin)
will build this from scratch — every page must be self-contained and unambiguous.

The spec describes *behaviour and intent* — NOT a rigid renderer schema. Be specific enough
that Devin can implement each interaction without follow-up questions.

## ANTI-BORING MANDATE
Write substantive, in-depth lessons that are STILL engaging. Every page must teach with rich,
specific explanatory prose AND be supported by media or interaction — never thin filler, but
also never a single undifferentiated wall of text. Use concrete examples, real data, scenarios,
charts, and diagrams to carry the depth. Make it specific and real-world.

## PROSE DEPTH (required)
Every content page must contain AT LEAST 500 words of explanatory prose, split across MULTIPLE
`paragraph` blocks (typically 2–4 paragraphs of ~150–250 words each) — never one giant block.
Break the prose up with `heading`/`callout`/`list` blocks and interactions so it reads as a
well-structured lesson, not a wall of text. The 500-word minimum is the body copy a learner
reads on that page; interactions, quizzes, and asset briefs do NOT count toward it.

Chapter-level fields (populate for EVERY chapter):
  - `learning_points`: concrete things the learner will know/be able to do after this chapter.
  - `estimated_minutes`: realistic time budget.
  - `competency`: the competency this chapter targets.
  - `bloom_level`: Bloom's taxonomy level (remember/understand/apply/analyze/evaluate/create).

## PAGE STRUCTURE
Split EVERY chapter into 3–5 pages. Each page is one digestible screen (e.g. "Introduction",
"Key concepts", "Apply it", "Recap"). NEVER put a whole chapter on one page, and never put
the quiz inside a content page.

For EACH page provide ALL of these fields:

1. **learning_goal** — One clear sentence: what the learner can do after this page.
2. **content_goals** — 2–4 bullet points of concrete, non-generic topics/facts to cover.
   Use real data, real scenarios, real terminology. No “understand X” platitudes.
3. **learner_action** — What the learner DOES (e.g. "reads a scenario and picks a branch",
   "drags terms to definitions", "watches a worked example then answers reflection").
4. **ui_treatment** — Expected visual layout (e.g. "hero image top, two-column text + diagram
   below", "full-width interactive chart with annotation callouts", "speech-bubble dialogue
   with avatar").
5. **worked_example** — A CONCRETE scenario. Name people, give numbers, describe the situation.
   Never say "for example, a situation". Instead: "Maria in the warehouse notices a leaking
   drum near aisle 7. She checks the SDS, notifies the supervisor, and cordons the area."
6. **recommended_interaction** — Which block type(s) best serve this page’s goal. Pick from:
   dialogue, chart, flashcards, dragdrop, hotspot, timeline, accordion, scenario, image,
   video, audio. Explain WHY this interaction fits.
7. **required_behavior** — What the React component MUST do (e.g. "Drag-drop locks after
   correct match; incorrect items bounce back with shake animation; completion unlocks Next").
8. **feedback_behavior** — How the page responds to learner input (e.g. "Correct: green check +
   explanation. Wrong: orange highlight + hint. After 2 wrong: show answer.").
9. **success_criterion** — Observable condition proving this page works (e.g. "learner reorders
   all 5 steps correctly; chart renders with live data; scenario reaches at least one ending").
10. **blocks** — implementation-ready blocks. Types: heading, paragraph, list, callout,
    image, video, audio, dialogue, chart (Chart.js), flashcards, dragdrop, hotspot, timeline,
    accordion, scenario. Each page needs MULTIPLE `paragraph` blocks carrying ≥500 words of
    prose total (see PROSE DEPTH), interleaved with at least one heading and at least one
    interaction/media block. For every visual/media block set `asset` to a UNIQUE template link
    ("/resources/images/01", "/resources/videos/02", etc.). Describe interactions precisely
    in the `data` field so Devin can implement without questions.
11. **asset_needs** — List every asset this page needs. Each entry: template_link, type
    (image/video/audio/diagram), and a detailed visual/audio brief.

## ASSESSMENT (per chapter, SEPARATE from explanation)
Each chapter ends with ONE quiz (shown only after the last content page).
Also provide `assessment_requirements` on each chapter:
- **tested_goals**: Which learning goals from the chapter pages this quiz tests.
- **question_types**: e.g. ["multiple-choice", "ordering", "true-false"].
- **misconceptions_to_probe**: Common wrong beliefs the quiz should expose.
- **minimum_questions**: At least 3, ideally 5.
- **passing_pct**: 80.
- **feedback_on_wrong**: How wrong answers are handled (e.g. "Show correct answer +
  one-sentence explanation referencing the relevant page").

Quiz rules:
- passing_pct=80, retryable=true, 3–5 multiple-choice questions.
- Each question has the correct answerIndex and an explanation.
- Questions must test APPLICATION, not recall. Use scenarios in questions.
- Distractors must be plausible (not jokes like "office snacks" or "parking").

Return structured output: a list of chapters covering EVERY chapter in the plan, in order.
"""


class _State(TypedDict, total=False):
    plan: CoursePlan
    company_name: str
    primary_color: str
    chapters: list[SpecChapter]
    asset_manifest: list[AssetSpec]
    lastenheft: Lastenheft


def _course_context(plan: CoursePlan) -> str:
    """Course-level context shared with every per-chapter request."""
    lines = [
        f"Title: {plan.title}",
        f"Audience: {plan.audience}",
        f"Language: {plan.language}",
        f"Difficulty: {plan.difficulty}",
        f"Duration: ~{plan.estimated_minutes} min",
    ]
    if plan.objectives:
        lines.append("Objectives:\n" + "\n".join(f"- {o}" for o in plan.objectives))
    if plan.compliance_requirements:
        lines.append(
            "Compliance:\n" + "\n".join(f"- {c}" for c in plan.compliance_requirements)
        )
    if plan.mandatory_topics:
        lines.append(
            "Mandatory topics:\n" + "\n".join(f"- {t}" for t in plan.mandatory_topics)
        )
    lines.append("Full chapter outline (for context only):")
    for c in plan.chapters:
        lines.append(f"- [{c.id}] {c.title}")
    return "\n".join(lines)


def _chapter_text(plan: CoursePlan, chapter: PlanChapter) -> str:
    """Prompt for ONE chapter: course context + that chapter's full plan data."""
    kp = "; ".join(chapter.key_points)
    return (
        f"{_course_context(plan)}\n\n"
        "Design ONLY the following chapter. Return a SINGLE SpecChapter with its "
        "pages and quiz FULLY populated:\n"
        f"- id: {chapter.id}\n"
        f"- title: {chapter.title}\n"
        f"- competency: {chapter.competency}\n"
        f"- Bloom level: {chapter.bloom_level}\n"
        f"- estimated minutes: ~{chapter.estimated_minutes}\n"
        f"- objective: {chapter.objective}\n"
        f"- key points: {kp}\n\n"
        f"Produce 3-5 content pages (each with blocks and asset_needs) and a quiz "
        f"with 3-5 questions for chapter [{chapter.id}]. Every page must carry at least "
        f"500 words of explanatory prose split across multiple paragraph blocks (never one "
        f"giant block). Keep id='{chapter.id}' and title='{chapter.title}'.\n\n"
        f"{_CHAPTER_PARSER.get_format_instructions()}"
    )


def _message_text(message: AIMessage) -> str:
    """Flatten a chat message's content to text.

    Gemini 3 thinking models return ``content`` as a list of parts (text +
    thought-signature blocks); join only the text parts.
    """
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return str(content)


async def _design_one_chapter(
    model, plan: CoursePlan, chapter: PlanChapter
) -> SpecChapter:
    message = await model.ainvoke(
        [("system", SCRIPT_SYSTEM), ("user", _chapter_text(plan, chapter))]
    )
    spec: SpecChapter = _CHAPTER_PARSER.parse(_message_text(message))
    # Anchor identity to the plan so manifest/ordering stay consistent even if
    # the model echoes back blank or altered id/title fields.
    if not spec.id:
        spec.id = chapter.id
    if not spec.title:
        spec.title = chapter.title
    return spec


async def _design_interactions(state: _State) -> _State:
    plan = state["plan"]
    if not plan.chapters:
        raise RuntimeError("course plan has no chapters")
    model = get_chat_model(temperature=0.5)
    chapters = await asyncio.gather(
        *(_design_one_chapter(model, plan, ch) for ch in plan.chapters)
    )
    if not chapters:
        raise RuntimeError("script writer produced no chapters")
    return {"chapters": list(chapters)}


def _build_manifest(state: _State) -> _State:
    """Collect every referenced asset into the isolated manifest (dedup by link).

    Sources (in priority order):
    1. Per-page `asset_needs` (richest descriptions, preferred).
    2. Block-level `asset` links (fallback for any the LLM missed in asset_needs).
    """
    manifest: dict[str, AssetSpec] = {}
    for ch in state["chapters"]:
        for page in ch.pages:
            # 1. Per-page asset_needs (preferred source)
            for need in page.asset_needs:
                if need.template_link and need.template_link not in manifest:
                    manifest[need.template_link] = AssetSpec(
                        template_link=need.template_link,
                        type=need.type,
                        dimensions="16:9",
                        description=need.description,
                        purpose=f"{need.type} on page '{page.title}' in chapter '{ch.title}'",
                    )
            # 2. Block-level asset links (catch anything not in asset_needs)
            for block in page.blocks:
                link = block.asset
                if not link or link in manifest:
                    continue
                atype = block.type if block.type in {"image", "video", "audio"} else "image"
                if block.type == "chart":
                    atype = "diagram"
                desc = (block.text or ch.title or "Course asset").strip()
                manifest[link] = AssetSpec(
                    template_link=link,
                    type=atype,
                    dimensions="16:9",
                    description=desc,
                    purpose=f"{block.type} in chapter '{ch.title}'",
                    alt_text=desc[:120],
                    usage_context=(
                        f"{block.type} block on page '{page.title}'"
                        f" in chapter '{ch.title}'"
                    ),
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
