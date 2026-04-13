# Decision: Client Distribution Strategy

## Recommendation
Start with a **Debian package/service installer** for Raspberry Pi OS, then offer a **prebaked image** for high-volume provisioning.

## Why this order works
- Faster iteration: package updates are easy while API/client behavior evolves.
- Lower operational risk early on: easier troubleshooting on standard Raspberry Pi OS.
- Migration path: once stable, bake package + defaults into a custom image for mass deployment.

## Tradeoffs
### Debian package on Raspberry Pi OS
Pros:
- Smaller maintenance burden initially.
- Compatible with existing devices already in the field.
- Easier incremental rollout and rollback.

Cons:
- Slightly more manual provisioning per device.
- Possible drift if base OS differs across devices.

### Custom image
Pros:
- Consistent fleet state and quicker first-boot setup.
- Better for manufacturing or large-scale deployments.

Cons:
- Higher maintenance: image build pipeline, updates, reflash workflows.
- Harder debugging for teams unfamiliar with image customization.

## Practical rollout
1. Build and validate package-based installer (`client-system/scripts/install.sh`).
2. Stabilize API + onboarding UX.
3. Add image build pipeline (Packer or Pi-gen) embedding the package.
4. Keep package updater in image for OTA patches.

## Current status
- Package-first path is implemented, including `.deb` build script and maintainer scripts.
- Backend persistence uses MariaDB in Docker Compose.
