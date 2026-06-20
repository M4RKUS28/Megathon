"""Course concept generation: turn a brief + style guide into a structured
concept (chapters, objectives, content blocks, quizzes).

Uses the real Devin API when `DEVIN_API_KEY` is configured; otherwise falls back
to a deterministic local generator so the pipeline is fully demoable offline.
"""

import copy
import logging
from typing import Any

from src.services.devin.client import DevinClient, DevinError

logger = logging.getLogger(__name__)

# JSON Schema (Draft 7) the Devin session must satisfy in structured_output.
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
                "required": ["id", "title", "blocks", "quiz"],
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "objective": {"type": "string"},
                    "blocks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["type"],
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": ["heading", "paragraph", "list", "callout", "code"],
                                },
                                "text": {"type": "string"},
                                "items": {"type": "array", "items": {"type": "string"}},
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
        f"You are an instructional designer for {company_name}. Produce a complete, "
        f"engaging onboarding/training course as structured JSON.\n\n"
        f"Course title: {brief.get('title')}\n"
        f"Audience: {brief.get('audience', 'new employees')}\n"
        f"Goals: {brief.get('goals', 'onboard the audience effectively')}\n"
        f"Tone: {brief.get('tone', 'friendly and professional')}\n"
        f"Approximate length: {brief.get('duration', '4-6 chapters')}\n"
        f"Key topics to cover: {topics}\n\n"
        f"Brand: company '{company_name}'. Style guide: {style_guide}.\n\n"
        "Return ONLY structured output matching the provided schema. Each chapter must have "
        "a clear objective, 3-6 content blocks (paragraph/list/callout/code/heading), and "
        "1-2 multiple-choice quiz questions with the correct answerIndex and a short "
        "explanation. Make the content specific and useful, not generic filler."
    )


def _slugify(text: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in text).strip("-")[:48] or "chapter"


def local_concept(brief: dict, style_guide: dict, company_name: str, primary_color: str) -> dict:
    """Deterministic fallback concept used when Devin is not configured."""
    title = brief.get("title") or "Onboarding Course"
    topics = brief.get("topics") or ["Welcome & context", "Tools & access", "Ways of working"]
    audience = brief.get("audience", "new team members")
    chapters = []
    for i, topic in enumerate(topics):
        chapters.append(
            {
                "id": f"{i}-{_slugify(topic)}",
                "title": topic,
                "objective": f"Understand {topic.lower()} as it applies to {audience}.",
                "blocks": [
                    {
                        "type": "paragraph",
                        "text": (
                            f"This chapter introduces {topic.lower()} at {company_name}. "
                            f"It is written for {audience}."
                        ),
                    },
                    {
                        "type": "list",
                        "items": [
                            f"Why {topic.lower()} matters",
                            "What you need to get started",
                            "Where to ask for help",
                        ],
                    },
                    {
                        "type": "callout",
                        "text": f"Key takeaway: {topic} is part of how {company_name} works.",
                    },
                ],
                "quiz": [
                    {
                        "question": f"What is the focus of the '{topic}' chapter?",
                        "options": [topic, "Payroll", "Office snacks"],
                        "answerIndex": 0,
                        "explanation": f"This chapter is about {topic.lower()}.",
                    }
                ],
            }
        )
    return {
        "title": title,
        "description": brief.get("goals", f"An onboarding course for {audience}."),
        "companyName": company_name,
        "primaryColor": primary_color,
        "chapters": chapters,
    }


def _local_edit(current: dict, instruction: str, target_text: str | None) -> dict:
    """Offline fallback: append the requested change as a callout so the edit is
    visible end-to-end without Devin."""
    edited = copy.deepcopy(current)
    note = f"Requested change: {instruction}"
    if target_text:
        note += f' (target: "{target_text[:80]}")'
    if edited.get("chapters"):
        edited["chapters"][0].setdefault("blocks", []).insert(
            0, {"type": "callout", "text": note}
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
        "You are editing an existing course. Here is the current course concept as JSON:\n"
        f"{current_concept}\n\n"
        f"The user selected this element: \"{target_text or 'N/A'}\".\n"
        f"Requested change: {instruction}\n\n"
        "Return the FULL updated concept as structured output matching the schema. "
        "Preserve everything not affected by the request."
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
