from tests.factories import (
    seed_device,
    seed_floor,
    seed_household,
    seed_household_member,
    seed_household_url,
    seed_room,
    seed_user,
)


def _dev_headers(email: str) -> dict[str, str]:
    return {"X-Kpanel-Dev-Email": email}


# ---------- Household CRUD ----------


def test_create_household(client, db_session, dev_auth_enabled):
    user = seed_user(db_session, email="creator@example.com")

    response = client.post(
        "/api/v1/households",
        json={"name": "Beach House", "timezone": "America/Los_Angeles"},
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 200
    body = response.json()["household"]
    assert body["name"] == "Beach House"
    assert body["timezone"] == "America/Los_Angeles"
    assert body["owner_id"] == user.id
    assert len(body["members"]) == 1
    assert body["members"][0]["role"] == "owner"


def test_list_households(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    seed_household(db_session, user, name="Home A")
    seed_household(db_session, user, name="Home B")

    response = client.get("/api/v1/households", headers=_dev_headers(user.email))

    assert response.status_code == 200
    names = {h["name"] for h in response.json()["households"]}
    assert names == {"Home A", "Home B"}


def test_get_household(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    household = seed_household(db_session, user, name="My Home")

    response = client.get(
        f"/api/v1/households/{household.id}",
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 200
    assert response.json()["household"]["name"] == "My Home"


def test_get_household_not_member(client, db_session, dev_auth_enabled):
    owner = seed_user(db_session, user_id=1, email="owner@example.com")
    stranger = seed_user(db_session, user_id=2, email="stranger@example.com")
    household = seed_household(db_session, owner)

    response = client.get(
        f"/api/v1/households/{household.id}",
        headers=_dev_headers(stranger.email),
    )

    assert response.status_code == 404


def test_update_household(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    household = seed_household(db_session, user, name="Old Name")

    response = client.patch(
        f"/api/v1/households/{household.id}",
        json={"name": "New Name"},
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 200
    assert response.json()["household"]["name"] == "New Name"


def test_delete_household(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    household = seed_household(db_session, user)
    room = seed_room(db_session, household_id=household.id)
    device = seed_device(
        db_session,
        registration_code="KPANEL-HHDEL",
        device_id="kpanel-hhdel",
        user_id=user.id,
        display_name="Panel",
        target_url="https://panel.example.com",
    )
    device.room_id = room.id
    device.url_mode = "household_url"
    device.household_url_id = seed_household_url(db_session, household_id=household.id).id
    db_session.commit()

    response = client.delete(
        f"/api/v1/households/{household.id}",
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "deleted"

    db_session.refresh(device)
    assert device.room_id is None
    assert device.url_mode is None


def test_delete_household_non_owner_forbidden(client, db_session, dev_auth_enabled):
    owner = seed_user(db_session, user_id=1, email="owner@example.com")
    member = seed_user(db_session, user_id=2, email="member@example.com")
    household = seed_household(db_session, owner)
    seed_household_member(db_session, household_id=household.id, user_id=member.id)

    response = client.delete(
        f"/api/v1/households/{household.id}",
        headers=_dev_headers(member.email),
    )

    assert response.status_code == 403


# ---------- Members ----------


def test_list_members(client, db_session, dev_auth_enabled):
    owner = seed_user(db_session, user_id=1, email="owner@example.com")
    member = seed_user(db_session, user_id=2, email="member@example.com")
    household = seed_household(db_session, owner)
    seed_household_member(db_session, household_id=household.id, user_id=member.id)

    response = client.get(
        f"/api/v1/households/{household.id}/members",
        headers=_dev_headers(owner.email),
    )

    assert response.status_code == 200
    emails = {m["email"] for m in response.json()["members"]}
    assert emails == {"owner@example.com", "member@example.com"}


def test_add_member(client, db_session, dev_auth_enabled):
    owner = seed_user(db_session, user_id=1, email="owner@example.com")
    invitee = seed_user(db_session, user_id=2, email="invitee@example.com")
    household = seed_household(db_session, owner)

    response = client.post(
        f"/api/v1/households/{household.id}/members",
        json={"email": invitee.email},
        headers=_dev_headers(owner.email),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "added"
    assert response.json()["member"]["email"] == invitee.email


def test_add_member_unknown_email(client, db_session, dev_auth_enabled):
    owner = seed_user(db_session)
    household = seed_household(db_session, owner)

    response = client.post(
        f"/api/v1/households/{household.id}/members",
        json={"email": "nobody@example.com"},
        headers=_dev_headers(owner.email),
    )

    assert response.status_code == 404


def test_remove_member(client, db_session, dev_auth_enabled):
    owner = seed_user(db_session, user_id=1, email="owner@example.com")
    member = seed_user(db_session, user_id=2, email="member@example.com")
    household = seed_household(db_session, owner)
    seed_household_member(db_session, household_id=household.id, user_id=member.id)

    response = client.delete(
        f"/api/v1/households/{household.id}/members/{member.id}",
        headers=_dev_headers(owner.email),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "removed"


def test_remove_owner_rejected(client, db_session, dev_auth_enabled):
    owner = seed_user(db_session)
    household = seed_household(db_session, owner)

    response = client.delete(
        f"/api/v1/households/{household.id}/members/{owner.id}",
        headers=_dev_headers(owner.email),
    )

    assert response.status_code == 400
    assert "owner" in response.json()["detail"]


# ---------- Floors ----------


def test_floor_crud(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    household = seed_household(db_session, user)

    create = client.post(
        f"/api/v1/households/{household.id}/floors",
        json={"name": "Ground", "sort_order": 1},
        headers=_dev_headers(user.email),
    )
    assert create.status_code == 200
    floor_id = create.json()["floor"]["id"]

    listed = client.get(
        f"/api/v1/households/{household.id}/floors",
        headers=_dev_headers(user.email),
    )
    assert listed.status_code == 200
    assert len(listed.json()["floors"]) == 1

    updated = client.patch(
        f"/api/v1/households/{household.id}/floors/{floor_id}",
        json={"name": "First Floor"},
        headers=_dev_headers(user.email),
    )
    assert updated.status_code == 200
    assert updated.json()["floor"]["name"] == "First Floor"

    deleted = client.delete(
        f"/api/v1/households/{household.id}/floors/{floor_id}",
        headers=_dev_headers(user.email),
    )
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "deleted"


# ---------- Rooms ----------


def test_room_crud(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    household = seed_household(db_session, user)
    floor = seed_floor(db_session, household_id=household.id)

    create = client.post(
        f"/api/v1/households/{household.id}/rooms",
        json={"name": "Office", "floor_id": floor.id, "slug": "office"},
        headers=_dev_headers(user.email),
    )
    assert create.status_code == 200
    room = create.json()["room"]
    room_id = room["id"]
    assert room["slug"] == "office"

    listed = client.get(
        f"/api/v1/households/{household.id}/rooms",
        headers=_dev_headers(user.email),
    )
    assert listed.status_code == 200
    assert len(listed.json()["rooms"]) == 1
    assert listed.json()["rooms"][0]["slug"] == "office"

    updated = client.patch(
        f"/api/v1/households/{household.id}/rooms/{room_id}",
        json={"name": "Study", "slug": "study"},
        headers=_dev_headers(user.email),
    )
    assert updated.status_code == 200
    assert updated.json()["room"]["name"] == "Study"
    assert updated.json()["room"]["slug"] == "study"

    cleared = client.patch(
        f"/api/v1/households/{household.id}/rooms/{room_id}",
        json={"clear_slug": True},
        headers=_dev_headers(user.email),
    )
    assert cleared.status_code == 200
    assert cleared.json()["room"]["slug"] is None

    deleted = client.delete(
        f"/api/v1/households/{household.id}/rooms/{room_id}",
        headers=_dev_headers(user.email),
    )
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "deleted"


def test_create_room_invalid_floor(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    household = seed_household(db_session, user)

    response = client.post(
        f"/api/v1/households/{household.id}/rooms",
        json={"name": "Orphan", "floor_id": 9999},
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 400
    assert "Floor not found" in response.json()["detail"]


def test_room_slug_unique_per_household(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    household = seed_household(db_session, user)
    other = seed_household(db_session, user, name="Other Home")

    first = client.post(
        f"/api/v1/households/{household.id}/rooms",
        json={"name": "Kitchen", "slug": "kitchen"},
        headers=_dev_headers(user.email),
    )
    assert first.status_code == 200

    duplicate = client.post(
        f"/api/v1/households/{household.id}/rooms",
        json={"name": "Kitchen 2", "slug": "kitchen"},
        headers=_dev_headers(user.email),
    )
    assert duplicate.status_code == 400
    assert "slug" in duplicate.json()["detail"].lower()

    elsewhere = client.post(
        f"/api/v1/households/{other.id}/rooms",
        json={"name": "Kitchen", "slug": "kitchen"},
        headers=_dev_headers(user.email),
    )
    assert elsewhere.status_code == 200
    assert elsewhere.json()["room"]["slug"] == "kitchen"


def test_create_room_blank_slug_becomes_null(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    household = seed_household(db_session, user)

    response = client.post(
        f"/api/v1/households/{household.id}/rooms",
        json={"name": "Den", "slug": "  "},
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 200
    assert response.json()["room"]["slug"] is None


# ---------- Household URLs ----------


def test_household_url_crud(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    household = seed_household(db_session, user)

    create = client.post(
        f"/api/v1/households/{household.id}/urls",
        json={
            "friendly_name": "Dashboard",
            "url_template": "https://dash.example.com/{device}",
            "is_default": True,
        },
        headers=_dev_headers(user.email),
    )
    assert create.status_code == 200
    url_id = create.json()["url"]["id"]
    assert create.json()["url"]["is_default"] is True

    listed = client.get(
        f"/api/v1/households/{household.id}/urls",
        headers=_dev_headers(user.email),
    )
    assert listed.status_code == 200
    assert len(listed.json()["urls"]) == 1

    by_name = client.get(
        f"/api/v1/households/{household.id}/urls/by-name/Dashboard",
        headers=_dev_headers(user.email),
    )
    assert by_name.status_code == 200
    assert by_name.json()["url"]["id"] == url_id

    updated = client.patch(
        f"/api/v1/households/{household.id}/urls/{url_id}",
        json={"friendly_name": "Main Dashboard"},
        headers=_dev_headers(user.email),
    )
    assert updated.status_code == 200
    assert updated.json()["url"]["friendly_name"] == "Main Dashboard"

    second = client.post(
        f"/api/v1/households/{household.id}/urls",
        json={
            "friendly_name": "Backup",
            "url_template": "https://backup.example.com/{device}",
            "is_default": True,
        },
        headers=_dev_headers(user.email),
    )
    assert second.status_code == 200
    assert second.json()["url"]["is_default"] is True

    set_default = client.post(
        f"/api/v1/households/{household.id}/urls/{url_id}/set-default",
        headers=_dev_headers(user.email),
    )
    assert set_default.status_code == 200
    assert set_default.json()["url"]["is_default"] is True

    deleted = client.delete(
        f"/api/v1/households/{household.id}/urls/{url_id}",
        headers=_dev_headers(user.email),
    )
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "deleted"


def test_create_second_default_url_clears_previous(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    household = seed_household(db_session, user)
    first = seed_household_url(
        db_session,
        household_id=household.id,
        friendly_name="First",
        is_default=True,
    )

    response = client.post(
        f"/api/v1/households/{household.id}/urls",
        json={
            "friendly_name": "Second",
            "url_template": "https://second.example.com/{device}",
            "is_default": True,
        },
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 200
    db_session.refresh(first)
    assert first.is_default is False


def test_update_household_no_fields(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    household = seed_household(db_session, user)

    response = client.patch(
        f"/api/v1/households/{household.id}",
        json={},
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 400


def test_update_household_ha_binding(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    household = seed_household(db_session, user)

    response = client.patch(
        f"/api/v1/households/{household.id}",
        json={
            "ha_bootstrap_url": "https://ha.example/api/kpanel_dashboard/bootstrap",
            "ha_binding_secret": "household-secret",
        },
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 200
    body = response.json()["household"]
    assert body["has_ha_binding"] is True
    assert body["ha_bootstrap_url"] == "https://ha.example/api/kpanel_dashboard/bootstrap"
    assert "ha_binding_secret" not in body

    clear = client.patch(
        f"/api/v1/households/{household.id}",
        json={"clear_ha_binding": True},
        headers=_dev_headers(user.email),
    )
    assert clear.status_code == 200
    assert clear.json()["household"]["has_ha_binding"] is False


def test_update_room_ha_binding(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    household = seed_household(db_session, user)
    room = seed_room(db_session, household_id=household.id, name="Kitchen")

    response = client.patch(
        f"/api/v1/households/{household.id}/rooms/{room.id}",
        json={
            "ha_bootstrap_url": "https://ha.example/api/kpanel_dashboard/bootstrap",
            "ha_binding_secret": "room-secret",
        },
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 200
    body = response.json()["room"]
    assert body["has_ha_binding"] is True
    assert body["ha_bootstrap_url"] == "https://ha.example/api/kpanel_dashboard/bootstrap"
    assert "ha_binding_secret" not in body

    clear = client.patch(
        f"/api/v1/households/{household.id}/rooms/{room.id}",
        json={"clear_ha_binding": True},
        headers=_dev_headers(user.email),
    )
    assert clear.status_code == 200
    assert clear.json()["room"]["has_ha_binding"] is False


def test_add_duplicate_member(client, db_session, dev_auth_enabled):
    owner = seed_user(db_session, user_id=1, email="owner@example.com")
    member = seed_user(db_session, user_id=2, email="member@example.com")
    household = seed_household(db_session, owner)
    seed_household_member(db_session, household_id=household.id, user_id=member.id)

    response = client.post(
        f"/api/v1/households/{household.id}/members",
        json={"email": member.email},
        headers=_dev_headers(owner.email),
    )

    assert response.status_code == 409


def test_get_household_url_by_name_not_found(client, db_session, dev_auth_enabled):
    user = seed_user(db_session)
    household = seed_household(db_session, user)

    response = client.get(
        f"/api/v1/households/{household.id}/urls/by-name/Missing",
        headers=_dev_headers(user.email),
    )

    assert response.status_code == 404
