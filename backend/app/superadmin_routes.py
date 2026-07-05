"""Cross-tenant system admin routes (kpanel:superadmin)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl, field_validator
from sqlalchemy.orm import Session

from app.account_routes import _validate_timezone
from app.db import get_db_session
from app.households import _serialize_household, _serialize_household_url
from app.kumpe_auth import require_superadmin
from app.models import (
    DeviceRegistration,
    Household,
    HouseholdMember,
    HouseholdUrl,
    User,
    UserIdentity,
)
from app.serializers import serialize_device, serialize_identity
from app.session_auth import now_utc, to_iso
from app.user_service import normalize_email

router = APIRouter(prefix="/api/v1/superadmin", tags=["superadmin"])


class SuperadminUserUpdateRequest(BaseModel):
    is_active: bool | None = None


class SuperadminHouseholdUpdateRequest(BaseModel):
    name: str | None = None
    timezone: str | None = None
    owner_id: int | None = None


class SuperadminHouseholdMemberRequest(BaseModel):
    email: str
    role: str = "member"


class SuperadminDeviceUpdateRequest(BaseModel):
    user_id: int | None = None
    unclaim: bool = False
    display_name: str | None = None
    target_url: HttpUrl | None = None
    timezone: str | None = None
    room_id: int | None = None
    clear_room: bool = False
    url_mode: str | None = None
    household_url_id: int | None = None

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


class SuperadminUrlUpdateRequest(BaseModel):
    friendly_name: str | None = None
    url_template: str | None = None
    is_default: bool | None = None
    household_id: int | None = None

    @field_validator("url_template")
    @classmethod
    def _validate_url_template(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.strip()
        lowered = cleaned.lower()
        if not (lowered.startswith("http://") or lowered.startswith("https://")):
            raise ValueError("URL template must start with http:// or https://")
        return cleaned


def _serialize_user_summary(user: User, db: Session) -> dict:
    device_count = (
        db.query(DeviceRegistration)
        .filter(DeviceRegistration.user_id == user.id)
        .count()
    )
    household_count = (
        db.query(HouseholdMember)
        .filter(HouseholdMember.user_id == user.id)
        .count()
    )
    owned_count = (
        db.query(Household)
        .filter(Household.owner_id == user.id)
        .count()
    )
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "timezone": user.timezone,
        "is_active": user.is_active,
        "created_at": to_iso(user.created_at),
        "updated_at": to_iso(user.updated_at),
        "device_count": device_count,
        "household_count": household_count,
        "owned_household_count": owned_count,
    }


def _get_user_or_404(user_id: int, db: Session) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _get_household_or_404(household_id: int, db: Session) -> Household:
    household = db.get(Household, household_id)
    if household is None:
        raise HTTPException(status_code=404, detail="Household not found")
    return household


def _get_device_or_404(registration_code: str, db: Session) -> DeviceRegistration:
    device = db.get(DeviceRegistration, registration_code.strip().upper())
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


def _get_url_or_404(url_id: int, db: Session) -> HouseholdUrl:
    household_url = db.get(HouseholdUrl, url_id)
    if household_url is None:
        raise HTTPException(status_code=404, detail="Household URL not found")
    return household_url


def _owner_brief(user: User | None) -> dict | None:
    if user is None:
        return None
    return {"id": user.id, "email": user.email, "display_name": user.display_name}


def _transfer_household_owner(household: Household, new_owner_id: int, db: Session) -> None:
    if new_owner_id == household.owner_id:
        return

    new_owner = _get_user_or_404(new_owner_id, db)
    old_owner_id = household.owner_id
    timestamp = now_utc()

    household.owner_id = new_owner.id
    household.updated_at = timestamp

    new_membership = (
        db.query(HouseholdMember)
        .filter(
            HouseholdMember.household_id == household.id,
            HouseholdMember.user_id == new_owner.id,
        )
        .first()
    )
    if new_membership is None:
        db.add(
            HouseholdMember(
                household_id=household.id,
                user_id=new_owner.id,
                role="owner",
                created_at=timestamp,
            )
        )
    else:
        new_membership.role = "owner"

    if old_owner_id != new_owner.id:
        old_membership = (
            db.query(HouseholdMember)
            .filter(
                HouseholdMember.household_id == household.id,
                HouseholdMember.user_id == old_owner_id,
            )
            .first()
        )
        if old_membership is None:
            db.add(
                HouseholdMember(
                    household_id=household.id,
                    user_id=old_owner_id,
                    role="member",
                    created_at=timestamp,
                )
            )
        elif old_membership.role == "owner":
            old_membership.role = "member"


def _serialize_device_admin(device: DeviceRegistration, db: Session) -> dict:
    payload = serialize_device(device, db)
    owner = db.get(User, device.user_id) if device.user_id is not None else None
    payload["owner"] = _owner_brief(owner)
    return payload


def _serialize_household_summary(household: Household, db: Session) -> dict:
    owner = db.get(User, household.owner_id)
    member_count = (
        db.query(HouseholdMember)
        .filter(HouseholdMember.household_id == household.id)
        .count()
    )
    url_count = (
        db.query(HouseholdUrl)
        .filter(HouseholdUrl.household_id == household.id)
        .count()
    )
    device_count = (
        db.query(DeviceRegistration)
        .join(HouseholdMember, HouseholdMember.user_id == DeviceRegistration.user_id)
        .filter(HouseholdMember.household_id == household.id)
        .count()
    )
    return {
        "id": household.id,
        "name": household.name,
        "timezone": household.timezone,
        "owner_id": household.owner_id,
        "owner": _owner_brief(owner),
        "member_count": member_count,
        "url_count": url_count,
        "device_count": device_count,
        "created_at": to_iso(household.created_at),
        "updated_at": to_iso(household.updated_at),
    }


def _serialize_url_admin(household_url: HouseholdUrl, db: Session) -> dict:
    payload = _serialize_household_url(household_url)
    household = db.get(Household, household_url.household_id)
    owner = db.get(User, household.owner_id) if household is not None else None
    payload["household_name"] = household.name if household is not None else None
    payload["owner"] = _owner_brief(owner)
    return payload


@router.get("/overview")
def superadmin_overview(
    _: object = Depends(require_superadmin),
    db: Session = Depends(get_db_session),
) -> dict:
    return {
        "users": db.query(User).count(),
        "active_users": db.query(User).filter(User.is_active == True).count(),  # noqa: E712
        "households": db.query(Household).count(),
        "devices": db.query(DeviceRegistration).count(),
        "claimed_devices": db.query(DeviceRegistration).filter(DeviceRegistration.user_id.isnot(None)).count(),
        "household_urls": db.query(HouseholdUrl).count(),
    }


@router.get("/users")
def superadmin_list_users(
    _: object = Depends(require_superadmin),
    db: Session = Depends(get_db_session),
) -> dict:
    users = db.query(User).order_by(User.id.asc()).all()
    return {"users": [_serialize_user_summary(user, db) for user in users]}


@router.get("/users/{user_id}")
def superadmin_get_user(
    user_id: int,
    _: object = Depends(require_superadmin),
    db: Session = Depends(get_db_session),
) -> dict:
    user = _get_user_or_404(user_id, db)
    identities = (
        db.query(UserIdentity)
        .filter(UserIdentity.user_id == user.id)
        .order_by(UserIdentity.provider_name.asc())
        .all()
    )
    devices = (
        db.query(DeviceRegistration)
        .filter(DeviceRegistration.user_id == user.id)
        .order_by(DeviceRegistration.created_at.desc())
        .all()
    )
    memberships = (
        db.query(HouseholdMember)
        .filter(HouseholdMember.user_id == user.id)
        .order_by(HouseholdMember.created_at.asc())
        .all()
    )
    household_rows = []
    for membership in memberships:
        household = db.get(Household, membership.household_id)
        if household is None:
            continue
        household_rows.append(
            {
                "household_id": household.id,
                "name": household.name,
                "role": membership.role,
                "is_owner": household.owner_id == user.id,
            }
        )
    return {
        "user": _serialize_user_summary(user, db),
        "identities": [serialize_identity(identity) for identity in identities],
        "devices": [_serialize_device_admin(device, db) for device in devices],
        "households": household_rows,
    }


@router.patch("/users/{user_id}")
def superadmin_update_user(
    user_id: int,
    req: SuperadminUserUpdateRequest,
    _: object = Depends(require_superadmin),
    db: Session = Depends(get_db_session),
) -> dict:
    user = _get_user_or_404(user_id, db)
    if req.is_active is None:
        raise HTTPException(status_code=400, detail="No editable fields were provided")

    user.is_active = req.is_active
    user.updated_at = now_utc()
    db.commit()
    db.refresh(user)
    return {"status": "updated", "user": _serialize_user_summary(user, db)}


@router.get("/households")
def superadmin_list_households(
    _: object = Depends(require_superadmin),
    db: Session = Depends(get_db_session),
) -> dict:
    households = db.query(Household).order_by(Household.id.asc()).all()
    return {"households": [_serialize_household_summary(household, db) for household in households]}


@router.get("/households/{household_id}")
def superadmin_get_household(
    household_id: int,
    _: object = Depends(require_superadmin),
    db: Session = Depends(get_db_session),
) -> dict:
    household = _get_household_or_404(household_id, db)
    return {"household": _serialize_household(household, db)}


@router.patch("/households/{household_id}")
def superadmin_update_household(
    household_id: int,
    req: SuperadminHouseholdUpdateRequest,
    _: object = Depends(require_superadmin),
    db: Session = Depends(get_db_session),
) -> dict:
    household = _get_household_or_404(household_id, db)
    updated = False

    if req.name is not None:
        cleaned = req.name.strip()
        if not cleaned:
            raise HTTPException(status_code=400, detail="Household name cannot be empty")
        household.name = cleaned
        updated = True

    if req.timezone is not None:
        cleaned_tz = req.timezone.strip()
        household.timezone = _validate_timezone(cleaned_tz) if cleaned_tz else None
        updated = True

    if req.owner_id is not None:
        _transfer_household_owner(household, req.owner_id, db)
        updated = True

    if not updated:
        raise HTTPException(status_code=400, detail="No editable fields were provided")

    household.updated_at = now_utc()
    db.commit()
    db.refresh(household)
    return {"status": "updated", "household": _serialize_household(household, db)}


@router.post("/households/{household_id}/members")
def superadmin_add_household_member(
    household_id: int,
    req: SuperadminHouseholdMemberRequest,
    _: object = Depends(require_superadmin),
    db: Session = Depends(get_db_session),
) -> dict:
    household = _get_household_or_404(household_id, db)
    role = req.role.strip().lower()
    if role not in {"owner", "member"}:
        raise HTTPException(status_code=400, detail="role must be 'owner' or 'member'")

    try:
        email = normalize_email(req.email)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise HTTPException(status_code=404, detail="No local user exists for that email")

    existing = (
        db.query(HouseholdMember)
        .filter(
            HouseholdMember.household_id == household.id,
            HouseholdMember.user_id == user.id,
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="User is already a member of this household")

    timestamp = now_utc()
    db.add(
        HouseholdMember(
            household_id=household.id,
            user_id=user.id,
            role=role,
            created_at=timestamp,
        )
    )
    if role == "owner":
        _transfer_household_owner(household, user.id, db)

    household.updated_at = timestamp
    db.commit()
    return {"status": "added", "household": _serialize_household(household, db)}


@router.delete("/households/{household_id}/members/{member_user_id}")
def superadmin_remove_household_member(
    household_id: int,
    member_user_id: int,
    _: object = Depends(require_superadmin),
    db: Session = Depends(get_db_session),
) -> dict:
    household = _get_household_or_404(household_id, db)
    if member_user_id == household.owner_id:
        raise HTTPException(status_code=400, detail="Transfer ownership before removing the household owner")

    membership = (
        db.query(HouseholdMember)
        .filter(
            HouseholdMember.household_id == household.id,
            HouseholdMember.user_id == member_user_id,
        )
        .first()
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Household member not found")

    db.delete(membership)
    household.updated_at = now_utc()
    db.commit()
    return {"status": "removed", "household": _serialize_household(household, db)}


@router.get("/devices")
def superadmin_list_devices(
    _: object = Depends(require_superadmin),
    db: Session = Depends(get_db_session),
) -> dict:
    devices = (
        db.query(DeviceRegistration)
        .order_by(DeviceRegistration.created_at.desc())
        .all()
    )
    return {"devices": [_serialize_device_admin(device, db) for device in devices]}


@router.patch("/devices/{registration_code}")
def superadmin_update_device(
    registration_code: str,
    req: SuperadminDeviceUpdateRequest,
    _: object = Depends(require_superadmin),
    db: Session = Depends(get_db_session),
) -> dict:
    device = _get_device_or_404(registration_code, db)
    updated = False
    timestamp = now_utc()

    if req.unclaim:
        device.user_id = None
        device.claimed_at = None
        updated = True
    elif req.user_id is not None:
        _get_user_or_404(req.user_id, db)
        device.user_id = req.user_id
        device.claimed_at = device.claimed_at or timestamp
        updated = True

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

    if not updated:
        raise HTTPException(status_code=400, detail="No editable fields were provided")

    device.updated_at = timestamp
    db.commit()
    return {"status": "updated", "device": _serialize_device_admin(device, db)}


@router.get("/urls")
def superadmin_list_urls(
    _: object = Depends(require_superadmin),
    db: Session = Depends(get_db_session),
) -> dict:
    urls = (
        db.query(HouseholdUrl)
        .order_by(HouseholdUrl.household_id.asc(), HouseholdUrl.id.asc())
        .all()
    )
    return {"urls": [_serialize_url_admin(url, db) for url in urls]}


@router.patch("/urls/{url_id}")
def superadmin_update_url(
    url_id: int,
    req: SuperadminUrlUpdateRequest,
    _: object = Depends(require_superadmin),
    db: Session = Depends(get_db_session),
) -> dict:
    household_url = _get_url_or_404(url_id, db)
    updated = False

    if req.household_id is not None:
        _get_household_or_404(req.household_id, db)
        household_url.household_id = req.household_id
        updated = True

    if req.friendly_name is not None:
        cleaned = req.friendly_name.strip()
        if not cleaned:
            raise HTTPException(status_code=400, detail="Friendly name cannot be empty")
        household_url.friendly_name = cleaned
        updated = True

    if req.url_template is not None:
        household_url.url_template = req.url_template
        updated = True

    if req.is_default is not None:
        if req.is_default:
            db.query(HouseholdUrl).filter(
                HouseholdUrl.household_id == household_url.household_id,
                HouseholdUrl.id != household_url.id,
            ).update({"is_default": False}, synchronize_session=False)
        household_url.is_default = req.is_default
        updated = True

    if not updated:
        raise HTTPException(status_code=400, detail="No editable fields were provided")

    household_url.updated_at = now_utc()
    db.commit()
    db.refresh(household_url)
    return {"status": "updated", "url": _serialize_url_admin(household_url, db)}
