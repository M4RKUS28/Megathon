"""Composite asset provider -- dispatches per asset type to the configured real
provider, with deterministic placeholder fallback.

Selection is driven by settings (`ASSET_IMAGE_PROVIDER`, `ASSET_AUDIO_PROVIDER`).
"auto" picks the best configured provider per asset type and falls back to the
branded SVG placeholder. Images use Nano-Banana (Gemini); audio uses Gemini TTS.
Video generation is disabled (no provider configured); video/animation assets
receive an SVG placeholder.

Audio does not fall back to silence; if TTS is unavailable, the renderer can use
the transcript/browser voice instead.
"""

from __future__ import annotations

import logging

from src.config.settings import settings

from ...agents.schemas import AssetSpec
from ..assets import AssetProvider, PlaceholderAssetProvider
from .gemini_media import GeminiTTSProvider, NanoBananaImageProvider

logger = logging.getLogger(__name__)

_IMAGE_TYPES = {"image", "diagram", "chart", "model"}
_VIDEO_TYPES = {"video", "animation"}
_AUDIO_TYPES = {"audio"}
# Audio must NOT fall back to SVG placeholder (browser can't play it).
_NO_PLACEHOLDER_TYPES = _AUDIO_TYPES


def _image_provider() -> AssetProvider | None:
    choice = settings.asset_image_provider
    if choice == "placeholder":
        return None
    if choice == "nano_banana" or choice == "auto":
        return NanoBananaImageProvider() if NanoBananaImageProvider.configured() else None
    return None


def _audio_provider() -> AssetProvider | None:
    choice = settings.asset_audio_provider
    if choice == "placeholder":
        return None
    if choice in {"gemini_tts", "auto"} and GeminiTTSProvider.configured():
        return GeminiTTSProvider()
    return None


class CompositeAssetProvider(AssetProvider):
    def __init__(self) -> None:
        self.placeholder = PlaceholderAssetProvider()
        self._image = _image_provider()
        self._audio = _audio_provider()
        logger.info(
            "asset providers: image=%s audio=%s video=placeholder(disabled)",
            type(self._image).__name__ if self._image else "placeholder",
            type(self._audio).__name__ if self._audio else "placeholder",
        )

    def _select(self, spec: AssetSpec) -> AssetProvider | None:
        if spec.type in _AUDIO_TYPES:
            return self._audio
        if spec.type in _IMAGE_TYPES:
            return self._image
        # Video/animation: no provider, will use placeholder SVG
        return None

    def produce(self, spec: AssetSpec, primary_color: str) -> tuple[bytes, str, str]:
        provider = self._select(spec)
        if provider is not None:
            try:
                return provider.produce(spec, primary_color)
            except Exception as exc:  # noqa: BLE001
                if spec.type in _NO_PLACEHOLDER_TYPES:
                    logger.warning(
                        "%s provider %s failed for %s (%s); skipping (no SVG fallback)",
                        spec.type,
                        type(provider).__name__,
                        spec.template_link,
                        exc,
                    )
                    raise
                logger.warning(
                    "provider %s failed for %s (%s); using placeholder",
                    type(provider).__name__,
                    spec.template_link,
                    exc,
                )
        if spec.type in _NO_PLACEHOLDER_TYPES:
            raise RuntimeError(f"no {spec.type} provider configured")
        return self.placeholder.produce(spec, primary_color)


def build_asset_provider() -> AssetProvider:
    """Return the composite provider (real providers + placeholder fallback)."""
    return CompositeAssetProvider()
