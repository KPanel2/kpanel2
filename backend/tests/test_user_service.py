import pytest

from app.kumpe_permissions import KPANEL_PROVIDER_NAME
from app.models import UserIdentity
from app.user_service import (
    claims_custom_data,
    claims_display_name,
    claims_email,
    claims_timezone,
    ensure_identity_for_user,
    normalize_email,
    resolve_user_from_claims,
    sync_user_profile_from_claims,
)
from tests.factories import seed_user, seed_user_identity


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Owner@Example.COM ", "owner@example.com"),
        ("user@domain.co", "user@domain.co"),
    ],
)
def test_normalize_email_valid(raw, expected):
    assert normalize_email(raw) == expected


@pytest.mark.parametrize(
    "invalid",
    [
        "",
        "   ",
        "not-an-email",
        "@example.com",
        "user@",
    ],
)
def test_normalize_email_invalid(invalid):
    with pytest.raises(ValueError, match="valid email"):
        normalize_email(invalid)


def test_claims_email_from_email_claim():
    assert claims_email({"email": "  User@Example.com "}) == "user@example.com"


def test_claims_email_from_username_fallback():
    assert claims_email({"username": "alt@example.com"}) == "alt@example.com"


@pytest.mark.parametrize(
    "claims",
    [
        {},
        {"email": ""},
        {"email": "   "},
        {"email": 42},
    ],
)
def test_claims_email_missing_or_invalid(claims):
    with pytest.raises(ValueError, match="email claim"):
        claims_email(claims)


def test_claims_display_name_prefers_name():
    assert claims_display_name({"name": "  Alice "}, "alice@example.com") == "Alice"


def test_claims_display_name_prefers_preferred_username():
    assert claims_display_name(
        {"preferred_username": "  bob "},
        "bob@example.com",
    ) == "bob"


def test_claims_display_name_falls_back_to_local_part():
    assert claims_display_name({}, "carol@example.com") == "carol"


@pytest.mark.parametrize(
    ("claims", "expected"),
    [
        ({"custom_data": {"timezone": "America/New_York"}}, {"timezone": "America/New_York"}),
        ({"customData": {"foo": "bar"}}, {"foo": "bar"}),
        ({"custom_data": "not-a-dict"}, {}),
        ({}, {}),
    ],
)
def test_claims_custom_data(claims, expected):
    assert claims_custom_data(claims) == expected


def test_claims_timezone_returns_stripped_value():
    claims = {"custom_data": {"timezone": "  Europe/London  "}}
    assert claims_timezone(claims) == "Europe/London"


def test_claims_timezone_returns_none_when_missing():
    assert claims_timezone({}) is None


def test_sync_user_profile_from_claims_updates_fields(db_session):
    user = seed_user(db_session, email="old@example.com")
    user.display_name = "Old Name"
    user.timezone = "America/Chicago"
    db_session.commit()

    claims = {
        "sub": "auth-subject-1",
        "email": "new@example.com",
        "name": "New Name",
        "custom_data": {"timezone": "America/Denver"},
    }

    updated = sync_user_profile_from_claims(user, claims, db_session)

    assert updated.email == "new@example.com"
    assert updated.display_name == "New Name"
    assert updated.timezone == "America/Denver"


def test_sync_user_profile_from_claims_keeps_email_when_claim_missing(db_session):
    user = seed_user(db_session, email="keep@example.com")

    sync_user_profile_from_claims(user, {"name": "Updated"}, db_session)

    assert user.email == "keep@example.com"
    assert user.display_name == "Updated"


def test_sync_user_profile_from_claims_ignores_invalid_timezone(db_session):
    user = seed_user(db_session)
    original_tz = user.timezone

    sync_user_profile_from_claims(
        user,
        {"email": user.email, "custom_data": {"timezone": "Not/A/Timezone"}},
        db_session,
    )

    assert user.timezone == original_tz


def test_resolve_user_from_claims_by_identity(db_session):
    user = seed_user(db_session)
    seed_user_identity(db_session, user, provider_subject="subject-abc")

    resolved = resolve_user_from_claims(
        {"sub": "subject-abc", "email": user.email},
        db_session,
    )

    assert resolved is not None
    assert resolved.id == user.id


def test_resolve_user_from_claims_by_email(db_session):
    user = seed_user(db_session, email="lookup@example.com")

    resolved = resolve_user_from_claims(
        {"sub": "new-subject", "email": "lookup@example.com"},
        db_session,
    )

    assert resolved is not None
    assert resolved.id == user.id


def test_resolve_user_from_claims_returns_none_without_sub(db_session):
    assert resolve_user_from_claims({"email": "x@example.com"}, db_session) is None


def test_resolve_user_from_claims_returns_none_without_email(db_session):
    assert resolve_user_from_claims({"sub": "orphan-sub"}, db_session) is None


def test_ensure_identity_for_user_creates_identity(db_session):
    user = seed_user(db_session)
    claims = {"sub": "new-subject", "email": user.email, "name": "Owner"}

    identity = ensure_identity_for_user(user, claims, db_session)

    assert identity.user_id == user.id
    assert identity.provider_name == KPANEL_PROVIDER_NAME
    assert identity.provider_subject == "new-subject"
    assert identity.email == user.email
    assert identity.display_name == "Owner"

    stored = db_session.query(UserIdentity).filter_by(provider_subject="new-subject").one()
    assert stored.id == identity.id


def test_ensure_identity_for_user_updates_existing_identity(db_session):
    user = seed_user(db_session, email="first@example.com")
    other = seed_user(db_session, user_id=2, email="second@example.com")
    identity = seed_user_identity(
        db_session,
        user,
        provider_subject="shared-subject",
        email="first@example.com",
        display_name="First",
    )

    updated = ensure_identity_for_user(
        other,
        {"sub": "shared-subject", "email": "second@example.com", "name": "Second"},
        db_session,
    )

    db_session.refresh(identity)
    assert updated.id == identity.id
    assert updated.user_id == other.id
    assert updated.email == "second@example.com"
    assert updated.display_name == "Second"
