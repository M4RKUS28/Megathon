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
import re
import wave

from src.config.settings import settings
from src.db.minio import ensure_bucket_exists, public_object_url, put_bytes

from ..agents.schemas import AssetSpec

logger = logging.getLogger(__name__)

_AUDIO_TYPES = {"audio", "narration"}

# Patterns indicating a description was fabricated by the manifest builder
# rather than being a genuine creative brief from the LLM.
_GENERIC_DESCRIPTION_PATTERNS = [
    re.compile(r"^Spoken narration for", re.IGNORECASE),
    re.compile(r"^Course asset$", re.IGNORECASE),
    re.compile(r"key metrics", re.IGNORECASE),
    re.compile(r"Q[1-4].*Q[1-4]", re.IGNORECASE),
    re.compile(r"\bAdoption\b.*\b(Q[1-4]|quarter)", re.IGNORECASE),
    re.compile(r"^(image|video|audio|diagram|chart)\s+in\s+chapter\b", re.IGNORECASE),
]

# Purpose strings indicating the asset is a chart/diagram with structured data
_FORCED_CHART_PURPOSES = re.compile(
    r"(chart|diagram)\s+in\s+chapter", re.IGNORECASE
)


def _is_likely_placeholder(spec: AssetSpec) -> bool:
    """Return True if the spec's description/purpose suggest a forced or
    fabricated asset that won't benefit from expensive generation."""
    desc = spec.description.strip()
    purpose = spec.purpose.strip()

    # Empty or extremely short descriptions are generic
    if not desc or len(desc) < 15:
        return True

    # Check description against known generic patterns
    for pat in _GENERIC_DESCRIPTION_PATTERNS:
        if pat.search(desc):
            return True

    # Charts with purpose like "chart in chapter 'X'" and generic data labels
    if spec.type in {"diagram", "chart"} and _FORCED_CHART_PURPOSES.search(purpose):
        return True

    # Audio with just a purpose string (no real narration text)
    if spec.type in _AUDIO_TYPES and desc == purpose:
        return True

    return False


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


# ── SVG icon paths for type-aware placeholders ────────────────────────────────

_ICON_IMAGE = (
    '<path d="M4 5a1 1 0 011-1h14a1 1 0 011 1v14a1 1 0 01-1 1H5a1 1 0 01-1-1V5z'
    'M7 15l3-3 2 2 4-4" stroke-linecap="round" stroke-linejoin="round"/>'
    '<circle cx="8.5" cy="8.5" r="1.5"/>'
)
_ICON_CHART = (
    '<rect x="3" y="12" width="4" height="7" rx="0.5"/>'
    '<rect x="9" y="8" width="4" height="11" rx="0.5"/>'
    '<rect x="15" y="4" width="4" height="15" rx="0.5"/>'
)
_ICON_DIAGRAM = (
    '<rect x="3" y="3" width="7" height="5" rx="1"/>'
    '<rect x="14" y="3" width="7" height="5" rx="1"/>'
    '<rect x="8.5" y="16" width="7" height="5" rx="1"/>'
    '<line x1="6.5" y1="8" x2="6.5" y2="12"/><line x1="6.5" y1="12" x2="12" y2="16"/>'
    '<line x1="17.5" y1="8" x2="17.5" y2="12"/><line x1="17.5" y1="12" x2="12" y2="16"/>'
)
_ICON_VIDEO = (
    '<rect x="3" y="5" width="14" height="14" rx="1"/>'
    '<polygon points="21,12 17,9 17,15"/>'
)

_TYPE_ICONS: dict[str, str] = {
    "image": _ICON_IMAGE,
    "diagram": _ICON_DIAGRAM,
    "chart": _ICON_CHART,
    "video": _ICON_VIDEO,
    "model": _ICON_DIAGRAM,
}


