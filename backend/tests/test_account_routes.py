import pytest

from tests.factories import (
    seed_device,
    seed_household,
    seed_household_member,
    seed_household_url,
    seed_room,
    seed_user,
    seed_user_identity,
)


def _dev_headers(email: str) -> dict[str, str]:
    return {"X-Kpanel-Dev-Email": email}


def _post_device_action(client, *, registration_code: str, action: str, email: str):
    return client.post(
        f"/api/v1/account/devices/{registration_code}/actions/{action}",
        headers=_dev_headers(email),
    )


# ---------- POST /api/v1/account/create ----------


def test_account_create_creates_new_user(client, db_session, dev_auth_enabled):
    response = client.post(
        "/api/v1/account/create",
        json={},
        headers=_dev_headers("newuser@example.com"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "authenticated"
    assert body["user"]["email"] == "newuser@example.com"
    assert body["user"]["display_name"] == "newuser"


def test_account_create_returns_existing_user_session(client, db_session, dev_auth_enabled):
    user = seed_user(db_session, email="existing@example.com")
    seed_user_identity(db_session, user)

    response = client.post(
        "/api/v1/account/create",
        json={},
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "authenticated"
    assert body["user"]["id"] == user.id
    assert body["user"]["email"] == user.email


def test_account_create_requires_auth(client):
    response = client.post("/api/v1/account/create", json={})
    assert response.status_code == 401


# ---------- PATCH /api/v1/account/profile ----------


def test_account_update_profile_timezone_in_dev_mode(client, db_session, dev_auth_enabled):
    user = seed_user(db_session, email="profile@example.com")

    response = client.patch(
        "/api/v1/account/profile",
        json={"timezone": "America/New_York"},
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["timezone"] == "America/New_York"

    db_session.refresh(user)
    assert user.timezone == "America/New_York"


def test_account_update_profile_rejects_non_dev_timezone(client, db_session, dev_auth_enabled):
    user = seed_user(db_session, email="profile2@example.com")

    response = client.patch(
        "/api/v1/account/profile",
        json={},
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 400
    assert "KumpeCloud Auth" in response.json()["detail"]


def test_account_update_profile_rejects_invalid_timezone(client, db_session, dev_auth_enabled):
    user = seed_user(db_session, email="profile3@example.com")

    response = client.patch(
        "/api/v1/account/profile",
        json={"timezone": "Not/A/Timezone"},
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 400
    assert "Invalid timezone" in response.json()["detail"]


# ---------- GET /api/v1/account/devices ----------


def test_account_devices_lists_owned_devices(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    seed_device(
        db_session,
        registration_code="KPANEL-LIST01",
        device_id="kpanel-list1",
        user_id=user.id,
        display_name="Kitchen",
        target_url="https://kitchen.example.com",
    )
    seed_device(
        db_session,
        registration_code="KPANEL-OTHER1",
        device_id="kpanel-other",
        user_id=99,
        display_name="Other",
        target_url="https://other.example.com",
    )

    response = client.get("/api/v1/account/devices", headers=_dev_headers(user.email))

    assert response.status_code == 200
    devices = response.json()["devices"]
    assert len(devices) == 1
    assert devices[0]["registration_code"] == "KPANEL-LIST01"


def test_account_devices_requires_auth(client):
    response = client.get("/api/v1/account/devices")
    assert response.status_code == 401


# ---------- POST /api/v1/account/devices/claim ----------


def test_account_claim_device_with_target_url(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    device = seed_device(db_session, registration_code="KPANEL-CLAIM1", device_id="kpanel-claim1")

    response = client.post(
        "/api/v1/account/devices/claim",
        json={
            "registration_code": "kpanel-claim1",
            "display_name": "Living Room",
            "target_url": "https://panel.example.com",
        },
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "configured"
    assert body["device"]["display_name"] == "Living Room"
    assert body["device"]["target_url"] == "https://panel.example.com/"

    db_session.refresh(device)
    assert device.user_id == user.id
    assert device.url_mode == "custom"


def test_account_claim_device_with_household_url(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    household = seed_household(db_session, user)
    hurl = seed_household_url(
        db_session,
        household_id=household.id,
        friendly_name="Default",
        url_template="https://dash.example.com/{device}",
        is_default=True,
    )
    device = seed_device(db_session, registration_code="KPANEL-HH001", device_id="kpanel-hh1")

    response = client.post(
        "/api/v1/account/devices/claim",
        json={
            "registration_code": "KPANEL-HH001",
            "display_name": "Panel",
            "household_id": household.id,
        },
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "configured"
    assert body["device"]["url_mode"] == "household_url"
    assert body["device"]["household_url_id"] == hurl.id


def test_account_claim_device_not_found(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)

    response = client.post(
        "/api/v1/account/devices/claim",
        json={"registration_code": "KPANEL-MISSING"},
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 404
    assert "Registration code not found" in response.json()["detail"]


def test_account_claim_device_already_claimed_by_other(client, db_session, dev_auth_enabled):
    owner = seed_user(db_session, user_id=1, email="owner@example.com")
    other = seed_user(db_session, user_id=2, email="other@example.com")
    seed_device(
        db_session,
        registration_code="KPANEL-TAKEN1",
        device_id="kpanel-taken",
        user_id=owner.id,
        display_name="Taken",
        target_url="https://taken.example.com",
    )

    response = client.post(
        "/api/v1/account/devices/claim",
        json={"registration_code": "KPANEL-TAKEN1"},
        headers=_dev_headers(other.email),
    )

    assert response.status_code == 409
    assert "already claimed" in response.json()["detail"]


def test_account_claim_device_household_not_member(client, db_session, dev_auth_enabled):
    owner = seed_user(db_session, user_id=1, email="owner@example.com")
    stranger = seed_user(db_session, user_id=2, email="stranger@example.com")
    household = seed_household(db_session, owner)
    seed_household_url(db_session, household_id=household.id, is_default=True)
    seed_device(db_session, registration_code="KPANEL-NOMEM", device_id="kpanel-nomem")

    response = client.post(
        "/api/v1/account/devices/claim",
        json={"registration_code": "KPANEL-NOMEM", "household_id": household.id},
        headers=_dev_headers(stranger.email),
    )

    assert response.status_code == 403
    assert "not a member" in response.json()["detail"]


def test_account_claim_device_household_no_urls(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    household = seed_household(db_session, user)
    seed_device(db_session, registration_code="KPANEL-NOURL", device_id="kpanel-nourl")

    response = client.post(
        "/api/v1/account/devices/claim",
        json={"registration_code": "KPANEL-NOURL", "household_id": household.id},
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 400
    assert "no URLs configured" in response.json()["detail"]


# ---------- PATCH /api/v1/account/devices/{registration_code} ----------


def test_account_update_device(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    device = seed_device(
        db_session,
        registration_code="KPANEL-UPD01",
        device_id="kpanel-upd1",
        user_id=user.id,
        display_name="Old Name",
        target_url="https://old.example.com",
    )

    response = client.patch(
        "/api/v1/account/devices/KPANEL-UPD01",
        json={"display_name": "New Name", "timezone": "America/Denver"},
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "updated"
    assert body["device"]["display_name"] == "New Name"
    assert body["device"]["timezone"] == "America/Denver"

    db_session.refresh(device)
    assert device.display_name == "New Name"
    assert device.timezone == "America/Denver"


def test_account_update_device_not_owned(client, db_session, dev_auth_enabled):
    owner = seed_user(db_session, user_id=1, email="owner@example.com")
    other = seed_user(db_session, user_id=2, email="other@example.com")
    seed_device(
        db_session,
        registration_code="KPANEL-NOOWN",
        device_id="kpanel-noown",
        user_id=owner.id,
        display_name="Owned",
        target_url="https://owned.example.com",
    )

    response = client.patch(
        "/api/v1/account/devices/KPANEL-NOOWN",
        json={"display_name": "Hacked"},
        headers=_dev_headers(other.email),
    )

    assert response.status_code == 404


def test_account_update_device_no_fields(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    seed_device(
        db_session,
        registration_code="KPANEL-NOFLD",
        device_id="kpanel-nofld",
        user_id=user.id,
        display_name="Panel",
        target_url="https://panel.example.com",
    )

    response = client.patch(
        "/api/v1/account/devices/KPANEL-NOFLD",
        json={},
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 400
    assert "No editable fields" in response.json()["detail"]


def test_account_update_device_invalid_url_mode(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    seed_device(
        db_session,
        registration_code="KPANEL-BADMD",
        device_id="kpanel-badmd",
        user_id=user.id,
        display_name="Panel",
        target_url="https://panel.example.com",
    )

    response = client.patch(
        "/api/v1/account/devices/KPANEL-BADMD",
        json={"url_mode": "invalid"},
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 400
    assert "url_mode" in response.json()["detail"]


def test_account_update_device_clear_room(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    household = seed_household(db_session, user)
    room = seed_room(db_session, household_id=household.id)
    device = seed_device(
        db_session,
        registration_code="KPANEL-ROOM1",
        device_id="kpanel-room1",
        user_id=user.id,
        display_name="Panel",
        target_url="https://panel.example.com",
    )
    device.room_id = room.id
    db_session.commit()

    response = client.patch(
        "/api/v1/account/devices/KPANEL-ROOM1",
        json={"clear_room": True},
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 200
    db_session.refresh(device)
    assert device.room_id is None


# ---------- DELETE /api/v1/account/devices/{registration_code} ----------


def test_account_delete_device(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    seed_device(
        db_session,
        registration_code="KPANEL-DEL01",
        device_id="kpanel-del1",
        user_id=user.id,
        display_name="To Delete",
        target_url="https://delete.example.com",
    )

    response = client.delete(
        "/api/v1/account/devices/KPANEL-DEL01",
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "deleted"
    assert response.json()["registration_code"] == "KPANEL-DEL01"


def test_account_delete_device_not_found(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)

    response = client.delete(
        "/api/v1/account/devices/KPANEL-GONE1",
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 404


# ---------- POST /api/v1/account/devices/{registration_code}/actions/{action} ----------


def test_account_device_action_queues_reboot(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    device = seed_device(
        db_session,
        registration_code="KPANEL-QUEUE1",
        device_id="kpanel-queue1",
        user_id=user.id,
        display_name="Kitchen",
        target_url="https://dashboard.example.com",
    )

    response = _post_device_action(
        client,
        registration_code="KPANEL-QUEUE1",
        action=" Reboot ",
        email=user.email,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert body["action"] == "reboot"
    assert body["device"]["pending_action"] == "reboot"

    db_session.refresh(device)
    assert device.pending_action == "reboot"
    assert device.pending_action_requested_at is not None


def test_account_device_action_rejects_unsupported_action(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    seed_device(
        db_session,
        registration_code="KPANEL-BADACT",
        device_id="kpanel-badact",
        user_id=user.id,
        display_name="Kitchen",
        target_url="https://dashboard.example.com",
    )

    response = _post_device_action(
        client,
        registration_code="KPANEL-BADACT",
        action="factory-reset",
        email=user.email,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported action"


# ---------- POST/DELETE temp-url ----------


def test_account_set_device_temp_url(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    device = seed_device(
        db_session,
        registration_code="KPANEL-TEMP1",
        device_id="kpanel-temp1",
        user_id=user.id,
        display_name="Panel",
        target_url="https://permanent.example.com",
    )
    device.url_mode = "custom"
    db_session.commit()

    response = client.post(
        "/api/v1/account/devices/KPANEL-TEMP1/temp-url",
        json={"temp_url": "https://temporary.example.com"},
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "temp_url_set"
    assert body["device"]["has_temp_url"] is True
    assert body["device"]["temp_url"] == "https://temporary.example.com"

    db_session.refresh(device)
    assert device.temp_url == "https://temporary.example.com"
    assert device.temp_url_revert_mode == "custom"


def test_account_clear_device_temp_url(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    device = seed_device(
        db_session,
        registration_code="KPANEL-TEMP2",
        device_id="kpanel-temp2",
        user_id=user.id,
        display_name="Panel",
        target_url="https://permanent.example.com",
    )
    device.temp_url = "https://temporary.example.com"
    device.temp_url_revert_mode = "custom"
    device.temp_url_set_at = device.updated_at
    db_session.commit()

    response = client.delete(
        "/api/v1/account/devices/KPANEL-TEMP2/temp-url",
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "temp_url_cleared"
    assert body["device"]["has_temp_url"] is False

    db_session.refresh(device)
    assert device.temp_url is None
    assert device.url_mode == "custom"


def test_account_clear_device_temp_url_when_none(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    seed_device(
        db_session,
        registration_code="KPANEL-TEMP3",
        device_id="kpanel-temp3",
        user_id=user.id,
        display_name="Panel",
        target_url="https://permanent.example.com",
    )

    response = client.delete(
        "/api/v1/account/devices/KPANEL-TEMP3/temp-url",
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 400
    assert "No temp URL" in response.json()["detail"]


@pytest.mark.parametrize(
    ("temp_url", "expected_status"),
    [
        ("", 422),
        ("ftp://bad.example.com", 422),
    ],
)
def test_account_set_device_temp_url_validation(
    client, db_session, dev_auth_enabled, temp_url, expected_status
):
    user = seed_user(db_session)
    seed_device(
        db_session,
        registration_code="KPANEL-TVAL1",
        device_id="kpanel-tval1",
        user_id=user.id,
        display_name="Panel",
        target_url="https://permanent.example.com",
    )

    response = client.post(
        "/api/v1/account/devices/KPANEL-TVAL1/temp-url",
        json={"temp_url": temp_url},
        headers=_dev_headers(user.email),
    )

    assert response.status_code == expected_status


def test_account_claim_rejects_invalid_target_url(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    seed_device(db_session, registration_code="KPANEL-BADURL", device_id="kpanel-badurl")

    response = client.post(
        "/api/v1/account/devices/claim",
        json={"registration_code": "KPANEL-BADURL", "target_url": "ftp://bad.example.com"},
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 422


def test_account_update_device_target_url_and_url_mode(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    household = seed_household(db_session, user)
    hurl = seed_household_url(db_session, household_id=household.id)

    device = seed_device(
        db_session,
        registration_code="KPANEL-MODE1",
        device_id="kpanel-mode1",
        user_id=user.id,
        display_name="Panel",
        target_url="https://old.example.com",
    )

    response = client.patch(
        "/api/v1/account/devices/KPANEL-MODE1",
        json={
            "target_url": "https://new.example.com",
            "url_mode": "household_url",
            "household_url_id": hurl.id,
            "room_id": seed_room(db_session, household_id=household.id).id,
        },
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 200
    db_session.refresh(device)
    assert device.target_url == "https://new.example.com/"
    assert device.url_mode == "household_url"
    assert device.household_url_id == hurl.id


def test_account_clear_temp_url_restores_household_mode(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    household = seed_household(db_session, user)
    hurl = seed_household_url(db_session, household_id=household.id)
    device = seed_device(
        db_session,
        registration_code="KPANEL-TMPRV",
        device_id="kpanel-tmprv",
        user_id=user.id,
        display_name="Panel",
        target_url="https://permanent.example.com",
    )
    device.url_mode = "household_url"
    device.household_url_id = hurl.id
    device.temp_url = "https://temporary.example.com"
    device.temp_url_revert_mode = "household_url"
    device.temp_url_revert_household_url_id = hurl.id
    device.temp_url_set_at = device.updated_at
    db_session.commit()

    response = client.delete(
        "/api/v1/account/devices/KPANEL-TMPRV/temp-url",
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 200
    db_session.refresh(device)
    assert device.temp_url is None
    assert device.url_mode == "household_url"
    assert device.household_url_id == hurl.id
