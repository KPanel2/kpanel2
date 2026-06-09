import logging
import os
import threading
import time as _time
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, HttpUrl, field_validator
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.auth import require_admin_api_key, require_device_access
from app.db import Base, engine, get_db_session
from app.models import DeviceRegistration, Household, HouseholdMember, HouseholdUrl, Registration, Room, User, UserIdentity
from app.providers import ProviderConfig, init_oauth_clients, oauth
from app.security import issue_device_token
from app.session_auth import now_utc, to_iso

logger = logging.getLogger(__name__)


FRONTEND_BASE_URL = os.getenv("KPANEL_FRONTEND_BASE_URL", "http://localhost:8080").rstrip("/")
REQUIRE_HTTPS = os.getenv("KPANEL_REQUIRE_HTTPS", "false").lower() == "true"
SESSION_SECRET = os.getenv("KPANEL_SESSION_SECRET", "change-session-secret")
SESSION_HTTPS_ONLY = os.getenv("KPANEL_SESSION_HTTPS_ONLY", "false").lower() == "true"
DEVICE_TOKEN_EXPIRES_MINUTES = int(os.getenv("KPANEL_DEVICE_TOKEN_EXPIRES_MINUTES", str(60 * 24 * 30)))
KPANEL_CLIENT_LATEST_VERSION = os.getenv("KPANEL_CLIENT_LATEST_VERSION", "")
KPANEL_CLIENT_PACKAGE_URL = os.getenv("KPANEL_CLIENT_PACKAGE_URL", "")
# URL to a JSON manifest file: {"stable":{"version":"x","url":"..."},"stage":{...},"dev":{...}}
# When set, the backend fetches this (cached 5 min) instead of using the static env vars above.
KPANEL_CLIENT_MANIFEST_URL = os.getenv("KPANEL_CLIENT_MANIFEST_URL", "")

_MANIFEST_TTL = 300  # seconds
_manifest_lock = threading.Lock()
_manifest_cache: dict = {"data": None, "fetched_at": 0.0}


def _fetch_update_manifest() -> dict | None:
    """Fetch and cache the client update manifest from KPANEL_CLIENT_MANIFEST_URL."""
    if not KPANEL_CLIENT_MANIFEST_URL:
        return None
    now = _time.monotonic()
    with _manifest_lock:
        if _manifest_cache["data"] is not None and now - _manifest_cache["fetched_at"] < _MANIFEST_TTL:
            return _manifest_cache["data"]
    try:
        import httpx as _httpx
        resp = _httpx.get(KPANEL_CLIENT_MANIFEST_URL, timeout=5, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()
        with _manifest_lock:
            _manifest_cache["data"] = data
            _manifest_cache["fetched_at"] = _time.monotonic()
        return data
    except Exception as exc:
        print(f"Warning: failed to fetch update manifest: {exc}")
        with _manifest_lock:
            return _manifest_cache["data"]  # return stale data if available


def _detect_channel(version: str) -> str:
    if "~stage" in version:
        return "stage"
    if "~dev" in version:
        return "dev"
    return "stable"


def _get_latest_for_channel(current_version: str) -> tuple[str, str | None]:
    """Return (latest_version, package_url) for the channel inferred from current_version."""
    channel = _detect_channel(current_version)
    manifest = _fetch_update_manifest()
    if manifest:
        entry = manifest.get(channel) or {}
        return entry.get("version") or "", entry.get("url")
    return KPANEL_CLIENT_LATEST_VERSION, KPANEL_CLIENT_PACKAGE_URL or None


def _build_update_policy(current_version: str) -> dict | None:
    channel = _detect_channel(current_version)
    latest_version, package_url = _get_latest_for_channel(current_version)
    if not latest_version:
        return None
    outdated = bool(current_version) and current_version != latest_version
    return {
        "outdated": outdated,
        "update_now": outdated,
        "channel": channel,
        "current_version": current_version or None,
        "target_version": latest_version,
        "package_url": package_url,
    }

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


app = FastAPI(title="KPanel API", version="0.2.0")
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=SESSION_HTTPS_ONLY,
)
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


