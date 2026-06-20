from pydantic import BaseModel


class ProviderCheckResponse(BaseModel):
    provider: str
    label: str
    configured: bool
    ok: bool
    detail: str
    status: int | None = None
    latency_ms: int | None = None


class ProviderDiagnosticsResponse(BaseModel):
    providers: list[ProviderCheckResponse]
