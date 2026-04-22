#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-preflight}"
VERSION_RAW="${2:-0.1.0~local$(git -C "$(cd "$(dirname "$0")/../.." && pwd)" rev-parse --short HEAD)}"
IMAGE_NAME="${3:-kpanel-vm-appliance}"

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE_DIR="$ROOT_DIR/image/debian-vm"
BUILD_DIR="$ROOT_DIR/build/vm-image"
WORK_DIR="${KPANEL_VM_WORK_DIR:-/tmp/kpanel-vm-image}"
VERSION="${VERSION_RAW#v}"
DEB_PATH="$ROOT_DIR/build/kpanel-client_${VERSION}_all.deb"
BASE_IMAGE_URL="${KPANEL_VM_BASE_IMAGE_URL:-https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-genericcloud-amd64.qcow2}"
BASE_IMAGE_SHA_URL="${KPANEL_VM_BASE_IMAGE_SHA_URL:-https://cloud.debian.org/images/cloud/bookworm/latest/SHA512SUMS}"
BASE_IMAGE_NAME="$(basename "$BASE_IMAGE_URL")"
BASE_IMAGE_PATH="$WORK_DIR/$BASE_IMAGE_NAME"
OUTPUT_QCOW2="$BUILD_DIR/${IMAGE_NAME}-${VERSION}.qcow2"
OUTPUT_RAW="$BUILD_DIR/${IMAGE_NAME}-${VERSION}.raw"
VM_NBD_DEVICE=""
VM_MOUNT_DIR=""

usage() {
	cat <<EOF
Usage: $(basename "$0") <preflight|full> [package-version] [image-name]

Modes:
  preflight  Validate scripts and build the deb payload only.
  full       Build the deb and produce Debian VM appliance artifacts.

Environment:
  KPANEL_VM_WORK_DIR        Working directory for downloaded/customized images.
  KPANEL_VM_BASE_IMAGE_URL  Override the Debian base qcow2 URL.
  KPANEL_VM_BASE_IMAGE_SHA_URL  Override the SHA512SUMS URL for the base image.
EOF
}

require_file() {
	local path="$1"
	if [[ ! -f "$path" ]]; then
		echo "Missing required file: $path" >&2
		exit 1
	fi
}

require_command() {
	local command_name="$1"
	if ! command -v "$command_name" >/dev/null 2>&1; then
		echo "Missing required command: $command_name" >&2
		exit 1
	fi
}

ensure_host_build_dependencies() {
	local missing=0
	local packages=(
		curl
		gdisk
		kmod
		qemu-system-x86
		qemu-utils
		xz-utils
	)

	for command_name in curl qemu-img qemu-nbd lsblk partprobe sha512sum; do
		if ! command -v "$command_name" >/dev/null 2>&1; then
			missing=1
			break
		fi
	done

	if [[ "$missing" -eq 0 ]]; then
		return
	fi

	echo "Installing local VM image build dependencies with apt..."
	sudo apt-get update
	sudo apt-get install -y "${packages[@]}"
}

find_root_partition() {
	local device="$1"
	lsblk -lnpo NAME,FSTYPE,TYPE "$device" | awk '$3 == "part" && ($2 == "ext4" || $2 == "xfs" || $2 == "btrfs") { print $1; exit }'
}

find_efi_partition() {
	local device="$1"
	lsblk -lnpo NAME,FSTYPE,TYPE "$device" | awk '$3 == "part" && ($2 == "vfat" || $2 == "fat32") { print $1; exit }'
}

attach_nbd() {
	local image_path="$1"
	local nbd_device

	sudo modprobe nbd max_part=16

	for nbd_device in /dev/nbd0 /dev/nbd1 /dev/nbd2 /dev/nbd3 /dev/nbd4 /dev/nbd5 /dev/nbd6 /dev/nbd7; do
		if sudo qemu-nbd --connect "$nbd_device" "$image_path" 2>/dev/null; then
			echo "$nbd_device"
			return 0
		fi
	done

	echo "Unable to attach qcow2 image to an nbd device" >&2
	exit 1
}

cleanup_vm_mounts() {
	set +e
	if [[ -n "${VM_MOUNT_DIR:-}" && -d "${VM_MOUNT_DIR:-}" ]]; then
		sudo umount "$VM_MOUNT_DIR/boot/efi" >/dev/null 2>&1 || true
		sudo umount "$VM_MOUNT_DIR/dev/pts" >/dev/null 2>&1 || true
		sudo umount "$VM_MOUNT_DIR/dev" >/dev/null 2>&1 || true
		sudo umount "$VM_MOUNT_DIR/proc" >/dev/null 2>&1 || true
		sudo umount "$VM_MOUNT_DIR/sys" >/dev/null 2>&1 || true
		sudo umount "$VM_MOUNT_DIR/run" >/dev/null 2>&1 || true
		sudo umount "$VM_MOUNT_DIR" >/dev/null 2>&1 || true
		rm -rf "$VM_MOUNT_DIR"
		VM_MOUNT_DIR=""
	fi
	if [[ -n "${VM_NBD_DEVICE:-}" ]]; then
		sudo qemu-nbd --disconnect "$VM_NBD_DEVICE" >/dev/null 2>&1 || true
		VM_NBD_DEVICE=""
	fi
}

