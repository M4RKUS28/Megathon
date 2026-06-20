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
_MANAGED_REALM_ROLES = {"admin", "course_creator", "user"}


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


def _user_payload(
    *,
    username: str,
    email: str,
    first_name: str,
    last_name: str,
    company_slug: str,
) -> dict:
    return {
        "username": username,
        "email": email,
        "firstName": first_name,
        "lastName": last_name,
        "enabled": True,
        "emailVerified": True,
        "attributes": {"company_slug": [company_slug]},
    }


async def _create_user(
    client: httpx.AsyncClient,
    token: str,
    *,
    username: str,
    email: str,
    first_name: str,
    last_name: str,
    password: str,
    company_slug: str,
) -> str:
    payload = _user_payload(
        username=username,
        email=email,
        first_name=first_name,
        last_name=last_name,
        company_slug=company_slug,
    )
    payload["credentials"] = [{"type": "password", "value": password, "temporary": False}]
    resp = await client.post(
        f"{_admin_base()}/users",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
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


async def _update_user(
    client: httpx.AsyncClient,
    token: str,
    user_id: str,
    *,
    username: str,
    email: str,
    first_name: str,
    last_name: str,
    company_slug: str,
) -> None:
    resp = await client.put(
        f"{_admin_base()}/users/{user_id}",
        headers={"Authorization": f"Bearer {token}"},
        json=_user_payload(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            company_slug=company_slug,
        ),
    )
    resp.raise_for_status()


async def _reset_password(
    client: httpx.AsyncClient, token: str, user_id: str, password: str
) -> None:
    resp = await client.put(
        f"{_admin_base()}/users/{user_id}/reset-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"type": "password", "value": password, "temporary": False},
    )
    resp.raise_for_status()


async def _realm_role_rep(client: httpx.AsyncClient, token: str, role_name: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get(f"{_admin_base()}/roles/{role_name}", headers=headers)
    if resp.status_code == 404:
        create = await client.post(
            f"{_admin_base()}/roles",
            headers=headers,
            json={"name": role_name},
        )
        create.raise_for_status()
        resp = await client.get(f"{_admin_base()}/roles/{role_name}", headers=headers)
    resp.raise_for_status()
    return resp.json()


async def _current_realm_roles(client: httpx.AsyncClient, token: str, user_id: str) -> list[dict]:
    resp = await client.get(
        f"{_admin_base()}/users/{user_id}/role-mappings/realm",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json()


async def _sync_realm_roles(
    client: httpx.AsyncClient, token: str, user_id: str, role_names: list[str]
) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    desired = set(role_names)
    desired_reps = [await _realm_role_rep(client, token, name) for name in role_names]
    current = await _current_realm_roles(client, token, user_id)
    stale = [
        role
        for role in current
        if role.get("name") in _MANAGED_REALM_ROLES and role.get("name") not in desired
    ]
    if stale:
        resp = await client.request(
            "DELETE",
            f"{_admin_base()}/users/{user_id}/role-mappings/realm",
            headers=headers,
            json=stale,
        )
        resp.raise_for_status()
    if desired_reps:
        # Idempotent: re-assigning an already-mapped role is a no-op (204).
        resp = await client.post(
            f"{_admin_base()}/users/{user_id}/role-mappings/realm",
            headers=headers,
            json=desired_reps,
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
    company_slug: str | None = None,
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
        slug = company_slug or settings.demo_company_slug
        if user_id is None:
            user_id = await _create_user(
                client,
                token,
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=password,
                company_slug=slug,
            )
            logger.info("Created Keycloak user '%s'", username)
        else:
            await _update_user(
                client,
                token,
                user_id,
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                company_slug=slug,
            )
        await _reset_password(client, token, user_id, password)
        await _sync_realm_roles(client, token, user_id, realm_roles)
        return user_id
