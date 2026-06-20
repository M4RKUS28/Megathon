from fastapi import APIRouter

from src.api.v1.schemas.me import CompanySummary, MeResponse
from src.core.tenant import AppUserDep, CompanyDep

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=MeResponse)
async def get_me(user: AppUserDep, company: CompanyDep) -> MeResponse:
    """Return the current user with their resolved tenant (auto-provisioned)."""
    return MeResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        company=CompanySummary(
            id=company.id, name=company.name, slug=company.slug, status=company.status
        ),
    )
