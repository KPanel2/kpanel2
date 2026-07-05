from typing import Any

from sqlalchemy.orm import Session

from app.kumpe_permissions import KPANEL_PROVIDER_NAME
from app.models import User, UserIdentity
from app.session_auth import now_utc

DEFAULT_TIMEZONE = "America/Chicago"


def _is_valid_timezone(tz: str) -> bool:
    try:
        from zoneinfo import ZoneInfo

        ZoneInfo(tz)
        return True
    except (KeyError, ModuleNotFoundError):
        return False


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise ValueError("A valid email address is required")
    return normalized


def claims_email(claims: dict[str, Any]) -> str:
    email = claims.get("email") or claims.get("username")
    if not isinstance(email, str) or not email.strip():
        raise ValueError("ID token missing email claim — ensure the email scope is requested at sign-in")
    return normalize_email(email)


def claims_display_name(claims: dict[str, Any], email: str) -> str:
    for key in ("name", "preferred_username"):
        value = claims.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return email.split("@")[0] or email


def claims_custom_data(claims: dict[str, Any]) -> dict[str, Any]:
    raw = claims.get("custom_data")
    if not isinstance(raw, dict):
        raw = claims.get("customData")
    return raw if isinstance(raw, dict) else {}


def claims_timezone(claims: dict[str, Any]) -> str | None:
    timezone = claims_custom_data(claims).get("timezone")
    if isinstance(timezone, str) and timezone.strip():
        return timezone.strip()
    return None


def sync_user_profile_from_claims(user: User, claims: dict[str, Any], db: Session) -> User:
    """Mirror KumpeCloud Auth profile fields onto the local user record."""
    changed = False

    try:
        email = claims_email(claims)
    except ValueError:
        email = user.email
    else:
        if user.email != email:
            user.email = email
            changed = True

    display_name = claims_display_name(claims, email)
    if user.display_name != display_name:
        user.display_name = display_name
        changed = True

    timezone = claims_timezone(claims)
    if timezone is not None and _is_valid_timezone(timezone) and user.timezone != timezone:
        user.timezone = timezone
        changed = True

    if changed:
        user.updated_at = now_utc()
        db.commit()
        db.refresh(user)

    return user


def resolve_user_from_claims(claims: dict[str, Any], db: Session) -> User | None:
    subject = str(claims.get("sub", ""))
    if not subject:
        return None

    identity = (
        db.query(UserIdentity)
        .filter(
            UserIdentity.provider_name == KPANEL_PROVIDER_NAME,
            UserIdentity.provider_subject == subject,
        )
        .first()
    )
    if identity is not None:
        return db.get(User, identity.user_id)

    try:
        email = claims_email(claims)
    except ValueError:
        return None

    return db.query(User).filter(User.email == email).first()


def ensure_identity_for_user(user: User, claims: dict[str, Any], db: Session) -> UserIdentity:
    subject = str(claims["sub"])
    identity = (
        db.query(UserIdentity)
        .filter(
            UserIdentity.provider_name == KPANEL_PROVIDER_NAME,
            UserIdentity.provider_subject == subject,
        )
        .first()
    )
    email = claims_email(claims)
    display_name = claims_display_name(claims, email)
    timestamp = now_utc()

    if identity is None:
        identity = UserIdentity(
            user_id=user.id,
            provider_name=KPANEL_PROVIDER_NAME,
            provider_subject=subject,
            email=email,
            display_name=display_name,
            created_at=timestamp,
            updated_at=timestamp,
        )
        db.add(identity)
    else:
        identity.user_id = user.id
        identity.email = email
        identity.display_name = display_name
        identity.updated_at = timestamp

    db.commit()
    db.refresh(identity)
    return identity
