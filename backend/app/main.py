import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl, field_validator
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.account_routes import router as account_router
from app.auth import require_admin_api_key, require_device_access
from app.auth_routes import router as auth_router
from app.superadmin_routes import router as superadmin_router
from app.client_updates import build_update_policy, get_latest_for_channel
from app.db import Base, engine, get_db_session
from app.device_actions import ack_device_action as record_device_action_ack
from app.models import DeviceRegistration, Household, HouseholdMember, HouseholdUrl, Registration, Room, User
from app.security import issue_device_token
from app.session_auth import now_utc

logger = logging.getLogger(__name__)


FRONTEND_BASE_URL = os.getenv("KPANEL_FRONTEND_BASE_URL", "http://localhost:8080").rstrip("/")
REQUIRE_HTTPS = os.getenv("KPANEL_REQUIRE_HTTPS", "false").lower() == "true"
DEVICE_TOKEN_EXPIRES_MINUTES = int(os.getenv("KPANEL_DEVICE_TOKEN_EXPIRES_MINUTES", str(60 * 24 * 30)))
KPANEL_CLIENT_LATEST_VERSION = os.getenv("KPANEL_CLIENT_LATEST_VERSION", "")
KPANEL_CLIENT_PACKAGE_URL = os.getenv("KPANEL_CLIENT_PACKAGE_URL", "")
# URL to a JSON manifest file: {"stable":{"version":"x","url":"..."},"stage":{...},"dev":{...}}
# When set, the backend fetches this (cached 5 min) instead of using the static env vars above.
KPANEL_CLIENT_MANIFEST_URL = os.getenv("KPANEL_CLIENT_MANIFEST_URL", "")

DEFAULT_CORS_ORIGINS = [
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("KPANEL_CORS_ORIGINS", ",".join(DEFAULT_CORS_ORIGINS)).split(",")
    if origin.strip()
]
CORS_ORIGIN_REGEX = os.getenv(
    "KPANEL_CORS_ORIGIN_REGEX",
    r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
)


app = FastAPI(title="KPanel API", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Must be outermost so X-Forwarded-Proto is resolved before any other
# middleware or route handler builds URLs (e.g. OAuth callback redirect_uri).
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

from app.households import router as _households_router  # noqa: E402

app.include_router(_households_router)
app.include_router(auth_router)
app.include_router(account_router)
app.include_router(superadmin_router)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_device_registration_columns()
    _ensure_user_columns()
    _ensure_room_columns()


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "service": "kpanel-backend"}


@app.middleware("http")
async def enforce_https(request: Request, call_next):
    if REQUIRE_HTTPS and request.url.path != "/healthz":
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        if proto != "https":
            return JSONResponse(status_code=426, content={"detail": "HTTPS required"})
    return await call_next(request)


class DeviceTokenIssueRequest(BaseModel):
    device_id: str
    expires_in_minutes: int = 60 * 24 * 30




class DeviceBootstrapRequest(BaseModel):
    device_id: str
    registration_code: str


class DeviceResolveRequest(BaseModel):
    device_id: str
    registration_code: str
    client_version: str | None = None


class DeviceActionAckRequest(BaseModel):
    registration_code: str
    action: str
    status: str = "completed"


class UpdateEventRequest(BaseModel):
    registration_code: str
    action: str
    status: str
    channel: str | None = None
    from_version: str | None = None
    target_version: str | None = None
    message: str = ""





class RegistrationCreateRequest(BaseModel):
    registration_code: str
    target_url: HttpUrl
    expires_in_minutes: int = 60


def _validate_timezone(tz: str) -> str:
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(tz)
    except (KeyError, ModuleNotFoundError):
        raise HTTPException(status_code=400, detail=f"Invalid timezone: {tz!r}")
    return tz


def _effective_device_timezone(device: DeviceRegistration, db: Session) -> str:
    if device.timezone:
        return device.timezone
    if device.room_id:
        room = db.get(Room, device.room_id)
        if room:
            household = db.get(Household, room.household_id)
            if household and household.timezone:
                return household.timezone
    if device.user_id:
        user = db.get(User, device.user_id)
        if user and user.timezone:
            return user.timezone
    return "America/Chicago"



