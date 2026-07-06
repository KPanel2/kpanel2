from tests.factories import (
    seed_device,
    seed_household,
    seed_household_member,
    seed_household_url,
    seed_user,
    seed_user_identity,
)


def _dev_headers(email: str) -> dict[str, str]:
    return {"X-Kpanel-Dev-Email": email}


def test_superadmin_overview(client, db_session, dev_auth_enabled):
    admin = seed_user(db_session, email="admin@example.com")
    member = seed_user(db_session, user_id=2, email="member@example.com")
    household = seed_household(db_session, admin)
    seed_household_member(db_session, household_id=household.id, user_id=member.id)
    seed_household_url(db_session, household_id=household.id)
    seed_device(
        db_session,
        registration_code="KPANEL-SA01",
        device_id="kpanel-sa1",
        user_id=admin.id,
        display_name="Panel",
        target_url="https://panel.example.com",
    )
    seed_device(db_session, registration_code="KPANEL-SA02", device_id="kpanel-sa2")

    response = client.get("/api/v1/superadmin/overview", headers=_dev_headers(admin.email))

    assert response.status_code == 200
    body = response.json()
    assert body["users"] == 2
    assert body["households"] == 1
    assert body["devices"] == 2
    assert body["claimed_devices"] == 1
    assert body["household_urls"] == 1


def test_superadmin_list_and_get_user(client, db_session, dev_auth_enabled):
    user = seed_user(db_session, email="detail@example.com")
    seed_user_identity(db_session, user)
    seed_device(
        db_session,
        registration_code="KPANEL-SAUSR",
        device_id="kpanel-sausr",
        user_id=user.id,
        display_name="Panel",
        target_url="https://panel.example.com",
    )
    household = seed_household(db_session, user)

    list_response = client.get("/api/v1/superadmin/users", headers=_dev_headers(user.email))
    assert list_response.status_code == 200
    assert len(list_response.json()["users"]) == 1

    detail_response = client.get(
        f"/api/v1/superadmin/users/{user.id}",
        headers=_dev_headers(user.email),
    )
    assert detail_response.status_code == 200
    body = detail_response.json()
    assert body["user"]["email"] == user.email
    assert len(body["identities"]) == 1
    assert len(body["devices"]) == 1
    assert body["households"][0]["household_id"] == household.id


