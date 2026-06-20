"""Composite asset provider — dispatches per asset type to the configured real
provider, with deterministic placeholder fallback.

Selection is driven by settings (`ASSET_IMAGE_PROVIDER`, `ASSET_VIDEO_PROVIDER`,
`ASSET_AUDIO_PROVIDER`). "auto" picks the best configured provider for the type:
images -> Nano-Banana (Gemini), else PixVerse; videos -> PixVerse; audio ->
Gemini TTS. If the selected provider is unconfigured or raises, the branded SVG
placeholder is used so the pipeline always yields a hostable asset.

Graceful degradation: when a provider fails for an asset that looks forced or
generic (detected via `_is_likely_placeholder`), fall back immediately without
retry. Save expensive retries for assets with rich, intentional descriptions.
"""

from __future__ import annotations

import logging

from src.config.settings import settings

from ...agents.schemas import AssetSpec
from ..assets import AssetProvider, PlaceholderAssetProvider, _is_likely_placeholder
from .gemini_media import GeminiTTSProvider, NanoBananaImageProvider
from .pixverse import PixVerseProvider

logger = logging.getLogger(__name__)

_IMAGE_TYPES = {"image", "diagram", "chart", "model"}
_VIDEO_TYPES = {"video", "animation"}
_AUDIO_TYPES = {"audio", "narration"}


def _image_provider() -> AssetProvider | None:
    choice = settings.asset_image_provider
    if choice == "placeholder":
        return None
    if choice == "nano_banana":
        return NanoBananaImageProvider() if NanoBananaImageProvider.configured() else None
    if choice == "pixverse":
        return PixVerseProvider() if PixVerseProvider.configured() else None
    # auto
    if NanoBananaImageProvider.configured():
        return NanoBananaImageProvider()
    if PixVerseProvider.configured():
        return PixVerseProvider()
    return None


def _video_provider() -> AssetProvider | None:
    choice = settings.asset_video_provider
    if choice == "placeholder":
        return None
    if choice in {"pixverse", "auto"} and PixVerseProvider.configured():
        return PixVerseProvider()
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
        self._video = _video_provider()
        self._audio = _audio_provider()
        logger.info(
            "asset providers: image=%s video=%s audio=%s",
            type(self._image).__name__ if self._image else "placeholder",
            type(self._video).__name__ if self._video else "placeholder",
            type(self._audio).__name__ if self._audio else "placeholder",
        )

    def _select(self, spec: AssetSpec) -> AssetProvider | None:
        if spec.type in _VIDEO_TYPES:
            return self._video
        if spec.type in _AUDIO_TYPES:
            return self._audio
        if spec.type in _IMAGE_TYPES:
            return self._image
        return self._image

    def produce(self, spec: AssetSpec, primary_color: str) -> tuple[bytes, str, str]:
        provider = self._select(spec)
        if provider is not None:
            try:
                return provider.produce(spec, primary_color)
            except Exception as exc:  # noqa: BLE001 — fall back, never fail the batch
                # For forced/generic assets, don't log a scary warning — this is expected
                if _is_likely_placeholder(spec):
                    logger.debug(
                        "provider %s failed for forced asset %s; expected, using placeholder",
                        type(provider).__name__,
                        spec.template_link,
                    )
                else:
                    logger.warning(
                        "provider %s failed for %s (%s); using placeholder",
                        type(provider).__name__,
                        spec.template_link,
                        exc,
                    )
        return self.placeholder.produce(spec, primary_color)


def build_asset_provider() -> AssetProvider:
    """Return the composite provider (real providers + placeholder fallback)."""
    return CompositeAssetProvider()
