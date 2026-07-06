import os

from app.security import issue_device_token, verify_device_token
from tests.factories import seed_device, seed_household, seed_household_url, seed_room, seed_user


ADMIN_KEY = os.getenv("KPANEL_ADMIN_API_KEY", "change-me")


def _device_headers(device_id: str) -> dict[str, str]:
    return {"X-Device-Token": issue_device_token(device_id)}


def _admin_headers() -> dict[str, str]:
    return {"X-Admin-Key": ADMIN_KEY}


# ---------- GET /healthz ----------


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "kpanel-backend"}


# ---------- POST /api/v1/devices/resolve ----------


def test_resolve_device_pending_when_unclaimed(client, db_session):
    seed_device(db_session, registration_code="KPANEL-PEND1", device_id="kpanel-pend1")
    token = issue_device_token("kpanel-pend1")

    response = client.post(
        "/api/v1/devices/resolve",
        json={"device_id": "kpanel-pend1", "registration_code": "KPANEL-PEND1"},
        headers={"X-Device-Token": token},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert "waiting to be claimed" in body["message"]


def test_resolve_device_configured(client, db_session):
    user = seed_user(db_session)
    seed_device(
        db_session,
        registration_code="KPANEL-CFG01",
        device_id="kpanel-cfg1",
        user_id=user.id,
        display_name="Kitchen",
        target_url="https://kitchen.example.com",
    )

    response = client.post(
        "/api/v1/devices/resolve",
        json={
            "device_id": "kpanel-cfg1",
            "registration_code": "KPANEL-CFG01",
            "client_version": "1.2.3",
        },
        headers=_device_headers("kpanel-cfg1"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "configured"
    assert body["configured_url"] == "https://kitchen.example.com"
    assert body["timezone"] == "America/Chicago"
    assert "update" in body


def test_resolve_device_not_found_for_device(client, db_session):
    response = client.post(
        "/api/v1/devices/resolve",
        json={"device_id": "kpanel-missing", "registration_code": "KPANEL-NOPE1"},
        headers=_device_headers("kpanel-missing"),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    assert "not found" in response.json()["message"]


def test_resolve_device_requires_token(client, db_session):
    seed_device(db_session, registration_code="KPANEL-AUTH1", device_id="kpanel-auth1")

    response = client.post(
        "/api/v1/devices/resolve",
        json={"device_id": "kpanel-auth1", "registration_code": "KPANEL-AUTH1"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing device token"


# ---------- GET /api/v1/devices/{device_id}/config ----------


def test_get_device_config_unbound(client):
    response = client.get(
        "/api/v1/devices/kpanel-unbound/config",
        headers=_device_headers("kpanel-unbound"),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "unbound"


def test_get_device_config_pending(client, db_session):
    seed_device(db_session, registration_code="KPANEL-CFGP1", device_id="kpanel-cfgp1")

    response = client.get(
        "/api/v1/devices/kpanel-cfgp1/config",
        headers=_device_headers("kpanel-cfgp1"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["registration_code"] == "KPANEL-CFGP1"


def test_get_device_config_configured(client, db_session):
    user = seed_user(db_session)
    seed_device(
        db_session,
        registration_code="KPANEL-CFGC1",
        device_id="kpanel-cfgc1",
        user_id=user.id,
        display_name="Office",
        target_url="https://office.example.com",
    )

    response = client.get(
        "/api/v1/devices/kpanel-cfgc1/config",
        headers=_device_headers("kpanel-cfgc1"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "configured"
    assert body["configured_url"] == "https://office.example.com"


def test_get_device_config_household_url(client, db_session):
    user = seed_user(db_session)
    household = seed_household(db_session, user)
    hurl = seed_household_url(
        db_session,
        household_id=household.id,
        url_template="https://dash.example.com/{device}",
    )
    device = seed_device(
        db_session,
        registration_code="KPANEL-HHCFG",
        device_id="kpanel-hhcfg",
        user_id=user.id,
        display_name="Living Room",
        target_url=None,
    )
    device.url_mode = "household_url"
    device.household_url_id = hurl.id
    db_session.commit()

    response = client.get(
        "/api/v1/devices/kpanel-hhcfg/config",
        headers=_device_headers("kpanel-hhcfg"),
    )

    assert response.status_code == 200
    assert response.json()["configured_url"] == "https://dash.example.com/Living%20Room"


# ---------- POST /api/v1/devices/{device_id}/update-events ----------


def test_record_update_event(client, db_session):
    user = seed_user(db_session)
    seed_device(
        db_session,
        registration_code="KPANEL-EVT01",
        device_id="kpanel-evt1",
        user_id=user.id,
        display_name="Panel",
        target_url="https://panel.example.com",
    )

    response = client.post(
        "/api/v1/devices/kpanel-evt1/update-events",
        json={
            "registration_code": "KPANEL-EVT01",
            "action": "update",
            "status": "completed",
            "from_version": "1.0.0",
            "target_version": "1.1.0",
            "channel": "stable",
            "message": "ok",
        },
        headers=_device_headers("kpanel-evt1"),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "recorded"


def test_record_update_event_device_not_found(client, db_session):
    response = client.post(
        "/api/v1/devices/kpanel-missing/update-events",
        json={
            "registration_code": "KPANEL-MISSING",
            "action": "update",
            "status": "failed",
        },
        headers=_device_headers("kpanel-missing"),
    )

    assert response.status_code == 404


# ---------- Admin routes ----------


def test_create_device_token_admin(client):
    response = client.post(
        "/api/v1/admin/device-tokens",
        json={"device_id": "kpanel-admin1", "expires_in_minutes": 60},
        headers=_admin_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["device_id"] == "kpanel-admin1"
    assert verify_device_token(body["device_token"], "kpanel-admin1")


def test_create_device_token_admin_unauthorized(client):
    response = client.post(
        "/api/v1/admin/device-tokens",
        json={"device_id": "kpanel-admin2"},
        headers={"X-Admin-Key": "wrong-key"},
    )

    assert response.status_code == 401


def test_create_registration_admin(client, db_session):
    response = client.post(
        "/api/v1/admin/registrations",
        json={
            "registration_code": "KPANEL-REG01",
            "target_url": "https://provision.example.com",
            "expires_in_minutes": 30,
        },
        headers=_admin_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["registration_code"] == "KPANEL-REG01"
    assert body["target_url"] == "https://provision.example.com/"
    assert "expires_at" in body


def test_create_registration_admin_updates_existing(client, db_session):
    first = client.post(
        "/api/v1/admin/registrations",
        json={
            "registration_code": "KPANEL-REG02",
            "target_url": "https://first.example.com",
            "expires_in_minutes": 15,
        },
        headers=_admin_headers(),
    )
    assert first.status_code == 200

    second = client.post(
        "/api/v1/admin/registrations",
        json={
            "registration_code": "KPANEL-REG02",
            "target_url": "https://second.example.com",
            "expires_in_minutes": 45,
        },
        headers=_admin_headers(),
    )

    assert second.status_code == 200
    assert second.json()["target_url"] == "https://second.example.com/"


def test_resolve_device_uses_device_timezone(client, db_session):
    user = seed_user(db_session)
    device = seed_device(
        db_session,
        registration_code="KPANEL-TZ001",
        device_id="kpanel-tz1",
        user_id=user.id,
        display_name="Panel",
        target_url="https://panel.example.com",
    )
    device.timezone = "America/Denver"
    db_session.commit()

    response = client.post(
        "/api/v1/devices/resolve",
        json={"device_id": "kpanel-tz1", "registration_code": "KPANEL-TZ001"},
        headers=_device_headers("kpanel-tz1"),
    )

    assert response.status_code == 200
    assert response.json()["timezone"] == "America/Denver"


def test_resolve_device_timezone_from_household_room(client, db_session):
    user = seed_user(db_session)
    household = seed_household(db_session, user, timezone="America/Los_Angeles")
    room = seed_room(db_session, household_id=household.id)
    device = seed_device(
        db_session,
        registration_code="KPANEL-TZ002",
        device_id="kpanel-tz2",
        user_id=user.id,
        display_name="Panel",
        target_url="https://panel.example.com",
    )
    device.room_id = room.id
    db_session.commit()

    response = client.post(
        "/api/v1/devices/resolve",
        json={"device_id": "kpanel-tz2", "registration_code": "KPANEL-TZ002"},
        headers=_device_headers("kpanel-tz2"),
    )

    assert response.status_code == 200
    assert response.json()["timezone"] == "America/Los_Angeles"
