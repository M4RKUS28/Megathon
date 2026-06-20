"""Google Gemini media providers: Nano-Banana image generation + Gemini TTS.

Both call the Generative Language REST API (`:generateContent`) with the
appropriate `responseModalities`. Image output is returned as PNG bytes; audio is
returned as PCM and wrapped into a WAV container.

These reuse `GEMINI_API_KEY`. They raise on failure so the composite provider can
fall back to the placeholder.
"""

from __future__ import annotations

import base64
import io
import logging
import re
import wave

import httpx

from src.config.settings import settings

from ...agents.schemas import AssetSpec
from ..assets import AssetProvider

logger = logging.getLogger(__name__)

_API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"


def _gemini_key() -> str:
    import os

    return (settings.gemini_api_key or os.environ.get("GEMINI_API_KEY", "")).strip()


def _inline_parts(result: dict) -> list[dict]:
    """Return the inlineData parts from a generateContent response."""
    parts: list[dict] = []
    for cand in result.get("candidates", []) or []:
        content = cand.get("content") or {}
        for part in content.get("parts", []) or []:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                parts.append(inline)
    return parts


def _pcm_to_wav(pcm: bytes, sample_rate: int, channels: int = 1, sampwidth: int = 2) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(sampwidth)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return buf.getvalue()


def _rate_from_mime(mime: str, default: int = 24000) -> int:
    # e.g. "audio/L16;codec=pcm;rate=24000"
    for token in mime.split(";"):
        token = token.strip()
        if token.startswith("rate="):
            try:
                return int(token.split("=", 1)[1])
            except ValueError:
                return default
    return default


# ── Context-aware style suffixes for image generation ─────────────────────────

_STYLE_HERO = (
    "Cinematic wide-angle composition, atmospheric lighting, rich color depth. "
    "Modern and aspirational, suitable as a chapter opener."
)
_STYLE_EXAMPLE = (
    "Practical hands-on scene showing the concept being applied in a real work "
    "environment. Clear, step-by-step visual storytelling."
)
_STYLE_DIAGRAM = (
    "Clean technical diagram with labeled components, clear directional arrows, "
    "minimal color palette on a white background. Structured and readable."
)
_STYLE_SCENARIO = (
    "Narrative illustration depicting a workplace scenario with expressive "
    "characters in a realistic setting. Warm, approachable tone."
)
_STYLE_DEFAULT = (
    "Modern flat-design illustration, clean geometric shapes, limited cohesive "
    "color palette. Professional and engaging for e-learning."
)

_HERO_PATTERN = re.compile(r"\b(hero|intro|opener|welcome|banner)\b", re.IGNORECASE)
_EXAMPLE_PATTERN = re.compile(
    r"\b(example|apply|practice|hands-on|step|real|situation)\b", re.IGNORECASE
)
_SCENARIO_PATTERN = re.compile(
    r"\b(scenario|decision|choice|branch|consequence)\b", re.IGNORECASE
)


def _style_suffix(spec: AssetSpec) -> str:
    """Choose a style suffix based on asset type and purpose/description context."""
    if spec.type in {"diagram", "chart", "model"}:
        return _STYLE_DIAGRAM

    purpose_and_desc = f"{spec.purpose} {spec.description}"

    if _HERO_PATTERN.search(purpose_and_desc):
        return _STYLE_HERO
    if _SCENARIO_PATTERN.search(purpose_and_desc):
        return _STYLE_SCENARIO
    if _EXAMPLE_PATTERN.search(purpose_and_desc):
        return _STYLE_EXAMPLE

    return _STYLE_DEFAULT


class NanoBananaImageProvider(AssetProvider):
    """Image generation via Gemini ("Nano-Banana", gemini-3.1-flash-image)."""

    def __init__(self, model: str | None = None, timeout: int = 120) -> None:
        self.model = model or settings.gemini_image_model
        self.timeout = timeout

    @staticmethod
    def configured() -> bool:
        return bool(_gemini_key())

    def _prompt(self, spec: AssetSpec) -> str:
        desc = spec.description or spec.purpose or "an instructional illustration"
        style = _style_suffix(spec)

        parts = [desc]

        if spec.dimensions:
            parts.append(f"Aspect ratio: {spec.dimensions}.")

        parts.append(style)
        parts.append("No text overlays, no watermarks, no stock-photo cliches.")

        return " ".join(parts)

    def produce(self, spec: AssetSpec, primary_color: str) -> tuple[bytes, str, str]:
        key = _gemini_key()
        if not key:
            raise RuntimeError("GEMINI_API_KEY not set")
        body = {
            "contents": [{"parts": [{"text": self._prompt(spec)}]}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        }
        url = f"{_API_ROOT}/{self.model}:generateContent?key={key}"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, json=body)
        if resp.status_code >= 400:
            raise RuntimeError(f"nano-banana HTTP {resp.status_code}: {resp.text[:200]}")
        parts = _inline_parts(resp.json())
        if not parts:
            raise RuntimeError("nano-banana returned no image data")
        inline = parts[0]
        data = base64.b64decode(inline["data"])
        mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
        ext = "png" if "png" in mime else ("jpg" if "jpeg" in mime else "img")
        return data, ext, mime


class GeminiTTSProvider(AssetProvider):
    """Narration audio via Gemini TTS (gemini-3.1-flash-tts-preview)."""

    def __init__(
        self, model: str | None = None, voice: str | None = None, timeout: int = 120
    ) -> None:
        self.model = model or settings.gemini_tts_model
        self.voice = voice or settings.gemini_tts_voice
        self.timeout = timeout

    @staticmethod
    def configured() -> bool:
        return bool(_gemini_key())

    def _text(self, spec: AssetSpec) -> str:
        # Prefer an explicit narration script; else narrate the description.
        return spec.description or spec.purpose or "Welcome to this lesson."

    def produce(self, spec: AssetSpec, primary_color: str) -> tuple[bytes, str, str]:
        key = _gemini_key()
        if not key:
            raise RuntimeError("GEMINI_API_KEY not set")
        voice = (spec.voice or self.voice).strip()
        body = {
            "contents": [{"parts": [{"text": self._text(spec)}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {"voiceName": voice}
                    }
                },
            },
        }
        url = f"{_API_ROOT}/{self.model}:generateContent?key={key}"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, json=body)
        if resp.status_code >= 400:
            raise RuntimeError(f"gemini-tts HTTP {resp.status_code}: {resp.text[:200]}")
        parts = _inline_parts(resp.json())
        if not parts:
            raise RuntimeError("gemini-tts returned no audio data")
        inline = parts[0]
        pcm = base64.b64decode(inline["data"])
        mime = inline.get("mimeType") or inline.get("mime_type") or "audio/L16;rate=24000"
        wav = _pcm_to_wav(pcm, _rate_from_mime(mime))
        return wav, "wav", "audio/wav"
