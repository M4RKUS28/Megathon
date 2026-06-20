"""Phase 2 — Course Script Writer.

A LangGraph state graph that turns the *approved* Course Plan into a full
Lastenheft (interactive spec) plus an isolated asset manifest:

    design_interactions -> validate_and_enrich -> build_manifest -> assemble

`design_interactions` generates chapters one-at-a-time for higher quality and
variety. `validate_and_enrich` checks content depth, interaction variety, and
dialogue limits — re-prompting the LLM if quality is insufficient.
`build_manifest` collects every asset the spec references into the isolated
manifest (template_link + specs only — no asset is fetched in this phase).

Falls back to the deterministic Lastenheft generator when Gemini is unavailable.
"""

from __future__ import annotations

import json
import logging
from typing import TypedDict

from pydantic import BaseModel, Field

from .fallback import fallback_lastenheft
from .llm import gemini_available, get_chat_model
from .schemas import AssetSpec, Block, CoursePlan, Lastenheft, PlanChapter, SpecChapter

logger = logging.getLogger(__name__)

# Interactive block types used for variety tracking.
INTERACTION_TYPES = frozenset(
    {
        "flashcards",
        "dragdrop",
        "hotspot",
        "timeline",
        "accordion",
        "scenario",
        "chart",
        "conversation",
        "dialogue",
    }
)

