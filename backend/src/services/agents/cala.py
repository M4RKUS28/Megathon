"""Cala MCP company-knowledge provider (Phase 1).

`CalaKnowledge` is a `CompanyKnowledge` implementation backed by a real Cala MCP
server (streamable-HTTP transport, JSON-RPC 2.0). The planner agent's tools
(`cala_search`, `rag_retrieve`, `sop_search`, ...) each call the MCP `search`
tool with a different `kind`, so one MCP server serves the whole knowledge family.

The client performs the MCP `initialize` handshake once per instance, caches the
returned session id, and then issues `tools/call` requests. Responses may arrive
as plain JSON or as an SSE stream; both are parsed. Any transport/tool error
degrades gracefully to the deterministic placeholder snippets from the base class
so the pipeline never fails on knowledge lookups.

Configure via `CALA_MCP_URL` (+ `CALA_API_KEY`). When unset, the planner keeps
using the placeholder `CompanyKnowledge`.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

import httpx

from src.config.settings import settings

from .knowledge import CompanyKnowledge, KnowledgeResult

logger = logging.getLogger(__name__)

# The single MCP tool we call; `kind` disambiguates the knowledge family.
_DEFAULT_TOOL = "search"
_PROTOCOL_VERSION = "2025-03-26"


def cala_configured() -> bool:
    return bool(settings.cala_mcp_url)


class CalaMCPError(RuntimeError):
    pass


class _McpHttpClient:
    """Minimal synchronous MCP streamable-HTTP JSON-RPC client.

    Implements just enough of the spec for our use: `initialize`, the
    `notifications/initialized` notification, and `tools/call`. Handles both
    `application/json` and `text/event-stream` responses.
    """

    def __init__(self, url: str, api_key: str = "", timeout: int = 30) -> None:
        self.url = url
        self.api_key = api_key
        self.timeout = timeout
        self._session_id: str | None = None
        self._next_id = 0
        self._initialized = False

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    def _rpc_id(self) -> int:
        self._next_id += 1
        return self._next_id

    @staticmethod
    def _parse_response(resp: httpx.Response) -> dict:
        """Extract the first JSON-RPC result/error from a JSON or SSE response."""
        ctype = resp.headers.get("content-type", "")
        if "text/event-stream" in ctype:
            for line in resp.text.splitlines():
                line = line.strip()
                if line.startswith("data:"):
                    payload = line[len("data:"):].strip()
                    if not payload:
                        continue
                    try:
                        msg = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(msg, dict) and ("result" in msg or "error" in msg):
                        return msg
            raise CalaMCPError("no JSON-RPC message in SSE stream")
        return resp.json()

    def _post(self, client: httpx.Client, body: dict) -> dict:
        resp = client.post(self.url, json=body, headers=self._headers())
        sid = resp.headers.get("Mcp-Session-Id") or resp.headers.get("mcp-session-id")
        if sid:
            self._session_id = sid
        if resp.status_code >= 400:
            raise CalaMCPError(f"MCP HTTP {resp.status_code}: {resp.text[:200]}")
        message = self._parse_response(resp)
        if "error" in message:
            raise CalaMCPError(str(message["error"]))
        return message.get("result", {})

    def _notify(self, client: httpx.Client, method: str) -> None:
        try:
            client.post(
                self.url,
                json={"jsonrpc": "2.0", "method": method},
                headers=self._headers(),
            )
        except httpx.HTTPError as exc:  # notifications are best-effort
            logger.debug("MCP notify %s failed: %s", method, exc)

    def initialize(self, client: httpx.Client) -> None:
        result = self._post(
            client,
            {
                "jsonrpc": "2.0",
                "id": self._rpc_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": _PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "coursive-planner", "version": "1.0"},
                },
            },
        )
        self._initialized = True
        logger.info(
            "Cala MCP initialized (server=%s)",
            (result.get("serverInfo") or {}).get("name", "unknown"),
        )
        self._notify(client, "notifications/initialized")

    def call_tool(self, name: str, arguments: dict) -> list[str]:
        with httpx.Client(timeout=self.timeout) as client:
            if not self._initialized:
                self.initialize(client)
            result = self._post(
                client,
                {
                    "jsonrpc": "2.0",
                    "id": self._rpc_id(),
                    "method": "tools/call",
                    "params": {"name": name, "arguments": arguments},
                },
            )
        return _extract_snippets(result)


def _extract_snippets(result: dict) -> list[str]:
    """Pull human-readable text out of an MCP tool result."""
    snippets: list[str] = []
    for item in result.get("content", []) or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text" and item.get("text"):
            snippets.append(str(item["text"]).strip())
    # Some servers return a structured payload instead of content blocks.
    structured = result.get("structuredContent") or result.get("structured_content")
    if not snippets and isinstance(structured, dict):
        for value in structured.values():
            if isinstance(value, str):
                snippets.append(value)
            elif isinstance(value, list):
                snippets.extend(str(v) for v in value)
    return [s for s in snippets if s]


class CalaKnowledge(CompanyKnowledge):
    """Company knowledge backed by a Cala MCP server, with placeholder fallback."""

    def __init__(
        self,
        company_name: str = "the company",
        context: dict | None = None,
        tool_name: str = _DEFAULT_TOOL,
    ) -> None:
        super().__init__(company_name=company_name, context=context)
        self._client = _McpHttpClient(
            url=settings.cala_mcp_url,
            api_key=settings.cala_api_key,
            timeout=settings.cala_timeout,
        )
        self._tool_name = tool_name

    def _query(
        self,
        source: str,
        kind: str,
        query: str,
        fallback: Callable[[str], KnowledgeResult],
    ) -> KnowledgeResult:
        try:
            snippets = self._client.call_tool(
                self._tool_name,
                {"query": query, "kind": kind, "company": self.company_name},
            )
            if snippets:
                return KnowledgeResult(source=source, query=query, snippets=snippets)
            logger.info("Cala MCP returned no results for '%s' (%s)", query, kind)
        except Exception as exc:  # noqa: BLE001 — knowledge lookups must never crash
            logger.warning("Cala MCP %s lookup failed (%s); using placeholder", kind, exc)
        return fallback(query)

    def cala_search(self, query: str) -> KnowledgeResult:
        return self._query("cala_mcp", "knowledge", query, super().cala_search)

    def rag_retrieve(self, query: str) -> KnowledgeResult:
        return self._query("rag", "rag", query, super().rag_retrieve)

    def sop_search(self, query: str) -> KnowledgeResult:
        return self._query("sop", "sop", query, super().sop_search)

    def compliance_search(self, query: str) -> KnowledgeResult:
        return self._query("compliance", "compliance", query, super().compliance_search)

    def policy_search(self, query: str) -> KnowledgeResult:
        return self._query("policy", "policy", query, super().policy_search)

    def wiki_search(self, query: str) -> KnowledgeResult:
        return self._query("wiki", "wiki", query, super().wiki_search)

    def pdf_search(self, query: str) -> KnowledgeResult:
        return self._query("pdf", "pdf", query, super().pdf_search)


def get_company_knowledge(company_name: str, context: dict | None = None) -> CompanyKnowledge:
    """Return the Cala-backed provider when configured, else the placeholder."""
    if cala_configured():
        return CalaKnowledge(company_name=company_name, context=context)
    return CompanyKnowledge(company_name=company_name, context=context)
