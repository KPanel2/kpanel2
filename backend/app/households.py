from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.db import get_db_session
from app.models import (
    DeviceRegistration,
    Floor,
    Household,
    HouseholdMember,
    HouseholdUrl,
    Room,
    User,
)
from app.session_auth import now_utc

router = APIRouter(prefix="/api/v1/households", tags=["households"])


# ---------- Pydantic request schemas ----------


class HouseholdCreateRequest(BaseModel):
    name: str
    timezone: str | None = None


class HouseholdUpdateRequest(BaseModel):
    name: str | None = None
    timezone: str | None = None


class FloorCreateRequest(BaseModel):
    name: str
    sort_order: int = 0


class FloorUpdateRequest(BaseModel):
    name: str | None = None
    sort_order: int | None = None


class RoomCreateRequest(BaseModel):
    name: str
    floor_id: int | None = None
    sort_order: int = 0


class RoomUpdateRequest(BaseModel):
    name: str | None = None
    floor_id: int | None = None
    sort_order: int | None = None
    clear_floor: bool = False


class HouseholdUrlCreateRequest(BaseModel):
    friendly_name: str
    url_template: str
    is_default: bool = False

    @field_validator("url_template")
    @classmethod
    def _validate_url_template(cls, v: str) -> str:
        v = v.strip()
        lower = v.lower()
        if not (lower.startswith("http://") or lower.startswith("https://")):
            raise ValueError("URL template must start with http:// or https://")
        return v


