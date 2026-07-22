"""HA KPanel browser_auth payload for device resolve."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ha_binding import resolve_ha_binding
from app.models import DeviceRegistration

BROWSER_AUTH_TYPE_HA = "ha_hass_tokens"


def build_browser_auth_payload(device: DeviceRegistration, db: Session) -> dict | None:
    """
    Return browser_auth for the device channel when HA binding is configured.

    Uses account → household → room → device inheritance (device wins).
    Secrets are only included on authenticated device-token responses.
    """
    resolved = resolve_ha_binding(device, db)
    if resolved is None:
        return None
    return {
        "type": BROWSER_AUTH_TYPE_HA,
        "bootstrap_url": resolved["bootstrap_url"],
        "binding_secret": resolved["binding_secret"],
    }
