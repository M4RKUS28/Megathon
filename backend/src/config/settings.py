from pydantic import computed_field
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
    keycloak_realm: str = "app"
    keycloak_client_id: str = "app-frontend"
    keycloak_client_secret: str = "changeme"

    # App
    secret_key: str = "changeme"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost", "http://localhost:5173"]

    # Redis / Queue
    redis_url: str = "redis://redis:6379/0"

    # Devin API (course generation pipeline) — v3 org-scoped API
    devin_api_key: str = ""
    devin_api_base_url: str = "https://api.devin.ai/v3"
    devin_org_id: str = ""
    devin_snapshot_id: str = ""
    devin_playbook_id: str = ""
    devin_max_acu_limit: int = 20

    # Platform / multi-tenant
    demo_company_slug: str = "acme"
    platform_public_url: str = "http://localhost"

    # Course hosting: path to the prebuilt Vite course-template dist/ that the
    # worker publishes per course. Built into the image; overridable locally.
    # (Legacy single-renderer path — retained for backwards compatibility.)
    course_template_dist: str = "/app/course_template_dist"

    # Phase 3: per-course Vite/React/TS app template. The builder copies this
    # source, bakes in course.json/asset_map.json and runs `npm run build` to
    # produce each course's OWN dist/. Falls back to a static renderer if the
    # build toolchain is unavailable.
    course_app_template: str = "/app/course_app_template"
    course_build_enabled: bool = True
    course_build_timeout: int = 600

    # Google Gemini (agentic planner / script-writer pipeline)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

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
        return f"http://{self.keycloak_host}:{self.keycloak_port}"

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
