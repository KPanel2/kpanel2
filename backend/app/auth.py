import os

from fastapi import Header, HTTPException

from app.security import verify_device_token


def require_admin_api_key(x_admin_key: str | None = Header(default=None)) -> None:
    expected = os.getenv("KPANEL_ADMIN_API_KEY", "change-me")
    if not x_admin_key or x_admin_key != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


def require_device_access(device_id: str, device_token: str | None) -> None:
    enforce = os.getenv("KPANEL_ENFORCE_DEVICE_TOKEN", "true").lower() == "true"
    if not enforce:
        return

    if not device_token:
        raise HTTPException(status_code=401, detail="Missing device token")

    if not verify_device_token(device_token, device_id):
        raise HTTPException(status_code=403, detail="Invalid or expired device token")