def _ensure_device_registration_columns() -> None:
    inspector = inspect(engine)
    try:
        columns = {column["name"] for column in inspector.get_columns("device_registrations")}
    except Exception:
        return

    statements: list[str] = []
    if "client_version" not in columns:
        statements.append("ALTER TABLE device_registrations ADD COLUMN client_version VARCHAR(64)")
    if "pending_action" not in columns:
        statements.append("ALTER TABLE device_registrations ADD COLUMN pending_action VARCHAR(32)")
    if "pending_action_requested_at" not in columns:
        statements.append("ALTER TABLE device_registrations ADD COLUMN pending_action_requested_at DATETIME")
    if "last_action" not in columns:
        statements.append("ALTER TABLE device_registrations ADD COLUMN last_action VARCHAR(32)")
    if "last_action_status" not in columns:
        statements.append("ALTER TABLE device_registrations ADD COLUMN last_action_status VARCHAR(64)")
    if "last_action_at" not in columns:
        statements.append("ALTER TABLE device_registrations ADD COLUMN last_action_at DATETIME")
    if "timezone" not in columns:
        statements.append("ALTER TABLE device_registrations ADD COLUMN timezone VARCHAR(64)")
    if "room_id" not in columns:
        statements.append("ALTER TABLE device_registrations ADD COLUMN room_id INT")
    if "url_mode" not in columns:
        statements.append("ALTER TABLE device_registrations ADD COLUMN url_mode VARCHAR(16)")
    if "household_url_id" not in columns:
        statements.append("ALTER TABLE device_registrations ADD COLUMN household_url_id INT")
    if "temp_url" not in columns:
        statements.append("ALTER TABLE device_registrations ADD COLUMN temp_url TEXT")
    if "temp_url_revert_mode" not in columns:
        statements.append("ALTER TABLE device_registrations ADD COLUMN temp_url_revert_mode VARCHAR(16)")
    if "temp_url_revert_household_url_id" not in columns:
        statements.append("ALTER TABLE device_registrations ADD COLUMN temp_url_revert_household_url_id INT")
    if "temp_url_set_at" not in columns:
        statements.append("ALTER TABLE device_registrations ADD COLUMN temp_url_set_at DATETIME")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def _ensure_user_columns() -> None:
    inspector = inspect(engine)
    try:
        columns = {column["name"] for column in inspector.get_columns("users")}
    except Exception:
        return

    statements: list[str] = []
    if "timezone" not in columns:
        statements.append("ALTER TABLE users ADD COLUMN timezone VARCHAR(64) NOT NULL DEFAULT 'America/Chicago'")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def _ensure_room_columns() -> None:
    inspector = inspect(engine)
    try:
        columns = {column["name"] for column in inspector.get_columns("rooms")}
    except Exception:
        return

    statements: list[str] = []
    if "slug" not in columns:
        statements.append("ALTER TABLE rooms ADD COLUMN slug VARCHAR(255)")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))



@app.post("/api/v1/admin/device-tokens")
def create_device_token(
    req: DeviceTokenIssueRequest,
    _: None = Depends(require_admin_api_key),
) -> dict:
    token = issue_device_token(req.device_id, req.expires_in_minutes)
    return {
        "device_id": req.device_id,
        "device_token": token,
        "expires_in_minutes": req.expires_in_minutes,
    }


@app.post("/api/v1/admin/registrations")
def create_registration(
    req: RegistrationCreateRequest,
    db: Session = Depends(get_db_session),
    _: None = Depends(require_admin_api_key),
) -> dict:
    expires_at = now_utc() + timedelta(minutes=req.expires_in_minutes)
    existing = db.get(Registration, req.registration_code)
    if existing:
        existing.target_url = str(req.target_url)
        existing.expires_at = expires_at
    else:
        db.add(
            Registration(
                registration_code=req.registration_code,
                target_url=str(req.target_url),
                expires_at=expires_at,
            )
        )
    db.commit()
    return {
        "registration_code": req.registration_code,
        "target_url": str(req.target_url),
        "expires_at": expires_at.isoformat(),
    }


