# KPanel2 Architecture

## Goal
Deploy touchscreen Raspberry Pi panels that auto-configure by registration code, then run a configured URL in kiosk mode.

## Components
- `backend/`: FastAPI API for OIDC login, account linking, device ownership, and config resolution.
- `frontend/`: User-facing account portal for sign-in, account creation, provider linking, and panel claiming.
- `client-system/`: Raspberry Pi runtime service that handles network state, self-registration, and kiosk browser launching.
- `infra/caddy/`: Local TLS reverse-proxy config for HTTPS enforcement testing.

## Reverse proxy model
- The app stack can remain on plain HTTP internally.
- A separate Caddy instance can terminate TLS and route `/api/*` to backend and all other paths to frontend.
- When deployed that way, set `KPANEL_REQUIRE_HTTPS=true` on backend and rely on forwarded proxy headers.

## Data store and security
- MariaDB stores `users`, `user_identities`, and `device_registrations`.
- Web accounts are matched by normalized email across configured providers.
- A development-only `dev_email` provider can bypass upstream auth when `KPANEL_DEV_AUTH_ENABLED=true`.
- Production/staging should keep `KPANEL_DEV_AUTH_ENABLED=false`.
- Admin device-token issuance still uses `X-Admin-Key` matching `KPANEL_ADMIN_API_KEY`.
- Device endpoints can enforce signed `X-Device-Token` headers per `device_id`.
- Optional HTTPS enforcement mode rejects non-HTTPS requests when `KPANEL_REQUIRE_HTTPS=true`.
- `docker-compose.tls.yml` enables local TLS termination and forwards secure traffic to backend/frontend.

## Device state machine
1. Boot and run `kpanel-client` service.
2. Check internet connectivity.
3. If offline:
   - If Wi-Fi onboarding is enabled, prompt for Wi-Fi setup flow.
   - Retry until online.
4. If online:
   - Generate or load the persisted registration code.
   - Bootstrap device presence to backend.
   - If not configured, show the registration code so a user can claim it in the portal.
   - Poll by `device_id` + `registration_code` until a target URL exists.
5. Once configured URL exists, launch Chromium in kiosk mode.

## API contract (current)
- `GET /api/v1/auth/providers`
- `GET /api/v1/auth/session`
- `GET /api/v1/auth/login/{provider_name}`
- `GET /api/v1/auth/dev-login` (enabled only when `KPANEL_DEV_AUTH_ENABLED=true`)
- `GET /api/v1/auth/callback/{provider_name}`
- `POST /api/v1/account/create`
- `POST /api/v1/account/link/complete`
- `GET /api/v1/account/devices`
- `POST /api/v1/account/devices/claim`
- `POST /api/v1/admin/device-tokens`
- `POST /api/v1/devices/bootstrap`
- `POST /api/v1/devices/resolve`
- `GET /api/v1/devices/{device_id}/config`
- `GET /healthz`

## Implemented device onboarding
- If internet is unavailable and Wi-Fi onboarding is enabled, the client opens a touchscreen Tkinter credential dialog.
- Credentials are applied through `nmcli`.
- If no Wi-Fi networks are available, the client can start a recovery hotspot and display credentials on screen.
- Client persists generated registration code and auto-issued device token in local state.
- `POST /api/v1/devices/bootstrap` issues a signed device token and supports registration-code rotation for re-claim flows.
- `POST /api/v1/devices/resolve` and `GET /api/v1/devices/{device_id}/config` require a valid device token when token enforcement is enabled.

## Production hardening backlog
- Add encrypted storage for local secrets.
- Add OTA update strategy for the client package.
- Add full captive-portal UI served from the panel hotspot for one-step provisioning.
