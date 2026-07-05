from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.kumpe_auth import AuthContext
from app.kumpe_permissions import extract_api_permissions
from app.models import DeviceRegistration, UserIdentity
from app.serializers import serialize_user
from app.user_service import (
    DEFAULT_TIMEZONE,
    claims_display_name,
    claims_email,
    claims_timezone,
    ensure_identity_for_user,
    resolve_user_from_claims,
    sync_user_profile_from_claims,
)


def resolve_user_permissions(auth: AuthContext) -> list[str]:
    """Return RBAC permissions granted to the signed-in application user (from API access token scope)."""
    return extract_api_permissions(auth.claims.get("scope"))


def build_session_state(auth: AuthContext, db: Session, permissions: list[str]) -> dict:
    user = auth.user or resolve_user_from_claims(auth.claims, db)

    if user is None:
        try:
            email = claims_email(auth.claims)
            display_name = claims_display_name(auth.claims, email)
            timezone = claims_timezone(auth.claims) or DEFAULT_TIMEZONE
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

        return {
            "status": "needs_account",
            "permissions": permissions,
            "pending": {
                "email": email,
                "provider_name": "kumpecloud",
                "display_name": display_name,
                "timezone": timezone,
            },
        }

    user = sync_user_profile_from_claims(user, auth.claims, db)
    auth.user = user
    ensure_identity_for_user(user, auth.claims, db)

    identities = (
        db.query(UserIdentity)
        .filter(UserIdentity.user_id == user.id)
        .order_by(UserIdentity.provider_name.asc())
        .all()
    )
    devices = (
        db.query(DeviceRegistration)
        .filter(DeviceRegistration.user_id == user.id)
        .order_by(DeviceRegistration.created_at.desc())
        .all()
    )

    return {
        "status": "authenticated",
        "permissions": permissions,
        "user": serialize_user(user, identities, devices, db),
    }


def build_unauthenticated_state() -> dict[str, Any]:
    return {"status": "unauthenticated", "permissions": []}
