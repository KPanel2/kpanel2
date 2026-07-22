"""HA binding inheritance: account → household → room → device (lower overrides)."""

from app.browser_auth import BROWSER_AUTH_TYPE_HA, build_browser_auth_payload
from app.ha_binding import resolve_ha_binding
from tests.factories import seed_device, seed_household, seed_room, seed_user


BOOTSTRAP = "https://ha.example/api/kpanel_dashboard/bootstrap"


def _bind(entity, *, url: str = BOOTSTRAP, secret: str = "secret") -> None:
    entity.ha_bootstrap_url = url
    entity.ha_binding_secret = secret


def test_resolve_none_when_unconfigured(db_session):
    device = seed_device(db_session, target_url="https://dash.example.com")
    assert resolve_ha_binding(device, db_session) is None
    assert build_browser_auth_payload(device, db_session) is None


def test_resolve_device_level(db_session):
    device = seed_device(db_session, target_url="https://dash.example.com")
    _bind(device, secret="device-secret")
    db_session.commit()

    resolved = resolve_ha_binding(device, db_session)
    assert resolved == {
        "bootstrap_url": BOOTSTRAP,
        "binding_secret": "device-secret",
        "source": "device",
    }
    assert build_browser_auth_payload(device, db_session) == {
        "type": BROWSER_AUTH_TYPE_HA,
        "bootstrap_url": BOOTSTRAP,
        "binding_secret": "device-secret",
    }


def test_resolve_account_when_device_empty(db_session):
    user = seed_user(db_session)
    _bind(user, secret="account-secret")
    db_session.commit()
    device = seed_device(db_session, user_id=user.id, target_url="https://dash.example.com")

    resolved = resolve_ha_binding(device, db_session)
    assert resolved["source"] == "account"
    assert resolved["binding_secret"] == "account-secret"


def test_resolve_household_overrides_account(db_session):
    user = seed_user(db_session)
    _bind(user, secret="account-secret")
    household = seed_household(db_session, user)
    _bind(household, secret="household-secret")
    room = seed_room(db_session, household_id=household.id)
    db_session.commit()
    device = seed_device(db_session, user_id=user.id, target_url="https://dash.example.com")
    device.room_id = room.id
    db_session.commit()

    resolved = resolve_ha_binding(device, db_session)
    assert resolved["source"] == "household"
    assert resolved["binding_secret"] == "household-secret"


def test_resolve_room_overrides_household(db_session):
    user = seed_user(db_session)
    household = seed_household(db_session, user)
    _bind(household, secret="household-secret")
    room = seed_room(db_session, household_id=household.id)
    _bind(room, secret="room-secret")
    db_session.commit()
    device = seed_device(db_session, user_id=user.id, target_url="https://dash.example.com")
    device.room_id = room.id
    db_session.commit()

    resolved = resolve_ha_binding(device, db_session)
    assert resolved["source"] == "room"
    assert resolved["binding_secret"] == "room-secret"


def test_resolve_device_overrides_room(db_session):
    user = seed_user(db_session)
    household = seed_household(db_session, user)
    room = seed_room(db_session, household_id=household.id)
    _bind(room, secret="room-secret")
    db_session.commit()
    device = seed_device(db_session, user_id=user.id, target_url="https://dash.example.com")
    device.room_id = room.id
    _bind(device, secret="device-secret")
    db_session.commit()

    resolved = resolve_ha_binding(device, db_session)
    assert resolved["source"] == "device"
    assert resolved["binding_secret"] == "device-secret"


def test_partial_binding_does_not_override(db_session):
    user = seed_user(db_session)
    _bind(user, secret="account-secret")
    db_session.commit()
    device = seed_device(db_session, user_id=user.id, target_url="https://dash.example.com")
    device.ha_bootstrap_url = BOOTSTRAP  # secret missing — incomplete
    db_session.commit()

    resolved = resolve_ha_binding(device, db_session)
    assert resolved["source"] == "account"


def test_household_ignored_without_room(db_session):
    user = seed_user(db_session)
    household = seed_household(db_session, user)
    _bind(household, secret="household-secret")
    db_session.commit()
    device = seed_device(db_session, user_id=user.id, target_url="https://dash.example.com")

    assert resolve_ha_binding(device, db_session) is None


def test_normalize_ha_bootstrap_url():
    from app.ha_binding import normalize_ha_bootstrap_url

    assert normalize_ha_bootstrap_url(None) is None
    assert normalize_ha_bootstrap_url("  ") is None
    assert normalize_ha_bootstrap_url("https://ha.example/api/bootstrap") == (
        "https://ha.example/api/bootstrap"
    )
    try:
        normalize_ha_bootstrap_url("ftp://bad.example")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "http" in str(exc)
    assert normalize_ha_bootstrap_url(42) == 42


def test_serialize_device_ha_binding_without_db(db_session):
    from app.ha_binding import serialize_device_ha_binding

    device = seed_device(db_session, target_url="https://dash.example.com")
    _bind(device, secret="device-secret")
    db_session.commit()

    payload = serialize_device_ha_binding(device, None)
    assert payload["has_ha_binding"] is True
    assert payload["has_local_ha_binding"] is True
    assert payload["ha_binding_source"] == "device"
