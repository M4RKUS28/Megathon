"""Course concept generation: turn a brief + style guide into a structured,
**interactive** course concept (multi-page chapters, gated quizzes, drag-and-drop,
click-to-reveal dialogues, image hotspots, flip cards, charts, and prompts for
generated images / narration / video).

Uses the real Devin API when configured; otherwise falls back to a deterministic
local generator that exercises every interactive element so the pipeline is fully
demoable offline. Media (image/audio/video) is produced later by the media pass
(`media.py`); here we only emit the *prompts* for it.
"""

import copy
import logging
from typing import Any

from src.services.devin.client import DevinClient, DevinError

logger = logging.getLogger(__name__)

# Interactive block types the renderer (courses-template) knows how to play.
BLOCK_TYPES = [
    "heading",
    "paragraph",
    "list",
    "callout",
    "code",
    "image",
    "video",
    "audio",
    "dialogue",
    "dragdrop",
    "ordering",
    "hotspot",
    "flipcards",
    "chart",
]

# JSON Schema (Draft 7) the Devin session must satisfy in structured_output.
# Chapters hold ordered *pages*; each page is a sequence of interactive blocks.
# A chapter is gated by an end-of-chapter quiz (must score >= passingScore).
CONCEPT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["title", "description", "chapters"],
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "companyName": {"type": "string"},
        "primaryColor": {"type": "string"},
        "chapters": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "title", "pages", "quiz"],
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "objective": {"type": "string"},
                    "passingScore": {"type": "integer"},
                    "pages": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["blocks"],
                            "properties": {
                                "id": {"type": "string"},
                                "title": {"type": "string"},
                                "blocks": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "required": ["type"],
                                        "properties": {
                                            "type": {"type": "string", "enum": BLOCK_TYPES},
                                            # generic text payloads
                                            "text": {"type": "string"},
                                            "items": {
                                                "type": "array",
                                                "items": {"type": "string"},
                                            },
                                            "variant": {"type": "string"},
                                            "language": {"type": "string"},
                                            "caption": {"type": "string"},
                                            "alt": {"type": "string"},
                                            "title": {"type": "string"},
                                            "instructions": {"type": "string"},
                                            # media prompts (filled in by media pass)
                                            "prompt": {"type": "string"},
                                            "say": {"type": "string"},
                                            "imagePrompt": {"type": "string"},
                                            # dialogue
                                            "speakers": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "name": {"type": "string"},
                                                        "role": {"type": "string"},
                                                        "avatarPrompt": {"type": "string"},
                                                    },
                                                },
                                            },
                                            "steps": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "speaker": {"type": "string"},
                                                        "text": {"type": "string"},
                                                    },
                                                },
                                            },
                                            # drag-and-drop matching
                                            "pairs": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "term": {"type": "string"},
                                                        "match": {"type": "string"},
                                                    },
                                                },
                                            },
                                            # image hotspots
                                            "spots": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "x": {"type": "number"},
                                                        "y": {"type": "number"},
                                                        "label": {"type": "string"},
                                                        "text": {"type": "string"},
                                                    },
                                                },
                                            },
                                            # flip cards
                                            "cards": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "front": {"type": "string"},
                                                        "back": {"type": "string"},
                                                    },
                                                },
                                            },
                                            # chart
                                            "chartType": {"type": "string"},
                                            "labels": {
                                                "type": "array",
                                                "items": {"type": "string"},
                                            },
                                            "series": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "label": {"type": "string"},
                                                        "data": {
                                                            "type": "array",
                                                            "items": {"type": "number"},
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                    "quiz": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["question", "options", "answerIndex"],
                            "properties": {
                                "question": {"type": "string"},
                                "options": {"type": "array", "items": {"type": "string"}},
                                "answerIndex": {"type": "integer"},
                                "explanation": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
    },
}


