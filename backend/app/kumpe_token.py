from typing import Any

import jwt
from fastapi import HTTPException, status
from jwt import PyJWKClient

from app.kumpe_auth_config import settings

_jwks_client: PyJWKClient | None = None


def get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(settings.jwks_uri)
    return _jwks_client


def validate_access_token(token: str, *, audience: str | None = None) -> dict[str, Any]:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing access token")

    expected_audience = audience or settings.api_resource

    try:
        signing_key = get_jwks_client().get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256", "ES384", "ES512"],
            issuer=settings.issuer,
            audience=expected_audience,
            options={"require": ["exp", "iss", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired") from exc
    except jwt.InvalidAudienceError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid audience — expected '{expected_audience}'",
        ) from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {exc}",
        ) from exc


def validate_id_token(token: str) -> dict[str, Any]:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing ID token")

    if not settings.logto_app_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ID token validation is not configured",
        )

    try:
        signing_key = get_jwks_client().get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256", "ES384", "ES512"],
            issuer=settings.issuer,
            audience=settings.logto_app_id,
            options={"require": ["exp", "iss", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="ID token expired") from exc
    except jwt.InvalidAudienceError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid ID token audience — expected '{settings.logto_app_id}'",
        ) from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"ID token validation failed: {exc}",
        ) from exc


_PROFILE_CLAIM_KEYS = (
    # Logto ID token (profile + email scopes): name, picture, username, email
    "email",
    "email_verified",
    "username",
    "name",
    "preferred_username",
    "picture",
)

_CUSTOM_DATA_CLAIM_KEYS = ("custom_data", "customData")


def merge_profile_claims(api_claims: dict[str, Any], id_claims: dict[str, Any]) -> dict[str, Any]:
    """Attach identity claims from the OIDC ID token onto API access-token claims.

    API resource access tokens carry sub + scope (RBAC). Email and profile live on the
    ID token per KumpeCloud / Logto — see Console → ID token claims.
    """
    api_sub = str(api_claims.get("sub", ""))
    id_sub = str(id_claims.get("sub", ""))
    if not api_sub or api_sub != id_sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ID token subject does not match API access token",
        )

    merged = dict(api_claims)
    for key in _PROFILE_CLAIM_KEYS:
        value = id_claims.get(key)
        if isinstance(value, str) and value.strip():
            merged[key] = value.strip()

    for key in _CUSTOM_DATA_CLAIM_KEYS:
        value = id_claims.get(key)
        if isinstance(value, dict):
            merged[key] = value

    custom_data = merged.get("custom_data")
    if not isinstance(custom_data, dict):
        fallback = merged.get("customData")
        if isinstance(fallback, dict):
            merged["custom_data"] = fallback

    return merged