class PlaceholderAssetProvider(AssetProvider):
    """Generates type-aware SVG placeholders that look intentional and clean."""

    def produce(self, spec: AssetSpec, primary_color: str) -> tuple[bytes, str, str]:
        if spec.type in _AUDIO_TYPES:
            return _silent_wav(), "wav", "audio/wav"
        w, h = _aspect(spec.dimensions)
        svg = self._build_svg(spec, w, h, primary_color)
        return svg.encode("utf-8"), "svg", "image/svg+xml"

    def _build_svg(self, spec: AssetSpec, w: int, h: int, color: str) -> str:
        desc = html.escape((spec.description or spec.purpose or "")[:100])
        icon_path = _TYPE_ICONS.get(spec.type, _ICON_IMAGE)
        # Determine a lighter tint of the brand color for the background
        bg_light = f"{color}08"  # 3% opacity hex suffix

        # Icon is drawn at 24x24 viewBox, center it in the placeholder
        icon_x = w // 2 - 16
        icon_y = h // 2 - 28

        label = html.escape(spec.type.capitalize())

        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" fill="none">'
            # Soft background
            f'<rect width="{w}" height="{h}" fill="#f9fafb"/>'
            f'<rect width="{w}" height="{h}" fill="{bg_light}"/>'
            # Subtle border
            f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="12" '
            f'stroke="{color}" stroke-opacity="0.15" stroke-width="2" fill="none"/>'
            # Centered icon
            f'<g transform="translate({icon_x},{icon_y}) scale(1.33)" '
            f'stroke="{color}" stroke-width="1.5" fill="none" opacity="0.6">'
            f'{icon_path}</g>'
            # Type label
            f'<text x="50%" y="{h // 2 + 12}" fill="{color}" opacity="0.7" '
            f'font-family="system-ui,sans-serif" font-size="{max(12, w // 48)}" '
            f'font-weight="600" text-anchor="middle">{label}</text>'
            # Description (truncated)
            f'<text x="50%" y="{h // 2 + 32}" fill="#6b7280" '
            f'font-family="system-ui,sans-serif" font-size="{max(10, w // 60)}" '
            f'text-anchor="middle">{desc}</text>'
            f"</svg>"
        )
        return svg


def fetch_assets(
    manifest: list[dict] | list[AssetSpec],
    course_prefix: str,
    primary_color: str = "#5145E5",
    provider: AssetProvider | None = None,
) -> dict[str, str]:
    """Produce + upload every manifest asset; return template_link -> storage_url.

    Applies smart filtering: assets with obviously generic/fabricated descriptions
    are routed directly to the placeholder provider (skipping expensive API calls).
    """
    if provider is None:
        from .providers import build_asset_provider

        provider = build_asset_provider()
    specs = [a if isinstance(a, AssetSpec) else AssetSpec(**a) for a in manifest]
    ensure_bucket_exists(settings.courses_bucket)

    asset_map: dict[str, str] = {}
    skipped = 0

    for spec in specs:
        try:
            # For forced/generic assets, skip expensive providers and use placeholder
            if _is_likely_placeholder(spec):
                skipped += 1
                logger.debug(
                    "asset %s looks forced/generic; using placeholder", spec.template_link
                )
                content, ext, ctype = _placeholder_for(spec, primary_color)
            else:
                content, ext, ctype = provider.produce(spec, primary_color)
        except Exception as exc:  # noqa: BLE001 — one bad asset must not fail the batch
            logger.warning("asset %s failed: %s", spec.template_link, exc)
            continue
        rel = spec.template_link.lstrip("/")
        object_name = f"{course_prefix}/{rel}.{ext}"
        put_bytes(content, object_name, settings.courses_bucket, ctype)
        asset_map[spec.template_link] = public_object_url(object_name, settings.courses_bucket)

    logger.info(
        "asset pipeline mapped %d/%d assets (%d skipped as forced/generic)",
        len(asset_map),
        len(specs),
        skipped,
    )
    return asset_map


def _placeholder_for(spec: AssetSpec, primary_color: str) -> tuple[bytes, str, str]:
    """Generate a placeholder for a forced/generic asset without hitting APIs."""
    placeholder = PlaceholderAssetProvider()
    return placeholder.produce(spec, primary_color)


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
