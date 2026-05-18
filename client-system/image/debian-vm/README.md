# KPanel Debian VM Appliance

This target packages KPanel as a zero-touch Debian VM image for:

- Proxmox imports
- QEMU and local VM testing
- generic server-style virtualization where the Raspberry Pi image is the wrong artifact

## Output artifacts

The VM build produces:

- `*.qcow2` for Proxmox import and VM-oriented workflows
- `*.raw.xz` for raw-disk consumers that prefer a compressed raw image

Both artifacts are built from a Debian 12 generic cloud base image and customized offline with the same `kpanel-client` deb package used by the Raspberry Pi appliance image.

## Zero-touch behavior

The VM appliance build configures the guest to:

- install `kpanel-client`
- create a local `kpanel` user
- autologin via LightDM into Openbox
- launch `/usr/local/bin/kpanel-client-launcher.sh` at session start
- boot into graphical target by default
- disable Debian cloud-image first-boot overrides so appliance defaults persist
- enable `ssh` for recovery access
- include `xterm` so the Openbox session has a terminal available
- enable a serial console on `ttyS0` for Proxmox recovery access
- reassert autologin and SSH policy on each boot with a small self-heal service

The goal is the same as the Pi image: import image, boot VM, land in KPanel.

## Local build

From the repo root:

```bash
client-system/scripts/build_vm_image.sh preflight
client-system/scripts/build_vm_image.sh full 0.1.0 kpanel-vm-appliance
```

The local builder installs host dependencies when needed:

- `libguestfs-tools`
- `qemu-utils`
- `qemu-system-x86`
- `xz-utils`

## Proxmox import helper

Run this script on a Proxmox host to either create a fresh VM from a qcow2 image or replace the boot disk on an existing VM with a newer qcow2 build:

```bash
bash client-system/scripts/proxmox-deploy-vm.sh
```

It prompts for:

- deployment mode: `fresh` or `replace`
- VM ID
- absolute qcow2 path on the Proxmox host
- target storage ID

For fresh installs it also prompts for VM name, bridge, memory, cores, and sockets.

The script will:

- create the VM shell when needed
- import the qcow2 into the selected storage
- attach the imported disk as `scsi0`
- use a conservative Proxmox hardware profile for compatibility: `SeaBIOS`, `i440fx`, `VirtIO SCSI`, and tablet input while leaving the display adapter at the Proxmox default
- optionally start the VM

In `replace` mode it preserves the existing VM shell, imports the new qcow2, reassigns `scsi0`, and offers to remove the detached old disk.

## Notes

- Default credentials are currently `kpanel` / `kpanel` for convenience during bring-up.
- SSH is enabled by default in the VM image so you can recover even if kiosk startup fails.
- Password login is explicitly enabled for the default `kpanel` user so you can SSH in immediately after boot.
- The Proxmox helper also enables `serial0`, and the guest enables `serial-getty@ttyS0`, so you can recover from the Proxmox serial console even if the GUI path is broken.
- This is a VM-specific appliance target. It is not a replacement for the Raspberry Pi image.
- A future generic hardware installer can reuse the same package and kiosk defaults while using Debian autoinstall instead of a VM disk image.

## Recovery and dev mode

After the VM gets a DHCP lease, you should be able to log in with:

```bash
ssh kpanel@<vm-ip>
```

Default password:

```text
kpanel
```

To switch the appliance to dev mode after logging in:

```bash
sudo kpanel-set-mode dev
sudo systemctl restart display-manager
```