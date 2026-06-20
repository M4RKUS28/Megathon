"""Thin async client for the Devin API (https://docs.devin.ai/api-reference).

Used by the generation pipeline to create sessions, poll them to completion, and
read back validated `structured_output`.
"""

import asyncio
import logging

import httpx

from src.config.settings import settings

logger = logging.getLogger(__name__)

# status_enum values from GET /v1/sessions/{id}
_TERMINAL = {"finished", "blocked", "expired"}


class DevinError(RuntimeError):
    pass


class DevinClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        max_acu_limit: int | None = None,
    ) -> None:
        self.api_key = api_key or settings.devin_api_key
        self.base_url = (base_url or settings.devin_api_base_url).rstrip("/")
        self.max_acu_limit = max_acu_limit or settings.devin_max_acu_limit

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

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
        if title:
            body["title"] = title
        if tags:
            body["tags"] = tags
        if idempotent:
            body["idempotent"] = True

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/sessions", json=body, headers=self._headers()
            )
        if resp.status_code >= 400:
            raise DevinError(f"create_session failed [{resp.status_code}]: {resp.text}")
        return resp.json()

    async def get_session(self, session_id: str) -> dict:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(
                f"{self.base_url}/sessions/{session_id}", headers=self._headers()
            )
        if resp.status_code >= 400:
            raise DevinError(f"get_session failed [{resp.status_code}]: {resp.text}")
        return resp.json()

    async def send_message(self, session_id: str, message: str) -> None:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/sessions/{session_id}/message",
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
        """Poll a session until it reaches a terminal state; return structured_output."""
        waited = 0
        while waited < timeout_seconds:
            session = await self.get_session(session_id)
            status = session.get("status_enum") or session.get("status")
            if status in _TERMINAL:
                if status != "finished":
                    raise DevinError(f"session {session_id} ended in state '{status}'")
                output = session.get("structured_output")
                if output is None:
                    raise DevinError(f"session {session_id} finished without structured_output")
                return output
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
    ) -> tuple[str, dict]:
        """Create a session, wait for completion, return (session_id, structured_output)."""
        created = await self.create_session(
            prompt,
            structured_output_schema=structured_output_schema,
            title=title,
            tags=tags,
        )
        session_id = created["session_id"]
        logger.info("Devin session created: %s (%s)", session_id, created.get("url"))
        output = await self.wait_for_output(session_id)
        return session_id, output