run_preflight() {
	require_file "$IMAGE_DIR/provision/configure-image.sh"
	bash -n "$IMAGE_DIR/provision/configure-image.sh"
	bash -n "$ROOT_DIR/scripts/build_deb.sh"
	"$ROOT_DIR/scripts/build_deb.sh" "$VERSION"
	test -f "$DEB_PATH"
	echo "Preflight passed. Deb payload prepared at $DEB_PATH"
}

download_base_image() {
	mkdir -p "$WORK_DIR"
	if [[ ! -f "$BASE_IMAGE_PATH" ]]; then
		curl -fsSL "$BASE_IMAGE_URL" -o "$BASE_IMAGE_PATH"
	fi
	local sums_path="$WORK_DIR/SHA512SUMS"
	curl -fsSL "$BASE_IMAGE_SHA_URL" -o "$sums_path"
	(
		cd "$WORK_DIR"
		grep " ${BASE_IMAGE_NAME}$" "$sums_path" | sha512sum -c -
	)
}

run_full_build() {
	local root_partition=""
	local efi_partition=""
	VM_MOUNT_DIR="$(mktemp -d)"
	trap cleanup_vm_mounts EXIT

	ensure_host_build_dependencies
	require_command qemu-img
	require_command qemu-nbd
	require_command xz

	run_preflight
	download_base_image

	mkdir -p "$BUILD_DIR"
	rm -f "$OUTPUT_QCOW2" "$OUTPUT_QCOW2.sha256" "$OUTPUT_RAW" "$OUTPUT_RAW.xz" "$OUTPUT_RAW.xz.sha256"
	cp "$BASE_IMAGE_PATH" "$OUTPUT_QCOW2"
	qemu-img resize -f qcow2 "$OUTPUT_QCOW2" 16G

	VM_NBD_DEVICE="$(attach_nbd "$OUTPUT_QCOW2")"
	sudo partprobe "$VM_NBD_DEVICE"
	sudo udevadm settle

	root_partition="$(find_root_partition "$VM_NBD_DEVICE")"
	if [[ -z "$root_partition" ]]; then
		echo "Unable to locate root filesystem partition in $VM_NBD_DEVICE" >&2
		exit 1
	fi

	efi_partition="$(find_efi_partition "$VM_NBD_DEVICE")"

	sudo mount "$root_partition" "$VM_MOUNT_DIR"
	if [[ -n "$efi_partition" ]]; then
		sudo mkdir -p "$VM_MOUNT_DIR/boot/efi"
		sudo mount "$efi_partition" "$VM_MOUNT_DIR/boot/efi"
	fi

	sudo mount --bind /dev "$VM_MOUNT_DIR/dev"
	sudo mount --bind /dev/pts "$VM_MOUNT_DIR/dev/pts"
	sudo mount --bind /proc "$VM_MOUNT_DIR/proc"
	sudo mount --bind /sys "$VM_MOUNT_DIR/sys"
	sudo mount --bind /run "$VM_MOUNT_DIR/run"
	sudo cp /etc/resolv.conf "$VM_MOUNT_DIR/etc/resolv.conf"
	sudo cp "$DEB_PATH" "$VM_MOUNT_DIR/tmp/kpanel-client.deb"
	sudo cp "$IMAGE_DIR/provision/configure-image.sh" "$VM_MOUNT_DIR/tmp/configure-image.sh"
	sudo chmod 755 "$VM_MOUNT_DIR/tmp/configure-image.sh"

	sudo chroot "$VM_MOUNT_DIR" /usr/bin/env DEBIAN_FRONTEND=noninteractive bash -lc '
		set -euo pipefail
		apt-get update
		apt-get install -y sudo dbus-x11 lightdm openbox x11-xserver-utils xserver-xorg xserver-xorg-input-all xserver-xorg-input-libinput network-manager chromium qemu-guest-agent openssh-server xterm linux-image-amd64
		/tmp/configure-image.sh kpanel
		apt-get clean
		apt-get autoclean
		rm -rf /var/cache/apt/archives/*
		rm -rf /tmp/*
	'

	cleanup_vm_mounts
	trap - EXIT

	qemu-img convert -f qcow2 -O raw "$OUTPUT_QCOW2" "$OUTPUT_RAW"
	xz --threads=0 "$OUTPUT_RAW"
	sha256sum "$OUTPUT_QCOW2" > "$OUTPUT_QCOW2.sha256"
	sha256sum "$OUTPUT_RAW.xz" > "$OUTPUT_RAW.xz.sha256"

	echo "Built VM artifacts:"
	ls -lh "$OUTPUT_QCOW2" "$OUTPUT_QCOW2.sha256" "$OUTPUT_RAW.xz" "$OUTPUT_RAW.xz.sha256"
}

case "$MODE" in
	preflight)
		run_preflight
		;;
	full)
		run_full_build
		;;
	-h|--help|help)
		usage
		;;
	*)
		usage >&2
		exit 1
		;;
esac