class HouseholdUrlUpdateRequest(BaseModel):
    friendly_name: str | None = None
    url_template: str | None = None
    is_default: bool | None = None

    @field_validator("url_template")
    @classmethod
    def _validate_url_template(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        lower = v.lower()
        if not (lower.startswith("http://") or lower.startswith("https://")):
            raise ValueError("URL template must start with http:// or https://")
        return v


class HouseholdMemberAddRequest(BaseModel):
    email: str


# ---------- Serializers ----------


def _serialize_floor(floor: Floor) -> dict:
    return {
        "id": floor.id,
        "household_id": floor.household_id,
        "name": floor.name,
        "sort_order": floor.sort_order,
    }


def _serialize_room(room: Room) -> dict:
    return {
        "id": room.id,
        "household_id": room.household_id,
        "floor_id": room.floor_id,
        "name": room.name,
        "sort_order": room.sort_order,
    }


def _serialize_household_url(hu: HouseholdUrl) -> dict:
    return {
        "id": hu.id,
        "household_id": hu.household_id,
        "friendly_name": hu.friendly_name,
        "url_template": hu.url_template,
        "is_default": hu.is_default,
    }


def _serialize_member(member: HouseholdMember, user: User) -> dict:
    return {
        "user_id": member.user_id,
        "role": member.role,
        "email": user.email,
        "display_name": user.display_name,
    }


def _serialize_household(household: Household, db: Session) -> dict:
    floors = (
        db.query(Floor)
        .filter(Floor.household_id == household.id)
        .order_by(Floor.sort_order.asc(), Floor.id.asc())
        .all()
    )
    rooms = (
        db.query(Room)
        .filter(Room.household_id == household.id)
        .order_by(Room.sort_order.asc(), Room.id.asc())
        .all()
    )
    urls = (
        db.query(HouseholdUrl)
        .filter(HouseholdUrl.household_id == household.id)
        .order_by(HouseholdUrl.id.asc())
        .all()
    )
    members = (
        db.query(HouseholdMember)
        .filter(HouseholdMember.household_id == household.id)
        .order_by(HouseholdMember.created_at.asc())
        .all()
    )
    member_dicts = []
    for m in members:
        u = db.get(User, m.user_id)
        if u:
            member_dicts.append(_serialize_member(m, u))
    return {
        "id": household.id,
        "name": household.name,
        "timezone": household.timezone,
        "owner_id": household.owner_id,
        "floors": [_serialize_floor(f) for f in floors],
        "rooms": [_serialize_room(r) for r in rooms],
        "urls": [_serialize_household_url(u) for u in urls],
        "members": member_dicts,
    }


# ---------- Helpers ----------


def _get_current_user(request: Request, db: Session) -> User:
    from app.main import SESSION_USER_ID

    user_id = request.session.get(SESSION_USER_ID)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def _get_member_household(household_id: int, user_id: int, db: Session) -> Household:
    membership = (
        db.query(HouseholdMember)
        .filter(
            HouseholdMember.household_id == household_id,
            HouseholdMember.user_id == user_id,
        )
        .first()
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Household not found")
    household = db.get(Household, household_id)
    if household is None:
        raise HTTPException(status_code=404, detail="Household not found")
    return household


def _require_owner(household: Household, user_id: int) -> None:
    if household.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Only the household owner can perform this action")


def _validate_timezone(tz: str) -> str:
    try:
        from zoneinfo import ZoneInfo

        ZoneInfo(tz)
    except (KeyError, ModuleNotFoundError):
        raise HTTPException(status_code=400, detail=f"Invalid timezone: {tz!r}")
    return tz


def expand_url_template(template: str, device: DeviceRegistration, db: Session) -> str:
    """Replace {device}, {room}, {floor}, {household} placeholders in a URL template."""
    placeholders: dict[str, str] = {
        "device": device.display_name or "",
        "household": "",
        "floor": "",
        "room": "",
    }
    if device.room_id:
        room = db.get(Room, device.room_id)
        if room:
            placeholders["room"] = room.name
            if room.floor_id:
                floor = db.get(Floor, room.floor_id)
                if floor:
                    placeholders["floor"] = floor.name
            household = db.get(Household, room.household_id)
            if household:
                placeholders["household"] = household.name

    result = template
    for key, value in placeholders.items():
        result = result.replace(f"{{{key}}}", quote(value, safe=""))
    return result


def resolve_device_url(device: DeviceRegistration, db: Session) -> str | None:
    """Return the effective URL for a device, honouring temp URL and household URL templates."""
    if device.temp_url:
        return device.temp_url

    if device.url_mode == "household_url" and device.household_url_id:
        hurl = db.get(HouseholdUrl, device.household_url_id)
        if hurl:
            return expand_url_template(hurl.url_template, device, db)

    return device.target_url


# ---------- Household CRUD ----------


@router.post("")
def create_household(
    req: HouseholdCreateRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict:
    user = _get_current_user(request, db)
    tz = _validate_timezone(req.timezone.strip()) if req.timezone and req.timezone.strip() else user.timezone
    timestamp = now_utc()
    household = Household(
        name=req.name.strip(),
        timezone=tz,
        owner_id=user.id,
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(household)
    db.flush()
    db.add(
        HouseholdMember(
            household_id=household.id,
            user_id=user.id,
            role="owner",
            created_at=timestamp,
        )
    )
    db.commit()
    db.refresh(household)
    return {"household": _serialize_household(household, db)}


@router.get("")
def list_households(request: Request, db: Session = Depends(get_db_session)) -> dict:
    user = _get_current_user(request, db)
    memberships = (
        db.query(HouseholdMember)
        .filter(HouseholdMember.user_id == user.id)
        .order_by(HouseholdMember.created_at.asc())
        .all()
    )
    households = []
    for m in memberships:
        h = db.get(Household, m.household_id)
        if h:
            households.append(_serialize_household(h, db))
    return {"households": households}


@router.get("/{household_id}")
def get_household(
    household_id: int,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict:
    user = _get_current_user(request, db)
    household = _get_member_household(household_id, user.id, db)
    return {"household": _serialize_household(household, db)}


@router.patch("/{household_id}")
def update_household(
    household_id: int,
    req: HouseholdUpdateRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict:
    user = _get_current_user(request, db)
    household = _get_member_household(household_id, user.id, db)

    updated = False
    if req.name is not None:
        household.name = req.name.strip()
        updated = True
    if req.timezone is not None:
        cleaned = req.timezone.strip()
        household.timezone = _validate_timezone(cleaned) if cleaned else None
        updated = True

    if not updated:
        raise HTTPException(status_code=400, detail="No editable fields were provided")

    household.updated_at = now_utc()
    db.commit()
    return {"household": _serialize_household(household, db)}


@router.delete("/{household_id}")
def delete_household(
    household_id: int,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict:
    user = _get_current_user(request, db)
    household = _get_member_household(household_id, user.id, db)
    _require_owner(household, user.id)

    # Detach devices assigned to rooms in this household
    room_ids = [r.id for r in db.query(Room).filter(Room.household_id == household_id).all()]
    if room_ids:
        db.query(DeviceRegistration).filter(
            DeviceRegistration.room_id.in_(room_ids)
        ).update(
            {
                "room_id": None,
                "url_mode": None,
                "household_url_id": None,
            },
            synchronize_session=False,
        )

    db.query(HouseholdMember).filter(HouseholdMember.household_id == household_id).delete(synchronize_session=False)
    db.query(HouseholdUrl).filter(HouseholdUrl.household_id == household_id).delete(synchronize_session=False)
    db.query(Room).filter(Room.household_id == household_id).delete(synchronize_session=False)
    db.query(Floor).filter(Floor.household_id == household_id).delete(synchronize_session=False)
    db.delete(household)
    db.commit()
    return {"status": "deleted", "household_id": household_id}


# ---------- Members ----------


@router.get("/{household_id}/members")
def list_members(
    household_id: int,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict:
    user = _get_current_user(request, db)
    _get_member_household(household_id, user.id, db)
    members = (
        db.query(HouseholdMember)
        .filter(HouseholdMember.household_id == household_id)
        .order_by(HouseholdMember.created_at.asc())
        .all()
    )
    result = []
    for m in members:
        u = db.get(User, m.user_id)
        if u:
            result.append(_serialize_member(m, u))
    return {"members": result}


@router.post("/{household_id}/members")
def add_member(
    household_id: int,
    req: HouseholdMemberAddRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict:
    user = _get_current_user(request, db)
    household = _get_member_household(household_id, user.id, db)
    _require_owner(household, user.id)

    email = req.email.strip().lower()
    target_user = db.query(User).filter(User.email == email).first()
    if target_user is None:
        raise HTTPException(status_code=404, detail="No account found with that email address")

    existing = (
        db.query(HouseholdMember)
        .filter(
            HouseholdMember.household_id == household_id,
            HouseholdMember.user_id == target_user.id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="User is already a member of this household")

    db.add(
        HouseholdMember(
            household_id=household_id,
            user_id=target_user.id,
            role="member",
            created_at=now_utc(),
        )
    )
    db.commit()
    return {"status": "added", "member": _serialize_member(
        db.query(HouseholdMember)
        .filter(HouseholdMember.household_id == household_id, HouseholdMember.user_id == target_user.id)
        .first(),
        target_user,
    )}


@router.delete("/{household_id}/members/{user_id}")
def remove_member(
    household_id: int,
    user_id: int,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict:
    user = _get_current_user(request, db)
    household = _get_member_household(household_id, user.id, db)
    _require_owner(household, user.id)

    if user_id == household.owner_id:
        raise HTTPException(status_code=400, detail="Cannot remove the household owner")

    membership = (
        db.query(HouseholdMember)
        .filter(
            HouseholdMember.household_id == household_id,
            HouseholdMember.user_id == user_id,
        )
        .first()
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Member not found")

    db.delete(membership)
    db.commit()
    return {"status": "removed", "user_id": user_id}


# ---------- Floors ----------


@router.get("/{household_id}/floors")
def list_floors(
    household_id: int,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict:
    user = _get_current_user(request, db)
    _get_member_household(household_id, user.id, db)
    floors = (
        db.query(Floor)
        .filter(Floor.household_id == household_id)
        .order_by(Floor.sort_order.asc(), Floor.id.asc())
        .all()
    )
    return {"floors": [_serialize_floor(f) for f in floors]}


@router.post("/{household_id}/floors")
def create_floor(
    household_id: int,
    req: FloorCreateRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict:
    user = _get_current_user(request, db)
    _get_member_household(household_id, user.id, db)
    timestamp = now_utc()
    floor = Floor(
        household_id=household_id,
        name=req.name.strip(),
        sort_order=req.sort_order,
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(floor)
    db.commit()
    db.refresh(floor)
    return {"floor": _serialize_floor(floor)}


@router.patch("/{household_id}/floors/{floor_id}")
def update_floor(
    household_id: int,
    floor_id: int,
    req: FloorUpdateRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict:
    user = _get_current_user(request, db)
    _get_member_household(household_id, user.id, db)
    floor = db.get(Floor, floor_id)
    if floor is None or floor.household_id != household_id:
        raise HTTPException(status_code=404, detail="Floor not found")

    updated = False
    if req.name is not None:
        floor.name = req.name.strip()
        updated = True
    if req.sort_order is not None:
        floor.sort_order = req.sort_order
        updated = True

    if not updated:
        raise HTTPException(status_code=400, detail="No editable fields were provided")

    floor.updated_at = now_utc()
    db.commit()
    return {"floor": _serialize_floor(floor)}


@router.delete("/{household_id}/floors/{floor_id}")
def delete_floor(
    household_id: int,
    floor_id: int,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict:
    user = _get_current_user(request, db)
    _get_member_household(household_id, user.id, db)
    floor = db.get(Floor, floor_id)
    if floor is None or floor.household_id != household_id:
        raise HTTPException(status_code=404, detail="Floor not found")

    # Unassign rooms from the floor (keep rooms in the household, just unset floor)
    db.query(Room).filter(Room.floor_id == floor_id).update(
        {"floor_id": None}, synchronize_session=False
    )
    db.delete(floor)
    db.commit()
    return {"status": "deleted", "floor_id": floor_id}


# ---------- Rooms ----------


@router.get("/{household_id}/rooms")
def list_rooms(
    household_id: int,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict:
    user = _get_current_user(request, db)
    _get_member_household(household_id, user.id, db)
    rooms = (
        db.query(Room)
        .filter(Room.household_id == household_id)
        .order_by(Room.sort_order.asc(), Room.id.asc())
        .all()
    )
    return {"rooms": [_serialize_room(r) for r in rooms]}


@router.post("/{household_id}/rooms")
def create_room(
    household_id: int,
    req: RoomCreateRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict:
    user = _get_current_user(request, db)
    _get_member_household(household_id, user.id, db)

    if req.floor_id is not None:
        floor = db.get(Floor, req.floor_id)
        if floor is None or floor.household_id != household_id:
            raise HTTPException(status_code=400, detail="Floor not found in this household")

    timestamp = now_utc()
    room = Room(
        household_id=household_id,
        floor_id=req.floor_id,
        name=req.name.strip(),
        sort_order=req.sort_order,
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return {"room": _serialize_room(room)}


@router.patch("/{household_id}/rooms/{room_id}")
def update_room(
    household_id: int,
    room_id: int,
    req: RoomUpdateRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict:
    user = _get_current_user(request, db)
    _get_member_household(household_id, user.id, db)
    room = db.get(Room, room_id)
    if room is None or room.household_id != household_id:
        raise HTTPException(status_code=404, detail="Room not found")

    updated = False
    if req.name is not None:
        room.name = req.name.strip()
        updated = True
    if req.clear_floor:
        room.floor_id = None
        updated = True
    elif req.floor_id is not None:
        floor = db.get(Floor, req.floor_id)
        if floor is None or floor.household_id != household_id:
            raise HTTPException(status_code=400, detail="Floor not found in this household")
        room.floor_id = req.floor_id
        updated = True
    if req.sort_order is not None:
        room.sort_order = req.sort_order
        updated = True

    if not updated:
        raise HTTPException(status_code=400, detail="No editable fields were provided")

    room.updated_at = now_utc()
    db.commit()
    return {"room": _serialize_room(room)}


@router.delete("/{household_id}/rooms/{room_id}")
def delete_room(
    household_id: int,
    room_id: int,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict:
    user = _get_current_user(request, db)
    _get_member_household(household_id, user.id, db)
    room = db.get(Room, room_id)
    if room is None or room.household_id != household_id:
        raise HTTPException(status_code=404, detail="Room not found")

    # Detach devices from this room
    db.query(DeviceRegistration).filter(DeviceRegistration.room_id == room_id).update(
        {"room_id": None}, synchronize_session=False
    )
    db.delete(room)
    db.commit()
    return {"status": "deleted", "room_id": room_id}


# ---------- Household URLs ----------


@router.get("/{household_id}/urls")
def list_household_urls(
    household_id: int,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict:
    user = _get_current_user(request, db)
    _get_member_household(household_id, user.id, db)
    urls = (
        db.query(HouseholdUrl)
        .filter(HouseholdUrl.household_id == household_id)
        .order_by(HouseholdUrl.id.asc())
        .all()
    )
    return {"urls": [_serialize_household_url(u) for u in urls]}


@router.post("/{household_id}/urls")
def create_household_url(
    household_id: int,
    req: HouseholdUrlCreateRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict:
    user = _get_current_user(request, db)
    _get_member_household(household_id, user.id, db)

    timestamp = now_utc()
    if req.is_default:
        db.query(HouseholdUrl).filter(
            HouseholdUrl.household_id == household_id,
            HouseholdUrl.is_default == True,  # noqa: E712
        ).update({"is_default": False, "updated_at": timestamp}, synchronize_session=False)

    hurl = HouseholdUrl(
        household_id=household_id,
        friendly_name=req.friendly_name.strip(),
        url_template=req.url_template,
        is_default=req.is_default,
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(hurl)
    db.commit()
    db.refresh(hurl)
    return {"url": _serialize_household_url(hurl)}


@router.patch("/{household_id}/urls/{url_id}")
def update_household_url(
    household_id: int,
    url_id: int,
    req: HouseholdUrlUpdateRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict:
    user = _get_current_user(request, db)
    _get_member_household(household_id, user.id, db)
    hurl = db.get(HouseholdUrl, url_id)
    if hurl is None or hurl.household_id != household_id:
        raise HTTPException(status_code=404, detail="URL not found")

    timestamp = now_utc()
    updated = False
    if req.friendly_name is not None:
        hurl.friendly_name = req.friendly_name.strip()
        updated = True
    if req.url_template is not None:
        hurl.url_template = req.url_template
        updated = True
    if req.is_default is not None:
        if req.is_default and not hurl.is_default:
            db.query(HouseholdUrl).filter(
                HouseholdUrl.household_id == household_id,
                HouseholdUrl.is_default == True,  # noqa: E712
            ).update({"is_default": False, "updated_at": timestamp}, synchronize_session=False)
        hurl.is_default = req.is_default
        updated = True

    if not updated:
        raise HTTPException(status_code=400, detail="No editable fields were provided")

    hurl.updated_at = timestamp
    db.commit()
    return {"url": _serialize_household_url(hurl)}


@router.post("/{household_id}/urls/{url_id}/set-default")
def set_default_household_url(
    household_id: int,
    url_id: int,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict:
    user = _get_current_user(request, db)
    _get_member_household(household_id, user.id, db)
    hurl = db.get(HouseholdUrl, url_id)
    if hurl is None or hurl.household_id != household_id:
        raise HTTPException(status_code=404, detail="URL not found")

    timestamp = now_utc()
    db.query(HouseholdUrl).filter(
        HouseholdUrl.household_id == household_id,
        HouseholdUrl.is_default == True,  # noqa: E712
    ).update({"is_default": False, "updated_at": timestamp}, synchronize_session=False)
    hurl.is_default = True
    hurl.updated_at = timestamp
    db.commit()
    return {"url": _serialize_household_url(hurl)}


@router.delete("/{household_id}/urls/{url_id}")
def delete_household_url(
    household_id: int,
    url_id: int,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict:
    user = _get_current_user(request, db)
    _get_member_household(household_id, user.id, db)
    hurl = db.get(HouseholdUrl, url_id)
    if hurl is None or hurl.household_id != household_id:
        raise HTTPException(status_code=404, detail="URL not found")

    # Detach devices that reference this household URL
    db.query(DeviceRegistration).filter(
        DeviceRegistration.household_url_id == url_id
    ).update(
        {"household_url_id": None, "url_mode": None},
        synchronize_session=False,
    )
    db.delete(hurl)
    db.commit()
    return {"status": "deleted", "url_id": url_id}


# ---------- Household URL lookup by friendly name (for API automations) ----------


@router.get("/{household_id}/urls/by-name/{friendly_name}")
def get_household_url_by_name(
    household_id: int,
    friendly_name: str,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict:
    user = _get_current_user(request, db)
    _get_member_household(household_id, user.id, db)
    hurl = (
        db.query(HouseholdUrl)
        .filter(
            HouseholdUrl.household_id == household_id,
            HouseholdUrl.friendly_name == friendly_name,
        )
        .first()
    )
    if hurl is None:
        raise HTTPException(status_code=404, detail="URL not found")
    return {"url": _serialize_household_url(hurl)}
