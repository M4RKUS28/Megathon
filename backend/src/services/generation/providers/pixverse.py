"""PixVerse image/video generation provider (Phase 2.5 asset pipeline).

Implements PixVerse's OpenAPI v2 text-to-video flow (create -> poll -> download)
and a best-effort image path. Requires `PIXVERSE_API_KEY`. Raises on failure so
the composite provider can fall back to the placeholder.

Endpoint paths are configurable via constants; adjust if your PixVerse plan
exposes different routes.
"""

from __future__ import annotations

import logging
import time
import uuid

import httpx

from src.config.settings import settings

from ...agents.schemas import AssetSpec
from ..assets import AssetProvider

logger = logging.getLogger(__name__)

_VIDEO_CREATE = "/openapi/v2/video/text/generate"
_VIDEO_RESULT = "/openapi/v2/video/result/{video_id}"
_IMAGE_CREATE = "/openapi/v2/image/generation"

# PixVerse video result status codes: 1 = success, 5 = generating/processing.
_STATUS_SUCCESS = 1
_STATUS_GENERATING = {5, 7}


def _aspect_ratio(dimensions: str) -> str:
    d = (dimensions or "").lower()
    if ":" in d:
        return d
    if "x" in d:
        try:
            w, h = (int(x) for x in d.split("x"))
            from math import gcd

            g = gcd(w, h) or 1
            return f"{w // g}:{h // g}"
        except ValueError:
            return "16:9"
    return "16:9"


class PixVerseProvider(AssetProvider):
    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key or settings.pixverse_api_key
        self.base_url = (base_url or settings.pixverse_api_base_url).rstrip("/")
        self.timeout = settings.pixverse_timeout

    @staticmethod
    def configured() -> bool:
        return bool(settings.pixverse_api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "API-KEY": self.api_key,
            "Ai-trace-id": str(uuid.uuid4()),
            "Content-Type": "application/json",
        }

    def produce(self, spec: AssetSpec, primary_color: str) -> tuple[bytes, str, str]:
        if not self.api_key:
            raise RuntimeError("PIXVERSE_API_KEY not set")
        if spec.type == "video":
            return self._produce_video(spec)
        return self._produce_image(spec)

    # ── video ────────────────────────────────────────────────────────────────
    def _produce_video(self, spec: AssetSpec) -> tuple[bytes, str, str]:
        body = {
            "prompt": spec.description or spec.purpose or "instructional clip",
            "model": "v3.5",
            "duration": 5,
            "quality": "540p",
            "aspect_ratio": _aspect_ratio(spec.dimensions),
            "motion_mode": "normal",
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                f"{self.base_url}{_VIDEO_CREATE}", json=body, headers=self._headers()
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"pixverse create HTTP {resp.status_code}: {resp.text[:200]}")
            payload = resp.json()
            if payload.get("ErrCode"):
                raise RuntimeError(f"pixverse error: {payload.get('ErrMsg', payload)}")
            video_id = (payload.get("Resp") or {}).get("video_id")
            if not video_id:
                raise RuntimeError("pixverse returned no video_id")

            url = self._poll_video(client, video_id)
            video = client.get(url, timeout=self.timeout)
            if video.status_code >= 400:
                raise RuntimeError(f"pixverse download HTTP {video.status_code}")
            return video.content, "mp4", "video/mp4"

    def _poll_video(self, client: httpx.Client, video_id: int) -> str:
        deadline = time.monotonic() + self.timeout
        result_url = f"{self.base_url}{_VIDEO_RESULT.format(video_id=video_id)}"
        while time.monotonic() < deadline:
            resp = client.get(result_url, headers=self._headers())
            if resp.status_code >= 400:
                raise RuntimeError(f"pixverse result HTTP {resp.status_code}: {resp.text[:200]}")
            data = (resp.json() or {}).get("Resp") or {}
            status = data.get("status")
            if status == _STATUS_SUCCESS and data.get("url"):
                return data["url"]
            if status in _STATUS_GENERATING or status is None:
                time.sleep(5)
                continue
            raise RuntimeError(f"pixverse video failed (status={status})")
        raise RuntimeError("pixverse video timed out")

    # ── image ──────────────────────────────────────────────────────────────--
    def _produce_image(self, spec: AssetSpec) -> tuple[bytes, str, str]:
        body = {
            "prompt": spec.description or spec.purpose or "instructional illustration",
            "aspect_ratio": _aspect_ratio(spec.dimensions),
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                f"{self.base_url}{_IMAGE_CREATE}", json=body, headers=self._headers()
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"pixverse image HTTP {resp.status_code}: {resp.text[:200]}")
            data = (resp.json() or {}).get("Resp") or {}
            img_url = data.get("url") or data.get("image_url")
            if not img_url:
                raise RuntimeError("pixverse returned no image url")
            img = client.get(img_url, timeout=self.timeout)
            if img.status_code >= 400:
                raise RuntimeError(f"pixverse image download HTTP {img.status_code}")
            ctype = img.headers.get("content-type", "image/png")
            ext = "jpg" if "jpeg" in ctype else "png"
            return img.content, ext, ctype
