from __future__ import annotations

import os
from dataclasses import dataclass, field


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    devin_api_key: str = field(default_factory=lambda: os.getenv("DEVIN_API_KEY", ""))
    devin_api_base_url: str = field(default_factory=lambda: os.getenv("DEVIN_API_BASE_URL", "https://api.devin.ai"))
    devin_org_id: str = field(default_factory=lambda: os.getenv("DEVIN_ORG_ID", ""))
    devin_project_id: str = field(default_factory=lambda: os.getenv("DEVIN_PROJECT_ID", ""))
    devin_repo_url: str = field(default_factory=lambda: os.getenv("DEVIN_REPO_URL", ""))
    devin_default_branch: str = field(default_factory=lambda: os.getenv("DEVIN_DEFAULT_BRANCH", "main"))
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./courseforge.db"))
    testing: bool = field(default_factory=lambda: _bool_env("TESTING", False))
    poll_interval_seconds: int = field(default_factory=lambda: int(os.getenv("DEVIN_POLL_INTERVAL_SECONDS", "30")))
    poll_timeout_seconds: int = field(default_factory=lambda: int(os.getenv("DEVIN_POLL_TIMEOUT_SECONDS", "14400")))

    @property
    def normalized_base_url(self) -> str:
        return self.devin_api_base_url.rstrip("/") or "https://api.devin.ai"

    @property
    def required_env_status(self) -> dict[str, bool]:
        return {
            "DEVIN_API_KEY": bool(self.devin_api_key),
            "DEVIN_API_BASE_URL": bool(self.devin_api_base_url),
            "DEVIN_REPO_URL": bool(self.devin_repo_url),
            "DEVIN_DEFAULT_BRANCH": bool(self.devin_default_branch),
        }

    @property
    def optional_env_status(self) -> dict[str, bool]:
        return {
            "DEVIN_ORG_ID": bool(self.devin_org_id),
            "DEVIN_PROJECT_ID": bool(self.devin_project_id),
        }

    @property
    def missing_required_env(self) -> list[str]:
        return [key for key, ok in self.required_env_status.items() if not ok]


def get_settings() -> Settings:
    return Settings()