SCRIPT_SYSTEM = """You are a senior instructional content author. Turn the approved course plan
into a rich, implementation-ready Lastenheft for a Vite/React course app.

Your job is to define WHAT each chapter teaches and WHICH resources it uses — NOT to lock down
the visual design. A separate implementation agent owns the layout, styling and interaction
design, and it needs deep, substantial content to build great chapters. Thin specs produce
short, poorly designed chapters, so always err on the side of MORE and RICHER content.

## Content depth rules

- The course must NEVER be plain text. Back every idea with concrete substance: explanations,
  context, real-world examples, scenarios, media or interactions. Be thorough and specific to
  the company/audience.
- ONE main idea per page — but EXPLORE that idea in depth. A page about "What is X" should
  include: a clear definition, WHY it matters, a concrete real-world example or case study,
  and a "watch out" or common misconception. If the idea is complex, use multiple paragraphs,
  lists, and callouts to build a complete explanation.
- Each page MUST have 4-8 blocks and 150-400 words of actual on-screen content. A page with
  only 1-2 sentences is a FAILURE — go deeper. Use short paragraphs, bullet lists, bolded key
  terms, and `callout` blocks to keep it scannable. "Scannable" means well-structured, NOT
  brief.
- Split EVERY chapter into at least 5 pages (complex topics need more; never cram a chapter
  into fewer than 5 pages, and never put the quiz inside a content page). Follow a teaching
  arc: "Introduction" → "Core concept" → "Deep dive / How it works" → "Real-world example"
  → "Common pitfalls" → "Practice / Apply it" → "Recap".
- Give each page as many blocks as the content warrants — do not artificially limit the count.
  Write real, fleshed-out copy in `text`/`items`, not placeholders or one-liners.

## Interaction & block type rules

- Use a rich, VARIED mix of block `type`s, and feel free to be FORMALLY INVENTIVE — the
  renderer is deliberately open, so different pages should genuinely look different. Available
  types (you may combine or invent your own): heading, paragraph, list, callout, image, video,
  audio, conversation (two characters talking — see below), chart (Chart.js), flashcards,
  dragdrop, hotspot, timeline, accordion, scenario (branching decision).
- VARIETY IS MANDATORY:
  • Each chapter must use a DIFFERENT primary interaction type from the previous chapter. If
    chapter N uses flashcards as its main interaction, chapter N+1 must use a different one
    (scenario, hotspot, timeline, dragdrop, accordion, etc.).
  • Across the entire course, use at least 4 distinct interactive block types.
  • Never repeat the exact same page structure (e.g. paragraph → list → flashcards) in more
    than one chapter. Vary the order, combination, and placement of blocks.
  • Mix the placement: some pages should LEAD with an interaction, others should build up
    to one. Surprise the learner.
- Prioritise interactions where the learner DOES something: scenario branches (choose a
  path and see consequences), hotspot explorations (click to reveal), drag-and-drop matching,
  accordion reveals, and flashcard self-checks. These are more engaging than passive reading.

## Conversation / character scenes (use SPARINGLY)

- Conversations are for behavioural, soft-skill, communication, compliance, ethics or any
  "how should I act" topic ONLY. Do NOT use conversations as a primary content format.
  Use at most ONE conversation block per chapter, and only when the plan marks the chapter
  as `dialogue_appropriate=true` or the topic genuinely involves interpersonal behaviour.
- `conversation` data shape:
    "data": {
      "personas": [
        {"id": "anna", "name": "Anna", "role": "Team Lead", "side": "left",  "avatar": "f-2"},
        {"id": "max",  "name": "Max",  "role": "New hire",  "side": "right", "avatar": "m-5"}
      ],
      "turns": [
        {"persona": "anna", "text": "Hi Max, do you have a minute?",
         "audio": "/resources/audio/NN"},
        {"persona": "max", "text": "Sure, what's up?",
         "audio": "/resources/audio/NN"}
      ]
    }
  Give exactly two personas (one side="left", one side="right") with realistic name + role.
  `avatar` is a short STABLE key for the cartoon-avatar library — use "f-1".."f-8" for female-
  presenting and "m-1".."m-8" for male-presenting characters; reuse the SAME key for a persona
  every time so the face stays consistent. Write 4-8 natural spoken turns that dramatise the
  lesson. EVERY turn MUST have a UNIQUE `audio` template link.
- Most content should be direct instruction, guided examples, and hands-on interactions —
  NOT conversations between people.

## Data visualisation rules

- When the content involves real quantitative data, sequential processes, or structured
  comparisons, present them as a `chart`, `timeline`, or infographic for clarity.
- Do NOT force a chart or timeline when the topic is qualitative or conceptual. A well-
  written paragraph, callout, or scenario is better than a chart with fabricated data.
  Only use charts when the data is REAL and meaningful, or the plan marks the chapter
  as `chart_appropriate=true`.

## Minigames

Minigames (gamify practice — include at least ONE `minigame` per chapter, ideally on the
"Apply it"/practice or "Recap" pages):
- A `minigame` block turns practice into play: the renderer scores the learner and gives
  instant feedback. Choose the `data.game` kind that best fits the content (you may also invent
  your own kind — then put everything the implementer needs into `data`):
    quiz   -> {"game": "quiz", "prompt": "..", "questions": [
                {"question": "..", "options": ["..", ".."], "answerIndex": 0, "explanation": ".."}]}
    order  -> {"game": "order", "prompt": "..", "steps": ["first", "second", "third"]}
               (list the steps in the CORRECT order; the game shuffles them for the learner)
    sort   -> {"game": "sort", "prompt": "..", "categories": ["A", "B"],
                "items": [{"text": "..", "category": "A"}]}
    memory -> {"game": "memory", "prompt": "..", "pairs": [{"a": "term", "b": "definition"}]}
- Make minigames meaningful — test real understanding, not trivia — and keep them short
  (3-6 questions/items/steps/pairs). Prefer a different game kind from the chapter-end quiz.

## Resource (asset) rules


- For every visual/media block set `asset` to a UNIQUE template link like
  "/resources/images/01", "/resources/videos/02", "/resources/audio/03". Do NOT invent URLs.
- Write authentic, specific image briefs in the block `text`. Avoid stock-photo clichés
  (no "smiling people in suits giving a thumbs-up"); prefer realistic scenes, modern abstract
  illustrations or meaningful diagrams. Keep all illustrations/icons in ONE consistent visual
  family (all flat, all outline, or all 3D — never mixed).

## Audio narration

- Add an `audio` block to EVERY content page. Set its `text` to the FULL, natural spoken
  narration of that page — a friendly, plain-language read-aloud of everything on the page.
  This `text` is used directly as the text-to-speech script and is available to the
  learner through a transcript/info button, so write it as spoken sentences (no markdown,
  no bullet symbols), typically 80-200 words.
  Give each audio block a UNIQUE `asset` link like "/resources/audio/NN".
- Do NOT put essential teaching content only into audio narration. Every concrete method,
  step, option, example or checklist item mentioned by an audio block must also be present
  in visible page blocks (`paragraph`, `list`, interactions or structured `data`). For example,
  a heading like "Git Installation Methods" must be followed by visible methods, not just an
  audio summary that names them.
- EXCEPTION: a page built primarily around a `conversation` block does NOT need a separate
  page-level `audio` block — each conversation turn is already narrated via its own `audio`
  link, so a page narration would double up. Skip it there.

## Quiz rules

- Each chapter ends with ONE quiz (shown only after the last page): passing_pct=80,
  retryable=true, 3-5 multiple-choice questions with the correct answerIndex and an
  explanation. Learners must score >=80% to unlock the next chapter.
- Quiz questions should test UNDERSTANDING, not memorisation. Include scenario-based
  questions ("What would you do if...") alongside knowledge-check questions.

Return structured output: a list of chapters covering EVERY chapter in the plan, in order."""


