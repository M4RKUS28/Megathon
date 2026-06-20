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
from .schemas import AssetSpec, Block, CoursePlan, Lastenheft, SpecChapter, StyleGuide

logger = logging.getLogger(__name__)

SCRIPT_SYSTEM = """You are a senior instructional content author creating an implementation-
ready Lastenheft (specification) for a bespoke Vite/React course app. A coding agent (Devin)
will build this from scratch — every page must be self-contained and unambiguous.

Your job is to define WHAT each chapter teaches and WHICH resources it uses — NOT to lock down
the visual design. A separate implementation agent owns the layout, styling and interaction
design, and it needs deep, substantial content to build great chapters. Thin specs produce
short, poorly designed chapters, so always err on the side of MORE and RICHER content.

The spec describes *behaviour and intent* — NOT a rigid renderer schema. Be specific enough
that Devin can implement each interaction without follow-up questions.

Content rules:
- The course must NEVER be plain text. Back every idea with concrete substance: explanations,
  examples, scenarios, media or interactions. Be thorough and specific to the company/audience.
- ONE main idea per page (the "1-thought rule"): if a page would cover several concepts, split
  it into more pages. Keep each page focused and "snackable" — short paragraphs, bullet lists,
  bolded key terms, and info `callout`s instead of walls of text. Aim to convey ~30% of a point
  through a visual/interaction rather than prose.
- Split EVERY chapter into as many pages as the topic genuinely needs to be taught well
  (typically 4+; never cram a chapter onto one page, and never put the quiz inside a content
  page). Each `page` is one digestible step (e.g. "Introduction", "Key concepts", "Examples",
  "Apply it", "Common pitfalls", "Recap") with a short, descriptive `title`.
- Give each page as many blocks as the content warrants — do not artificially limit the count.
  Write real, fleshed-out copy in `text`/`items`, not placeholders or one-liners.
- Use a rich, varied mix of block `type`s, and feel free to be FORMALLY INVENTIVE — the
  renderer is deliberately open, so different pages should genuinely look different. The
  following are SUGGESTIONS, not a closed list — you may use any of them, combine them, or
  introduce your own custom types when they express the content better: heading, paragraph,
  list, callout, image, video, audio, conversation (two characters talking — see below),
  chart (Chart.js), flashcards, dragdrop, hotspot, timeline, accordion, scenario (branching).
  Favour visualisations and character-driven conversations over plain prose.
- Turn numbers, processes and comparisons into a `chart`, `timeline` or infographic — never
  leave data trapped in prose.

Conversation / character scenes (use these A LOT):
- For behavioural, soft-skill, communication, compliance, ethics or any "how should I act"
  topic, teach through a `conversation` block: two people talking, one on the left and one on
  the right, with speech bubbles the learner clicks through one at a time while each line is
  read aloud. Concrete dialogue between believable people is far more memorable than rules in
  a bullet list, so prefer it whenever the content is about behaviour or interaction.
- `conversation` data shape:
    "data": {
      "personas": [
        {"id": "anna", "name": "Anna", "role": "Team Lead", "side": "left",  "avatar": "f-2"},
        {"id": "max",  "name": "Max",  "role": "New hire",  "side": "right", "avatar": "m-5"}
      ],
      "turns": [
        {"persona": "anna", "text": "Hi Max, do you have a minute?", "audio": "/resources/audio/NN"},
        {"persona": "max",  "text": "Sure, what's up?",              "audio": "/resources/audio/NN"}
      ]
    }
  Give exactly two personas (one side="left", one side="right") with realistic name + role.
  `avatar` is a short STABLE key for the cartoon-avatar library — use "f-1".."f-8" for female-
  presenting and "m-1".."m-8" for male-presenting characters; reuse the SAME key for a persona
  every time so the face stays consistent. Write 4-8 natural spoken turns that dramatise the
  lesson (a realistic situation, a small tension, the right way to handle it). EVERY turn MUST
  have a UNIQUE `audio` template link like "/resources/audio/NN" — that line is narrated per
  bubble, so write `text` as natural spoken language.
- Lean heavily on PEOPLE: use images and conversations featuring real, relatable characters
  (diverse, everyday colleagues) rather than abstract icons, especially for behavioural topics.

Resource (asset) rules:
- For every visual/media block set `asset` to a UNIQUE template link like
  "/resources/images/01", "/resources/videos/02", "/resources/audio/03". Do NOT invent URLs.
- Write authentic, specific image briefs in the block `text`. Avoid stock-photo clichés
  (no "smiling people in suits giving a thumbs-up"); prefer realistic scenes, modern abstract
  illustrations or meaningful diagrams. Keep all illustrations/icons in ONE consistent visual
  family (all flat, all outline, or all 3D — never mixed).

Audio narration rule (make the whole course listenable):
- Add an `audio` block to (almost) EVERY content page. Set its `text` to the FULL, natural
  spoken narration of that page — a friendly, plain-language read-aloud of everything on the
  page. This `text` is used directly as the text-to-speech script and is NOT shown on screen,
  so write it as spoken sentences (no markdown, no bullet symbols), typically 60-150 words.
  Give each audio block a UNIQUE `asset` link like "/resources/audio/NN".
- EXCEPTION: a page built primarily around a `conversation` block does NOT need a separate
  page-level `audio` block — each conversation turn is already narrated via its own `audio`
  link, so a page narration would double up. Skip it there.

Validation:
- Each chapter ends with ONE quiz (shown only after the last page): passing_pct=80,
  retryable=true, 3-5 multiple-choice questions with the correct answerIndex and an
  explanation. Learners must score >=80% to unlock the next chapter.

## ANTI-BORING MANDATE
Avoid generic text-heavy lessons. Prefer visual explanations, interaction, scenarios,
simulations, charts, diagrams, and concrete examples. Every topic must be supported by media
or interaction — never plain text walls. Make it engaging, specific, and real-world.

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
10. **blocks** — 2–4 implementation-ready blocks. Types: heading, paragraph, list, callout,
    image, video, audio, dialogue, chart (Chart.js), flashcards, dragdrop, hotspot, timeline,
    accordion, scenario. For every visual/media block set `asset` to a UNIQUE template link
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
    lines.append("Chapters:")
    for c in plan.chapters:
        kp = "; ".join(c.key_points)
        lines.append(
            f"- [{c.id}] {c.title} (Bloom: {c.bloom_level}, ~{c.estimated_minutes} min)\n"
            f"  Objective: {c.objective}\n"
            f"  Key points: {kp}"
        )
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


# Distinct TTS voices for the two sides of a conversation so the speakers sound
# different. `None` on the left means "use the configured default voice".
_LEFT_VOICE: str | None = None
_RIGHT_VOICE: str | None = "Puck"


def _conversation_audio_specs(block: Block, chapter_title: str) -> list[AssetSpec]:
    """One narrated audio asset per conversation/dialogue turn (per-bubble TTS),
    voiced by the speaking persona's side so left/right sound distinct."""
    data = block.data or {}
    side_by_id: dict[str, str] = {}
    for p in data.get("personas") or []:
        if isinstance(p, dict) and p.get("id"):
            side_by_id[str(p["id"])] = str(p.get("side") or "left").lower()
    specs: list[AssetSpec] = []
    for turn in data.get("turns") or []:
        if not isinstance(turn, dict):
            continue
        link = turn.get("audio")
        text = (turn.get("text") or "").strip()
        if not link or not text:
            continue
        pid = str(turn.get("persona") or turn.get("speaker") or "")
        side = side_by_id.get(pid, "left")
        specs.append(
            AssetSpec(
                template_link=str(link),
                type="audio",
                description=text,
                purpose=f"conversation line in chapter '{chapter_title}'",
                voice=_RIGHT_VOICE if side == "right" else _LEFT_VOICE,
            )
        )
    return specs


def _build_manifest(state: _State) -> _State:
    """Collect every referenced asset into the isolated manifest (dedup by link).

    Sources (in priority order):
    1. Per-page `asset_needs` (richest descriptions, preferred).
    2. Block-level `asset` links (fallback for any the LLM missed in asset_needs).
    Besides direct block `asset` links, this walks conversation/dialogue turns so
    each speech bubble gets its own narrated audio asset (per-bubble Server-TTS).
    """
    manifest: dict[str, AssetSpec] = {}

    def add(spec: AssetSpec) -> None:
        if spec.template_link and spec.template_link not in manifest:
            manifest[spec.template_link] = spec

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
                if link:
                    atype = block.type if block.type in {"image", "video", "audio"} else "image"
                    if block.type == "chart":
                        atype = "diagram"
                    desc = (block.text or ch.title or "Course asset").strip()
                    add(
                        AssetSpec(
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
                    )
                if block.type in {"conversation", "dialogue"}:
                    for spec in _conversation_audio_specs(block, ch.title):
                        add(spec)
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