def build_concept_prompt(brief: dict, style_guide: dict, company_name: str) -> str:
    topics = ", ".join(brief.get("topics", [])) or "the subject described in the title"
    return (
        f"You are a senior instructional designer and interaction designer for "
        f"{company_name}. Produce a COMPLETE, richly INTERACTIVE training course as "
        f"structured JSON matching the provided schema. This is not an article — it is "
        f"a hands-on, multi-page, gamified learning experience.\n\n"
        f"Course title: {brief.get('title')}\n"
        f"Audience: {brief.get('audience', 'new employees')}\n"
        f"Goals: {brief.get('goals', 'onboard the audience effectively')}\n"
        f"Tone: {brief.get('tone', 'friendly, vivid, encouraging')}\n"
        f"Approximate length: {brief.get('duration', '4-6 chapters')}\n"
        f"Key topics to cover: {topics}\n\n"
        f"Brand: company '{company_name}'. Style guide: {style_guide}.\n\n"
        "STRUCTURE\n"
        "- Produce 4-6 chapters. Each chapter has an `objective` and 2-4 ordered `pages`.\n"
        "- The learner moves one page at a time; after the last page they take the "
        "chapter `quiz`. They must score >= `passingScore` (default 80) to unlock the "
        "next chapter, so write 3-5 meaningful multiple-choice questions per chapter "
        "with a correct `answerIndex` and a teaching `explanation`.\n\n"
        "MAKE IT INTERACTIVE — across the course use a rich mix of these block types "
        "(not just paragraphs). Every chapter must contain at least three DIFFERENT "
        "interactive block types from this list:\n"
        "- `dialogue`: a click-to-reveal conversation. Define 2-3 `speakers` (each with "
        "a `name`, `role`, and a vivid `avatarPrompt` for their portrait) and an ordered "
        "list of `steps` ({speaker, text}). The learner clicks to reveal each line and "
        "the next speaker.\n"
        "- `dragdrop`: drag-and-drop matching. Give `instructions` and 3-5 `pairs` "
        "({term, match}).\n"
        "- `ordering`: drag items into the correct sequence. Give `instructions` and "
        "`items` already in the CORRECT order (the renderer shuffles them).\n"
        "- `hotspot`: an explorable image. Give a detailed `imagePrompt` and 3-5 `spots` "
        "with `x`/`y` as PERCENT (0-100) positions, a short `label`, and revealed `text`.\n"
        "- `flipcards`: `cards` ({front, back}) for term/definition reveals.\n"
        "- `chart`: a data visualization (rendered with Chart.js). Set `chartType` "
        "(bar|line|pie|doughnut|radar), a `title`, `labels`, and `series` "
        "({label, data}). Use realistic illustrative numbers.\n"
        "- `image`: set a detailed `prompt` and `alt`; we generate the image.\n"
        "- `video`: set a short cinematic `prompt`; we generate a short clip.\n"
        "- `audio`: set `say` to narration text; we synthesize voiceover. Add one short "
        "narration near the start of most chapters.\n"
        "- plus `heading`, `paragraph`, `list`, `callout` (variant info|tip|warning|"
        "success), and `code` where relevant.\n\n"
        "Include at least one `image` and one `audio` block per chapter, and at least "
        "one `video`, one `dialogue`, one `dragdrop`, one `hotspot`, and one `chart` "
        "somewhere in the course. Keep media `prompt`/`say`/`imagePrompt`/`avatarPrompt` "
        "fields concise and self-contained (they are sent verbatim to media models). "
        "Do NOT put URLs anywhere — only prompts. Make all content specific, accurate, "
        "and tailored to the audience and brand; no generic filler."
    )


def _slugify(text: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in text).strip("-")[:48] or "chapter"


def _intro_chapter(company_name: str, audience: str, title: str) -> dict:
    return {
        "id": "0-welcome",
        "title": f"Welcome to {title}",
        "objective": f"Understand what this course covers and how it works at {company_name}.",
        "passingScore": 80,
        "pages": [
            {
                "title": "Your journey",
                "blocks": [
                    {"type": "heading", "text": f"Welcome, {audience}!"},
                    {
                        "type": "audio",
                        "say": (
                            f"Welcome to {title}. Over the next few chapters you'll learn by "
                            f"doing — dragging, clicking, and exploring, not just reading. "
                            f"Let's get started."
                        ),
                        "caption": "Intro narration",
                    },
                    {
                        "type": "image",
                        "prompt": (
                            f"Friendly flat-vector illustration of a diverse team at "
                            f"{company_name} starting an online training course, bright brand "
                            f"colors, clean modern style"
                        ),
                        "alt": "Team starting a course",
                    },
                    {
                        "type": "callout",
                        "variant": "tip",
                        "text": (
                            "Each chapter ends with a short quiz. Score 80% or higher to "
                            "unlock the next chapter — you can retry as many times as you like."
                        ),
                    },
                ],
            },
            {
                "title": "How you'll learn",
                "blocks": [
                    {
                        "type": "flipcards",
                        "title": "What to expect",
                        "cards": [
                            {"front": "Dialogues", "back": "Click through real conversations."},
                            {"front": "Drag & drop", "back": "Match concepts hands-on."},
                            {"front": "Explore", "back": "Click hotspots on diagrams."},
                            {"front": "Quizzes", "back": "Prove it before moving on."},
                        ],
                    },
                    {
                        "type": "dialogue",
                        "title": "Meet your guides",
                        "speakers": [
                            {
                                "name": "Maya",
                                "role": "Mentor",
                                "avatarPrompt": (
                                    "friendly woman mentor portrait, flat vector avatar, "
                                    "warm smile"
                                ),
                            },
                            {
                                "name": "Sam",
                                "role": "New hire",
                                "avatarPrompt": (
                                    "curious young man portrait, flat vector avatar, "
                                    "headphones"
                                ),
                            },
                        ],
                        "steps": [
                            {"speaker": "Maya", "text": "Hi! I'll guide you through this course."},
                            {"speaker": "Sam", "text": "Great — I learn best by doing."},
                            {
                                "speaker": "Maya",
                                "text": (
                                    "Perfect, because that's exactly how this "
                                    "works. Click Continue when you're ready."
                                ),
                            },
                        ],
                    },
                ],
            },
        ],
        "quiz": [
            {
                "question": "How do you unlock the next chapter?",
                "options": [
                    "Score at least 80% on the chapter quiz",
                    "Wait 24 hours",
                    "Email the admin",
                ],
                "answerIndex": 0,
                "explanation": "Pass the quiz with 80%+ to continue; retries are unlimited.",
            },
            {
                "question": "What makes this course interactive?",
                "options": [
                    "Dialogues, drag-and-drop, hotspots and quizzes",
                    "Only long text",
                    "Only videos",
                ],
                "answerIndex": 0,
                "explanation": "You learn by doing across many interaction types.",
            },
        ],
    }


