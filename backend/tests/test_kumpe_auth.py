import pytest
from fastapi import HTTPException

from app.kumpe_auth import (
    AuthContext,
    get_auth_context,
    get_bearer_token,
    get_optional_auth_context,
    require_authenticated,
    require_permission,
    require_superadmin,
    require_user,
    require_user_with_permission,
)
from app.kumpe_permissions import Permissions
from tests.factories import seed_user


class _Credentials:
    def __init__(self, token: str, scheme: str = "Bearer"):
        self.credentials = token
        self.scheme = scheme


def test_get_bearer_token_accepts_valid_credentials():
    creds = _Credentials("access-token")

    assert get_bearer_token(credentials=creds) == "access-token"


@pytest.mark.parametrize("credentials", [None, _Credentials("token", scheme="Basic")])
def test_get_bearer_token_rejects_missing_or_invalid_scheme(credentials):
    with pytest.raises(HTTPException) as exc_info:
        get_bearer_token(credentials=credentials)
    assert exc_info.value.status_code == 401


def test_get_optional_auth_context_bearer_flow(db_session, monkeypatch):
    user = seed_user(db_session, email="bearer@example.com")
    api_claims = {"sub": "bearer-sub", "scope": Permissions.DEVICES_READ}
    id_claims = {"sub": "bearer-sub", "email": "bearer@example.com", "name": "Bearer User"}
    merged = {**api_claims, **id_claims}

    monkeypatch.setattr("app.kumpe_auth_config.settings.dev_auth_enabled", False)
    monkeypatch.setattr("app.kumpe_auth.validate_access_token", lambda token: api_claims)
    monkeypatch.setattr("app.kumpe_auth.validate_id_token", lambda token: id_claims)
    monkeypatch.setattr("app.kumpe_auth.merge_profile_claims", lambda api, id_: merged)

    auth = get_optional_auth_context(
        credentials=_Credentials("access-token"),
        x_kpanel_dev_email=None,
        x_id_token="id-token",
        db=db_session,
    )

    assert auth is not None
    assert auth.dev_mode is False
    assert auth.user is not None
    assert auth.user.id == user.id
    assert auth.claims["email"] == "bearer@example.com"


def test_get_optional_auth_context_bearer_requires_id_token(db_session, monkeypatch):
    monkeypatch.setattr("app.kumpe_auth_config.settings.dev_auth_enabled", False)
    monkeypatch.setattr(
        "app.kumpe_auth.validate_access_token",
        lambda token: {"sub": "sub", "scope": Permissions.DEVICES_READ},
    )

    with pytest.raises(HTTPException) as exc_info:
        get_optional_auth_context(
            credentials=_Credentials("access-token"),
            x_kpanel_dev_email=None,
            x_id_token=None,
            db=db_session,
        )
    assert exc_info.value.status_code == 401
    assert "X-Id-Token" in exc_info.value.detail


def test_get_auth_context_requires_auth():
    with pytest.raises(HTTPException) as exc_info:
        get_auth_context(auth=None)
    assert exc_info.value.status_code == 401


def test_get_auth_context_returns_context():
    auth = AuthContext(claims={"sub": "x"}, user=None)
    assert get_auth_context(auth=auth) is auth


def test_require_authenticated_dev_mode_bypasses_security_flags(db_session, dev_auth_enabled):
    user = seed_user(db_session)
    auth = AuthContext(claims={"sub": user.email, "email": user.email}, user=user, dev_mode=True)

    assert require_authenticated(auth=auth, x_security_flags_token=None) is auth


def test_require_authenticated_raises_on_security_flag_denial(monkeypatch):
    auth = AuthContext(claims={"sub": "user"}, user=None, dev_mode=False)
    monkeypatch.setattr(
        "app.kumpe_auth.evaluate_security_flag_access",
        lambda **kwargs: {"status": "access_denied", "message": "blocked"},
    )

    with pytest.raises(HTTPException) as exc_info:
        require_authenticated(auth=auth, x_security_flags_token="flags-token")
    assert exc_info.value.status_code == 403


def test_require_user_returns_user(db_session):
    user = seed_user(db_session)
    auth = AuthContext(claims={"sub": "sub"}, user=user)

    returned_auth, returned_user = require_user(auth=auth)

    assert returned_auth is auth
    assert returned_user is user


def test_require_user_rejects_missing_user():
    with pytest.raises(HTTPException) as exc_info:
        require_user(auth=AuthContext(claims={"sub": "sub"}, user=None))
    assert exc_info.value.status_code == 401


def test_require_user_rejects_deactivated_account(db_session):
    user = seed_user(db_session)
    user.is_active = False
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        require_user(auth=AuthContext(claims={"sub": "sub"}, user=user, dev_mode=False))
    assert exc_info.value.status_code == 403


