import pytest

from app.security import issue_device_token
from tests.factories import seed_device, seed_user


def _ack_payload(*, registration_code: str, action: str, status: str = "started") -> dict:
    return {
        "registration_code": registration_code,
        "action": action,
        "status": status,
    }


def _post_ack(client, *, device_id: str, token: str, payload: dict):
    return client.post(
        f"/api/v1/devices/{device_id}/actions/ack",
        json=payload,
        headers={"X-Device-Token": token},
    )


def test_ack_route_clears_pending_reboot(client, db_session):
    seed_user(db_session)
    device = seed_device(
        db_session,
        registration_code="KPANEL-REBOOT",
        device_id="kpanel-reboot",
        user_id=1,
        target_url="https://dashboard.example.com",
        pending_action="reboot",
    )
    token = issue_device_token("kpanel-reboot")

    response = _post_ack(
        client,
        device_id="kpanel-reboot",
        token=token,
        payload=_ack_payload(registration_code="KPANEL-REBOOT", action="reboot"),
    )

    assert response.status_code == 200
    assert response.json() == {"status": "acknowledged"}

    db_session.refresh(device)
    assert device.pending_action is None
    assert device.pending_action_requested_at is None
    assert device.last_action == "reboot"
    assert device.last_action_status == "started"


def test_ack_route_is_registered_for_update(client, db_session):
    seed_user(db_session)
    seed_device(
        db_session,
        registration_code="KPANEL-UPDATE",
        device_id="kpanel-update",
        user_id=1,
        target_url="https://dashboard.example.com",
        pending_action="update",
    )
    token = issue_device_token("kpanel-update")

    response = _post_ack(
        client,
        device_id="kpanel-update",
        token=token,
        payload=_ack_payload(
            registration_code="KPANEL-UPDATE",
            action="update",
            status="completed",
        ),
    )

    assert response.status_code == 200


@pytest.mark.parametrize(
    ("device_id", "registration_code", "expected_status"),
    [
        ("kpanel-missing", "KPANEL-MISSING", 404),
        ("kpanel-other", "KPANEL-WRONGID", 404),
    ],
)
def test_ack_route_returns_not_found(client, db_session, device_id, registration_code, expected_status):
    seed_user(db_session)
    seed_device(
        db_session,
        registration_code="KPANEL-WRONGID",
        device_id="kpanel-wrongid",
        user_id=1,
        target_url="https://dashboard.example.com",
        pending_action="reboot",
    )
    token = issue_device_token(device_id)

    response = _post_ack(
        client,
        device_id=device_id,
        token=token,
        payload=_ack_payload(registration_code=registration_code, action="reboot"),
    )

    assert response.status_code == expected_status


@pytest.mark.parametrize(
    ("headers", "expected_status"),
    [
        ({}, 401),
        ({"X-Device-Token": "invalid.token"}, 403),
    ],
)
def test_ack_route_requires_valid_device_token(client, db_session, headers, expected_status):
    seed_user(db_session)
    seed_device(
        db_session,
        registration_code="KPANEL-AUTH",
        device_id="kpanel-auth",
        user_id=1,
        target_url="https://dashboard.example.com",
        pending_action="reboot",
    )

    response = client.post(
        "/api/v1/devices/kpanel-auth/actions/ack",
        json=_ack_payload(registration_code="KPANEL-AUTH", action="reboot"),
        headers=headers,
    )

    assert response.status_code == expected_status
