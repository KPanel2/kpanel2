from sqlalchemy.orm import Session

from app.client_updates import get_latest_for_channel
from app.ha_binding import serialize_device_ha_binding, serialize_local_ha_binding
from app.models import DeviceRegistration, User, UserIdentity
from app.session_auth import to_iso


def serialize_identity(identity: UserIdentity) -> dict:
    return {
        "id": identity.id,
        "provider_name": identity.provider_name,
        "email": identity.email,
        "display_name": identity.display_name,
        "expires_at": to_iso(identity.expires_at),
    }


def serialize_device(device: DeviceRegistration, db: Session | None = None) -> dict:
    from app.households import resolve_device_url

    return {
        "registration_code": device.registration_code,
        "device_id": device.device_id,
        "display_name": device.display_name,
        "target_url": device.target_url,
        "claimed_at": to_iso(device.claimed_at),
        "registered_at": to_iso(device.claimed_at),
        "last_seen_at": to_iso(device.last_seen_at),
        "last_seen": to_iso(device.last_seen_at),
        "client_version": device.client_version,
        "pending_action": device.pending_action,
        "pending_action_requested_at": to_iso(device.pending_action_requested_at),
        "last_action": device.last_action,
        "last_action_status": device.last_action_status,
        "last_action_at": to_iso(device.last_action_at),
        "timezone": device.timezone,
        "room_id": device.room_id,
        "url_mode": device.url_mode or "custom",
        "household_url_id": device.household_url_id,
        "has_temp_url": bool(device.temp_url),
        "temp_url": device.temp_url,
        "temp_url_revert_mode": device.temp_url_revert_mode,
        "temp_url_revert_household_url_id": device.temp_url_revert_household_url_id,
        "temp_url_set_at": to_iso(device.temp_url_set_at),
        "resolved_url": resolve_device_url(device, db) if db is not None else None,
        "latest_client_version": get_latest_for_channel(device.client_version or "")[0] or None,
        **serialize_device_ha_binding(device, db),
    }


def serialize_user(
    user: User,
    identities: list[UserIdentity],
    devices: list[DeviceRegistration],
    db: Session | None = None,
) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "timezone": user.timezone or "America/Chicago",
        **serialize_local_ha_binding(user),
        "identities": [serialize_identity(identity) for identity in identities],
        "devices": [serialize_device(device, db) for device in devices],
    }