PROVIDERS: dict[str, ProviderConfig] = {}


SESSION_USER_ID = "kpanel_user_id"
SESSION_ACTIVE_IDENTITY_ID = "kpanel_active_identity_id"
SESSION_AUTH_REQUEST = "kpanel_auth_request"
SESSION_PENDING_AUTH = "kpanel_pending_auth"
SESSION_PENDING_LINK_USER_ID = "kpanel_pending_link_user_id"


class DeviceTokenIssueRequest(BaseModel):
    device_id: str
    expires_in_minutes: int = 60 * 24 * 30


class AccountCreateRequest(BaseModel):
    display_name: str


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


class DeviceUpdateRequest(BaseModel):
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


class AccountProfileUpdateRequest(BaseModel):
    timezone: str | None = None


class RegistrationCreateRequest(BaseModel):
    registration_code: str
    target_url: HttpUrl
    expires_in_minutes: int = 60


def _frontend_redirect() -> RedirectResponse:
    return RedirectResponse(f"{FRONTEND_BASE_URL}/")


def _clear_auth_flow(request: Request) -> None:
    request.session.pop(SESSION_AUTH_REQUEST, None)
    request.session.pop(SESSION_PENDING_AUTH, None)
    request.session.pop(SESSION_PENDING_LINK_USER_ID, None)


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


def _set_authenticated_session(request: Request, user_id: int, identity_id: int) -> None:
    request.session[SESSION_USER_ID] = user_id
    request.session[SESSION_ACTIVE_IDENTITY_ID] = identity_id


def _email_normalized(email: str) -> str:
    return email.strip().lower()


def _validate_email(email: str) -> str:
    normalized = _email_normalized(email)
    if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise HTTPException(status_code=400, detail="A valid email address is required")
    return normalized


def _serialize_identity(identity: UserIdentity) -> dict:
    return {
        "id": identity.id,
        "provider_name": identity.provider_name,
        "email": identity.email,
        "display_name": identity.display_name,
        "expires_at": to_iso(identity.expires_at),
    }


def _serialize_device(device: DeviceRegistration, db: Session | None = None) -> dict:
    from app.households import resolve_device_url

    return {
        "registration_code": device.registration_code,
        "device_id": device.device_id,
        "display_name": device.display_name,
        "target_url": device.target_url,
        "claimed_at": to_iso(device.claimed_at),
        "last_seen_at": to_iso(device.last_seen_at),
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
        "latest_client_version": _get_latest_for_channel(device.client_version or "")[0] or None,
    }


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


def _serialize_user(user: User, identities: list[UserIdentity], devices: list[DeviceRegistration], db: Session | None = None) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "timezone": user.timezone or "America/Chicago",
        "identities": [_serialize_identity(identity) for identity in identities],
        "devices": [_serialize_device(device, db) for device in devices],
    }


def _current_user(request: Request, db: Session) -> User | None:
    user_id = request.session.get(SESSION_USER_ID)
    if not user_id:
        return None
    return db.get(User, user_id)


def _active_identity(request: Request, db: Session) -> UserIdentity | None:
    identity_id = request.session.get(SESSION_ACTIVE_IDENTITY_ID)
    if not identity_id:
        return None
    return db.get(UserIdentity, identity_id)


def _store_pending_auth(request: Request, payload: dict, link_user_id: int | None = None) -> None:
    request.session[SESSION_PENDING_AUTH] = payload
    if link_user_id is None:
        request.session.pop(SESSION_PENDING_LINK_USER_ID, None)
    else:
        request.session[SESSION_PENDING_LINK_USER_ID] = link_user_id


