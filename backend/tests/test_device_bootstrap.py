from app.models import DeviceRegistration
from app.security import verify_device_token
from tests.factories import seed_device, seed_user


def test_bootstrap_creates_new_device(client):
    response = client.post(
        "/api/v1/devices/bootstrap",
        json={"device_id": "kpanel-new", "registration_code": "KPANEL-NEW001"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["device_id"] == "kpanel-new"
    assert body["registration_code"] == "KPANEL-NEW001"
    assert body["claimed"] is False
    assert body["configured"] is False
    assert verify_device_token(body["device_token"], "kpanel-new")


def test_bootstrap_existing_device_same_code_refreshes_token(client, db_session):
    seed_device(db_session, registration_code="KPANEL-SAME01", device_id="kpanel-same")

    response = client.post(
        "/api/v1/devices/bootstrap",
        json={"device_id": "kpanel-same", "registration_code": "kpanel-same01"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["registration_code"] == "KPANEL-SAME01"
    assert verify_device_token(body["device_token"], "kpanel-same")


def test_bootstrap_claimed_device_mismatched_code_returns_409(client, db_session):
    seed_user(db_session)
    device = seed_device(
        db_session,
        registration_code="KPANEL-CLAIM1",
        device_id="kpanel-claimed",
        user_id=1,
        display_name="Kitchen Panel",
        target_url="https://dashboard.example.com",
    )

    response = client.post(
        "/api/v1/devices/bootstrap",
        json={"device_id": "kpanel-claimed", "registration_code": "KPANEL-WRONG1"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "error": "registration-code-mismatch",
        "registration_code": "KPANEL-CLAIM1",
    }

    db_session.refresh(device)
    assert device.user_id == 1
    assert device.display_name == "Kitchen Panel"
    assert device.target_url == "https://dashboard.example.com"
    assert device.registration_code == "KPANEL-CLAIM1"


def test_bootstrap_unclaimed_device_rotates_registration_code(client, db_session):
    device = seed_device(
        db_session,
        registration_code="KPANEL-OLD001",
        device_id="kpanel-unclaimed",
        target_url="https://old.example.com",
    )

    response = client.post(
        "/api/v1/devices/bootstrap",
        json={"device_id": "kpanel-unclaimed", "registration_code": "KPANEL-NEW777"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["registration_code"] == "KPANEL-NEW777"
    assert body["claimed"] is False
    assert body["configured"] is False

    db_session.refresh(device)
    assert device.registration_code == "KPANEL-NEW777"
    assert device.user_id is None
    assert device.display_name is None
    assert device.target_url is None
    assert device.claimed_at is None


def test_bootstrap_new_device_replaces_unclaimed_orphan_code(client, db_session):
    orphan = seed_device(
        db_session,
        registration_code="KPANEL-ORPHAN",
        device_id="kpanel-other",
    )

    response = client.post(
        "/api/v1/devices/bootstrap",
        json={"device_id": "kpanel-brand-new", "registration_code": "KPANEL-ORPHAN"},
    )

    assert response.status_code == 200
    assert response.json()["device_id"] == "kpanel-brand-new"
    assert db_session.get(DeviceRegistration, "KPANEL-ORPHAN") is not None
    assert db_session.get(DeviceRegistration, orphan.registration_code).device_id == "kpanel-brand-new"


def test_bootstrap_rejects_code_claimed_by_other_device(client, db_session):
    seed_user(db_session)
    seed_device(
        db_session,
        registration_code="KPANEL-TAKEN1",
        device_id="kpanel-owner",
        user_id=1,
        display_name="Owner Panel",
        target_url="https://owner.example.com",
    )

    response = client.post(
        "/api/v1/devices/bootstrap",
        json={"device_id": "kpanel-intruder", "registration_code": "KPANEL-TAKEN1"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Registration code is already in use by another device"


def test_bootstrap_unclaimed_device_replaces_conflicting_orphan(client, db_session):
    seed_device(
        db_session,
        registration_code="KPANEL-OLDORPH",
        device_id="kpanel-unclaimed",
    )
    seed_device(
        db_session,
        registration_code="KPANEL-NEWORPH",
        device_id="kpanel-other",
    )

    response = client.post(
        "/api/v1/devices/bootstrap",
        json={"device_id": "kpanel-unclaimed", "registration_code": "KPANEL-NEWORPH"},
    )

    assert response.status_code == 200
    assert response.json()["registration_code"] == "KPANEL-NEWORPH"
    assert db_session.get(DeviceRegistration, "KPANEL-OLDORPH") is None


def test_bootstrap_claimed_device_reports_configured_state(client, db_session):
    seed_user(db_session)
    seed_device(
        db_session,
        registration_code="KPANEL-READY1",
        device_id="kpanel-ready",
        user_id=1,
        display_name="Ready Panel",
        target_url="https://ready.example.com",
    )

    response = client.post(
        "/api/v1/devices/bootstrap",
        json={"device_id": "kpanel-ready", "registration_code": "KPANEL-READY1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["claimed"] is True
    assert body["configured"] is True
    assert verify_device_token(body["device_token"], "kpanel-ready")


def test_bootstrap_strips_and_uppercases_registration_code(client, db_session):
    seed_device(db_session, registration_code="KPANEL-NORM01", device_id="kpanel-norm")

    response = client.post(
        "/api/v1/devices/bootstrap",
        json={"device_id": "kpanel-norm", "registration_code": "  kpanel-norm01  "},
    )

    assert response.status_code == 200
    assert response.json()["registration_code"] == "KPANEL-NORM01"


def test_bootstrap_unclaimed_rotation_rejects_code_claimed_elsewhere(client, db_session):
    seed_user(db_session)
    rotating = seed_device(
        db_session,
        registration_code="KPANEL-ROTOLD",
        device_id="kpanel-rotating",
    )
    seed_device(
        db_session,
        registration_code="KPANEL-TARGET",
        device_id="kpanel-claimed-other",
        user_id=1,
        display_name="Other",
        target_url="https://other.example.com",
    )

    response = client.post(
        "/api/v1/devices/bootstrap",
        json={"device_id": "kpanel-rotating", "registration_code": "KPANEL-TARGET"},
    )

    assert response.status_code == 409
    db_session.refresh(rotating)
    assert rotating.registration_code == "KPANEL-ROTOLD"
