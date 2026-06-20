"""Thin async client for the Devin v3 API (https://docs.devin.ai/api-reference).

Uses the org-scoped Organization API (`/v3/organizations/{org_id}/sessions`) with a
service-user key (`cog_` prefix). Creates sessions, polls them to completion, and
reads back validated `structured_output`.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

import httpx

from src.config.settings import settings

logger = logging.getLogger(__name__)


def session_web_url(session_id: str | None) -> str | None:
    """Human-facing Devin app URL for a session id (for links shown in the UI)."""
    if not session_id:
        return None
    return f"{settings.devin_app_base_url.rstrip('/')}/sessions/{session_id}"

# v3 GET session fields: `status` (new/claimed/running/exit/error/suspended/resuming)
# and `status_detail` (working/waiting_for_user/finished/...). A session that has
# produced structured_output and is no longer "working" is treated as done; an
# error/suspended status (or detail "finished" with no output) is a failure.
_FAILED_STATUSES = {"error", "suspended"}
_DONE_DETAILS = {"finished"}


class DevinError(RuntimeError):
    pass


class DevinClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        org_id: str | None = None,
        max_acu_limit: int | None = None,
    ) -> None:
        self.api_key = api_key or settings.devin_api_key
        self.base_url = (base_url or settings.devin_api_base_url).rstrip("/")
        self.org_id = org_id or settings.devin_org_id
        self.max_acu_limit = max_acu_limit or settings.devin_max_acu_limit

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and self.org_id)

    @property
    def _sessions_base(self) -> str:
        return f"{self.base_url}/organizations/{self.org_id}/sessions"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def create_session(
        self,
        prompt: str,
        *,
        structured_output_schema: dict | None = None,
        title: str | None = None,
        tags: list[str] | None = None,
        idempotent: bool = False,
    ) -> dict:
        body: dict = {"prompt": prompt, "max_acu_limit": self.max_acu_limit}
        if settings.devin_snapshot_id:
            body["snapshot_id"] = settings.devin_snapshot_id
        if settings.devin_playbook_id:
            body["playbook_id"] = settings.devin_playbook_id
        if structured_output_schema:
            body["structured_output_schema"] = structured_output_schema
            body["structured_output_required"] = True
        if title:
            body["title"] = title
        if tags:
            body["tags"] = tags
        if idempotent:
            body["idempotent"] = True

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                self._sessions_base, json=body, headers=self._headers()
            )
        if resp.status_code >= 400:
            raise DevinError(f"create_session failed [{resp.status_code}]: {resp.text}")
        return resp.json()

    async def get_session(self, session_id: str) -> dict:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(
                f"{self._sessions_base}/{session_id}", headers=self._headers()
            )
        if resp.status_code >= 400:
            raise DevinError(f"get_session failed [{resp.status_code}]: {resp.text}")
        return resp.json()

    async def send_message(self, session_id: str, message: str) -> None:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self._sessions_base}/{session_id}/messages",
                json={"message": message},
                headers=self._headers(),
            )
        if resp.status_code >= 400:
            raise DevinError(f"send_message failed [{resp.status_code}]: {resp.text}")

    async def wait_for_output(
        self,
        session_id: str,
        *,
        poll_interval: int = 10,
        timeout_seconds: int = 60 * 30,
    ) -> dict:
        """Poll a session until the task finishes; return structured_output."""
        waited = 0
        while waited < timeout_seconds:
            session = await self.get_session(session_id)
            status = session.get("status")
            detail = session.get("status_detail")
            output = session.get("structured_output")
            if status in _FAILED_STATUSES or detail == "error":
                raise DevinError(
                    f"session {session_id} ended in state '{status}' ({detail})"
                )
            # Done once the agent has stopped working and produced its output.
            stopped = status == "exit" or (status == "running" and detail != "working")
            if output is not None and stopped:
                return output
            if detail in _DONE_DETAILS or status == "exit":
                raise DevinError(f"session {session_id} finished without structured_output")
            await asyncio.sleep(poll_interval)
            waited += poll_interval
        raise DevinError(f"session {session_id} timed out after {timeout_seconds}s")

    async def run(
        self,
        prompt: str,
        *,
        structured_output_schema: dict | None = None,
        title: str | None = None,
        tags: list[str] | None = None,
        on_created: Callable[[dict], Awaitable[None]] | None = None,
    ) -> tuple[str, dict]:
        """Create a session, wait for completion, return (session_id, structured_output).

        `on_created` is awaited with the create-session response as soon as the
        session exists (before the potentially long wait), so callers can persist
        the live `url` and session id immediately.
        """
        created = await self.create_session(
            prompt,
            structured_output_schema=structured_output_schema,
            title=title,
            tags=tags,
        )
        session_id = created["session_id"]
        logger.info("Devin session created: %s (%s)", session_id, created.get("url"))
        if on_created is not None:
            try:
                await on_created(created)
            except Exception:  # noqa: BLE001 — surfacing the link must never fail the run
                logger.warning("on_created callback failed for session %s", session_id)
        output = await self.wait_for_output(session_id)
        return session_id, output