@app.post("/api/v1/devices/bootstrap")
def device_bootstrap(req: DeviceBootstrapRequest, db: Session = Depends(get_db_session)) -> dict:
    registration_code = req.registration_code.strip().upper()
    timestamp = now_utc()

    device = db.query(DeviceRegistration).filter(DeviceRegistration.device_id == req.device_id).first()
    if device is None:
        existing_code = db.get(DeviceRegistration, registration_code)
        if existing_code is not None and existing_code.device_id != req.device_id:
            if existing_code.user_id is not None:
                raise HTTPException(status_code=409, detail="Registration code is already in use by another device")
            # Unclaimed orphan — remove it so this device can take the code.
            db.delete(existing_code)
            db.flush()

        device = DeviceRegistration(
            registration_code=registration_code,
            device_id=req.device_id,
            user_id=None,
            display_name=None,
            target_url=None,
            claimed_at=None,
            last_seen_at=timestamp,
            created_at=timestamp,
            updated_at=timestamp,
        )
        db.add(device)
        db.commit()
        db.refresh(device)
    else:
        if registration_code != device.registration_code:
            if device.user_id is not None:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "registration-code-mismatch",
                        "registration_code": device.registration_code,
                    },
                )

            existing_code = db.get(DeviceRegistration, registration_code)
            if existing_code is not None and existing_code.device_id != req.device_id:
                if existing_code.user_id is not None:
                    raise HTTPException(status_code=409, detail="Registration code is already in use by another device")
                # Unclaimed orphan — remove it so this device can take the code.
                db.delete(existing_code)
                db.flush()

            # Rotating the registration code re-enters claim flow for this device.
            device.registration_code = registration_code
            device.user_id = None
            device.display_name = None
            device.target_url = None
            device.claimed_at = None

        device.last_seen_at = timestamp
        device.updated_at = timestamp
        db.commit()

    return {
        "device_id": device.device_id,
        "registration_code": device.registration_code,
        "device_token": issue_device_token(device.device_id, DEVICE_TOKEN_EXPIRES_MINUTES),
        "claimed": device.user_id is not None,
        "configured": bool(device.target_url or device.url_mode == "household_url"),
    }


@app.post("/api/v1/devices/resolve")
def resolve_device(
    req: DeviceResolveRequest,
    db: Session = Depends(get_db_session),
    x_device_token: str | None = Header(default=None),
) -> dict:
    registration_code = req.registration_code.strip().upper()
    require_device_access(req.device_id, x_device_token)
    device = db.get(DeviceRegistration, registration_code)
    if device is None or device.device_id != req.device_id:
        return {"status": "pending", "message": "Registration code not found for this device"}

    timestamp = now_utc()
    device.last_seen_at = timestamp
    device.updated_at = timestamp
    if req.client_version:
        device.client_version = req.client_version.strip()
    db.commit()

    from app.households import resolve_device_url

    resolved_url = resolve_device_url(device, db)
    if not resolved_url:
        return {"status": "pending", "message": "Registration code is waiting to be claimed by an account"}

    current_version = device.client_version or ""
    update_policy = build_update_policy(
        current_version,
        force_update=device.pending_action == "update",
    )

    return {
        "status": "configured",
        "device_id": req.device_id,
        "registration_code": device.registration_code,
        "configured_url": resolved_url,
        "pending_action": device.pending_action,
        "timezone": _effective_device_timezone(device, db),
        "update": update_policy,
    }


@app.post("/api/v1/devices/{device_id}/update-events")
def record_update_event(
    device_id: str,
    req: UpdateEventRequest,
    db: Session = Depends(get_db_session),
    x_device_token: str | None = Header(default=None),
) -> dict:
    require_device_access(device_id, x_device_token)
    registration_code = req.registration_code.strip().upper()
    device = db.get(DeviceRegistration, registration_code)
    if device is None or device.device_id != device_id:
        raise HTTPException(status_code=404, detail="Device not found")
    logger.info(
        "Device update event recorded",
        extra={
            "device_id": device_id,
            "registration_code": registration_code,
            "action": req.action,
            "status": req.status,
            "from_version": req.from_version,
            "target_version": req.target_version,
            "channel": req.channel,
            "message": req.message,
        },
    )
    return {"status": "recorded"}


@app.post("/api/v1/devices/{device_id}/actions/ack")
def ack_device_action(
    device_id: str,
    req: DeviceActionAckRequest,
    db: Session = Depends(get_db_session),
    x_device_token: str | None = Header(default=None),
) -> dict:
    require_device_access(device_id, x_device_token)
    result = record_device_action_ack(
        db,
        device_id=device_id,
        registration_code=req.registration_code,
        action=req.action,
        status=req.status,
        now=now_utc(),
    )
    return {"status": result.status}


@app.get("/api/v1/devices/{device_id}/config")
def get_device_config(
    device_id: str,
    db: Session = Depends(get_db_session),
    x_device_token: str | None = Header(default=None),
) -> dict:
    require_device_access(device_id, x_device_token)
    device = db.query(DeviceRegistration).filter(DeviceRegistration.device_id == device_id).first()
    if device is None:
        return {"status": "unbound"}

    from app.households import resolve_device_url

    resolved_url = resolve_device_url(device, db)
    if not resolved_url:
        return {"status": "pending", "registration_code": device.registration_code}

    return {
        "status": "configured",
        "device_id": device_id,
        "registration_code": device.registration_code,
        "configured_url": resolved_url,
        "pending_action": device.pending_action,
        "timezone": _effective_device_timezone(device, db),
    }
