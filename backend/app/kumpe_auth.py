from dataclasses import dataclass
from typing import Any

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db_session
from app.kumpe_auth_config import settings
from app.kumpe_permissions import extract_api_permissions, has_permission
from app.kumpe_token import merge_profile_claims, validate_access_token, validate_id_token
from app.models import User
from app.security_flag_access import evaluate_security_flag_access
from app.user_service import normalize_email, resolve_user_from_claims

security = HTTPBearer(auto_error=False)
SECURITY_FLAGS_TOKEN_HEADER = "X-SecurityFlags-Token"


@dataclass
class AuthContext:
    claims: dict[str, Any]
    user: User | None
    dev_mode: bool = False


def _build_dev_context(email: str, db: Session) -> AuthContext:
    normalized = normalize_email(email)
    user = db.query(User).filter(User.email == normalized).first()
    return AuthContext(
        claims={"sub": normalized, "email": normalized, "name": user.display_name if user else normalized.split("@")[0]},
        user=user,
        dev_mode=True,
    )


def get_bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    return credentials.credentials


def get_optional_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    x_kpanel_dev_email: str | None = Header(default=None),
    x_id_token: str | None = Header(default=None, alias="X-Id-Token"),
    db: Session = Depends(get_db_session),
) -> AuthContext | None:
    if settings.dev_auth_enabled and x_kpanel_dev_email:
        try:
            return _build_dev_context(x_kpanel_dev_email, db)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if credentials is None or credentials.scheme.lower() != "bearer":
        return None

    token = credentials.credentials
    api_claims = validate_access_token(token)

    if not x_id_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "OIDC ID token required — send X-Id-Token header. "
                "API access tokens carry permissions only; email and profile are on the ID token."
            ),
        )

    claims = merge_profile_claims(api_claims, validate_id_token(x_id_token))

    user = resolve_user_from_claims(claims, db)
    return AuthContext(claims=claims, user=user)


def get_auth_context(
    auth: AuthContext | None = Depends(get_optional_auth_context),
) -> AuthContext:
    if auth is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    return auth


def _enforce_security_flags_or_raise(auth: AuthContext, security_flags_token: str | None) -> None:
    denied = evaluate_security_flag_access(
        dev_mode=auth.dev_mode,
        security_flags_token=security_flags_token,
    )
    if denied is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=denied.get("message", "Access denied"),
        )


def require_authenticated(
    auth: AuthContext = Depends(get_auth_context),
    x_security_flags_token: str | None = Header(default=None, alias=SECURITY_FLAGS_TOKEN_HEADER),
) -> AuthContext:
    _enforce_security_flags_or_raise(auth, x_security_flags_token)
    return auth


def require_user(auth: AuthContext = Depends(get_auth_context)) -> tuple[AuthContext, User]:
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return auth, auth.user


def require_permission(permission: str):
    def _dependency(
        auth: AuthContext = Depends(get_auth_context),
        x_security_flags_token: str | None = Header(default=None, alias=SECURITY_FLAGS_TOKEN_HEADER),
    ) -> AuthContext:
        if auth.dev_mode:
            return auth

        _enforce_security_flags_or_raise(auth, x_security_flags_token)

        permissions = extract_api_permissions(auth.claims.get("scope"))
        if not has_permission(permissions, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {permission}",
            )
        return auth

    return _dependency


def require_user_with_permission(permission: str):
    def _dependency(
        auth: AuthContext = Depends(require_permission(permission)),
    ) -> tuple[AuthContext, User]:
        if auth.user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        return auth, auth.user

    return _dependency
