"""Phase 1 — Course Planner.

A single tool-using ReAct agent (LangGraph + Gemini) that calls company-knowledge
tools (Cala MCP, Google Search, RAG/SOP/compliance/...) to research the topic and
the company context, then emits a structured Course Plan. The plan is presented at
the approval gate before any further generation happens.

Falls back to a deterministic plan when Gemini is unavailable or the call fails.
"""

from __future__ import annotations

import logging

from .fallback import fallback_plan
from .knowledge import CompanyKnowledge, build_knowledge_tools
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

        knowledge = CompanyKnowledge(company_name=company_name, context=context)
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
