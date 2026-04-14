# KPanel Appliance Image (Option 3)

This directory contains the Raspberry Pi appliance-image scaffolding so a flashed device can:

- boot without manual OS login,
- autologin into the desktop session,
- auto-start KPanel client,
- immediately enter Wi-Fi/onboarding + registration flow.

## What is included

- `pi-gen/stage-kpanel/`
  Custom pi-gen stage that installs `kpanel-client` deb package into the image.
- LightDM autologin configuration for user `pi`.
- Desktop autostart entry launching KPanel client at session start.

## CI image build

Workflow: `.github/workflows/build-rpi-appliance-image.yml`

Build triggers:

- `workflow_dispatch`
- `release.published`

The workflow:

1. Builds `kpanel-client_<version>_all.deb`.
2. Injects it into custom `stage-kpanel`.
3. Builds a Raspberry Pi OS image using `pi-gen`.
4. Uploads resulting image artifact.

## Notes

- The image build is heavier than package builds and can take significant CI time.
- This stage disables system `kpanel-client.service` and uses desktop autostart for kiosk UX.
- If you want strict no-desktop/sessionless boot later, migrate launcher to a compositor-based kiosk service.
- Current CI image defaults configure `pi` user password as `kpanel` and enable SSH for provisioning convenience.
- For production, rotate credentials immediately or adjust the workflow config to use hardened credentials.

## Environment modes (dev/stage/prod)

The appliance image includes `/etc/default/kpanel-client` with mode-aware API targets:

- `KPANEL_ENV_MODE=prod|stage|dev`
- `KPANEL_API_BASE_URL_PROD=...`
- `KPANEL_API_BASE_URL_STAGE=...`
- `KPANEL_API_BASE_URL_DEV=...`
- Optional `KPANEL_API_BASE_URL_OVERRIDE=...` (wins over mode)

Switch modes on a device:

```bash
sudo kpanel-set-mode dev
sudo reboot
```

Examples:

- Stage: `sudo kpanel-set-mode stage`
- Prod: `sudo kpanel-set-mode prod`

For ad-hoc testing against a custom API URL, edit `/etc/default/kpanel-client` and set:

```bash
KPANEL_API_BASE_URL_OVERRIDE=http://<host>:8000
```
