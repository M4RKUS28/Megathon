"""Google Gemini chat-model factory for the agentic pipeline.

Returns a configured `ChatGoogleGenerativeAI` when `GEMINI_API_KEY` is set, and
exposes `gemini_available()` so callers can fall back to the deterministic
offline generators when no key is configured.
"""

from __future__ import annotations

import logging
import os

from src.config.settings import settings

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-3.5-flash"


def gemini_api_key() -> str:
    return (settings.gemini_api_key or os.environ.get("GEMINI_API_KEY", "")).strip()


def gemini_available() -> bool:
    return bool(gemini_api_key())


def get_chat_model(
    model: str | None = None,
    temperature: float = 0.4,
    max_output_tokens: int | None = None,
):
    """Build a Gemini chat model. Raises if the key/library is unavailable."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    key = gemini_api_key()
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    kwargs: dict = {
        "model": model or settings.gemini_model or DEFAULT_MODEL,
        "google_api_key": key,
        "temperature": temperature,
    }
    if max_output_tokens is not None:
        kwargs["max_output_tokens"] = max_output_tokens
    return ChatGoogleGenerativeAI(**kwargs)
