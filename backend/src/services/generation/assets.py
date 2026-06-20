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

import asyncio
import html
import json
import logging
from collections.abc import Awaitable, Callable

from src.config.settings import settings
from src.db.minio import ensure_bucket_exists, public_object_url, put_bytes

from ..agents.schemas import AssetSpec

logger = logging.getLogger(__name__)


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
    concurrency: int = 8,
    on_step: Callable[[str], Awaitable[None]] | None = None,
) -> dict[str, str]:
    """Produce + upload every manifest asset; return template_link -> storage_url.

    Assets are produced and uploaded concurrently (each provider call and MinIO
    upload runs in a worker thread, so the blocking image/audio generation no
    longer serializes). ``concurrency`` caps in-flight provider calls so we don't
    hammer the media APIs. A single failing asset never fails the batch.
    """
    if provider is None:
        from .providers import build_asset_provider

        provider = build_asset_provider()
    specs = [a if isinstance(a, AssetSpec) else AssetSpec(**a) for a in manifest]
    ensure_bucket_exists(settings.courses_bucket)

    sem = asyncio.Semaphore(max(1, concurrency))
    total = len(specs)
    done = {"n": 0}

    async def _produce_one(spec: AssetSpec) -> tuple[str, str] | None:
        async with sem:
            try:
                content, ext, ctype = await asyncio.to_thread(
                    provider.produce, spec, primary_color
                )
            except Exception as exc:  # noqa: BLE001 — one bad asset must not fail the batch
                logger.warning("asset %s failed: %s", spec.template_link, exc)
                return None
            rel = spec.template_link.lstrip("/")
            object_name = f"{course_prefix}/{rel}.{ext}"
            await asyncio.to_thread(
                put_bytes, content, object_name, settings.courses_bucket, ctype
            )
            done["n"] += 1
            if on_step is not None:
                try:
                    await on_step(f"Generated asset {done['n']}/{total}")
                except Exception:  # noqa: BLE001 — progress logging is non-critical
                    logger.debug("asset on_step failed", exc_info=True)
            return spec.template_link, public_object_url(
                object_name, settings.courses_bucket
            )

    results = await asyncio.gather(*(_produce_one(spec) for spec in specs))
    asset_map: dict[str, str] = {link: url for link, url in (r for r in results if r)}

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
