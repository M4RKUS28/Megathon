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
