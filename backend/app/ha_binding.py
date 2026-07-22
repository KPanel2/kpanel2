"""HA binding storage helpers and inheritance resolution."""

from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.models import DeviceRegistration, Household, Room, User

HA_BINDING_SOURCES = ("device", "room", "household", "account")


class _HaBindingEntity(Protocol):
    ha_bootstrap_url: str | None
    ha_binding_secret: str | None


def complete_ha_binding(entity: _HaBindingEntity) -> tuple[str, str] | None:
    """Return (url, secret) when both fields are non-empty after strip."""
    bootstrap_url = (entity.ha_bootstrap_url or "").strip()
    binding_secret = (entity.ha_binding_secret or "").strip()
    if not bootstrap_url or not binding_secret:
        return None
    return bootstrap_url, binding_secret


def serialize_local_ha_binding(entity: _HaBindingEntity) -> dict[str, Any]:
    pair = complete_ha_binding(entity)
    return {
        "ha_bootstrap_url": entity.ha_bootstrap_url,
        "has_ha_binding": pair is not None,
    }


def apply_ha_binding_update(
    entity: _HaBindingEntity,
    *,
    clear_ha_binding: bool = False,
    ha_bootstrap_url: str | None = None,
    ha_binding_secret: str | None = None,
) -> bool:
    """
    Apply HA binding mutations onto an entity.

    Returns True when any field was changed. Clearing nulls both fields.
    Omitting bootstrap/secret (None) leaves existing values unchanged.
    """
    if clear_ha_binding:
        entity.ha_bootstrap_url = None
        entity.ha_binding_secret = None
        return True

    updated = False
    if ha_bootstrap_url is not None:
        entity.ha_bootstrap_url = ha_bootstrap_url
        updated = True
    if ha_binding_secret is not None:
        cleaned = ha_binding_secret.strip()
        entity.ha_binding_secret = cleaned or None
        updated = True
    return updated


def normalize_ha_bootstrap_url(value: object) -> object:
    """Pydantic before-validator: empty → None; require http(s) scheme."""
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        lowered = cleaned.lower()
        if not (lowered.startswith("http://") or lowered.startswith("https://")):
            raise ValueError("ha_bootstrap_url must start with http:// or https://")
        return cleaned
    return value


def resolve_ha_binding(device: DeviceRegistration, db: Session) -> dict[str, str] | None:
    """
    Resolve effective HA binding for a device.

    Priority (lower overrides higher): device → room → household → account.
    A level wins only when both bootstrap URL and binding secret are set.
    """
    pair = complete_ha_binding(device)
    if pair:
        return {
            "bootstrap_url": pair[0],
            "binding_secret": pair[1],
            "source": "device",
        }

    room: Room | None = None
    household: Household | None = None
    if device.room_id:
        room = db.get(Room, device.room_id)
        if room is not None:
            pair = complete_ha_binding(room)
            if pair:
                return {
                    "bootstrap_url": pair[0],
                    "binding_secret": pair[1],
                    "source": "room",
                }
            household = db.get(Household, room.household_id)
            if household is not None:
                pair = complete_ha_binding(household)
                if pair:
                    return {
                        "bootstrap_url": pair[0],
                        "binding_secret": pair[1],
                        "source": "household",
                    }

    if device.user_id:
        user = db.get(User, device.user_id)
        if user is not None:
            pair = complete_ha_binding(user)
            if pair:
                return {
                    "bootstrap_url": pair[0],
                    "binding_secret": pair[1],
                    "source": "account",
                }

    return None


def serialize_device_ha_binding(device: DeviceRegistration, db: Session | None) -> dict[str, Any]:
    """Portal fields: local override plus effective resolution when db is available."""
    local = serialize_local_ha_binding(device)
    if db is None:
        return {
            **local,
            "has_local_ha_binding": local["has_ha_binding"],
            "ha_binding_source": "device" if local["has_ha_binding"] else None,
            "effective_ha_bootstrap_url": device.ha_bootstrap_url if local["has_ha_binding"] else None,
        }

    resolved = resolve_ha_binding(device, db)
    return {
        "ha_bootstrap_url": device.ha_bootstrap_url,
        "has_local_ha_binding": local["has_ha_binding"],
        "has_ha_binding": resolved is not None,
        "ha_binding_source": resolved["source"] if resolved else None,
        "effective_ha_bootstrap_url": resolved["bootstrap_url"] if resolved else None,
    }