def _topic_chapter(i: int, topic: str, company_name: str, audience: str) -> dict:
    t = topic.strip()
    tl = t.lower()
    return {
        "id": f"{i}-{_slugify(t)}",
        "title": t,
        "objective": f"Apply {tl} confidently in your day-to-day work at {company_name}.",
        "passingScore": 80,
        "pages": [
            {
                "title": "Concept",
                "blocks": [
                    {"type": "heading", "text": f"Why {t} matters"},
                    {
                        "type": "audio",
                        "say": (
                            f"In this chapter we explore {tl}. Listen, then try the "
                            f"interactive exercises to lock it in."
                        ),
                        "caption": f"{t} narration",
                    },
                    {
                        "type": "paragraph",
                        "text": (
                            f"{t} is a core part of how {company_name} works. For {audience}, "
                            f"getting this right early prevents mistakes and builds confidence."
                        ),
                    },
                    {
                        "type": "image",
                        "prompt": (
                            f"Clean flat-vector concept illustration representing '{t}' in a "
                            f"corporate training context, modern brand colors"
                        ),
                        "alt": f"Illustration of {t}",
                    },
                    {
                        "type": "callout",
                        "variant": "info",
                        "text": f"Key idea: {t} is a skill you practice, not a fact you memorize.",
                    },
                ],
            },
            {
                "title": "Explore & practice",
                "blocks": [
                    {
                        "type": "dialogue",
                        "title": f"A day with {t}",
                        "speakers": [
                            {
                                "name": "Maya",
                                "role": "Mentor",
                                "avatarPrompt": "friendly woman mentor flat vector avatar",
                            },
                            {
                                "name": "Sam",
                                "role": "New hire",
                                "avatarPrompt": "curious young man flat vector avatar",
                            },
                        ],
                        "steps": [
                            {"speaker": "Sam", "text": f"When does {tl} actually come up?"},
                            {
                                "speaker": "Maya",
                                "text": f"Almost daily. Let me show you how we handle {tl} here.",
                            },
                            {"speaker": "Sam", "text": "That makes sense — let me try."},
                        ],
                    },
                    {
                        "type": "dragdrop",
                        "instructions": f"Match each {tl} term to its meaning.",
                        "pairs": [
                            {"term": f"{t} basics", "match": "The foundational idea"},
                            {"term": "Best practice", "match": "The recommended way to do it"},
                            {"term": "Pitfall", "match": "A common mistake to avoid"},
                        ],
                    },
                    {
                        "type": "hotspot",
                        "instructions": "Click the markers to explore the workflow.",
                        "imagePrompt": (
                            f"labeled flat-vector workflow diagram for '{t}' with three "
                            f"distinct stages, corporate infographic style"
                        ),
                        "spots": [
                            {"x": 20, "y": 40, "label": "Start", "text": f"Where {tl} begins."},
                            {
                                "x": 50,
                                "y": 55,
                                "label": "Apply",
                                "text": f"Putting {tl} into action.",
                            },
                            {
                                "x": 80,
                                "y": 40,
                                "label": "Review",
                                "text": f"Checking your {tl} results.",
                            },
                        ],
                    },
                    {
                        "type": "chart",
                        "title": f"Impact of strong {tl}",
                        "chartType": "bar",
                        "labels": ["Before", "Month 1", "Month 3"],
                        "series": [{"label": "Confidence", "data": [30, 65, 90]}],
                    },
                ],
            },
        ],
        "quiz": [
            {
                "question": f"What is the focus of the '{t}' chapter?",
                "options": [t, "Payroll", "Office snacks"],
                "answerIndex": 0,
                "explanation": f"This chapter is about {tl}.",
            },
            {
                "question": f"How is {tl} best learned?",
                "options": ["By practicing it", "By ignoring it", "Only on your first day"],
                "answerIndex": 0,
                "explanation": f"{t} is a skill you build through practice.",
            },
            {
                "question": "What should you do if you make a mistake?",
                "options": ["Learn from it and ask for help", "Hide it", "Quit"],
                "answerIndex": 0,
                "explanation": "A growth mindset is part of the culture.",
            },
        ],
    }


