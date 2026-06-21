"""Phase 2.5 Process A — Resource fetch / asset pipeline.

Works the isolated asset manifest from the Lastenheft and produces an
`asset_map`: each `template_link` -> a final, production `storage_url` (MinIO).

Providers (Unsplash/Pexels/Google Images, Nano-Banana, Google TTS) sit
behind the `AssetProvider` interface. The default `PlaceholderAssetProvider`
generates a deterministic branded SVG placeholder for visual assets. Audio is not
silently replaced with fake speech; if TTS is unavailable the course renderer can
fall back to the transcript/browser voice instead of playing a silent snippet.
"""

from __future__ import annotations

import asyncio
import html
import json
import logging
from collections import Counter
from dataclasses import dataclass
from typing import Callable

from src.config.settings import settings
from src.db.minio import ensure_bucket_exists, public_object_url, put_bytes

from ..agents.schemas import AssetSpec

logger = logging.getLogger(__name__)

_AUDIO_TYPES = {"audio", "narration"}


@dataclass
class AssetProgress:
    """Tracks parallel asset pipeline progress."""

    total: int = 0
    completed: int = 0
    failed: int = 0

    def to_dict(self) -> dict[str, int]:
        return {"total": self.total, "completed": self.completed, "failed": self.failed}


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
            raise RuntimeError("audio placeholder disabled; TTS provider unavailable")
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


async def fetch_assets(
    manifest: list[dict] | list[AssetSpec],
    course_prefix: str,
    primary_color: str = "#5145E5",
    provider: AssetProvider | None = None,
    max_concurrent: int = 10,
    on_progress: Callable[[AssetProgress], None] | None = None,
) -> dict[str, str]:
    """Produce + upload every manifest asset concurrently; return template_link -> storage_url.

    Uses asyncio.gather with a bounded semaphore (max_concurrent) to limit
    parallel API calls. Synchronous providers are offloaded via
    asyncio.to_thread() so they don't block the event loop.
    """
    if provider is None:
        from .providers import build_asset_provider

        provider = build_asset_provider()
    specs = [a if isinstance(a, AssetSpec) else AssetSpec(**a) for a in manifest]
    ensure_bucket_exists(settings.courses_bucket)

    by_type = Counter(spec.type for spec in specs)
    logger.info(
        "asset pipeline starting: prefix=%s total=%d by_type=%s provider=%s max_concurrent=%d",
        course_prefix,
        len(specs),
        dict(sorted(by_type.items())),
        type(provider).__name__,
        max_concurrent,
    )

    progress = AssetProgress(total=len(specs))
    asset_map: dict[str, str] = {}
    skipped: Counter[str] = Counter()
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _process_one(spec: AssetSpec) -> tuple[str, str] | None:
        """Process a single asset spec; returns (template_link, storage_url) or None on failure."""
        async with semaphore:
            logger.debug(
                "asset produce start: link=%s type=%s purpose=%s description_chars=%d",
                spec.template_link,
                spec.type,
                spec.purpose,
                len(spec.description or ""),
            )
            try:
                content, ext, ctype = await asyncio.to_thread(
                    provider.produce, spec, primary_color
                )
            except Exception as exc:  # noqa: BLE001
                skipped[spec.type] += 1
                progress.failed += 1
                if on_progress:
                    on_progress(progress)
                logger.warning(
                    "asset produce failed: link=%s type=%s provider=%s error=%s",
                    spec.template_link,
                    spec.type,
                    type(provider).__name__,
                    exc,
                )
                return None

            rel = spec.template_link.lstrip("/")
            object_name = f"{course_prefix}/{rel}.{ext}"
            await asyncio.to_thread(
                put_bytes, content, object_name, settings.courses_bucket, ctype
            )
            url = public_object_url(object_name, settings.courses_bucket)
            logger.debug(
                "asset uploaded: link=%s object=%s bytes=%d content_type=%s",
                spec.template_link,
                object_name,
                len(content),
                ctype,
            )
            progress.completed += 1
            if on_progress:
                on_progress(progress)
            return spec.template_link, url

    results = await asyncio.gather(*[_process_one(spec) for spec in specs])

    for result in results:
        if result is not None:
            link, url = result
            asset_map[link] = url

    logger.info(
        "asset pipeline finished: mapped=%d/%d skipped_by_type=%s",
        len(asset_map),
        len(specs),
        dict(sorted(skipped.items())),
    )
    return asset_map


async def publish_asset_map(course_prefix: str, asset_map: dict[str, str]) -> str:
    """Store the asset_map.json alongside the course and return its object name."""
    object_name = f"{course_prefix}/asset_map.json"
    await asyncio.to_thread(
        put_bytes,
        json.dumps(asset_map).encode("utf-8"),
        object_name,
        settings.courses_bucket,
        "application/json",
    )
    return object_name
