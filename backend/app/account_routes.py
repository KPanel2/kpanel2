from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl, field_validator
from sqlalchemy.orm import Session

from app.db import get_db_session
from app.device_actions import queue_device_action
from app.ha_binding import apply_ha_binding_update, normalize_ha_bootstrap_url
from app.households import resolve_device_url
from app.kumpe_auth import AuthContext, require_authenticated, require_user_with_permission
from app.kumpe_permissions import Permissions
from app.models import DeviceRegistration, HouseholdMember, HouseholdUrl, User
from app.serializers import serialize_device
from app.session_auth import now_utc
from app.session_service import build_session_state, resolve_user_permissions
from app.user_service import (
    DEFAULT_TIMEZONE,
    claims_display_name,
    claims_email,
    claims_timezone,
    ensure_identity_for_user,
    sync_user_profile_from_claims,
)

router = APIRouter(prefix="/api/v1/account", tags=["account"])


class AccountCreateRequest(BaseModel):
    """Local account bootstrap — profile fields come from KumpeCloud Auth claims."""

    pass


class AccountProfileUpdateRequest(BaseModel):
    timezone: str | None = None
    ha_bootstrap_url: str | None = None
    ha_binding_secret: str | None = None
    clear_ha_binding: bool = False

    @field_validator("ha_bootstrap_url", mode="before")
    @classmethod
    def _validate_ha_bootstrap_url(cls, v: object) -> object:
        return normalize_ha_bootstrap_url(v)


