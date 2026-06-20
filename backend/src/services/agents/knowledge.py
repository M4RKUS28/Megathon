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
        return KnowledgeResult(
            source="cala_mcp",
            query=query,
            snippets=[
                f"(placeholder) Cala MCP would return {self.company_name} knowledge for '{query}'.",
            ],
        )

    # ── Web search (placeholder) ─────────────────────────────────────────────
    def google_search(self, query: str) -> KnowledgeResult:
        """PLACEHOLDER for Google/Web search."""
        return KnowledgeResult(
            source="google_search",
            query=query,
            snippets=[f"(placeholder) Web search results for '{query}'."],
        )

    # ── Internal document family (placeholders, all via Cala/RAG later) ───────
    def rag_retrieve(self, query: str) -> KnowledgeResult:
        return KnowledgeResult("rag", query, [f"(placeholder) RAG passages for '{query}'."])

    def sop_search(self, query: str) -> KnowledgeResult:
        return KnowledgeResult("sop", query, [f"(placeholder) SOP matches for '{query}'."])

    def compliance_search(self, query: str) -> KnowledgeResult:
        return KnowledgeResult(
            "compliance",
            query,
            [f"(placeholder) Compliance requirements related to '{query}'."],
        )

    def policy_search(self, query: str) -> KnowledgeResult:
        return KnowledgeResult("policy", query, [f"(placeholder) Policy excerpts for '{query}'."])

    def wiki_search(self, query: str) -> KnowledgeResult:
        return KnowledgeResult("wiki", query, [f"(placeholder) Wiki articles for '{query}'."])

    def pdf_search(self, query: str) -> KnowledgeResult:
        return KnowledgeResult("pdf", query, [f"(placeholder) PDF document hits for '{query}'."])


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
