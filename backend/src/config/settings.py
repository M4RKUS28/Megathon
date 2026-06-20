from pydantic import AliasChoices, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # PostgreSQL
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "appdb"
    postgres_user: str = "appuser"
    postgres_password: str = "changeme"

    # MinIO
    minio_host: str = "minio"
    minio_port: int = 9000
    minio_root_user: str = "minioadmin"
    minio_root_password: str = "changeme"
    minio_bucket: str = "uploads"
    courses_bucket: str = "courses"
    minio_presigned_expiry: int = 3600
    minio_secure: bool = False
    # Browser-reachable base URL for presigned URLs (proxied to MinIO by nginx
    # at /storage). The internal endpoint (minio:9000) is not resolvable from
    # the user's browser.
    minio_public_url: str = "http://localhost/storage"

    # Keycloak
    keycloak_host: str = "keycloak"
    keycloak_port: int = 8080
    keycloak_relative_path: str = Field(
        default="",
        validation_alias=AliasChoices("KEYCLOAK_RELATIVE_PATH", "KC_HTTP_RELATIVE_PATH"),
    )
    keycloak_realm: str = "app"
    keycloak_client_id: str = "app-frontend"
    keycloak_client_secret: str = "changeme"
    # Admin credentials (master realm) used to provision demo users on startup.
    # Leave the password empty to disable Keycloak user provisioning.
    keycloak_admin_user: str = Field(
        default="admin", validation_alias=AliasChoices("KEYCLOAK_ADMIN", "KEYCLOAK_ADMIN_USER")
    )
    keycloak_admin_password: str = ""

    # App
    secret_key: str = "changeme"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost", "http://localhost:5173"]

    # Redis / Queue
    redis_url: str = "redis://redis:6379/0"

    # Devin API (course generation pipeline) — v3 org-scoped API
    devin_api_key: str = Field(
        default="", validation_alias=AliasChoices("DEVIN_API_KEY", "DEVIN")
    )
    devin_api_base_url: str = "https://api.devin.ai/v3"
    # Public web app base used to build human-facing session links shown in the UI.
    devin_app_base_url: str = "https://app.devin.ai"
    devin_org_id: str = ""
    devin_snapshot_id: str = ""
    devin_playbook_id: str = ""
    devin_max_acu_limit: int = 20

    # Platform / multi-tenant
    demo_company_slug: str = "acme"
    platform_public_url: str = "http://localhost"

    # Phase 3: per-course Vite/React/TS app template. The builder copies this
    # source, bakes in course.json/asset_map.json and runs `npm run build` to
    # produce each course's OWN dist/. Falls back to a static renderer if the
    # build toolchain is unavailable.
    course_app_template: str = "/app/course_app_template"
    course_build_enabled: bool = True
    course_build_timeout: int = 600
    # Phase 3: use a real Devin coding session to author the per-course Vite app
    # (it returns the project source files). Falls back to the template build.
    course_build_use_devin: bool = False
    # Max repair iterations when a Devin-generated build fails. Each iteration
    # sends the exact error logs back to a new Devin session for a fix attempt.
    course_build_repair_max_retries: int = 2

    # Google Gemini (agentic planner / script-writer pipeline + media)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    # Nano-Banana image generation + Gemini TTS (reuse gemini_api_key).
    gemini_image_model: str = "gemini-3.1-flash-image"
    gemini_tts_model: str = "gemini-3.1-flash-tts-preview"
    gemini_tts_voice: str = "Kore"

    # Cala MCP — company knowledge source for the planner agent (Phase 1).
    # `cala_mcp_url` is a streamable-HTTP MCP endpoint; tools are called over it.
    cala_api_key: str = Field(
        default="", validation_alias=AliasChoices("CALA_API_KEY", "CALA")
    )
    cala_mcp_url: str = ""
    cala_timeout: int = 30

    # PixVerse — image/video generation (Phase 2.5 asset pipeline).
    pixverse_api_key: str = Field(
        default="", validation_alias=AliasChoices("PIXVERSE_API_KEY", "PIX_VERSE")
    )
    pixverse_api_base_url: str = "https://app-api.pixverse.ai"
    pixverse_timeout: int = 300

    # Asset-pipeline provider selection. "auto" picks the best configured
    # provider per asset type and falls back to the branded SVG placeholder.
    asset_image_provider: str = "auto"  # auto | nano_banana | pixverse | placeholder
    asset_video_provider: str = "auto"  # auto | pixverse | placeholder
    asset_audio_provider: str = "auto"  # auto | gemini_tts | placeholder

    @computed_field
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field
    @property
    def keycloak_url(self) -> str:
        base = f"http://{self.keycloak_host}:{self.keycloak_port}"
        path = self.keycloak_relative_path.strip()
        if not path or path == "/":
            return base
        return f"{base}/{path.strip('/')}"

    @computed_field
    @property
    def keycloak_jwks_uri(self) -> str:
        return (
            f"{self.keycloak_url}/realms/{self.keycloak_realm}"
            f"/protocol/openid-connect/certs"
        )

    @computed_field
    @property
    def minio_endpoint(self) -> str:
        return f"{self.minio_host}:{self.minio_port}"


settings = Settings()
