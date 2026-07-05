import pytest
from fastapi import HTTPException

from app.device_actions import (
    ack_device_action,
    get_device_for_ack,
    normalize_action_status,
    normalize_device_action,
    normalize_registration_code,
    queue_device_action,
)
from tests.conftest import utcnow
from tests.factories import seed_device, seed_user


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (" reboot ", "reboot"),
        ("UPDATE", "update"),
    ],
)
def test_normalize_device_action(raw, expected):
    assert normalize_device_action(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (" kpanel-code ", "KPANEL-CODE"),
        ("kpanel-code", "KPANEL-CODE"),
    ],
)
def test_normalize_registration_code(raw, expected):
    assert normalize_registration_code(raw) == expected


def test_normalize_action_status():
    assert normalize_action_status(" Started ") == "started"


def test_get_device_for_ack_returns_matching_device(db_session):
    seed_user(db_session)
    device = seed_device(
        db_session,
        registration_code="KPANEL-ACK001",
        device_id="kpanel-ack",
        user_id=1,
        target_url="https://dashboard.example.com",
    )

    resolved = get_device_for_ack(
        db_session,
        device_id="kpanel-ack",
        registration_code=" kpanel-ack001 ",
    )

    assert resolved.registration_code == device.registration_code


@pytest.mark.parametrize(
    ("registration_code", "device_id"),
    [
        ("KPANEL-MISSING", "kpanel-ack"),
        ("KPANEL-ACK001", "kpanel-other"),
    ],
)
def test_get_device_for_ack_raises_when_device_not_found(db_session, registration_code, device_id):
    seed_user(db_session)
    seed_device(
        db_session,
        registration_code="KPANEL-ACK001",
        device_id="kpanel-ack",
        user_id=1,
        target_url="https://dashboard.example.com",
    )

    with pytest.raises(HTTPException) as exc_info:
        get_device_for_ack(
            db_session,
            device_id=device_id,
            registration_code=registration_code,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Device not found"


@pytest.mark.parametrize(
    ("queued_action", "ack_action", "expected_pending_action"),
    [
        ("reboot", "reboot", None),
        ("reboot", "update", "reboot"),
        (None, "update", None),
    ],
)
def test_ack_device_action_clears_pending_only_when_action_matches(
    db_session,
    queued_action,
    ack_action,
    expected_pending_action,
):
    seed_user(db_session)
    device = seed_device(
        db_session,
        registration_code="KPANEL-ACK002",
        device_id="kpanel-ack2",
        user_id=1,
        target_url="https://dashboard.example.com",
        pending_action=queued_action,
    )
    timestamp = utcnow()

    result = ack_device_action(
        db_session,
        device_id="kpanel-ack2",
        registration_code="KPANEL-ACK002",
        action=ack_action,
        status=" Completed ",
        now=timestamp,
    )

    assert result.status == "acknowledged"
    db_session.refresh(device)
    assert device.pending_action == expected_pending_action
    assert device.last_action == ack_action
    assert device.last_action_status == "completed"
    assert device.last_action_at is not None
    assert device.updated_at is not None


def test_queue_device_action_sets_pending_fields(db_session):
    seed_user(db_session)
    device = seed_device(
        db_session,
        registration_code="KPANEL-QUEUE",
        device_id="kpanel-queue",
        user_id=1,
        target_url="https://dashboard.example.com",
    )
    timestamp = utcnow()

    normalized = queue_device_action(device, " Reboot ", now=timestamp)

    assert normalized == "reboot"
    assert device.pending_action == "reboot"
    assert device.pending_action_requested_at is not None
    assert device.updated_at is not None


def test_queue_device_action_rejects_unsupported_action(db_session):
    seed_user(db_session)
    device = seed_device(
        db_session,
        registration_code="KPANEL-BADACT",
        device_id="kpanel-badact",
        user_id=1,
        target_url="https://dashboard.example.com",
    )

    with pytest.raises(HTTPException) as exc_info:
        queue_device_action(device, "factory-reset", now=utcnow())

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Unsupported action"
