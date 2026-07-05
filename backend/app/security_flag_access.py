"""Security-flag access evaluation (kept separate from kumpe_auth to avoid import cycles)."""

from typing import Any

from fastapi import HTTPException

from app.kumpe_auth_config import settings as kumpe_settings
from app.kumpe_token import validate_access_token
from app.security_flags import (
    extract_security_flag_permissions,
    find_blocking_security_flags,
    security_flag_denial_message,
)


def evaluate_security_flag_access(
    *,
    dev_mode: bool,
    security_flags_token: str | None,
) -> dict[str, Any] | None:
    """Return access_denied only when a blocking security flag scope is present on the token.

    KumpeCloud only returns scopes assigned to the user — no securityflags:* scopes means
    the user is clear. A missing or invalid secondary token is treated as no flags.
    """
    if dev_mode or not kumpe_settings.secondary_api_resource:
        return None

    if not security_flags_token:
        return None

    try:
        claims = validate_access_token(
            security_flags_token,
            audience=kumpe_settings.secondary_api_resource,
        )
    except HTTPException:
        return None

    blocked = find_blocking_security_flags(extract_security_flag_permissions(claims.get("scope")))
    if blocked:
        return {
            "status": "access_denied",
            "permissions": [],
            "message": security_flag_denial_message(blocked),
        }
    return None
