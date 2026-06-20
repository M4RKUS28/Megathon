from functools import lru_cache
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt

from src.config.settings import settings

bearer_scheme = HTTPBearer()


@lru_cache(maxsize=1)
def _get_jwks() -> dict:
    """Cached JWKS fetch — refreshed on process restart."""
    resp = httpx.get(settings.keycloak_jwks_uri, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _decode_token(token: str) -> dict:
    """Validate and decode a Keycloak JWT using public JWKS keys."""
    try:
        jwks = _get_jwks()
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.keycloak_client_id,
            options={"verify_at_hash": False},
        )
        return payload
    except ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


class TokenData:
    def __init__(self, payload: dict) -> None:
        self.user_id: str = payload["sub"]
        self.email: str = payload.get("email", "")
        self.username: str = payload.get("preferred_username", "")
        self.roles: list[str] = payload.get("realm_access", {}).get("roles", [])
        self.raw: dict = payload

    def has_role(self, role: str) -> bool:
        return role in self.roles


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> TokenData:
    payload = _decode_token(credentials.credentials)
    return TokenData(payload)


def require_role(role: str):
    """Factory for role-restricted dependencies."""

    async def _check(user: Annotated[TokenData, Depends(get_current_user)]) -> TokenData:
        if not user.has_role(role):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return _check