class ClaimDeviceRequest(BaseModel):
    registration_code: str
    target_url: HttpUrl | None = None
    display_name: str | None = None
    household_id: int | None = None

    @field_validator("target_url", mode="before")
    @classmethod
    def _validate_target_url_scheme(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        if isinstance(v, str):
            cleaned = v.strip()
            lowered = cleaned.lower()
            if cleaned and not (lowered.startswith("http://") or lowered.startswith("https://")):
                raise ValueError("Display URL must start with http:// or https://")
            return cleaned
        return v


class DeviceUpdateRequest(BaseModel):
    display_name: str | None = None
    target_url: HttpUrl | None = None
    timezone: str | None = None
    room_id: int | None = None
    clear_room: bool = False
    url_mode: str | None = None
    household_url_id: int | None = None
    ha_bootstrap_url: str | None = None
    ha_binding_secret: str | None = None
    clear_ha_binding: bool = False

    @field_validator("target_url", mode="before")
    @classmethod
    def _validate_target_url_scheme(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        if isinstance(v, str):
            cleaned = v.strip()
            lowered = cleaned.lower()
            if cleaned and not (lowered.startswith("http://") or lowered.startswith("https://")):
                raise ValueError("Display URL must start with http:// or https://")
            return cleaned
        return v

    @field_validator("ha_bootstrap_url", mode="before")
    @classmethod
    def _validate_ha_bootstrap_url(cls, v: object) -> object:
        return normalize_ha_bootstrap_url(v)


class DeviceTempUrlSetRequest(BaseModel):
    temp_url: str

    @field_validator("temp_url", mode="before")
    @classmethod
    def _validate_scheme(cls, v: object) -> object:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("temp_url is required")
        cleaned = v.strip()
        lowered = cleaned.lower()
        if not (lowered.startswith("http://") or lowered.startswith("https://")):
            raise ValueError("temp_url must start with http:// or https://")
        return cleaned


def _validate_timezone(tz: str) -> str:
    try:
        from zoneinfo import ZoneInfo

        ZoneInfo(tz)
    except (KeyError, ModuleNotFoundError):
        raise HTTPException(status_code=400, detail=f"Invalid timezone: {tz!r}")
    return tz


def _get_owned_device(registration_code: str, user: User, db: Session) -> DeviceRegistration:
    device = db.get(DeviceRegistration, registration_code.strip().upper())
    if device is None or device.user_id != user.id:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.post("/create")
def account_create(
    req: AccountCreateRequest,
    auth: AuthContext = Depends(require_authenticated),
    db: Session = Depends(get_db_session),
) -> dict:
    if auth.user is not None:
        permissions = resolve_user_permissions(auth)
        return build_session_state(auth, db, permissions)

    email = claims_email(auth.claims)
    display_name = claims_display_name(auth.claims, email)
    timezone = claims_timezone(auth.claims) or DEFAULT_TIMEZONE

    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user is not None:
        auth.user = sync_user_profile_from_claims(existing_user, auth.claims, db)
        ensure_identity_for_user(auth.user, auth.claims, db)
        permissions = resolve_user_permissions(auth)
        return build_session_state(auth, db, permissions)

    timestamp = now_utc()
    user = User(
        email=email,
        display_name=display_name,
        timezone=_validate_timezone(timezone),
        created_at=timestamp,
        updated_at=timestamp,
        is_active=True,
    )
    db.add(user)
    db.flush()
    ensure_identity_for_user(user, auth.claims, db)
    db.commit()
    db.refresh(user)

    auth.user = user
    permissions = resolve_user_permissions(auth)
    return build_session_state(auth, db, permissions)


@router.patch("/profile")
def account_update_profile(
    req: AccountProfileUpdateRequest,
    auth_user: tuple = Depends(require_user_with_permission(Permissions.ACCOUNT_WRITE)),
    db: Session = Depends(get_db_session),
) -> dict:
    auth, user = auth_user
    updated = False

    if auth.dev_mode and req.timezone is not None:
        user.timezone = _validate_timezone(req.timezone.strip())
        updated = True

    if apply_ha_binding_update(
        user,
        clear_ha_binding=req.clear_ha_binding,
        ha_bootstrap_url=req.ha_bootstrap_url,
        ha_binding_secret=req.ha_binding_secret,
    ):
        updated = True

    if not updated:
        raise HTTPException(
            status_code=400,
            detail="Profile is managed in KumpeCloud Auth. Use the Account Center to update your profile.",
        )

    user.updated_at = now_utc()
    db.commit()
    permissions = resolve_user_permissions(auth)
    return build_session_state(auth, db, permissions)


@router.get("/devices")
def account_devices(
    auth_user: tuple = Depends(require_user_with_permission(Permissions.DEVICES_READ)),
    db: Session = Depends(get_db_session),
) -> dict:
    _, user = auth_user
    devices = (
        db.query(DeviceRegistration)
        .filter(DeviceRegistration.user_id == user.id)
        .order_by(DeviceRegistration.created_at.desc())
        .all()
    )
    return {"devices": [serialize_device(device, db) for device in devices]}


@router.post("/devices/claim")
def account_claim_device(
    req: ClaimDeviceRequest,
    auth_user: tuple = Depends(require_user_with_permission(Permissions.DEVICES_WRITE)),
    db: Session = Depends(get_db_session),
) -> dict:
    _, user = auth_user
    device = db.get(DeviceRegistration, req.registration_code.strip().upper())
    if device is None:
        raise HTTPException(
            status_code=404,
            detail="Registration code not found. Power on the panel first so it can register itself.",
        )

    if device.user_id is not None and device.user_id != user.id:
        raise HTTPException(status_code=409, detail="This registration code is already claimed by a different account")

    timestamp = now_utc()
    device.user_id = user.id
    device.display_name = (req.display_name or device.display_name or req.registration_code).strip()

    if req.target_url is not None:
        device.target_url = str(req.target_url)
        device.url_mode = "custom"
    elif req.household_id is not None:
        membership = (
            db.query(HouseholdMember)
            .filter(
                HouseholdMember.household_id == req.household_id,
                HouseholdMember.user_id == user.id,
            )
            .first()
        )
        if membership is None:
            raise HTTPException(status_code=403, detail="You are not a member of the specified household")
        household_hurl = (
            db.query(HouseholdUrl)
            .filter(
                HouseholdUrl.household_id == req.household_id,
                HouseholdUrl.is_default == True,  # noqa: E712
            )
            .first()
        )
        if household_hurl is None:
            household_hurl = (
                db.query(HouseholdUrl)
                .filter(HouseholdUrl.household_id == req.household_id)
                .order_by(HouseholdUrl.id)
                .first()
            )
        if household_hurl is None:
            raise HTTPException(
                status_code=400,
                detail="The specified household has no URLs configured. Add a household URL before claiming a device.",
            )
        device.url_mode = "household_url"
        device.household_url_id = household_hurl.id

    device.claimed_at = timestamp
    device.updated_at = timestamp
    db.commit()
    configured = bool(resolve_device_url(device, db))
    return {"status": "configured" if configured else "claimed", "device": serialize_device(device, db)}


@router.patch("/devices/{registration_code}")
def account_update_device(
    registration_code: str,
    req: DeviceUpdateRequest,
    auth_user: tuple = Depends(require_user_with_permission(Permissions.DEVICES_WRITE)),
    db: Session = Depends(get_db_session),
) -> dict:
    _, user = auth_user
    device = _get_owned_device(registration_code, user, db)

    updated = False
    if req.display_name is not None:
        cleaned = req.display_name.strip()
        device.display_name = cleaned or device.display_name
        updated = True
    if req.target_url is not None:
        device.target_url = str(req.target_url)
        if device.url_mode is None:
            device.url_mode = "custom"
        updated = True
    if req.timezone is not None:
        cleaned_tz = req.timezone.strip()
        device.timezone = _validate_timezone(cleaned_tz) if cleaned_tz else None
        updated = True
    if req.clear_room:
        device.room_id = None
        updated = True
    elif req.room_id is not None:
        device.room_id = req.room_id
        updated = True
    if req.url_mode is not None:
        cleaned_mode = req.url_mode.strip().lower()
        if cleaned_mode not in {"custom", "household_url"}:
            raise HTTPException(status_code=400, detail="url_mode must be 'custom' or 'household_url'")
        device.url_mode = cleaned_mode
        updated = True
    if req.household_url_id is not None:
        device.household_url_id = req.household_url_id
        updated = True
    if apply_ha_binding_update(
        device,
        clear_ha_binding=req.clear_ha_binding,
        ha_bootstrap_url=req.ha_bootstrap_url,
        ha_binding_secret=req.ha_binding_secret,
    ):
        updated = True

    if not updated:
        raise HTTPException(status_code=400, detail="No editable fields were provided")

    device.updated_at = now_utc()
    db.commit()
    return {"status": "updated", "device": serialize_device(device, db)}


@router.delete("/devices/{registration_code}")
def account_delete_device(
    registration_code: str,
    auth_user: tuple = Depends(require_user_with_permission(Permissions.DEVICES_WRITE)),
    db: Session = Depends(get_db_session),
) -> dict:
    _, user = auth_user
    device = _get_owned_device(registration_code, user, db)
    device_id = device.device_id
    db.delete(device)
    db.query(DeviceRegistration).filter(
        DeviceRegistration.device_id == device_id,
        DeviceRegistration.user_id == None,  # noqa: E711
    ).delete(synchronize_session=False)
    db.commit()
    return {"status": "deleted", "registration_code": registration_code.strip().upper()}


@router.post("/devices/{registration_code}/actions/{action}")
def account_device_action(
    registration_code: str,
    action: str,
    auth_user: tuple = Depends(require_user_with_permission(Permissions.DEVICES_WRITE)),
    db: Session = Depends(get_db_session),
) -> dict:
    _, user = auth_user
    device = _get_owned_device(registration_code, user, db)
    timestamp = now_utc()
    normalized_action = queue_device_action(device, action, now=timestamp)
    db.commit()
    return {"status": "queued", "action": normalized_action, "device": serialize_device(device, db)}


@router.post("/devices/{registration_code}/temp-url")
def account_set_device_temp_url(
    registration_code: str,
    req: DeviceTempUrlSetRequest,
    auth_user: tuple = Depends(require_user_with_permission(Permissions.DEVICES_WRITE)),
    db: Session = Depends(get_db_session),
) -> dict:
    _, user = auth_user
    device = _get_owned_device(registration_code, user, db)

    if not device.temp_url:
        device.temp_url_revert_mode = device.url_mode
        device.temp_url_revert_household_url_id = device.household_url_id

    device.temp_url = req.temp_url
    device.temp_url_set_at = now_utc()
    device.updated_at = now_utc()
    db.commit()
    return {"status": "temp_url_set", "device": serialize_device(device, db)}


@router.delete("/devices/{registration_code}/temp-url")
def account_clear_device_temp_url(
    registration_code: str,
    auth_user: tuple = Depends(require_user_with_permission(Permissions.DEVICES_WRITE)),
    db: Session = Depends(get_db_session),
) -> dict:
    _, user = auth_user
    device = _get_owned_device(registration_code, user, db)

    if not device.temp_url:
        raise HTTPException(status_code=400, detail="No temp URL is currently set")

    if device.temp_url_revert_mode is not None:
        device.url_mode = device.temp_url_revert_mode
    if device.temp_url_revert_household_url_id is not None:
        device.household_url_id = device.temp_url_revert_household_url_id

    device.temp_url = None
    device.temp_url_set_at = None
    device.temp_url_revert_mode = None
    device.temp_url_revert_household_url_id = None
    device.updated_at = now_utc()
    db.commit()
    return {"status": "temp_url_cleared", "device": serialize_device(device, db)}
