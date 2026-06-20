"""Minimal async Keycloak Admin REST client.

Only the operations needed to provision demo users at startup are implemented:
obtain an admin token (master realm, ``admin-cli`` public client), find or create
a user, and assign realm roles. All operations are idempotent. Callers are
expected to treat failures as best-effort (Keycloak may be unavailable or admin
credentials may be unset), so transport/HTTP errors propagate for the caller to
log-and-continue.
"""

import logging

import httpx

from src.config.settings import settings

logger = logging.getLogger(__name__)

_ADMIN_REALM = "master"
_ADMIN_CLIENT_ID = "admin-cli"


def _admin_base() -> str:
    return f"{settings.keycloak_url}/admin/realms/{settings.keycloak_realm}"


async def _get_token(client: httpx.AsyncClient) -> str:
    resp = await client.post(
        f"{settings.keycloak_url}/realms/{_ADMIN_REALM}/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": _ADMIN_CLIENT_ID,
            "username": settings.keycloak_admin_user,
            "password": settings.keycloak_admin_password,
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


async def _find_user_id(client: httpx.AsyncClient, token: str, username: str) -> str | None:
    resp = await client.get(
        f"{_admin_base()}/users",
        params={"username": username, "exact": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    users = resp.json()
    return users[0]["id"] if users else None


async def _create_user(
    client: httpx.AsyncClient,
    token: str,
    *,
    username: str,
    email: str,
    first_name: str,
    last_name: str,
    password: str,
) -> str:
    resp = await client.post(
        f"{_admin_base()}/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "username": username,
            "email": email,
            "firstName": first_name,
            "lastName": last_name,
            "enabled": True,
            "emailVerified": True,
            "credentials": [{"type": "password", "value": password, "temporary": False}],
        },
    )
    # 409 = created concurrently; fall back to a lookup.
    if resp.status_code == 409:
        existing = await _find_user_id(client, token, username)
        if existing:
            return existing
    resp.raise_for_status()
    # On 201 the new user's URL is returned in the Location header.
    location = resp.headers.get("Location", "")
    return location.rstrip("/").rsplit("/", 1)[-1]


async def _assign_realm_roles(
    client: httpx.AsyncClient, token: str, user_id: str, role_names: list[str]
) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    reps = []
    for name in role_names:
        r = await client.get(f"{_admin_base()}/roles/{name}", headers=headers)
        r.raise_for_status()
        reps.append(r.json())
    if reps:
        # Idempotent: re-assigning an already-mapped role is a no-op (204).
        resp = await client.post(
            f"{_admin_base()}/users/{user_id}/role-mappings/realm",
            headers=headers,
            json=reps,
        )
        resp.raise_for_status()


async def ensure_user(
    *,
    username: str,
    email: str,
    first_name: str,
    last_name: str,
    password: str,
    realm_roles: list[str],
) -> str | None:
    """Ensure a Keycloak user exists with the given realm roles.

    Returns the Keycloak user id (the token ``sub``, used as the app ``User.id``),
    or ``None`` when admin provisioning is disabled (no admin password set).
    """
    if not settings.keycloak_admin_password:
        logger.info("Keycloak admin password not set; skipping user provisioning")
        return None
    async with httpx.AsyncClient(timeout=15) as client:
        token = await _get_token(client)
        user_id = await _find_user_id(client, token, username)
        if user_id is None:
            user_id = await _create_user(
                client,
                token,
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=password,
            )
            logger.info("Created Keycloak user '%s'", username)
        await _assign_realm_roles(client, token, user_id, realm_roles)
        return user_id
