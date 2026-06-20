"""Agentic course-generation backend (LangGraph + Google Gemini).

Phase 1 (planner) is a single tool-using ReAct agent that calls company-knowledge
tools (Cala MCP, Google Search, RAG/SOP/compliance/...) and emits a Course Plan.
Phase 2 (script writer) is a small graph that turns the approved plan into a full
Lastenheft (interactive spec) plus an isolated asset manifest.

Every LLM-backed entrypoint has a deterministic offline fallback so the pipeline
is fully runnable without an API key.
"""