def _persist_identity(identity: UserIdentity, pending_auth: dict) -> None:
    token = pending_auth["token"]
    identity.provider_name = pending_auth["provider_name"]
    identity.provider_subject = pending_auth["provider_subject"]
    identity.email = pending_auth["email"]
    identity.display_name = pending_auth["display_name"]
    identity.access_token = token.get("access_token")
    identity.refresh_token = token.get("refresh_token")
    identity.token_type = token.get("token_type")
    identity.scope = token.get("scope")
    identity.id_token = token.get("id_token")
    expires_at = token.get("expires_at")
    identity.expires_at = (
        datetime.fromtimestamp(expires_at, tz=timezone.utc) if isinstance(expires_at, (int, float)) else None
    )
    identity.updated_at = now_utc()


async def _refresh_identity_if_needed(identity: UserIdentity, db: Session) -> bool:
    if identity.expires_at is None or identity.expires_at > now_utc() + timedelta(seconds=60):
        return True

    if not identity.refresh_token:
        return False

    client = oauth.create_client(identity.provider_name)
    provider = PROVIDERS.get(identity.provider_name)
    if client is None or provider is None:
        return False

    token_endpoint = provider.access_token_url
    if not token_endpoint and provider.server_metadata_url:
        metadata = await client.load_server_metadata()
        token_endpoint = metadata.get("token_endpoint")
    if not token_endpoint:
        return False

    try:
        refreshed = await client.refresh_token(token_endpoint, refresh_token=identity.refresh_token)
    except Exception:
        return False

    pending = {
        "provider_name": identity.provider_name,
        "provider_subject": identity.provider_subject,
        "email": identity.email,
        "display_name": identity.display_name,
        "token": refreshed,
    }
    _persist_identity(identity, pending)
    db.commit()
    return True


async def _fetch_provider_profile(provider_name: str, request: Request) -> dict:
    client = oauth.create_client(provider_name)
    provider = PROVIDERS[provider_name]
    token = await client.authorize_access_token(request)
    profile: dict

    if provider_name in {"google", "microsoft_login", "microsoft_entra", "apple", "custom_oidc"}:
        profile = token.get("userinfo") or {}
        if not profile:
            try:
                claims = await client.parse_id_token(request, token)
            except Exception:
                claims = None
            profile = dict(claims or {})
        if not profile:
            metadata = await client.load_server_metadata()
            userinfo_endpoint = metadata.get("userinfo_endpoint")
            response = await client.get(userinfo_endpoint, token=token)
            profile = response.json()
    elif provider_name == "github":
        user_response = await client.get("user", token=token)
        email_response = await client.get("user/emails", token=token)
        user_json = user_response.json()
        email_json = email_response.json()
        primary_email = next((item.get("email") for item in email_json if item.get("primary")), None)
        profile = {
            "sub": str(user_json.get("id")),
            "name": user_json.get("name") or user_json.get("login") or "GitHub user",
            "email": primary_email,
        }
    elif provider_name == "facebook":
        response = await client.get(provider.userinfo_endpoint or "me?fields=id,name,email", token=token)
        data = response.json()
        profile = {
            "sub": str(data.get("id")),
            "name": data.get("name") or "Facebook user",
            "email": data.get("email"),
        }
    else:
        raise HTTPException(status_code=400, detail="Unsupported provider")

    email = profile.get("email")
    subject = profile.get("sub") or profile.get("id")
    if not email or not subject:
        raise HTTPException(status_code=400, detail="OIDC provider did not return required email/sub claims")

    return {
        "provider_name": provider_name,
        "provider_subject": str(subject),
        "email": _validate_email(email),
        "display_name": profile.get("name") or email,
        "token": token,
    }


def _build_dev_provider_profile(provider_name: str, email: str, display_name: str | None = None) -> dict:
    normalized_email = _validate_email(email)
    resolved_display_name = (display_name or normalized_email.split("@")[0]).strip() or normalized_email
    return {
        "provider_name": provider_name,
        "provider_subject": normalized_email,
        "email": normalized_email,
        "display_name": resolved_display_name,
        "token": {
            "token_type": "dev",
            "scope": "dev_email",
        },
    }


