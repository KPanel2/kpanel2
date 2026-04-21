# Decision: Client Distribution Strategy

## Recommendation
Use **one reusable KPanel client package** and ship it through **multiple zero-touch appliance images**:

- Raspberry Pi appliance image for real Pi hardware
- Debian VM appliance image for Proxmox, QEMU, and local VM testing
- Debian installer-based hardware appliance path for generic x86_64 or arm64 systems

The user experience target is the same for all of them: install image, boot once, land in KPanel.

## Why this structure works
- One application payload: the `kpanel-client` package remains the single installable unit.
- Multiple appliance surfaces: each hardware class gets the right base image format instead of forcing one image onto incompatible targets.
- Zero-touch UX: kiosk/autologin/network defaults are baked into the image, not left to a post-install checklist.
- Faster iteration: the package can still be developed and updated independently of the image builders.
- Lower long-term risk: platform-specific boot logic stays inside each image pipeline, while KPanel logic stays in the package.

## Delivery targets
### Raspberry Pi appliance image
Pros:
- Best fit for Raspberry Pi firmware and boot expectations.
- Simplest manufacturing and field provisioning story for Pi hardware.
- Matches the current `pi-gen` workflow already in this repo.

Cons:
- Not appropriate for Proxmox or generic UEFI VM boot.
- Poor emulator experience on macOS and generic virtualization stacks.

### Debian VM appliance image
Pros:
- Proper fit for Proxmox, QEMU, UTM experiments, and server-class hardware.
- Can be emitted as `qcow2` and raw disk images.
- Supports the same zero-touch kiosk experience as the Pi image.

Cons:
- Separate image builder is required; `pi-gen` is the wrong tool for this target.

### Debian hardware appliance installer
Pros:
- Opens the door to mini PCs, laptops, NUCs, and mixed x86_64 or arm64 hardware.
- Still allows a zero-touch first boot if the installer is preseeded/autoinstalled.
- Reuses the same `kpanel-client` package and kiosk defaults.

Cons:
- More work than the VM image if a custom installer ISO is required.
- Hardware variability increases graphics, Wi-Fi, and driver validation burden.

## Architecture rule
The package is the product payload. Images are delivery wrappers.

That means:

- the Python app, launcher, defaults, and mode helper live in the package
- each image builder installs that package during build time
- autologin, kiosk startup, and platform boot mechanics are handled by the image pipeline for that target
- OTA updates continue to flow through the package updater already present on the device

## Practical rollout
1. Keep the existing Raspberry Pi `pi-gen` image as the Pi-specific appliance path.
2. Add a Debian VM image pipeline that outputs `qcow2` and raw artifacts for Proxmox and local virtualization.
3. Reuse the existing `kpanel-client` package in both image builds.
4. After the VM image is stable, add a Debian autoinstall-based hardware installer image for generic systems.
5. Keep package-based OTA updates enabled in every image so post-deploy fixes do not require reflashing.

## Zero-touch requirement
For every supported target, the expected install flow is:

1. Write or import image.
2. Boot system.
3. System autologins or autostarts into KPanel.
4. Device enters Wi-Fi/onboarding and registration flow without OS-level setup.

No supported path should require the user to separately install an OS, open a shell, install KPanel, or hand-configure kiosk startup.

## Current status
- The reusable package path is implemented, including `.deb` build script and maintainer scripts.
- The Raspberry Pi appliance image path is implemented with `pi-gen`.
- The VM-friendly Debian appliance image is the next missing delivery target.
- Backend persistence uses MariaDB in Docker Compose.
