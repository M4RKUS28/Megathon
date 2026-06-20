from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import quote

import httpx

from .config import Settings


class DevinClientError(RuntimeError):
    pass


class DevinClient(Protocol):
    async def preflight(self, prepare_repository: bool = False) -> dict[str, Any]:
        ...

    async def create_session(self, *, title: str, prompt: str, tags: list[str]) -> dict[str, Any]:
        ...

    async def get_session(self, devin_id: str) -> dict[str, Any]:
        ...

    async def list_messages(self, devin_id: str) -> dict[str, Any]:
        ...


def repo_path_from_url(repo_url: str) -> str:
    cleaned = repo_url.strip().removesuffix(".git").rstrip("/")
    if not cleaned:
        return ""
    if cleaned.startswith("git@"):
        _, path = cleaned.split(":", 1)
        return path
    if "://" in cleaned:
        return "/".join(cleaned.split("://", 1)[1].split("/")[1:])
    return cleaned


@dataclass
class RealDevinClient:
    settings: Settings
    timeout: float = 20.0

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.settings.devin_api_key}", "Content-Type": "application/json"}

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self.settings.normalized_base_url}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(method, url, headers=self._headers(), **kwargs)
        if response.status_code >= 400:
            detail = response.text[:1000]
            raise DevinClientError(f"Devin API {method} {path} failed with {response.status_code}: {detail}")
        if not response.content:
            return {}
        return response.json()

    async def preflight(self, prepare_repository: bool = False) -> dict[str, Any]:
        missing = self.settings.missing_required_env
        checks: dict[str, Any] = {
            "env": self.settings.required_env_status,
            "api_base_url": self.settings.normalized_base_url,
            "repo_path": repo_path_from_url(self.settings.devin_repo_url),
            "prepare_repository": prepare_repository,
        }
        if missing:
            return {"ok": False, "mode": "real", "checks": checks, "error": f"Missing required env vars: {', '.join(missing)}"}
        if not self.settings.devin_api_key.startswith("cog_"):
            return {"ok": False, "mode": "real", "checks": checks, "error": "DEVIN_API_KEY must be a v3 service-user key starting with cog_."}

        self_payload = await self._request("GET", "/v3/self")
        checks["self"] = self_payload
        if self_payload.get("org_id") and self_payload.get("org_id") != self.settings.devin_org_id:
            return {
                "ok": False,
                "mode": "real",
                "checks": checks,
                "error": f"Authenticated org_id {self_payload.get('org_id')} does not match DEVIN_ORG_ID.",
            }

        repo_path = checks["repo_path"]
        repo_list = await self._request(
            "GET",
            f"/v3beta1/organizations/{quote(self.settings.devin_org_id, safe='')}/repositories",
            params=[("only_repo_paths", repo_path), ("load_indexing_status", "true"), ("first", "10")],
        )
        checks["repository_lookup"] = repo_list
        if not repo_list.get("items"):
            return {"ok": False, "mode": "real", "checks": checks, "error": f"Repository {repo_path} is not visible to Devin."}

        if prepare_repository:
            prepared = await self._request(
                "PUT",
                f"/v3beta1/organizations/{quote(self.settings.devin_org_id, safe='')}/repositories/{quote(repo_path, safe='')}/indexing",
                json={"branch_names": [self.settings.devin_default_branch]},
            )
            checks["repository_prepare"] = prepared
        return {"ok": True, "mode": "real", "checks": checks, "error": None}

    async def create_session(self, *, title: str, prompt: str, tags: list[str]) -> dict[str, Any]:
        repo_path = repo_path_from_url(self.settings.devin_repo_url)
        payload = {
            "title": title,
            "prompt": prompt,
            "repos": [repo_path] if repo_path else [],
            "tags": tags,
            "structured_output_required": True,
            "structured_output_schema": {
                "type": "object",
                "required": ["summary", "branch", "commit_sha", "build_status", "tests", "lint", "qa_notes"],
                "properties": {
                    "summary": {"type": "string"},
                    "branch": {"type": "string"},
                    "commit_sha": {"type": "string"},
                    "pr_url": {"type": ["string", "null"]},
                    "build_status": {"type": "string"},
                    "tests": {"type": "string"},
                    "lint": {"type": "string"},
                    "qa_notes": {"type": "string"},
                },
            },
        }
        return await self._request("POST", f"/v3/organizations/{quote(self.settings.devin_org_id, safe='')}/sessions", json=payload)

    async def get_session(self, devin_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/v3/organizations/{quote(self.settings.devin_org_id, safe='')}/sessions/{quote(devin_id, safe='')}")

    async def list_messages(self, devin_id: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/v3/organizations/{quote(self.settings.devin_org_id, safe='')}/sessions/{quote(devin_id, safe='')}/messages",
            params={"first": 100},
        )


class FakeDevinClient:
    def __init__(self) -> None:
        self._counter = 0

    async def preflight(self, prepare_repository: bool = False) -> dict[str, Any]:
        return {
            "ok": True,
            "mode": "testing_fake",
            "checks": {
                "env": {"TESTING": True},
                "self": {"principal_type": "service_user", "service_user_id": "svc_test", "org_id": "org-test"},
                "repository_prepare": {"indexing_enabled": True, "branches": ["main"]} if prepare_repository else None,
            },
            "error": None,
        }

    async def create_session(self, *, title: str, prompt: str, tags: list[str]) -> dict[str, Any]:
        self._counter += 1
        await asyncio.sleep(0)
        return {
            "session_id": f"devin-test-{self._counter:03d}",
            "status": "exit",
            "status_detail": "finished",
            "url": f"https://app.devin.ai/sessions/devin-test-{self._counter:03d}",
            "title": title,
            "tags": tags,
            "pull_requests": [{"pr_url": f"https://example.invalid/pr/{self._counter}", "pr_state": "open"}],
            "structured_output": {
                "summary": f"Test fake completed {title}",
                "branch": f"courseforge/test-{self._counter}",
                "commit_sha": f"deadbeef{self._counter:04d}",
                "pr_url": f"https://example.invalid/pr/{self._counter}",
                "build_status": "passed",
                "tests": "passed",
                "lint": "passed",
                "qa_notes": "Fake client is available only when TESTING=true.",
            },
        }

    async def get_session(self, devin_id: str) -> dict[str, Any]:
        return {
            "session_id": devin_id,
            "status": "exit",
            "status_detail": "finished",
            "pull_requests": [{"pr_url": f"https://example.invalid/{devin_id}", "pr_state": "open"}],
            "structured_output": {
                "summary": f"Completed {devin_id}",
                "branch": f"courseforge/{devin_id}",
                "commit_sha": f"{devin_id.replace('-', '')[:12]:0<12}",
                "pr_url": f"https://example.invalid/{devin_id}",
                "build_status": "passed",
                "tests": "passed",
                "lint": "passed",
                "qa_notes": "All fake QA checks passed.",
            },
        }

    async def list_messages(self, devin_id: str) -> dict[str, Any]:
        return {"items": [{"event_id": f"evt-{devin_id}", "message": f"{devin_id} completed in TESTING=true fake mode."}], "has_next_page": False}


def get_devin_client(settings: Settings) -> DevinClient:
    if settings.testing:
        return FakeDevinClient()
    return RealDevinClient(settings)
