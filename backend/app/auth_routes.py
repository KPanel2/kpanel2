from typing import Any

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.db import get_db_session
from app.kumpe_auth import SECURITY_FLAGS_TOKEN_HEADER, AuthContext, get_optional_auth_context
from app.kumpe_auth_config import settings as kumpe_settings
from app.kumpe_permissions import ELEVATED_KPANEL_PERMISSIONS
from app.security_flag_access import build_auth_debug, evaluate_security_flag_access
from app.session_service import (
    build_session_state,
    build_unauthenticated_state,
    resolve_user_permissions,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.get("/config")
def auth_config() -> dict[str, Any]:
    """SPA / application-user OIDC settings (app ID — not M2M)."""
    return {
        "logtoEndpoint": kumpe_settings.logto_endpoint,
        "appId": kumpe_settings.logto_app_id,
        "apiResource": kumpe_settings.api_resource,
        "secondaryApiResource": kumpe_settings.secondary_api_resource,
        "apiResources": kumpe_settings.api_resources,
        "devAuthEnabled": kumpe_settings.dev_auth_enabled,
        "authDebugEnabled": kumpe_settings.auth_debug_enabled,
    }


@router.get("/permissions")
def auth_permissions() -> dict[str, Any]:
    """Permission scope names to request during application-user OAuth sign-in."""
    return {
        "apiResource": kumpe_settings.api_resource,
        "permissions": kumpe_settings.oauth_permissions,
        "elevatedPermissions": list(ELEVATED_KPANEL_PERMISSIONS),
        "secondaryApiResource": kumpe_settings.secondary_api_resource,
        "secondaryPermissions": kumpe_settings.secondary_oauth_permissions,
    }


@router.get("/session")
def auth_session(
    auth: AuthContext | None = Depends(get_optional_auth_context),
    x_security_flags_token: str | None = Header(default=None, alias=SECURITY_FLAGS_TOKEN_HEADER),
    db: Session = Depends(get_db_session),
) -> dict:
    if auth is None:
        return build_unauthenticated_state()

    debug = (
        build_auth_debug(dev_mode=auth.dev_mode, security_flags_token=x_security_flags_token)
        if kumpe_settings.auth_debug_enabled
        else None
    )

    denied = evaluate_security_flag_access(
        dev_mode=auth.dev_mode,
        security_flags_token=x_security_flags_token,
    )
    if denied is not None:
        if debug is not None:
            denied["debug"] = debug
        return denied

    permissions = resolve_user_permissions(auth)
    session = build_session_state(auth, db, permissions)
    if debug is not None:
        session["debug"] = debug
    return session


@router.post("/logout")
def auth_logout() -> dict:
    return {"status": "logged_out"}