def _complete_provider_auth(
    request: Request,
    db: Session,
    pending_auth: dict,
    auth_mode: str = "login",
) -> RedirectResponse:
    current_user = _current_user(request, db)

    existing_identity = (
        db.query(UserIdentity)
        .filter(
            UserIdentity.provider_name == pending_auth["provider_name"],
            UserIdentity.provider_subject == pending_auth["provider_subject"],
        )
        .first()
    )
    if existing_identity is not None:
        _persist_identity(existing_identity, pending_auth)
        db.commit()
        _set_authenticated_session(request, existing_identity.user_id, existing_identity.id)
        return _frontend_redirect()

    if current_user is not None and auth_mode == "link":
        if current_user.email != pending_auth["email"]:
            _store_pending_auth(request, pending_auth, link_user_id=current_user.id)
            return _frontend_redirect()

        identity = UserIdentity(
            user_id=current_user.id,
            provider_name=pending_auth["provider_name"],
            provider_subject=pending_auth["provider_subject"],
            email=current_user.email,
            display_name=pending_auth["display_name"],
            created_at=now_utc(),
            updated_at=now_utc(),
        )
        _persist_identity(identity, pending_auth)
        db.add(identity)
        db.commit()
        db.refresh(identity)
        _clear_auth_flow(request)
        _set_authenticated_session(request, current_user.id, identity.id)
        return _frontend_redirect()

    existing_user = db.query(User).filter(User.email == pending_auth["email"]).first()
    if existing_user is None:
        _store_pending_auth(request, pending_auth)
        return _frontend_redirect()

    _store_pending_auth(request, pending_auth, link_user_id=existing_user.id)
    return _frontend_redirect()


def _build_session_state(request: Request, db: Session, revoked: bool = False) -> dict:
    providers = [{"name": item.name, "label": item.label} for item in PROVIDERS.values()]
    pending = request.session.get(SESSION_PENDING_AUTH)
    user = _current_user(request, db)

    if user is None:
        if pending:
            link_user_id = request.session.get(SESSION_PENDING_LINK_USER_ID)
            if link_user_id:
                linked_user = db.get(User, link_user_id)
                identities = (
                    db.query(UserIdentity)
                    .filter(UserIdentity.user_id == link_user_id)
                    .order_by(UserIdentity.provider_name.asc())
                    .all()
                )
                return {
                    "status": "needs_link",
                    "providers": providers,
                    "pending": {
                        "email": pending["email"],
                        "provider_name": pending["provider_name"],
                        "display_name": pending["display_name"],
                        "link_providers": [identity.provider_name for identity in identities],
                        "known_account_email": linked_user.email if linked_user else pending["email"],
                    },
                }
            return {
                "status": "needs_account",
                "providers": providers,
                "pending": {
                    "email": pending["email"],
                    "provider_name": pending["provider_name"],
                    "display_name": pending["display_name"],
                },
            }

        response = {"status": "unauthenticated", "providers": providers}
        if revoked:
            response["message"] = "Your upstream login session expired or was revoked."
        return response

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

    if pending and pending.get("email") == user.email:
        linked_provider_names = {identity.provider_name for identity in identities}
        if pending["provider_name"] not in linked_provider_names:
            return {
                "status": "link_ready",
                "providers": providers,
                "pending": {
                    "email": pending["email"],
                    "provider_name": pending["provider_name"],
                    "display_name": pending["display_name"],
                },
                "user": _serialize_user(user, identities, devices, db),
            }

    return {
        "status": "authenticated",
        "providers": providers,
        "user": _serialize_user(user, identities, devices, db),
    }


@app.on_event("startup")
def startup() -> None:
    global PROVIDERS
    Base.metadata.create_all(bind=engine)
    _ensure_device_registration_columns()
    _ensure_user_columns()
    PROVIDERS = init_oauth_clients()


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


