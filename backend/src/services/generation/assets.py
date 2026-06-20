"""Phase 2.5 Process A — Resource fetch / asset pipeline.

Works the isolated asset manifest from the Lastenheft and produces an
`asset_map`: each `template_link` -> a final, production `storage_url` (MinIO).

Providers (Unsplash/Pexels/Google Images, PixVerse, Nano-Banana, Google TTS) sit
behind the `AssetProvider` interface. The default `PlaceholderAssetProvider`
generates a deterministic branded SVG placeholder per asset and uploads it, so the
pipeline yields a real, hostable asset map without any external API keys. Drop in
a real provider to fetch/generate true assets.
"""

from __future__ import annotations

import html
import io
import json
import logging
import wave

from src.config.settings import settings
from src.db.minio import ensure_bucket_exists, public_object_url, put_bytes

from ..agents.schemas import AssetSpec

logger = logging.getLogger(__name__)

_AUDIO_TYPES = {"audio", "narration"}


def _silent_wav(seconds: float = 3.0, rate: int = 24000) -> bytes:
    """A valid, silent mono 16-bit WAV. Used as the audio placeholder so audio
    players stay functional when no real TTS narration is available."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))
    return buf.getvalue()


class AssetProvider:
    """Interface for resource-fetch agents. Implement to use real providers."""

    def produce(self, spec: AssetSpec, primary_color: str) -> tuple[bytes, str, str]:
        """Return (content_bytes, file_extension, content_type) for an asset."""
        raise NotImplementedError


def _aspect(dimensions: str) -> tuple[int, int]:
    try:
        if "x" in dimensions.lower():
            w, h = dimensions.lower().split("x")
            return int(w), int(h)
        if ":" in dimensions:
            a, b = dimensions.split(":")
            scale = 160
            return int(float(a) * scale), int(float(b) * scale)
    except (ValueError, TypeError):
        pass
    return 800, 450


class PlaceholderAssetProvider(AssetProvider):
    """Generates a branded SVG placeholder describing the requested asset."""

    def produce(self, spec: AssetSpec, primary_color: str) -> tuple[bytes, str, str]:
        if spec.type in _AUDIO_TYPES:
            return _silent_wav(), "wav", "audio/wav"
        w, h = _aspect(spec.dimensions)
        label = html.escape((spec.purpose or spec.type or "asset")[:60])
        desc = html.escape((spec.description or "")[:90])
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}">'
            f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
            f'<stop offset="0" stop-color="{primary_color}"/>'
            f'<stop offset="1" stop-color="#111827"/></linearGradient></defs>'
            f'<rect width="{w}" height="{h}" fill="url(#g)"/>'
            f'<text x="50%" y="46%" fill="#ffffff" font-family="sans-serif" '
            f'font-size="{max(16, w // 24)}" font-weight="700" text-anchor="middle">{label}</text>'
            f'<text x="50%" y="60%" fill="#e5e7eb" font-family="sans-serif" '
            f'font-size="{max(11, w // 44)}" text-anchor="middle">{desc}</text>'
            f"</svg>"
        )
        return svg.encode("utf-8"), "svg", "image/svg+xml"


def fetch_assets(
    manifest: list[dict] | list[AssetSpec],
    course_prefix: str,
    primary_color: str = "#5145E5",
    provider: AssetProvider | None = None,
) -> dict[str, str]:
    """Produce + upload every manifest asset; return template_link -> storage_url."""
    if provider is None:
        from .providers import build_asset_provider

        provider = build_asset_provider()
    specs = [a if isinstance(a, AssetSpec) else AssetSpec(**a) for a in manifest]
    ensure_bucket_exists(settings.courses_bucket)

    asset_map: dict[str, str] = {}
    for spec in specs:
        try:
            content, ext, ctype = provider.produce(spec, primary_color)
        except Exception as exc:  # noqa: BLE001 — one bad asset must not fail the batch
            logger.warning("asset %s failed: %s", spec.template_link, exc)
            continue
        rel = spec.template_link.lstrip("/")
        object_name = f"{course_prefix}/{rel}.{ext}"
        put_bytes(content, object_name, settings.courses_bucket, ctype)
        asset_map[spec.template_link] = public_object_url(object_name, settings.courses_bucket)

    logger.info("asset pipeline mapped %d/%d assets", len(asset_map), len(specs))
    return asset_map


def publish_asset_map(course_prefix: str, asset_map: dict[str, str]) -> str:
    """Store the asset_map.json alongside the course and return its object name."""
    object_name = f"{course_prefix}/asset_map.json"
    put_bytes(
        json.dumps(asset_map).encode("utf-8"),
        object_name,
        settings.courses_bucket,
        "application/json",
    )
    return object_name