class _SingleChapterOut(BaseModel):
    chapters: list[SpecChapter] = Field(default_factory=list)


class _ChaptersOut(BaseModel):
    chapters: list[SpecChapter] = Field(default_factory=list)


class _State(TypedDict, total=False):
    plan: CoursePlan
    company_name: str
    primary_color: str
    chapters: list[SpecChapter]
    asset_manifest: list[AssetSpec]
    lastenheft: Lastenheft
    validation_issues: list[str]
    enrichment_attempts: int


def _plan_text(plan: CoursePlan) -> str:
    lines = [
        f"Title: {plan.title}",
        f"Audience: {plan.audience}",
        f"Language: {plan.language}",
        f"Primary format: {plan.primary_format}",
        f"Content density: {plan.content_density}",
    ]
    if plan.style_notes:
        lines.append("Style notes:\n" + "\n".join(f"- {s}" for s in plan.style_notes))
    if plan.objectives:
        lines.append("Objectives:\n" + "\n".join(f"- {o}" for o in plan.objectives))
    if plan.compliance_requirements:
        lines.append(
            "Compliance:\n" + "\n".join(f"- {c}" for c in plan.compliance_requirements)
        )
    lines.append("Chapters:")
    for c in plan.chapters:
        kp = "; ".join(c.key_points)
        parts = [f"- [{c.id}] {c.title} — {c.objective} (key points: {kp})"]
        if c.subtopics:
            parts.append(f"  Subtopics: {'; '.join(c.subtopics)}")
        parts.append(f"  Min pages: {c.min_pages} | Depth: {c.depth}")
        if c.suggested_interactions:
            parts.append(f"  Suggested interactions: {', '.join(c.suggested_interactions)}")
        parts.append(
            f"  Dialogue appropriate: {c.dialogue_appropriate} | "
            f"Chart appropriate: {c.chart_appropriate}"
        )
        lines.append("\n".join(parts))
    return "\n".join(lines)


def _single_chapter_prompt(
    plan: CoursePlan,
    chapter: PlanChapter,
    index: int,
    prior_types: list[str],
) -> str:
    """Build a focused prompt for generating a single chapter."""
    lines = [_plan_text(plan)]
    lines.append(f"\n--- GENERATE ONLY chapter {index + 1}: '{chapter.title}' ---")
    lines.append(f"Objective: {chapter.objective}")
    lines.append(f"Key points: {'; '.join(chapter.key_points)}")
    if chapter.subtopics:
        lines.append(f"Subtopics to cover: {'; '.join(chapter.subtopics)}")
    lines.append(f"Minimum pages: {chapter.min_pages}")
    lines.append(f"Depth: {chapter.depth}")
    if chapter.suggested_interactions:
        lines.append(
            f"Suggested interaction types for this chapter: "
            f"{', '.join(chapter.suggested_interactions)}"
        )
    lines.append(f"Dialogue appropriate: {chapter.dialogue_appropriate}")
    lines.append(f"Chart appropriate: {chapter.chart_appropriate}")
    if prior_types:
        lines.append(
            f"\nInteraction types already used in previous chapters: "
            f"{', '.join(sorted(set(prior_types)))}. "
            f"Use DIFFERENT types for this chapter to ensure variety."
        )
    lines.append(
        "\nReturn a `chapters` list containing exactly ONE chapter (this one)."
    )
    return "\n".join(lines)


