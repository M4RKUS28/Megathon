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

from .fallback import fallback_chapter, fallback_lastenheft
from .llm import gemini_available, get_chat_model
from .schemas import AssetSpec, CoursePlan, Lastenheft, PlanChapter, SpecChapter

logger = logging.getLogger(__name__)

# Generate one chapter per LLM call: deeply nested "all chapters at once"
# structured output is unreliable on Gemini (it intermittently returns chapters
# with empty `pages`) and forces the model to ration tokens, yielding thin,
# one-sentence content. A focused per-chapter call produces substantial,
# reliable pages.
SCRIPT_SYSTEM = """You are a senior interactive learning designer. Turn ONE chapter of an
approved course plan into an implementation-ready chapter for a Vite/React course app.

The chapter must actually TEACH the topic in depth for real learners — not merely outline it.

Structure:
- Split the chapter into 3-5 `pages`. Each `page` is one digestible screen the learner steps
  through one at a time (e.g. "Introduction", "Key concepts", "Worked example", "Apply it",
  "Recap"). NEVER put the whole chapter on one page, and never put the quiz inside a content page.
- Give each page a short, descriptive `title` and 2-4 blocks.

Content depth (CRITICAL — do not skip):
- Every page MUST include at least one substantial `paragraph` block of 70-150 words of concrete,
  specific teaching text: real explanations, definitions, examples, numbers, names, regulations or
  step-by-step detail relevant to THIS exact topic. Never write one-sentence filler or generic
  placeholders like "This chapter introduces X".
- Across the chapter, write several paragraphs of genuine instructional content, so a learner who
  read only the prose would still understand the topic. Lists, callouts and interactions SUPPLEMENT
  the prose — they never replace it.

Interactions & media (the course must never be plain text):
- Use a rich mix of block types across the pages: heading, paragraph, list, callout, image, video,
  audio, dialogue (speech-bubble conversation), chart (Chart.js), flashcards, dragdrop, hotspot,
  timeline, accordion, scenario (branching). Favour visualisations and conversations.
- For every visual/media block set `asset` to a UNIQUE template link like "/resources/images/01",
  "/resources/videos/02", "/resources/audio/03". Do NOT invent real URLs.
- Describe interactions precisely via the `data` field so a coding agent can implement them without
  questions (chart: chartType/labels/datasets; dragdrop: pairs; dialogue: turns; scenario: branches;
  flashcards: cards; timeline: events; accordion: sections). Dialogue/scenario text must be
  substantive, not one-liners.

Quiz:
- End the chapter with ONE quiz (shown only after the last page): passing_pct=80, retryable=true,
  3-5 multiple-choice questions, each with the correct `answerIndex` and a one-sentence explanation.
  Learners must score >=80% to unlock the next chapter.

Return a single structured chapter object for the requested chapter only."""

# A chapter is acceptable only if it has real, multi-page content. Below this we
# retry once, then fall back to deterministic pages so `pages` is never empty.
_MIN_PAGES = 2
_MIN_CONTENT_CHARS = 600


class _State(TypedDict, total=False):
    plan: CoursePlan
    company_name: str
    primary_color: str
    chapters: list[SpecChapter]
    asset_manifest: list[AssetSpec]
    lastenheft: Lastenheft


def _course_context(plan: CoursePlan) -> str:
    lines = [
        f"Course title: {plan.title}",
        f"Audience: {plan.audience}",
        f"Language: {plan.language}",
    ]
    if plan.description:
        lines.append(f"Course description: {plan.description}")
    if plan.objectives:
        lines.append("Course objectives:\n" + "\n".join(f"- {o}" for o in plan.objectives))
    if plan.compliance_requirements:
        lines.append(
            "Compliance requirements:\n"
            + "\n".join(f"- {c}" for c in plan.compliance_requirements)
        )
    sources = [k.summary for k in plan.knowledge_sources if k.summary]
    if sources:
        lines.append("Company knowledge to weave in:\n" + "\n".join(f"- {s}" for s in sources))
    return "\n".join(lines)


def _chapter_brief(plan: CoursePlan, ch: PlanChapter, idx: int) -> str:
    key_points = "\n".join(f"- {k}" for k in ch.key_points) or "- (none provided)"
    return (
        f"{_course_context(plan)}\n\n"
        f"Design chapter {idx + 1} of {len(plan.chapters)} ONLY:\n"
        f"Chapter id: {ch.id}\n"
        f"Chapter title: {ch.title}\n"
        f"Learning objective: {ch.objective}\n"
        f"Target Bloom level: {ch.bloom_level}\n"
        f"Approximate length: {ch.estimated_minutes} minutes\n"
        f"Key points to cover:\n{key_points}"
    )


def _data_text_len(obj) -> int:
    if isinstance(obj, str):
        return len(obj)
    if isinstance(obj, dict):
        return sum(_data_text_len(v) for v in obj.values())
    if isinstance(obj, list):
        return sum(_data_text_len(v) for v in obj)
    return 0


def _content_chars(ch: SpecChapter) -> int:
    total = 0
    for page in ch.pages:
        for block in page.blocks:
            total += len(block.text or "")
            if block.items:
                total += sum(len(i) for i in block.items)
            if isinstance(block.data, dict):
                total += _data_text_len(block.data)
    return total


def _has_pages(ch: SpecChapter) -> bool:
    return len(ch.pages) >= _MIN_PAGES and any(p.blocks for p in ch.pages)


def _is_rich(ch: SpecChapter) -> bool:
    return _has_pages(ch) and _content_chars(ch) >= _MIN_CONTENT_CHARS


async def _design_one_chapter(
    model, plan: CoursePlan, ch: PlanChapter, idx: int, company_name: str
) -> SpecChapter:
    """Generate one rich chapter, retrying once; never returns empty pages."""
    brief = _chapter_brief(plan, ch, idx)
    best: SpecChapter | None = None
    for attempt in range(2):
        try:
            out: SpecChapter = await model.ainvoke(
                [("system", SCRIPT_SYSTEM), ("user", brief)]
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("chapter %s attempt %d failed (%s)", ch.id, attempt + 1, exc)
            continue
        # Keep identity tied to the approved plan (progress tracking by id).
        out.id = ch.id
        out.title = ch.title or out.title
        out.objective = out.objective or ch.objective
        if _is_rich(out):
            return out
        if best is None or _content_chars(out) > _content_chars(best):
            best = out
    if best is not None and _has_pages(best):
        logger.info("chapter %s: accepting model pages below rich threshold", ch.id)
        return best
    logger.warning("chapter %s: model pages empty/unusable — using deterministic pages", ch.id)
    chapter, _assets = fallback_chapter(ch, idx, company_name)
    return chapter


async def _design_interactions(state: _State) -> _State:
    plan = state["plan"]
    company_name = state.get("company_name", "Coursive")
    model = get_chat_model(temperature=0.5, max_output_tokens=8192).with_structured_output(
        SpecChapter
    )
    sem = asyncio.Semaphore(4)

    async def _one(idx: int, ch: PlanChapter) -> SpecChapter:
        async with sem:
            return await _design_one_chapter(model, plan, ch, idx, company_name)

    chapters = await asyncio.gather(
        *(_one(i, c) for i, c in enumerate(plan.chapters))
    )
    chapters = [c for c in chapters if c is not None]
    if not chapters:
        raise RuntimeError("script writer produced no chapters")
    return {"chapters": list(chapters)}


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
