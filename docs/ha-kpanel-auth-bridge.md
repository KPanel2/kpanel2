# HA KPanel Auth Bridge

End-to-end path for passwordless Home Assistant dashboard login on a KPanel device.

Living plan: `.cursor/plans/ha_kpanel_auth_bridge.plan.md`

## Pieces

| Layer | Role |
|-------|------|
| HA integration (`integrations/ha-kpanel-dashboard`) | Config flow picks user + dashboard; mints refresh token; `GET /api/kpanel_dashboard/bootstrap` returns `hassTokens` |
| KPanel2 portal | Account / household / room / device HA bootstrap URL + binding secret (lower overrides higher) |
| KPanel2 resolve API | Authenticated device channel returns `browser_auth` |
| KPanel client | Fetches bootstrap, launches Chromium with localhost CDP, seeds `localStorage.hassTokens`, navigates to dashboard |

## E2E path (v1)

1. **Install HA integration** (HACS custom repo → KPanel Dashboard) and restart HA.
2. **Configure integration** — Settings → Devices & Services → Add **KPanel Dashboard**. Select a non-admin kiosk user and dashboard path (e.g. `/lovelace/kiosk`). On the **Copy binding secret** confirmation screen, copy the secret into a password manager. (You can also open the integration → Configure later to view or rotate the secret.)
3. **Claim / configure the device** in the KPanel portal with the panel’s usual URL (or household URL that resolves to the HA dashboard).
4. **Bind HA auth** at the most convenient level (same cascade as timezone: **account → household → room → device**, lower overrides higher):
   - **Account** — Profile card → Home Assistant auth bridge
   - **Household** — Household settings tab
   - **Room** — Room edit in the household
   - **Device** — Device card override  
   Set Bootstrap URL to `https://<your-ha>/api/kpanel_dashboard/bootstrap` and paste the binding secret. Save.
5. **Boot the panel** — client `resolve` returns `browser_auth` from the effective binding; client calls bootstrap with `X-KPanel-Binding-Secret`; Chromium starts with `--remote-debugging-address=127.0.0.1`; CDP injects `hassTokens` before navigation; panel opens the **KPanel configured URL** (device / household / room template), not the HA integration’s dashboard path.
6. Optional: append `?kiosk` (or `?hide_header` / `?hide_sidebar`) for chrome hiding via the integration’s frontend module.

Room-based dashboards: set the HA integration dashboard path to something like `/control-panel` (auth binding only). Put the full view URL in KPanel, e.g. household template `https://homeassistant.example/control-panel/{room}` → Office panel opens `/control-panel/Office`.

### Local panels, remote KPanel portal

Devices can use a private HA address while you manage panels from the public internet:

| Setting | Example |
|---------|---------|
| HA integration **Local base URL** | `http://172.16.24.1:8123` |
| KPanel HA **bootstrap URL** | `http://172.16.24.1:8123/api/kpanel_dashboard/bootstrap` |
| KPanel device / household URL | `http://172.16.24.1:8123/control-panel/{room}` |

The binding secret still comes from HA → Configure (or the post-rotate screen). Portal and HA public URL can stay on `https://homeassistant.example`.

### Verify

- Bootstrap (from a trusted host):  
  `curl -sS -H 'X-KPanel-Binding-Secret: …' https://ha.example/api/kpanel_dashboard/bootstrap`  
  → `"ready": true` and a `hass_tokens` object.
- Rotate tokens in HA: Developer Tools → Services → `kpanel_dashboard.rotate_tokens`.
- Clear binding in the portal to fall back to normal URL-only kiosk (login form / trusted_networks / existing Chromium profile).

## Security model

- **Never** put refresh tokens or LLATs in the public dashboard URL.
- Prefer a **non-admin** HA user limited to the kiosk dashboard.
- Binding secrets are rotatable; deliver them only over the device-token channel (`X-Device-Token`).
- CDP debugging is bound to **127.0.0.1** only.
- Physical access to the panel ≡ access to that HA user’s session (same class of risk as `trusted_networks` kiosks).

### Fallback

If bootstrap/CDP is unavailable:

1. HA `trusted_networks` + `trusted_users` + `allow_bypass_login` for the kiosk LAN, and/or
2. Persistent Chromium profile (`KPANEL_CHROMIUM_PROFILE_DIR`) after a one-time interactive login.

## Troubleshooting

| Symptom | Checks |
|---------|--------|
| Login form still appears | Bootstrap `ready`? Secret match? CDP seed errors in client logs? Proxy stripping `localStorage` / wrong `hassUrl`? |
| Bootstrap 401 | Binding secret mismatch; re-copy from HA / re-save in portal |
| Bootstrap 429 | Rate limit (default 30/min per secret); wait or rotate |
| Bootstrap 503 | User deleted/inactive; re-run config flow |
| Black / blank Chromium | Existing GPU flags (`KPANEL_CHROMIUM_FLAGS`); or CDP stuck on `about:blank` — update client (≥ page-target CDP) and check logs for `CDP hassTokens seed failed` |
| Reverse proxy quirks | `hassTokens.hassUrl` / Local base URL must match the panel origin (e.g. `http://172.16.20.24:8123`) |

## Out of scope (v1)

- Custom HA auth providers / core patches  
- LLAT in query strings  
- Full feature parity with NemesisRE/kiosk-mode  