def local_concept(brief: dict, style_guide: dict, company_name: str, primary_color: str) -> dict:
    """Deterministic, fully-interactive fallback used when Devin is not configured."""
    title = brief.get("title") or "Onboarding Course"
    topics = brief.get("topics") or ["Welcome & context", "Tools & access", "Ways of working"]
    audience = brief.get("audience", "new team members")
    chapters = [_intro_chapter(company_name, audience, title)]
    for i, topic in enumerate(topics, start=1):
        chapters.append(_topic_chapter(i, topic, company_name, audience))
    return {
        "title": title,
        "description": brief.get("goals", f"An interactive onboarding course for {audience}."),
        "companyName": company_name,
        "primaryColor": primary_color,
        "chapters": chapters,
    }


def _local_edit(current: dict, instruction: str, target_text: str | None) -> dict:
    """Offline fallback: surface the requested change as a callout so the edit is
    visible end-to-end without Devin."""
    edited = copy.deepcopy(current)
    note = f"Requested change: {instruction}"
    if target_text:
        note += f' (target: "{target_text[:80]}")'
    chapters = edited.get("chapters") or []
    if chapters:
        pages = chapters[0].setdefault("pages", [{"blocks": []}])
        if not pages:
            pages.append({"blocks": []})
        pages[0].setdefault("blocks", []).insert(
            0, {"type": "callout", "variant": "tip", "text": note}
        )
    return edited


async def generate_edited_concept(
    current_concept: dict,
    instruction: str,
    target_text: str | None,
) -> tuple[str | None, dict]:
    """Return (devin_session_id | None, edited concept dict)."""
    client = DevinClient()
    if not client.enabled:
        logger.info("DEVIN_API_KEY not set — using local edit fallback")
        return None, _local_edit(current_concept, instruction, target_text)

    prompt = (
        "You are editing an existing INTERACTIVE course. Here is the current course "
        f"concept as JSON:\n{current_concept}\n\n"
        f"The user selected this element: \"{target_text or 'N/A'}\".\n"
        f"Requested change: {instruction}\n\n"
        "Return the FULL updated concept as structured output matching the schema "
        "(multi-page chapters with interactive blocks: dialogue, dragdrop, ordering, "
        "hotspot, flipcards, chart, image/video/audio prompts, and gated quizzes). "
        "Preserve everything not affected by the request, keep existing media prompts "
        "unless the change requires new ones, and keep ids stable where possible."
    )
    try:
        session_id, output = await client.run(
            prompt,
            structured_output_schema=CONCEPT_SCHEMA,
            title="Course edit",
            tags=["coursive", "edit"],
        )
    except DevinError as exc:
        logger.warning("Devin edit failed (%s); using local fallback", exc)
        return None, _local_edit(current_concept, instruction, target_text)
    return session_id, output


async def generate_concept(
    brief: dict,
    style_guide: dict,
    company_name: str,
    primary_color: str,
) -> tuple[str | None, dict]:
    """Return (devin_session_id | None, concept dict)."""
    client = DevinClient()
    if not client.enabled:
        logger.info("DEVIN_API_KEY not set — using local concept generator")
        return None, local_concept(brief, style_guide, company_name, primary_color)

    prompt = build_concept_prompt(brief, style_guide, company_name)
    try:
        session_id, output = await client.run(
            prompt,
            structured_output_schema=CONCEPT_SCHEMA,
            title=f"Course concept: {brief.get('title')}",
            tags=["coursive", "concept"],
        )
    except DevinError as exc:
        logger.warning("Devin concept generation failed (%s); using local fallback", exc)
        return None, local_concept(brief, style_guide, company_name, primary_color)

    output.setdefault("companyName", company_name)
    output.setdefault("primaryColor", primary_color)
    return session_id, output
