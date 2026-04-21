# KPanel Appliance Images

This directory currently contains the Raspberry Pi appliance-image scaffolding so a flashed device can:

- boot without manual OS login,
- autologin into a minimal graphical session,
- auto-start KPanel client,
- immediately enter Wi-Fi/onboarding + registration flow.

## What is included

- `pi-gen/stage-kpanel/`
  Custom pi-gen stage that installs `kpanel-client` deb package into the image.
- LightDM autologin configuration for user `pi`.
- Openbox autostart entry launching KPanel client at session start.

## Target model

KPanel should support zero-touch appliance delivery across multiple targets:

- Raspberry Pi image for Pi hardware
- Debian VM image for Proxmox and local virtualization
- Debian hardware installer image for generic systems

The common rule is that the image should boot directly into KPanel onboarding without requiring separate OS installation or manual KPanel setup.

This directory currently implements only the Raspberry Pi target. The shared application payload is the `kpanel-client` deb package; additional image builders should install that same package rather than creating a second application packaging path.

The first additional target scaffold now lives in `debian-vm/` for Proxmox and local VM imports.

## Raspberry Pi CI image build

Workflow: `.github/workflows/build-rpi-appliance-image.yml`

Build triggers:

- `workflow_dispatch`
- `release.published`

The workflow:

1. Builds `kpanel-client_<version>_all.deb`.
2. Injects it into custom `stage-kpanel`.
3. Builds a Raspberry Pi OS image using `pi-gen`.
4. Produces a flashable `*-flashable.img.xz` image artifact.
5. Derives a PiServer-compatible `*-piserver-rootfs.tar.xz` rootfs archive artifact from the same image.
6. Uploads resulting artifacts.

## Local validation

For local iteration, use `client-system/scripts/build_image_local.sh` from the repo root.

Fast preflight:

```bash
client-system/scripts/build_image_local.sh preflight
```

This checks the `stage-kpanel` layout that recently broke CI, syntax-checks the helper scripts, builds the `kpanel-client` deb, and injects it into the pi-gen stage payload without running a full image build.

Full local image build:

```bash
client-system/scripts/build_image_local.sh full
```

Behavior:

- Clones or refreshes `pi-gen` into `/tmp/pi-gen` by default.
- Copies `stage-kpanel` into that checkout.
- Writes a local pi-gen config matching CI's stage list.
- Runs `sudo ./build-docker.sh`.

Optional arguments:

```bash
client-system/scripts/build_image_local.sh full 0.1.0 kpanel-appliance
```

Optional environment override:

```bash
KPANEL_PI_GEN_DIR=/path/to/pi-gen client-system/scripts/build_image_local.sh full
```

Requirements for `full`:

- `docker`
- `git`
- `qemu-arm-static`
- local privileges to run `sudo ./build-docker.sh`

If those host dependencies are missing, the local wrapper installs the same apt packages used by CI before starting the build.

## Notes

- The image build is heavier than package builds and can take significant CI time.
- This stage disables system `kpanel-client.service` and uses a minimal LightDM + Openbox session for kiosk UX.
- If you want strict no-desktop/sessionless boot later, migrate launcher to a compositor-based kiosk service.
- Current CI image defaults configure `pi` user password as `kpanel` and enable SSH for provisioning convenience.
- For production, rotate credentials immediately or adjust the workflow config to use hardened credentials.
- Device identity now defaults to a stable machine-specific ID derived from `/etc/machine-id`, rather than the shared image hostname.
- Two artifact types are produced: `*-flashable.img.xz` for Raspberry Pi Imager / Balena Etcher, and `*-piserver-rootfs.tar.xz` for PiServer import.
- Do not flash `*-piserver-rootfs.tar.xz` to SD media; it is not a boot image.
- This image is Pi-specific and should not be treated as the VM or generic-hardware appliance artifact.

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