def test_superadmin_update_user(client, db_session, dev_auth_enabled):
    user = seed_user(db_session, email="deactivate@example.com")
    assert user.is_active is True

    response = client.patch(
        f"/api/v1/superadmin/users/{user.id}",
        json={"is_active": False},
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 200
    assert response.json()["user"]["is_active"] is False
    db_session.refresh(user)
    assert user.is_active is False


def test_superadmin_list_and_get_household(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    household = seed_household(db_session, user, name="Admin View")

    list_response = client.get("/api/v1/superadmin/households", headers=_dev_headers(user.email))
    assert list_response.status_code == 200
    assert list_response.json()["households"][0]["name"] == "Admin View"

    detail_response = client.get(
        f"/api/v1/superadmin/households/{household.id}",
        headers=_dev_headers(user.email),
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["household"]["id"] == household.id


def test_superadmin_update_household(client, db_session, dev_auth_enabled):
    owner = seed_user(db_session, user_id=1, email="owner@example.com")
    new_owner = seed_user(db_session, user_id=2, email="newowner@example.com")
    household = seed_household(db_session, owner, name="Transfer Me")

    response = client.patch(
        f"/api/v1/superadmin/households/{household.id}",
        json={"name": "Transferred", "owner_id": new_owner.id},
        headers=_dev_headers(owner.email),
    )

    assert response.status_code == 200
    body = response.json()["household"]
    assert body["name"] == "Transferred"
    assert body["owner_id"] == new_owner.id


def test_superadmin_household_member_management(client, db_session, dev_auth_enabled):
    owner = seed_user(db_session, user_id=1, email="owner@example.com")
    member = seed_user(db_session, user_id=2, email="member@example.com")
    household = seed_household(db_session, owner)

    add_response = client.post(
        f"/api/v1/superadmin/households/{household.id}/members",
        json={"email": member.email, "role": "member"},
        headers=_dev_headers(owner.email),
    )
    assert add_response.status_code == 200
    assert add_response.json()["status"] == "added"

    remove_response = client.delete(
        f"/api/v1/superadmin/households/{household.id}/members/{member.id}",
        headers=_dev_headers(owner.email),
    )
    assert remove_response.status_code == 200
    assert remove_response.json()["status"] == "removed"


def test_superadmin_list_and_update_device(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    device = seed_device(
        db_session,
        registration_code="KPANEL-SADEV",
        device_id="kpanel-sadev",
        user_id=user.id,
        display_name="Old Label",
        target_url="https://old.example.com",
    )

    list_response = client.get("/api/v1/superadmin/devices", headers=_dev_headers(user.email))
    assert list_response.status_code == 200
    assert list_response.json()["devices"][0]["owner"]["email"] == user.email

    update_response = client.patch(
        "/api/v1/superadmin/devices/KPANEL-SADEV",
        json={"display_name": "New Label", "target_url": "https://new.example.com"},
        headers=_dev_headers(user.email),
    )
    assert update_response.status_code == 200
    db_session.refresh(device)
    assert device.display_name == "New Label"
    assert device.target_url == "https://new.example.com/"


def test_superadmin_list_and_update_url(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    household = seed_household(db_session, user)
    hurl = seed_household_url(
        db_session,
        household_id=household.id,
        friendly_name="Original",
        url_template="https://original.example.com/{device}",
    )

    list_response = client.get("/api/v1/superadmin/urls", headers=_dev_headers(user.email))
    assert list_response.status_code == 200
    assert list_response.json()["urls"][0]["household_name"] == household.name

    update_response = client.patch(
        f"/api/v1/superadmin/urls/{hurl.id}",
        json={"friendly_name": "Renamed", "is_default": True},
        headers=_dev_headers(user.email),
    )
    assert update_response.status_code == 200
    db_session.refresh(hurl)
    assert hurl.friendly_name == "Renamed"
    assert hurl.is_default is True


def test_superadmin_get_user_not_found(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)

    response = client.get("/api/v1/superadmin/users/9999", headers=_dev_headers(user.email))

    assert response.status_code == 404


def test_superadmin_update_user_no_fields(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)

    response = client.patch(
        f"/api/v1/superadmin/users/{user.id}",
        json={},
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 400


def test_superadmin_update_household_empty_name(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    household = seed_household(db_session, user)

    response = client.patch(
        f"/api/v1/superadmin/households/{household.id}",
        json={"name": "   "},
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 400


def test_superadmin_add_duplicate_member(client, db_session, dev_auth_enabled):
    owner = seed_user(db_session, user_id=1, email="owner@example.com")
    member = seed_user(db_session, user_id=2, email="member@example.com")
    household = seed_household(db_session, owner)
    seed_household_member(db_session, household_id=household.id, user_id=member.id)

    response = client.post(
        f"/api/v1/superadmin/households/{household.id}/members",
        json={"email": member.email},
        headers=_dev_headers(owner.email),
    )

    assert response.status_code == 409


def test_superadmin_unclaim_device(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    device = seed_device(
        db_session,
        registration_code="KPANEL-UNCLM",
        device_id="kpanel-unclm",
        user_id=user.id,
        display_name="Panel",
        target_url="https://panel.example.com",
    )

    response = client.patch(
        "/api/v1/superadmin/devices/KPANEL-UNCLM",
        json={"unclaim": True},
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 200
    db_session.refresh(device)
    assert device.user_id is None
    assert device.claimed_at is None


def test_superadmin_remove_household_owner_rejected(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    household = seed_household(db_session, user)

    response = client.delete(
        f"/api/v1/superadmin/households/{household.id}/members/{user.id}",
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 400


def test_superadmin_update_device_assign_user(client, db_session, dev_auth_enabled):
    owner = seed_user(db_session, user_id=1, email="owner@example.com")
    other = seed_user(db_session, user_id=2, email="other@example.com")
    device = seed_device(
        db_session,
        registration_code="KPANEL-ASSGN",
        device_id="kpanel-assgn",
        user_id=owner.id,
        display_name="Panel",
        target_url="https://panel.example.com",
    )

    response = client.patch(
        "/api/v1/superadmin/devices/KPANEL-ASSGN",
        json={"user_id": other.id},
        headers=_dev_headers(owner.email),
    )

    assert response.status_code == 200
    db_session.refresh(device)
    assert device.user_id == other.id


def test_superadmin_add_member_invalid_role(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    household = seed_household(db_session, user)

    response = client.post(
        f"/api/v1/superadmin/households/{household.id}/members",
        json={"email": "new@example.com", "role": "admin"},
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 400
