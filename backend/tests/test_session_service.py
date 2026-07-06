import pytest
from fastapi import HTTPException

from app.kumpe_auth import AuthContext
from app.kumpe_permissions import Permissions
from app.session_service import (
    build_session_state,
    build_unauthenticated_state,
    resolve_user_permissions,
)
from tests.factories import seed_device, seed_user, seed_user_identity


def test_resolve_user_permissions_extracts_kpanel_scopes():
    auth = AuthContext(
        claims={"scope": f"openid profile {Permissions.DEVICES_READ} {Permissions.ACCOUNT_WRITE}"},
        user=None,
    )

    assert resolve_user_permissions(auth) == sorted(
        [Permissions.DEVICES_READ, Permissions.ACCOUNT_WRITE]
    )


def test_build_unauthenticated_state():
    assert build_unauthenticated_state() == {
        "status": "unauthenticated",
        "permissions": [],
    }


def test_build_session_state_needs_account(db_session):
    auth = AuthContext(
        claims={
            "sub": "unknown-subject",
            "email": "pending@example.com",
            "name": "Pending User",
            "custom_data": {"timezone": "America/Chicago"},
            "scope": Permissions.DEVICES_READ,
        },
        user=None,
    )

    state = build_session_state(auth, db_session, [Permissions.DEVICES_READ])

    assert state["status"] == "needs_account"
    assert state["permissions"] == [Permissions.DEVICES_READ]
    assert state["pending"] == {
        "email": "pending@example.com",
        "provider_name": "kumpecloud",
        "display_name": "Pending User",
        "timezone": "America/Chicago",
    }


def test_build_session_state_raises_when_email_missing(db_session):
    auth = AuthContext(claims={"sub": "orphan-sub"}, user=None)

    with pytest.raises(HTTPException) as exc_info:
        build_session_state(auth, db_session, [])

    assert exc_info.value.status_code == 401


def test_build_session_state_authenticated(db_session):
    user = seed_user(db_session, email="owner@example.com")
    seed_user_identity(db_session, user, provider_subject="owner-subject")
    device = seed_device(
        db_session,
        user_id=user.id,
        device_id="kpanel-owned",
        registration_code="KPANEL-OWNED1",
        target_url="https://dashboard.example.com",
    )

    auth = AuthContext(
        claims={
            "sub": "owner-subject",
            "email": user.email,
            "name": "Owner Updated",
            "scope": f"{Permissions.DEVICES_READ} {Permissions.ACCOUNT_READ}",
        },
        user=user,
    )
    permissions = [Permissions.ACCOUNT_READ, Permissions.DEVICES_READ]

    state = build_session_state(auth, db_session, permissions)

    assert state["status"] == "authenticated"
    assert state["permissions"] == permissions
    assert state["user"]["id"] == user.id
    assert state["user"]["email"] == user.email
    assert state["user"]["display_name"] == "Owner Updated"
    assert len(state["user"]["identities"]) == 1
    assert state["user"]["devices"][0]["device_id"] == device.device_id
