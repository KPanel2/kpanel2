from dataclasses import dataclass
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import DeviceRegistration

SUPPORTED_DEVICE_ACTIONS = frozenset({"update", "reboot"})


def normalize_device_action(action: str) -> str:
    return action.strip().lower()


def normalize_registration_code(registration_code: str) -> str:
    return registration_code.strip().upper()


def normalize_action_status(status: str) -> str:
    return status.strip().lower()


@dataclass(frozen=True)
class DeviceActionAckResult:
    status: str = "acknowledged"


def get_device_for_ack(
    db: Session,
    *,
    device_id: str,
    registration_code: str,
) -> DeviceRegistration:
    device = db.get(DeviceRegistration, normalize_registration_code(registration_code))
    if device is None or device.device_id != device_id:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


def queue_device_action(device: DeviceRegistration, action: str, *, now: datetime) -> str:
    normalized_action = normalize_device_action(action)
    if normalized_action not in SUPPORTED_DEVICE_ACTIONS:
        raise HTTPException(status_code=400, detail="Unsupported action")

    device.pending_action = normalized_action
    device.pending_action_requested_at = now
    device.updated_at = now
    return normalized_action


def ack_device_action(
    db: Session,
    *,
    device_id: str,
    registration_code: str,
    action: str,
    status: str,
    now: datetime,
) -> DeviceActionAckResult:
    device = get_device_for_ack(db, device_id=device_id, registration_code=registration_code)
    normalized_action = normalize_device_action(action)
    normalized_status = normalize_action_status(status)

    if device.pending_action and device.pending_action == normalized_action:
        device.pending_action = None
        device.pending_action_requested_at = None

    device.last_action = normalized_action
    device.last_action_status = normalized_status
    device.last_action_at = now
    device.updated_at = now
    db.commit()
    return DeviceActionAckResult()
