from tests.factories import seed_device, seed_user, seed_user_identity

from app.serializers import serialize_device, serialize_identity, serialize_user


def test_serialize_identity(db_session):
    user = seed_user(db_session)
    identity = seed_user_identity(
        db_session,
        user,
        provider_subject="serialize-subject",
        email="identity@example.com",
        display_name="Identity Name",
    )

    payload = serialize_identity(identity)

    assert payload == {
        "id": identity.id,
        "provider_name": identity.provider_name,
        "email": "identity@example.com",
        "display_name": "Identity Name",
        "expires_at": None,
    }


def test_serialize_device(db_session, monkeypatch):
    user = seed_user(db_session)
    device = seed_device(
        db_session,
        user_id=user.id,
        device_id="kpanel-serialize",
        registration_code="KPANEL-SER001",
        target_url="https://panel.example.com",
    )
    device.client_version = "1.0.0"
    db_session.commit()

    monkeypatch.setattr(
        "app.serializers.get_latest_for_channel",
        lambda _version: ("2.0.0", "https://example.com/pkg.tar.gz"),
    )

    payload = serialize_device(device, db_session)

    assert payload["registration_code"] == "KPANEL-SER001"
    assert payload["device_id"] == "kpanel-serialize"
    assert payload["target_url"] == "https://panel.example.com"
    assert payload["url_mode"] == "custom"
    assert payload["resolved_url"] == "https://panel.example.com"
    assert payload["latest_client_version"] == "2.0.0"
    assert payload["has_temp_url"] is False
    assert payload["client_version"] == "1.0.0"
    assert payload["last_seen"] == payload["last_seen_at"]
    assert payload["registered_at"] == payload["claimed_at"]


def test_serialize_device_without_db_skips_resolved_url(db_session):
    user = seed_user(db_session)
    device = seed_device(
        db_session,
        user_id=user.id,
        device_id="kpanel-no-db",
        registration_code="KPANEL-NODB01",
    )

    payload = serialize_device(device, None)

    assert payload["resolved_url"] is None


def test_serialize_user(db_session, monkeypatch):
    user = seed_user(db_session, email="owner@example.com")
    identity = seed_user_identity(db_session, user)
    device = seed_device(
        db_session,
        user_id=user.id,
        device_id="kpanel-user-ser",
        registration_code="KPANEL-USR001",
        target_url="https://dashboard.example.com",
    )

    monkeypatch.setattr(
        "app.serializers.get_latest_for_channel",
        lambda _version: ("", None),
    )

    payload = serialize_user(user, [identity], [device], db_session)

    assert payload["id"] == user.id
    assert payload["email"] == "owner@example.com"
    assert payload["display_name"] == "Owner"
    assert payload["timezone"] == "America/Chicago"
    assert len(payload["identities"]) == 1
    assert payload["identities"][0]["id"] == identity.id
    assert len(payload["devices"]) == 1
    assert payload["devices"][0]["device_id"] == device.device_id