async def _design_interactions(state: _State) -> _State:
    """Generate chapters one-at-a-time for higher quality and variety."""
    plan = state["plan"]
    model = get_chat_model(temperature=0.5).with_structured_output(_SingleChapterOut)
    all_chapters: list[SpecChapter] = []
    prior_interaction_types: list[str] = []

    for i, plan_ch in enumerate(plan.chapters):
        ch_prompt = _single_chapter_prompt(plan, plan_ch, i, prior_interaction_types)
        out: _SingleChapterOut = await model.ainvoke(
            [("system", SCRIPT_SYSTEM), ("user", ch_prompt)]
        )
        chapters = out.chapters or []
        if not chapters:
            raise RuntimeError(
                f"script writer produced no output for chapter '{plan_ch.title}'"
            )
        chapter = chapters[0]
        all_chapters.append(chapter)

        for page in chapter.pages:
            for block in page.blocks:
                if block.type in INTERACTION_TYPES:
                    prior_interaction_types.append(block.type)

    if not all_chapters:
        raise RuntimeError("script writer produced no chapters")
    return {"chapters": all_chapters}


# ── Quality thresholds ────────────────────────────────────────────────────────

QUALITY_THRESHOLDS = {
    "min_pages_per_chapter": 5,
    "min_blocks_per_page": 3,
    "min_words_per_page": 80,
    "min_interaction_types": 3,
    "max_dialogue_per_chapter": 1,
}


def _validate_and_enrich(state: _State) -> _State:
    """Check content quality and flag issues for the conditional edge."""
    chapters = state["chapters"]
    issues: list[str] = []

    for ch in chapters:
        if len(ch.pages) < QUALITY_THRESHOLDS["min_pages_per_chapter"]:
            issues.append(
                f"Chapter '{ch.title}': {len(ch.pages)} pages "
                f"(need {QUALITY_THRESHOLDS['min_pages_per_chapter']}+)"
            )
        dialogue_count = sum(
            1
            for p in ch.pages
            for b in p.blocks
            if b.type in {"conversation", "dialogue"}
        )
        if dialogue_count > QUALITY_THRESHOLDS["max_dialogue_per_chapter"]:
            issues.append(
                f"Chapter '{ch.title}': {dialogue_count} dialogue/conversation blocks "
                f"(max {QUALITY_THRESHOLDS['max_dialogue_per_chapter']})"
            )
        for page in ch.pages:
            non_audio = [b for b in page.blocks if b.type != "audio"]
            if len(non_audio) < QUALITY_THRESHOLDS["min_blocks_per_page"]:
                issues.append(
                    f"Page '{page.title}' in '{ch.title}': "
                    f"{len(non_audio)} content blocks "
                    f"(need {QUALITY_THRESHOLDS['min_blocks_per_page']}+)"
                )
            words = sum(
                len((b.text or "").split())
                for b in page.blocks
                if b.type != "audio"
            )
            if words < QUALITY_THRESHOLDS["min_words_per_page"]:
                issues.append(
                    f"Page '{page.title}' in '{ch.title}': ~{words} words "
                    f"(need {QUALITY_THRESHOLDS['min_words_per_page']}+)"
                )

    interaction_types = {
        b.type
        for ch in chapters
        for p in ch.pages
        for b in p.blocks
        if b.type in INTERACTION_TYPES
    }
    if len(interaction_types) < QUALITY_THRESHOLDS["min_interaction_types"]:
        issues.append(
            f"Only {len(interaction_types)} interaction type(s) used "
            f"(need {QUALITY_THRESHOLDS['min_interaction_types']}+): "
            f"{sorted(interaction_types)}"
        )

    return {
        "validation_issues": issues,
        "enrichment_attempts": state.get("enrichment_attempts", 0),
    }