@app.get("/api/v1/auth/providers")
def auth_providers() -> dict:
    return {"providers": [{"name": provider.name, "label": provider.label} for provider in PROVIDERS.values()]}


@app.get("/api/v1/auth/session")
async def auth_session(request: Request, db: Session = Depends(get_db_session)) -> dict:
    active_identity = _active_identity(request, db)
    if active_identity is not None:
        ok = await _refresh_identity_if_needed(active_identity, db)
        if not ok:
            request.session.clear()
            return _build_session_state(request, db, revoked=True)
    return _build_session_state(request, db)


@app.get("/api/v1/auth/login/{provider_name}")
async def auth_login(provider_name: str, request: Request, mode: str = "login"):
    if provider_name not in PROVIDERS:
        raise HTTPException(status_code=404, detail="Provider not configured")

    provider = PROVIDERS[provider_name]
    if provider.auth_mode == "dev":
        if os.getenv("KPANEL_DEV_AUTH_ENABLED", "false").lower() != "true":
            raise HTTPException(status_code=404, detail="Provider not configured")
        raise HTTPException(status_code=400, detail="Use /api/v1/auth/dev-login for dev email authentication")

    request.session[SESSION_AUTH_REQUEST] = {"provider_name": provider_name, "mode": mode}
    client = oauth.create_client(provider_name)
    redirect_uri = str(request.url_for("auth_callback", provider_name=provider_name))
    return await client.authorize_redirect(request, redirect_uri)


@app.get("/api/v1/auth/dev-login")
def auth_dev_login(
    request: Request,
    email: str,
    mode: str = "login",
    display_name: str | None = None,
    db: Session = Depends(get_db_session),
) -> RedirectResponse:
    if os.getenv("KPANEL_DEV_AUTH_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Provider not configured")
    if "dev_email" not in PROVIDERS:
        raise HTTPException(status_code=404, detail="Provider not configured")

    pending_auth = _build_dev_provider_profile("dev_email", email=email, display_name=display_name)
    request.session.pop(SESSION_AUTH_REQUEST, None)
    return _complete_provider_auth(request, db, pending_auth, auth_mode=mode)


@app.get("/api/v1/auth/callback/{provider_name}", name="auth_callback")
async def auth_callback(provider_name: str, request: Request, db: Session = Depends(get_db_session)):
    if provider_name not in PROVIDERS:
        raise HTTPException(status_code=404, detail="Provider not configured")

    pending_auth = await _fetch_provider_profile(provider_name, request)
    auth_request = request.session.pop(SESSION_AUTH_REQUEST, {"mode": "login"})
    return _complete_provider_auth(request, db, pending_auth, auth_mode=auth_request.get("mode", "login"))


@app.post("/api/v1/auth/logout")
def auth_logout(request: Request) -> dict:
    request.session.clear()
    return {"status": "logged_out"}


