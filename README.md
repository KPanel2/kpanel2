# KPanel2

KPanel2 is a three-part system for Raspberry Pi touchscreen panels:

- `backend/`: FastAPI API for OIDC login, account linking, device claiming, and client configuration resolution.
- `frontend/`: User account portal for OIDC sign-in and panel management.
- `client-system/`: Raspberry Pi service that handles connectivity checks, auto-generated registration codes, and kiosk launch.

Current persistence and security baseline:

- MariaDB stores users, linked identity providers, and device registration state.
- Web login is provider-based only; no local username/password flow exists.
- Accounts are matched by email address and providers can be linked after re-authentication.
- Device endpoints support signed `X-Device-Token` authentication when enabled.

## Monorepo layout

- `backend/`
- `frontend/`
- `client-system/`
- `docs/`
- `docker-compose.yml`

## Quick start (backend + frontend)

```bash
docker compose up --build
```

Default development URLs:

- Frontend portal: `http://localhost:8080`
- Backend docs: `http://localhost:8000/docs`

## OIDC provider configuration

Only configured providers are shown in the portal.

Supported provider keys:

- `custom_oidc`
- `microsoft_login`
- `microsoft_entra`
- `github`
- `google`
- `facebook`
- `apple`
- `dev_email` (development-only, no upstream auth)

Provider environment variables:

Google:

```bash
KPANEL_OIDC_GOOGLE_CLIENT_ID=...
KPANEL_OIDC_GOOGLE_CLIENT_SECRET=...
```

GitHub:

```bash
KPANEL_OIDC_GITHUB_CLIENT_ID=...
KPANEL_OIDC_GITHUB_CLIENT_SECRET=...
```

Facebook:

```bash
KPANEL_OIDC_FACEBOOK_CLIENT_ID=...
KPANEL_OIDC_FACEBOOK_CLIENT_SECRET=...
```

Apple:

```bash
KPANEL_OIDC_APPLE_CLIENT_ID=...
KPANEL_OIDC_APPLE_CLIENT_SECRET=...
```

Microsoft Login (consumer accounts):

```bash
KPANEL_OIDC_MICROSOFT_LOGIN_CLIENT_ID=...
KPANEL_OIDC_MICROSOFT_LOGIN_CLIENT_SECRET=...
```

Microsoft Entra:

```bash
KPANEL_OIDC_MICROSOFT_ENTRA_CLIENT_ID=...
KPANEL_OIDC_MICROSOFT_ENTRA_CLIENT_SECRET=...
KPANEL_OIDC_MICROSOFT_ENTRA_TENANT=organizations
```

Custom OIDC:

```bash
KPANEL_OIDC_CUSTOM_CLIENT_ID=...
KPANEL_OIDC_CUSTOM_CLIENT_SECRET=...
KPANEL_OIDC_CUSTOM_SERVER_METADATA_URL=https://issuer.example.com/.well-known/openid-configuration
KPANEL_OIDC_CUSTOM_SCOPE="openid email profile offline_access"
```

Development-only email provider:

```bash
KPANEL_DEV_AUTH_ENABLED=true
```

When `KPANEL_DEV_AUTH_ENABLED=true`, the portal exposes `Dev Email (No Auth)`. This flow prompts for an email address and directly creates/links a session without an external provider.

Safety requirements:

- Keep `KPANEL_DEV_AUTH_ENABLED=false` in shared, staging, and production environments.
- Enable it only for local development or controlled admin-only testing.

Account behavior:

- If a user signs in and no KPanel account exists for that email, the portal prompts account creation.
- If the email already exists under a different provider, the portal prompts re-authentication with a known linked provider before completing the new link.
- Session checks refresh upstream tokens when needed; if refresh fails, the user is logged out and must sign in again.

## Device flow (Pi)

1. Panel boots and runs `kpanel-client` service.
2. Service checks internet.
3. If offline and Wi-Fi onboarding enabled, it prompts for Wi-Fi setup.
4. If online, the client bootstraps itself and persists a generated registration code locally.
5. If the code has not been claimed in a user account yet, the panel shows the code on screen.
6. The user signs into the frontend, claims that code, and assigns a target URL.
7. The device polls backend with `device_id` + `registration_code`.
8. Backend returns configured URL.
9. Panel launches Chromium kiosk mode with that URL.

If no Wi-Fi networks are available during onboarding and hotspot fallback is enabled, the panel starts a recovery hotspot and displays SSID/password on screen.

## External Caddy reverse proxy

If you terminate TLS in a separate Caddy instance, keep this stack on plain HTTP and proxy to:

- `frontend:80` for web UI
- `backend:8000` for `/api/*`, `/healthz`, `/docs*`, `/openapi.json`

Example config:

- `infra/caddy/Caddyfile.external`

Recommended backend setting in that mode:

- `KPANEL_REQUIRE_HTTPS=true`

This works because Caddy forwards `X-Forwarded-Proto: https`.

## Local TLS test mode

```bash
docker compose -f docker-compose.yml -f docker-compose.tls.yml up --build
```

Open:

- `https://localhost:8443`

Notes:

- Local TLS uses an internal/self-signed Caddy cert; browser warning is expected.
- In TLS mode, backend HTTPS enforcement is enabled with `KPANEL_REQUIRE_HTTPS=true`.

## Device token flow

Device tokens are now automatic for client bootstrap.

- On bootstrap, backend returns a signed `device_token` for the current `device_id`.
- Client persists token and registration code in `KPANEL_STATE_PATH`.
- If token becomes invalid/expired, client rotates token + registration code and requires re-claim with the new code.

## Install client system on Raspberry Pi OS

From repo root on the Pi:

```bash
cd client-system
chmod +x scripts/install.sh
./scripts/install.sh
```

Default behavior after install/reboot is zero-touch:

- Client auto-starts and opens onboarding UI.
- If internet is unavailable, it prompts for Wi-Fi setup (with hotspot fallback when enabled).
- Once API is reachable, it generates/pushes registration code + auto-issued device token.
- User only needs to claim the displayed registration code in the portal.

Set service environment values in:

- `client-system/systemd/kpanel-client.service`

Important variables:

- `KPANEL_API_BASE_URL_OVERRIDE`: optional override for dev/test API target.
- `KPANEL_STATE_PATH`: local file used to persist generated registration code and auto-issued device token.
- `KPANEL_HOTSPOT_FALLBACK_ENABLED`: starts recovery hotspot if no networks are visible.
- `KPANEL_HOTSPOT_SSID`, `KPANEL_HOTSPOT_PASSWORD`: recovery hotspot credentials.

Then reload and restart service:

```bash
sudo systemctl daemon-reload
sudo systemctl restart kpanel-client
sudo systemctl status kpanel-client
```

## Build and install Debian package

Build package:

```bash
cd client-system
chmod +x scripts/build_deb.sh
./scripts/build_deb.sh 0.1.0
```

Install package on Pi:

```bash
sudo dpkg -i client-system/build/kpanel-client_0.1.0_all.deb
sudo apt-get install -f -y
```

## Strategy recommendation

Use package/service installation first, then custom image once stable.

See:

- `docs/client-distribution-decision.md`
- `docs/architecture.md`
