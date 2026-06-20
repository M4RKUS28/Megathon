"""Phase 1 — Course Planner.

A single tool-using ReAct agent (LangGraph + Gemini) that calls company-knowledge
tools (Cala MCP, Google Search, RAG/SOP/compliance/...) to research the topic and
the company context, then emits a structured Course Plan. The plan is presented at
the approval gate before any further generation happens.

Falls back to a deterministic plan when Gemini is unavailable or the call fails.
"""

from __future__ import annotations

import logging

from .cala import get_company_knowledge
from .fallback import fallback_plan
from .knowledge import build_knowledge_tools
from .llm import gemini_available, get_chat_model
from .schemas import CoursePlan

logger = logging.getLogger(__name__)

PLANNER_SYSTEM = """You are an expert instructional designer and course planner for {company}.
You are given a course brief. Produce a complete, well-structured COURSE PLAN.

Work like a ReAct agent:
1. Analyse the brief (title, audience, objectives, language, difficulty, duration, context).
2. Actively use your company-knowledge TOOLS (cala_search, google_search, rag_retrieve,
   sop_search, compliance_search, policy_search, wiki_search, pdf_search) to discover
   mandatory content, SOPs, compliance requirements, internal terms and processes.
   Call several tools — do not skip this research step.
3. Design the course: clear learning objectives, an ordered chapter structure with
   progressive competency build-up, and an assessment per chapter. Apply didactic best
   practices (Bloom's taxonomy, microlearning, scenario-based and spaced learning).

CONTENT DENSITY rules:
- Each chapter must have 5-10 specific, concrete key_points — not vague one-liners like
  "understand the basics." Each key point should name a specific concept, process, or skill.
- Provide 3-5 subtopics per chapter that break the chapter into teachable sub-sections.
- Set min_pages to at least 5 (more for complex chapters, up to 8).
- Set depth to "standard" for most chapters, "deep" for complex/technical topics.

FORMAT GUIDELINES:
- The primary format is expository prose with rich interactions — NOT conversation-driven.
- Set dialogue_appropriate=true ONLY for chapters focused on soft skills, communication,
  behavioural norms, ethics, or interpersonal scenarios. For technical, process, or knowledge
  chapters, set dialogue_appropriate=false.
- Set chart_appropriate=true ONLY when the chapter involves real quantitative data, metrics,
  trends, or structured comparisons. Do NOT set it for qualitative or conceptual topics.
- Set primary_format="expository" and content_density="rich" on the plan.

INTERACTION GUIDANCE:
- For each chapter, set suggested_interactions to 2-3 interaction types from this palette:
  flashcards, dragdrop, hotspot, timeline, accordion, scenario.
- Vary the interaction types across chapters — do not suggest the same set for every chapter.
  Each chapter should have a different primary interaction from its neighbours.
- Match interaction types to the content: use "timeline" for sequential processes,
  "scenario" for decision-making topics, "flashcards" for terminology-heavy chapters,
  "dragdrop" for matching/classification, "hotspot" for visual/spatial content,
  "accordion" for multi-faceted topics with distinct sub-sections.

PAGE COUNT GUIDANCE:
- Each chapter should have 5-8 pages (set min_pages accordingly).
- A typical chapter arc: Introduction → Core concept → Deep dive → Real-world example →
  Common pitfalls → Practice → Recap.

Return the final COURSE PLAN as structured output. Make it specific and useful — fold the
knowledge you found into objectives, mandatory_topics and compliance_requirements.
Record what you found in knowledge_sources."""


def _brief_text(brief: dict) -> str:
    lines = [f"{k}: {v}" for k, v in brief.items() if v]
    return "\n".join(lines) or "(no details provided)"


async def generate_plan(brief: dict, company_name: str, context: dict | None = None) -> CoursePlan:
    """Run the planner agent (or deterministic fallback) and return a CoursePlan."""
    if not gemini_available():
        logger.info("GEMINI_API_KEY not set — using deterministic planner fallback")
        return fallback_plan(brief, company_name)

    try:
        from langgraph.prebuilt import create_react_agent

        knowledge = get_company_knowledge(company_name, context)
        tools = build_knowledge_tools(knowledge)
        model = get_chat_model(temperature=0.3)
        agent = create_react_agent(
            model,
            tools,
            prompt=PLANNER_SYSTEM.format(company=company_name),
            response_format=CoursePlan,
        )
        result = await agent.ainvoke(
            {"messages": [("user", f"Course brief:\n{_brief_text(brief)}")]}
        )
        plan = result.get("structured_response")
        if isinstance(plan, CoursePlan) and plan.chapters:
            return plan
        logger.warning("planner returned no usable structured plan; using fallback")
    except Exception as exc:  # noqa: BLE001 — never fail the pipeline on agent errors
        logger.warning("planner agent failed (%s); using fallback", exc)
    return fallback_plan(brief, company_name)
