"""Company-knowledge tools for the planner agent (Phase 1).

The planner is a single tool-using ReAct agent. Company knowledge is exposed as
*tools* it can call — Cala (MCP), Google Search, and the RAG/SOP/compliance/
policy/wiki/PDF family. Every tool routes through the `CompanyKnowledge`
interface so a real Cala MCP client / Google Search client can be dropped in
later without touching the agent.

Right now these are PLACEHOLDERS: they return structured, clearly-labelled stub
results derived from the company context so the pipeline is demoable end-to-end.
Wire real providers by implementing `CompanyKnowledge` and passing it to
`build_knowledge_tools`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeResult:
    source: str
    query: str
    snippets: list[str] = field(default_factory=list)

    def render(self) -> str:
        if not self.snippets:
            return f"[{self.source}] no results for '{self.query}'."
        body = "\n".join(f"- {s}" for s in self.snippets)
        return f"[{self.source}] results for '{self.query}':\n{body}"


class CompanyKnowledge:
    """Provider interface for company knowledge. Replace the stub methods with a
    real Cala MCP client, Google Search client, vector RAG store, etc.

    `company_name` and `context` are used by the placeholder implementation to
    return plausible, clearly-marked stub data.
    """

    def __init__(self, company_name: str = "the company", context: dict | None = None):
        self.company_name = company_name
        self.context = context or {}

    # ── Cala MCP (placeholder) ───────────────────────────────────────────────
    def cala_search(self, query: str) -> KnowledgeResult:
        """PLACEHOLDER for the Cala MCP integration."""
        co = self.company_name
        return KnowledgeResult(
            source="cala_mcp",
            query=query,
            snippets=[
                f"{co} has established processes and guidelines for {query}.",
                f"Key aspects include: definitions, procedures, responsibilities, "
                f"and compliance requirements related to {query}.",
                f"New employees should understand both the 'what' and 'why' of "
                f"{query} within the {co} context.",
                f"Relevant internal resources: wiki pages, SOP library, and "
                f"team-specific guides covering {query}.",
                f"Training on {query} typically covers: fundamentals, hands-on "
                f"practice, and assessment.",
            ],
        )

    # ── Web search (placeholder) ─────────────────────────────────────────────
    def google_search(self, query: str) -> KnowledgeResult:
        """PLACEHOLDER for Google/Web search."""
        return KnowledgeResult(
            source="google_search",
            query=query,
            snippets=[
                f"Industry best practices for {query} emphasise structured "
                f"onboarding, clear documentation, and measurable outcomes.",
                f"Common frameworks: competency matrices, progressive skill "
                f"building, and scenario-based learning applied to {query}.",
                f"Key terminology and definitions that professionals should "
                f"know when working with {query}.",
                f"Current trends: micro-learning modules, interactive "
                f"assessments, and real-world case studies for {query}.",
            ],
        )

    # ── Internal document family (placeholders, all via Cala/RAG later) ───────
    def rag_retrieve(self, query: str) -> KnowledgeResult:
        co = self.company_name
        return KnowledgeResult(
            "rag",
            query,
            [
                f"Internal documentation at {co} describes {query} as a core "
                f"competency area with defined learning paths.",
                f"Related passages cover: foundational concepts, step-by-step "
                f"workflows, common mistakes, and escalation procedures for {query}.",
                f"Cross-references found: onboarding guide chapter 3, team "
                f"handbook section on {query}, and quarterly review criteria.",
                f"Subject-matter experts recommend hands-on exercises and "
                f"shadowing as supplements to the written material on {query}.",
            ],
        )

    def sop_search(self, query: str) -> KnowledgeResult:
        co = self.company_name
        return KnowledgeResult(
            "sop",
            query,
            [
                f"SOP for {query} at {co}: defines the standard step-by-step "
                f"procedure, required approvals, and responsible roles.",
                f"Pre-conditions: ensure access permissions are granted and "
                f"prerequisite training on {query} fundamentals is completed.",
                "Key steps: (1) preparation and checklist review, "
                "(2) execution following the documented procedure, "
                "(3) verification and sign-off by the designated reviewer.",
                f"Exception handling: deviations from the {query} SOP must be "
                f"documented and escalated to the team lead within 24 hours.",
                f"Review cycle: the {query} SOP is reviewed quarterly and "
                f"updated when regulations or internal processes change.",
            ],
        )

    def compliance_search(self, query: str) -> KnowledgeResult:
        co = self.company_name
        return KnowledgeResult(
            "compliance",
            query,
            [
                f"Regulatory requirements: {co} must comply with applicable "
                f"industry regulations governing {query}.",
                f"Mandatory training: all employees handling {query} must "
                f"complete compliance training annually and pass with >= 80%.",
                f"Audit points: documentation of {query} activities must be "
                f"retained for the period required by the relevant regulation.",
                f"Non-compliance consequences: violations related to {query} "
                f"can result in corrective action plans, fines, or licence "
                f"suspension depending on severity.",
                f"Reporting obligations: incidents involving {query} must be "
                f"reported to the compliance team within the mandated timeframe.",
            ],
        )

    def policy_search(self, query: str) -> KnowledgeResult:
        co = self.company_name
        return KnowledgeResult(
            "policy",
            query,
            [
                f"{co} policy on {query}: outlines acceptable practices, "
                f"employee responsibilities, and management oversight.",
                f"Scope: applies to all employees, contractors, and partners "
                f"engaged in activities related to {query}.",
                f"Key provisions: mandatory orientation, periodic refresher "
                f"training, and documented acknowledgement of the {query} policy.",
                "Enforcement: violations are addressed through the standard "
                "disciplinary process; repeated breaches may affect performance "
                "reviews.",
            ],
        )

    def wiki_search(self, query: str) -> KnowledgeResult:
        co = self.company_name
        return KnowledgeResult(
            "wiki",
            query,
            [
                f"Wiki article: '{query} at {co}' — overview of the topic, "
                f"key definitions, and links to related internal pages.",
                f"Getting started guide: prerequisites, tool setup, and first "
                f"steps for new team members working with {query}.",
                f"FAQ section covers the most common questions about {query}, "
                f"including troubleshooting tips and contact points for help.",
                f"Change log: recent updates to {query} processes, with dates "
                f"and summaries of what changed and why.",
            ],
        )

    def pdf_search(self, query: str) -> KnowledgeResult:
        co = self.company_name
        return KnowledgeResult(
            "pdf",
            query,
            [
                f"PDF handbook: '{co} Guide to {query}' — comprehensive "
                f"reference covering principles, procedures, and examples.",
                "Chapter outline: (1) Introduction & scope, (2) Core concepts, "
                "(3) Detailed procedures, (4) Case studies, (5) Assessment.",
                f"Appendices include: glossary of terms related to {query}, "
                f"quick-reference checklists, and role-responsibility matrices.",
                "Version history indicates the document is reviewed annually; "
                "the latest revision incorporates feedback from the last audit cycle.",
            ],
        )


def build_knowledge_tools(knowledge: CompanyKnowledge) -> list:
    """Wrap a `CompanyKnowledge` provider as LangChain tools for the agent."""
    from langchain_core.tools import StructuredTool

    def _mk(fn, name: str, description: str) -> StructuredTool:
        def _call(query: str) -> str:
            try:
                return fn(query).render()
            except Exception as exc:  # noqa: BLE001 — tool errors must not crash the agent
                logger.warning("knowledge tool %s failed: %s", name, exc)
                return f"[{name}] error: {exc}"

        return StructuredTool.from_function(func=_call, name=name, description=description)

    return [
        _mk(knowledge.cala_search, "cala_search",
            "Search the company knowledge base via Cala (MCP). Use for any internal info."),
        _mk(knowledge.google_search, "google_search",
            "Search the public web for general/best-practice information."),
        _mk(knowledge.rag_retrieve, "rag_retrieve",
            "Retrieve relevant internal document passages (RAG)."),
        _mk(knowledge.sop_search, "sop_search",
            "Find Standard Operating Procedures (SOPs) relevant to the topic."),
        _mk(knowledge.compliance_search, "compliance_search",
            "Find compliance and regulatory requirements that must be covered."),
        _mk(knowledge.policy_search, "policy_search",
            "Find internal company policies relevant to the topic."),
        _mk(knowledge.wiki_search, "wiki_search",
            "Search the internal wiki for processes and definitions."),
        _mk(knowledge.pdf_search, "pdf_search",
            "Search internal PDF documents for relevant content."),
    ]
