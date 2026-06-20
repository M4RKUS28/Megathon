from fastapi import APIRouter

from src.api.v1.schemas.diagnostics import (
    ProviderCheckResponse,
    ProviderDiagnosticsResponse,
)
from src.core.tenant import AppUserDep
from src.services.diagnostics import probe_providers

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@router.get("/providers", response_model=ProviderDiagnosticsResponse)
async def get_provider_diagnostics(user: AppUserDep) -> ProviderDiagnosticsResponse:
    """Live-probe each external provider with its configured key.

    Verifies whether the API keys from the `.env` actually work (reachability +
    authentication). The probes never trigger billable generation. The frontend
    logs the results to the browser console.
    """
    checks = await probe_providers()
    return ProviderDiagnosticsResponse(
        providers=[ProviderCheckResponse(**c.as_dict()) for c in checks]
    )
