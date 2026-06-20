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
import time
import wave

import httpx

from src.config.settings import settings

from ...agents.schemas import AssetSpec
from ..assets import AssetProvider

logger = logging.getLogger(__name__)

_API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"
_RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


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


class NanoBananaImageProvider(AssetProvider):
    """Image generation via Gemini ("Nano-Banana", gemini-3.1-flash-image)."""

    def __init__(self, model: str | None = None, timeout: int = 120) -> None:
        self.model = model or settings.gemini_image_model
        self.timeout = timeout

    @staticmethod
    def configured() -> bool:
        return bool(_gemini_key())

    def _prompt(self, spec: AssetSpec) -> str:
        bits = [spec.description or spec.purpose or "an instructional illustration"]
        if spec.dimensions:
            bits.append(f"Aspect ratio {spec.dimensions}.")
        bits.append(
            "Clean, modern corporate e-learning illustration. No text, no watermarks."
        )
        return " ".join(bits)

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
        self,
        model: str | None = None,
        voice: str | None = None,
        timeout: int = 120,
        max_attempts: int = 3,
        backoff_seconds: float = 1.5,
    ) -> None:
        self.model = model or settings.gemini_tts_model
        self.voice = voice or settings.gemini_tts_voice
        self.timeout = timeout
        self.max_attempts = max(1, max_attempts)
        self.backoff_seconds = max(0.0, backoff_seconds)

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
        text = self._text(spec)
        body = {
            "contents": [{"parts": [{"text": text}]}],
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
        logger.info(
            "gemini-tts start: link=%s model=%s voice=%s text_chars=%d attempts=%d",
            spec.template_link,
            self.model,
            voice,
            len(text),
            self.max_attempts,
        )
        last_error: Exception | None = None
        resp: httpx.Response | None = None
        with httpx.Client(timeout=self.timeout) as client:
            for attempt in range(1, self.max_attempts + 1):
                try:
                    resp = client.post(url, json=body)
                    if resp.status_code < 400:
                        logger.debug(
                            "gemini-tts response: link=%s attempt=%d status=%d",
                            spec.template_link,
                            attempt,
                            resp.status_code,
                        )
                        break
                    message = f"gemini-tts HTTP {resp.status_code}: {resp.text[:200]}"
                    last_error = RuntimeError(message)
                    retryable = resp.status_code in _RETRYABLE_STATUS
                except httpx.HTTPError as exc:
                    last_error = exc
                    retryable = True
                if attempt >= self.max_attempts or not retryable:
                    break
                delay = self.backoff_seconds * attempt
                logger.warning(
                    "gemini-tts retrying: link=%s attempt=%d/%d delay=%.1fs error=%s",
                    spec.template_link,
                    attempt,
                    self.max_attempts,
                    delay,
                    last_error,
                )
                time.sleep(delay)
        if resp is None or resp.status_code >= 400:
            raise RuntimeError(str(last_error or "gemini-tts request failed"))
        parts = _inline_parts(resp.json())
        if not parts:
            raise RuntimeError("gemini-tts returned no audio data")
        inline = parts[0]
        pcm = base64.b64decode(inline["data"])
        mime = inline.get("mimeType") or inline.get("mime_type") or "audio/L16;rate=24000"
        wav = _pcm_to_wav(pcm, _rate_from_mime(mime))
        logger.info(
            "gemini-tts success: link=%s mime=%s pcm_bytes=%d wav_bytes=%d",
            spec.template_link,
            mime,
            len(pcm),
            len(wav),
        )
        return wav, "wav", "audio/wav"