@app.post("/api/v1/account/create")
def account_create(
    req: AccountCreateRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict:
    pending_auth = request.session.get(SESSION_PENDING_AUTH)
    if not pending_auth:
        raise HTTPException(status_code=400, detail="No pending authentication to create an account from")

    existing_user = db.query(User).filter(User.email == pending_auth["email"]).first()
    if existing_user is not None:
        request.session[SESSION_PENDING_LINK_USER_ID] = existing_user.id
        return _build_session_state(request, db)

    timestamp = now_utc()
    user = User(
        email=pending_auth["email"],
        display_name=req.display_name.strip(),
        created_at=timestamp,
        updated_at=timestamp,
        is_active=True,
    )
    db.add(user)
    db.flush()

    identity = UserIdentity(
        user_id=user.id,
        provider_name=pending_auth["provider_name"],
        provider_subject=pending_auth["provider_subject"],
        email=user.email,
        display_name=pending_auth["display_name"],
        created_at=timestamp,
        updated_at=timestamp,
    )
    _persist_identity(identity, pending_auth)
    db.add(identity)
    db.commit()
    db.refresh(user)
    db.refresh(identity)
    _clear_auth_flow(request)
    _set_authenticated_session(request, user.id, identity.id)
    return _build_session_state(request, db)


@app.post("/api/v1/account/link/complete")
def account_link_complete(request: Request, db: Session = Depends(get_db_session)) -> dict:
    user = _current_user(request, db)
    pending_auth = request.session.get(SESSION_PENDING_AUTH)
    if user is None or not pending_auth:
        raise HTTPException(status_code=400, detail="No authenticated link flow is active")

    if user.email != pending_auth["email"]:
        raise HTTPException(status_code=409, detail="The pending provider email does not match the current account")

    existing = (
        db.query(UserIdentity)
        .filter(
            UserIdentity.provider_name == pending_auth["provider_name"],
            UserIdentity.provider_subject == pending_auth["provider_subject"],
        )
        .first()
    )
    if existing is not None:
        _clear_auth_flow(request)
        _set_authenticated_session(request, existing.user_id, existing.id)
        return _build_session_state(request, db)

    timestamp = now_utc()
    identity = UserIdentity(
        user_id=user.id,
        provider_name=pending_auth["provider_name"],
        provider_subject=pending_auth["provider_subject"],
        email=user.email,
        display_name=pending_auth["display_name"],
        created_at=timestamp,
        updated_at=timestamp,
    )
    _persist_identity(identity, pending_auth)
    db.add(identity)
    db.commit()
    db.refresh(identity)
    _clear_auth_flow(request)
    _set_authenticated_session(request, user.id, identity.id)
    return _build_session_state(request, db)


@app.patch("/api/v1/account/profile")
def account_update_profile(
    req: AccountProfileUpdateRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict:
    user = _current_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    updated = False
    if req.timezone is not None:
        user.timezone = _validate_timezone(req.timezone.strip())
        updated = True

    if not updated:
        raise HTTPException(status_code=400, detail="No editable fields were provided")

    user.updated_at = now_utc()
    db.commit()
    return _build_session_state(request, db)


@app.get("/api/v1/account/devices")
def account_devices(request: Request, db: Session = Depends(get_db_session)) -> dict:
    user = _current_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    devices = (
        db.query(DeviceRegistration)
        .filter(DeviceRegistration.user_id == user.id)
        .order_by(DeviceRegistration.created_at.desc())
        .all()
    )
    return {"devices": [_serialize_device(device, db) for device in devices]}


@app.post("/api/v1/account/devices/claim")
def account_claim_device(
    req: ClaimDeviceRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict:
    user = _current_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    device = db.get(DeviceRegistration, req.registration_code.strip().upper())
    if device is None:
        raise HTTPException(status_code=404, detail="Registration code not found. Power on the panel first so it can register itself.")

    if device.user_id is not None and device.user_id != user.id:
        raise HTTPException(status_code=409, detail="This registration code is already claimed by a different account")

    timestamp = now_utc()
    device.user_id = user.id
    device.display_name = (req.display_name or device.display_name or req.registration_code).strip()

    if req.target_url is not None:
        # Explicit custom URL always wins.
        device.target_url = str(req.target_url)
        device.url_mode = "custom"
    elif req.household_id is not None:
        # Verify the user belongs to the requested household.
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
    from app.households import resolve_device_url
    configured = bool(resolve_device_url(device, db))
    return {"status": "configured" if configured else "claimed", "device": _serialize_device(device, db)}


@app.patch("/api/v1/account/devices/{registration_code}")
def account_update_device(
    registration_code: str,
    req: DeviceUpdateRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict:
    user = _current_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    device = db.get(DeviceRegistration, registration_code.strip().upper())
    if device is None or device.user_id != user.id:
        raise HTTPException(status_code=404, detail="Device not found")

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
        if cleaned_tz:
            device.timezone = _validate_timezone(cleaned_tz)
        else:
            device.timezone = None
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

    device.updated_at = now_utc()
    db.commit()
    return {"status": "updated", "device": _serialize_device(device, db)}


@app.delete("/api/v1/account/devices/{registration_code}")
def account_delete_device(
    registration_code: str,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict:
    user = _current_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    device = db.get(DeviceRegistration, registration_code.strip().upper())
    if device is None or device.user_id != user.id:
        raise HTTPException(status_code=404, detail="Device not found")

    device_id = device.device_id
    db.delete(device)
    # Also remove any unclaimed orphan records for the same physical device.
    db.query(DeviceRegistration).filter(
        DeviceRegistration.device_id == device_id,
        DeviceRegistration.user_id == None,  # noqa: E711
    ).delete(synchronize_session=False)
    db.commit()
    return {"status": "deleted", "registration_code": registration_code.strip().upper()}


@app.post("/api/v1/account/devices/{registration_code}/actions/{action}")
def account_device_action(
    registration_code: str,
    action: str,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict:
    user = _current_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    normalized_action = action.strip().lower()
    if normalized_action not in {"update", "reboot"}:
        raise HTTPException(status_code=400, detail="Unsupported action")

    device = db.get(DeviceRegistration, registration_code.strip().upper())
    if device is None or device.user_id != user.id:
        raise HTTPException(status_code=404, detail="Device not found")

    timestamp = now_utc()
    device.pending_action = normalized_action
    device.pending_action_requested_at = timestamp
    device.updated_at = timestamp
    db.commit()
    return {"status": "queued", "action": normalized_action, "device": _serialize_device(device, db)}


@app.post("/api/v1/account/devices/{registration_code}/temp-url")
def account_set_device_temp_url(
    registration_code: str,
    req: DeviceTempUrlSetRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict:
    user = _current_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    device = db.get(DeviceRegistration, registration_code.strip().upper())
    if device is None or device.user_id != user.id:
        raise HTTPException(status_code=404, detail="Device not found")

    # Save current URL mode so we can revert later (only if not already in temp mode)
    if not device.temp_url:
        device.temp_url_revert_mode = device.url_mode
        device.temp_url_revert_household_url_id = device.household_url_id

    device.temp_url = req.temp_url
    device.temp_url_set_at = now_utc()
    device.updated_at = now_utc()
    db.commit()
    return {"status": "temp_url_set", "device": _serialize_device(device, db)}


@app.delete("/api/v1/account/devices/{registration_code}/temp-url")
def account_clear_device_temp_url(
    registration_code: str,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict:
    user = _current_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    device = db.get(DeviceRegistration, registration_code.strip().upper())
    if device is None or device.user_id != user.id:
        raise HTTPException(status_code=404, detail="Device not found")

    if not device.temp_url:
        raise HTTPException(status_code=400, detail="No temp URL is currently set")

    # Revert to the saved URL mode
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
    return {"status": "temp_url_cleared", "device": _serialize_device(device, db)}


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
    update_policy = _build_update_policy(current_version)

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


def ack_device_action(
    device_id: str,
    req: DeviceActionAckRequest,
    db: Session = Depends(get_db_session),
    x_device_token: str | None = Header(default=None),
) -> dict:
    require_device_access(device_id, x_device_token)
    registration_code = req.registration_code.strip().upper()
    device = db.get(DeviceRegistration, registration_code)
    if device is None or device.device_id != device_id:
        raise HTTPException(status_code=404, detail="Device not found")

    action = req.action.strip().lower()
    if device.pending_action and device.pending_action == action:
        device.pending_action = None
        device.pending_action_requested_at = None

    device.last_action = action
    device.last_action_status = req.status.strip().lower()
    device.last_action_at = now_utc()
    device.updated_at = now_utc()
    db.commit()
    return {"status": "acknowledged"}


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