def _should_enrich(state: _State) -> str:
    """Conditional edge: enrich if issues exist and attempts < 2."""
    if state.get("validation_issues") and state.get("enrichment_attempts", 0) < 2:
        return "enrich"
    return "proceed"


async def _enrich_thin_content(state: _State) -> _State:
    """Re-prompt LLM to fix specific quality issues."""
    issues = state.get("validation_issues", [])
    if not issues:
        return {"enrichment_attempts": state.get("enrichment_attempts", 0) + 1}

    model = get_chat_model(temperature=0.6).with_structured_output(_ChaptersOut)
    current_json = json.dumps(
        [ch.model_dump() for ch in state["chapters"]], indent=2
    )
    # Truncate if very large to stay within context window.
    if len(current_json) > 12000:
        current_json = current_json[:12000] + "\n... (truncated)"

    fix_prompt = (
        "Here is the current course spec (as JSON):\n"
        + current_json
        + "\n\nThe following quality issues were found:\n"
        + "\n".join(f"- {i}" for i in issues)
        + "\n\nFix ALL issues: add more pages where needed, write deeper content, "
        "vary interaction types across chapters, reduce dialogue/conversation blocks "
        "to max 1 per chapter. Return the COMPLETE fixed chapter list."
    )
    try:
        out: _ChaptersOut = await model.ainvoke(
            [("system", SCRIPT_SYSTEM), ("user", fix_prompt)]
        )
        if out.chapters:
            logger.info(
                "enrichment pass produced %d chapters (attempt %d)",
                len(out.chapters),
                state.get("enrichment_attempts", 0) + 1,
            )
            return {
                "chapters": out.chapters,
                "enrichment_attempts": state.get("enrichment_attempts", 0) + 1,
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("enrichment call failed (%s); keeping current chapters", exc)

    return {"enrichment_attempts": state.get("enrichment_attempts", 0) + 1}


# ── Conversation audio helpers ────────────────────────────────────────────────

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

    Besides direct block `asset` links, this walks conversation/dialogue turns so
    each speech bubble gets its own narrated audio asset (per-bubble Server-TTS).
    """
    manifest: dict[str, AssetSpec] = {}

    def add(spec: AssetSpec) -> None:
        if spec.template_link and spec.template_link not in manifest:
            manifest[spec.template_link] = spec

    for ch in state["chapters"]:
        for page in ch.pages:
            for block in page.blocks:
                link = block.asset
                if link:
                    atype = block.type if block.type in {"image", "video", "audio"} else "image"
                    if block.type == "chart":
                        atype = "diagram"
                    add(
                        AssetSpec(
                            template_link=link,
                            type=atype,
                            dimensions="16:9",
                            description=(block.text or ch.title or "Course asset").strip(),
                            purpose=f"{block.type} in chapter '{ch.title}'",
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
        )
    }


def _build_graph():
    from langgraph.graph import END, START, StateGraph

    g = StateGraph(_State)
    g.add_node("design_interactions", _design_interactions)
    g.add_node("validate_and_enrich", _validate_and_enrich)
    g.add_node("enrich_thin_content", _enrich_thin_content)
    g.add_node("build_manifest", _build_manifest)
    g.add_node("assemble", _assemble)

    g.add_edge(START, "design_interactions")
    g.add_edge("design_interactions", "validate_and_enrich")
    g.add_conditional_edges(
        "validate_and_enrich",
        _should_enrich,
        {"enrich": "enrich_thin_content", "proceed": "build_manifest"},
    )
    g.add_edge("enrich_thin_content", "validate_and_enrich")
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
