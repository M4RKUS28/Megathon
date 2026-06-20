"""Live provider diagnostics — verify that the configured external API keys work.

Each external provider (Gemini, Cala MCP, PixVerse, Devin) is probed with a
lightweight, real authenticated request so we can tell whether the keys from the
`.env` actually work. Probes never raise and never generate billable media; they
only validate reachability + authentication. Results are returned to the frontend
(which logs them to the browser console) and also written to the backend log.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass

import httpx

from src.config.settings import settings
from src.services.agents.cala import _McpHttpClient, cala_configured

logger = logging.getLogger(__name__)

# Keep probes snappy so the diagnostics endpoint stays responsive.
_PROBE_TIMEOUT = 12
_GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"


@dataclass
class ProviderCheck:
    """Result of probing a single external provider."""

    provider: str
    label: str
    configured: bool
    ok: bool
    detail: str
    status: int | None = None
    latency_ms: int | None = None

    def as_dict(self) -> dict:
        return {
            "provider": self.provider,
            "label": self.label,
            "configured": self.configured,
            "ok": self.ok,
            "detail": self.detail,
            "status": self.status,
            "latency_ms": self.latency_ms,
        }


def _gemini_key() -> str:
    return (settings.gemini_api_key or os.environ.get("GEMINI_API_KEY", "")).strip()


async def _check_gemini() -> ProviderCheck:
    label = "Google Gemini (planner / script-writer / Nano-Banana / TTS)"
    key = _gemini_key()
    if not key:
        return ProviderCheck("gemini", label, False, False, "GEMINI_API_KEY not set")
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT) as client:
            resp = await client.get(_GEMINI_MODELS_URL, params={"key": key})
        latency = int((time.monotonic() - start) * 1000)
        if resp.status_code == 200:
            count = len((resp.json() or {}).get("models", []) or [])
            return ProviderCheck(
                "gemini", label, True, True,
                f"key valid ({count} models reachable)", resp.status_code, latency,
            )
        return ProviderCheck(
            "gemini", label, True, False,
            f"HTTP {resp.status_code}: {resp.text[:160]}", resp.status_code, latency,
        )
    except Exception as exc:  # noqa: BLE001 — diagnostics must never crash
        latency = int((time.monotonic() - start) * 1000)
        return ProviderCheck("gemini", label, True, False, f"request failed: {exc}", None, latency)


async def _check_cala() -> ProviderCheck:
    label = "Cala MCP (company knowledge)"
    if not cala_configured():
        return ProviderCheck("cala", label, False, False, "CALA_MCP_URL not set")
    start = time.monotonic()

    def _handshake() -> str:
        client_obj = _McpHttpClient(
            url=settings.cala_mcp_url,
            api_key=settings.cala_api_key,
            timeout=_PROBE_TIMEOUT,
        )
        with httpx.Client(timeout=_PROBE_TIMEOUT) as http_client:
            client_obj.initialize(http_client)
        return client_obj._session_id or "ok"

    try:
        session = await asyncio.to_thread(_handshake)
        latency = int((time.monotonic() - start) * 1000)
        return ProviderCheck(
            "cala", label, True, True,
            f"MCP initialize handshake ok (session={session})", None, latency,
        )
    except Exception as exc:  # noqa: BLE001
        latency = int((time.monotonic() - start) * 1000)
        return ProviderCheck("cala", label, True, False, f"handshake failed: {exc}", None, latency)


async def _check_pixverse() -> ProviderCheck:
    label = "PixVerse (image / video generation)"
    key = (settings.pixverse_api_key or "").strip()
    if not key:
        return ProviderCheck("pixverse", label, False, False, "PIXVERSE_API_KEY not set")
    base = settings.pixverse_api_base_url.rstrip("/")
    # Cheap authenticated probe: query a video result with a sentinel id. A valid
    # key is accepted (the API replies with an app-level error, not an auth 401),
    # so we never trigger a billable generation.
    url = f"{base}/openapi/v2/video/result/1"
    headers = {"API-KEY": key, "Accept": "application/json"}
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT) as client:
            resp = await client.get(url, headers=headers)
        latency = int((time.monotonic() - start) * 1000)
        if resp.status_code in (401, 403):
            return ProviderCheck(
                "pixverse", label, True, False,
                f"key rejected (HTTP {resp.status_code})", resp.status_code, latency,
            )
        if resp.status_code >= 500:
            return ProviderCheck(
                "pixverse", label, True, False,
                f"server error HTTP {resp.status_code}", resp.status_code, latency,
            )
        err_msg = ""
        try:
            err_msg = str((resp.json() or {}).get("ErrMsg", ""))
        except Exception:  # noqa: BLE001 — body may not be JSON
            err_msg = resp.text[:120]
        return ProviderCheck(
            "pixverse", label, True, True,
            f"key accepted (HTTP {resp.status_code}{f': {err_msg}' if err_msg else ''})",
            resp.status_code, latency,
        )
    except Exception as exc:  # noqa: BLE001
        latency = int((time.monotonic() - start) * 1000)
        return ProviderCheck(
            "pixverse", label, True, False, f"request failed: {exc}", None, latency
        )


async def _check_devin() -> ProviderCheck:
    label = "Devin v3 API (per-course code-gen)"
    key = (settings.devin_api_key or "").strip()
    if not key:
        return ProviderCheck("devin", label, False, False, "DEVIN_API_KEY not set")
    if not settings.devin_org_id:
        return ProviderCheck(
            "devin", label, True, False,
            "DEVIN_API_KEY set but DEVIN_ORG_ID missing (cannot verify)",
        )
    base = settings.devin_api_base_url.rstrip("/")
    url = f"{base}/organizations/{settings.devin_org_id}/sessions"
    headers = {"Authorization": f"Bearer {key}"}
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT) as client:
            resp = await client.get(url, headers=headers, params={"limit": 1})
        latency = int((time.monotonic() - start) * 1000)
        if resp.status_code in (401, 403):
            return ProviderCheck(
                "devin", label, True, False,
                f"key rejected (HTTP {resp.status_code})", resp.status_code, latency,
            )
        if resp.status_code < 400:
            return ProviderCheck(
                "devin", label, True, True,
                f"key valid (HTTP {resp.status_code})", resp.status_code, latency,
            )
        return ProviderCheck(
            "devin", label, True, False,
            f"HTTP {resp.status_code}: {resp.text[:160]}", resp.status_code, latency,
        )
    except Exception as exc:  # noqa: BLE001
        latency = int((time.monotonic() - start) * 1000)
        return ProviderCheck("devin", label, True, False, f"request failed: {exc}", None, latency)


async def probe_providers() -> list[ProviderCheck]:
    """Probe every external provider concurrently and log a summary."""
    checks = await asyncio.gather(
        _check_gemini(),
        _check_cala(),
        _check_pixverse(),
        _check_devin(),
    )
    for check in checks:
        if not check.configured:
            logger.info("provider diagnostics: %s — not configured", check.provider)
        elif check.ok:
            logger.info(
                "provider diagnostics: %s — OK (%s, %sms)",
                check.provider, check.detail, check.latency_ms,
            )
        else:
            logger.warning(
                "provider diagnostics: %s — FAILED (%s)", check.provider, check.detail
            )
    return list(checks)
