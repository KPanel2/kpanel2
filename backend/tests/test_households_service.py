from urllib.parse import quote

import pytest
from fastapi import HTTPException

from app.households import _validate_timezone, expand_url_template, resolve_device_url
from tests.factories import (
    seed_device,
    seed_floor,
    seed_household,
    seed_household_url,
    seed_room,
    seed_user,
)


def test_validate_timezone_accepts_valid_zone():
    assert _validate_timezone("America/Chicago") == "America/Chicago"


def test_validate_timezone_rejects_invalid_zone():
    with pytest.raises(HTTPException) as exc_info:
        _validate_timezone("Not/A/Zone")
    assert exc_info.value.status_code == 400
    assert "Invalid timezone" in exc_info.value.detail


def test_expand_url_template_without_room(db_session):
    user = seed_user(db_session)
    device = seed_device(
        db_session,
        registration_code="KPANEL-EXP01",
        device_id="kpanel-exp1",
        user_id=user.id,
        display_name="Kitchen Panel",
        target_url="https://example.com",
    )
    template = "https://dash.example.com/{device}?room={room}&floor={floor}&house={household}"

    result = expand_url_template(template, device, db_session)

    assert result == (
        f"https://dash.example.com/{quote('Kitchen Panel', safe='')}"
        "?room=&floor=&house="
    )


def test_expand_url_template_with_room_floor_household(db_session):
    user = seed_user(db_session)
    household = seed_household(db_session, user, name="Kumpe Home")
    floor = seed_floor(db_session, household_id=household.id, name="Main Floor")
    room = seed_room(db_session, household_id=household.id, floor_id=floor.id, name="Kitchen")
    device = seed_device(
        db_session,
        registration_code="KPANEL-EXP02",
        device_id="kpanel-exp2",
        user_id=user.id,
        display_name="Panel A",
        target_url="https://example.com",
    )
    device.room_id = room.id
    db_session.commit()

    template = "https://dash.example.com/{household}/{floor}/{room}/{device}"
    result = expand_url_template(template, device, db_session)

    assert result == (
        f"https://dash.example.com/"
        f"{quote('Kumpe Home', safe='')}/"
        f"{quote('Main Floor', safe='')}/"
        f"{quote('Kitchen', safe='')}/"
        f"{quote('Panel A', safe='')}"
    )


def test_resolve_device_url_prefers_temp_url(db_session):
    user = seed_user(db_session)
    device = seed_device(
        db_session,
        registration_code="KPANEL-RES01",
        device_id="kpanel-res1",
        user_id=user.id,
        display_name="Panel",
        target_url="https://permanent.example.com",
    )
    device.temp_url = "https://temporary.example.com"
    db_session.commit()

    assert resolve_device_url(device, db_session) == "https://temporary.example.com"


def test_resolve_device_url_household_template(db_session):
    user = seed_user(db_session)
    household = seed_household(db_session, user)
    hurl = seed_household_url(
        db_session,
        household_id=household.id,
        url_template="https://dash.example.com/{device}",
    )
    device = seed_device(
        db_session,
        registration_code="KPANEL-RES02",
        device_id="kpanel-res2",
        user_id=user.id,
        display_name="Living Room",
        target_url=None,
    )
    device.url_mode = "household_url"
    device.household_url_id = hurl.id
    db_session.commit()

    assert resolve_device_url(device, db_session) == "https://dash.example.com/Living%20Room"


def test_resolve_device_url_falls_back_to_target_url(db_session):
    user = seed_user(db_session)
    device = seed_device(
        db_session,
        registration_code="KPANEL-RES03",
        device_id="kpanel-res3",
        user_id=user.id,
        display_name="Panel",
        target_url="https://custom.example.com",
    )

    assert resolve_device_url(device, db_session) == "https://custom.example.com"


def test_resolve_device_url_returns_none_when_unconfigured(db_session):
    device = seed_device(
        db_session,
        registration_code="KPANEL-RES04",
        device_id="kpanel-res4",
    )

    assert resolve_device_url(device, db_session) is None