def test_require_superadmin_dev_mode_bypass(db_session, dev_auth_enabled):
    user = seed_user(db_session)
    auth = AuthContext(claims={}, user=user, dev_mode=True)
    assert require_superadmin(auth=auth, x_security_flags_token=None) is auth


def test_require_superadmin_rejects_missing_permission():
    auth = AuthContext(
        claims={"scope": Permissions.DEVICES_READ},
        user=None,
        dev_mode=False,
    )

    with pytest.raises(HTTPException) as exc_info:
        require_superadmin(auth=auth, x_security_flags_token=None)
    assert exc_info.value.status_code == 403


def test_require_superadmin_accepts_superadmin_scope():
    auth = AuthContext(
        claims={"scope": Permissions.SUPERADMIN},
        user=None,
        dev_mode=False,
    )

    assert require_superadmin(auth=auth, x_security_flags_token=None) is auth


def test_require_permission_dev_mode_bypass(dev_auth_enabled):
    auth = AuthContext(claims={}, user=None, dev_mode=True)
    dependency = require_permission(Permissions.DEVICES_WRITE)

    assert dependency(auth=auth, x_security_flags_token=None) is auth


def test_require_permission_rejects_missing_scope():
    auth = AuthContext(
        claims={"scope": Permissions.DEVICES_READ},
        user=None,
        dev_mode=False,
    )
    dependency = require_permission(Permissions.DEVICES_WRITE)

    with pytest.raises(HTTPException) as exc_info:
        dependency(auth=auth, x_security_flags_token=None)
    assert exc_info.value.status_code == 403


def test_require_permission_admin_bypass():
    auth = AuthContext(
        claims={"scope": Permissions.ADMIN},
        user=None,
        dev_mode=False,
    )
    dependency = require_permission(Permissions.HOUSEHOLDS_WRITE)

    assert dependency(auth=auth, x_security_flags_token=None) is auth


def test_require_user_with_permission_returns_user(db_session):
    user = seed_user(db_session)
    auth = AuthContext(
        claims={"scope": Permissions.DEVICES_READ},
        user=user,
        dev_mode=False,
    )
    dependency = require_user_with_permission(Permissions.DEVICES_READ)

    returned_auth, returned_user = dependency(auth=auth)

    assert returned_auth is auth
    assert returned_user is user


def test_require_user_with_permission_rejects_missing_user():
    auth = AuthContext(
        claims={"scope": Permissions.DEVICES_READ},
        user=None,
        dev_mode=False,
    )
    dependency = require_user_with_permission(Permissions.DEVICES_READ)

    with pytest.raises(HTTPException) as exc_info:
        dependency(auth=auth)
    assert exc_info.value.status_code == 401


def test_get_optional_auth_context_dev_auth(db_session, dev_auth_enabled):
    user = seed_user(db_session, email="dev@example.com")

    auth = get_optional_auth_context(
        credentials=None,
        x_kpanel_dev_email=" dev@example.com ",
        x_id_token=None,
        db=db_session,
    )

    assert isinstance(auth, AuthContext)
    assert auth.dev_mode is True
    assert auth.user is not None
    assert auth.user.id == user.id
    assert auth.claims["email"] == "dev@example.com"
    assert auth.claims["sub"] == "dev@example.com"


def test_get_optional_auth_context_dev_auth_unknown_user(db_session, dev_auth_enabled):
    auth = get_optional_auth_context(
        credentials=None,
        x_kpanel_dev_email="newdev@example.com",
        x_id_token=None,
        db=db_session,
    )

    assert auth.dev_mode is True
    assert auth.user is None
    assert auth.claims["email"] == "newdev@example.com"
    assert auth.claims["name"] == "newdev"


def test_get_optional_auth_context_dev_auth_invalid_email(db_session, dev_auth_enabled):
    with pytest.raises(HTTPException) as exc_info:
        get_optional_auth_context(
            credentials=None,
            x_kpanel_dev_email="not-an-email",
            x_id_token=None,
            db=db_session,
        )
    assert exc_info.value.status_code == 400


def test_get_optional_auth_context_returns_none_without_credentials(db_session, monkeypatch):
    monkeypatch.setattr("app.kumpe_auth_config.settings.dev_auth_enabled", False)

    auth = get_optional_auth_context(
        credentials=None,
        x_kpanel_dev_email=None,
        x_id_token=None,
        db=db_session,
    )

    assert auth is None


def test_get_optional_auth_context_dev_auth_via_client(client, db_session, dev_auth_enabled):
    user = seed_user(db_session, email="header@example.com")

    response = client.get(
        "/api/v1/auth/session",
        headers={"X-Kpanel-Dev-Email": "header@example.com"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "authenticated"
    assert payload["user"]["id"] == user.id
