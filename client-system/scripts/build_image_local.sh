#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-preflight}"
VERSION_RAW="${2:-0.1.0~local$(git -C "$(cd "$(dirname "$0")/../.." && pwd)" rev-parse --short HEAD)}"
IMAGE_NAME="${3:-kpanel-appliance}"

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "$ROOT_DIR/.." && pwd)"
STAGE_DIR="$ROOT_DIR/image/pi-gen/stage-kpanel"
PAYLOAD_DEB_DIR="$STAGE_DIR/00-files/usr/local/src"
PI_GEN_DIR="${KPANEL_PI_GEN_DIR:-/tmp/pi-gen}"
VERSION="${VERSION_RAW#v}"

usage() {
	cat <<EOF
Usage: $(basename "$0") <preflight|full> [package-version] [image-name]

Modes:
  preflight  Validate stage layout and build/inject the deb payload only.
  full       Run preflight, clone pi-gen if needed, and build the local image.

Environment:
  KPANEL_PI_GEN_DIR   Target pi-gen checkout directory (default: /tmp/pi-gen)
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

cleanup_stale_pi_gen_container() {
	local container_name="${KPANEL_PIGEN_CONTAINER_NAME:-pigen_work}"
	local running_container_id
	local existing_container_id

	running_container_id="$(docker ps --filter "name=^/${container_name}$" -q)"
	if [[ -n "$running_container_id" ]]; then
		echo "pi-gen container $container_name is already running; stop it before starting another full build." >&2
		exit 1
	fi

	existing_container_id="$(docker ps -a --filter "name=^/${container_name}$" -q)"
	if [[ -n "$existing_container_id" ]]; then
		echo "Removing stale pi-gen container $container_name"
		docker rm -v "$container_name" >/dev/null 2>&1 || sudo docker rm -v "$container_name" >/dev/null
	fi

	export CONTAINER_NAME="$container_name"
}

ensure_host_build_dependencies() {
	local missing=0
	local packages=(
		quilt
		debootstrap
		libarchive-tools
		arch-test
		binfmt-support
		qemu-user-static
		xz-utils
		curl
		rsync
	)

	for command_name in docker git qemu-arm-static update-binfmts; do
		if ! command -v "$command_name" >/dev/null 2>&1; then
			missing=1
			break
		fi
	done

	if [[ "$missing" -eq 0 ]]; then
		return
	fi

	echo "Installing local pi-gen host dependencies with apt..."
	sudo apt-get update
	sudo apt-get install -y "${packages[@]}"
}

register_arm_binfmt() {
	sudo modprobe binfmt_misc || true
	sudo mount -t binfmt_misc binfmt_misc /proc/sys/fs/binfmt_misc || true
	sudo update-binfmts --enable qemu-arm || true
	sudo update-binfmts --enable qemu-aarch64 || true

	if ! command -v qemu-arm >/dev/null 2>&1 && command -v qemu-arm-static >/dev/null 2>&1; then
		sudo ln -sf "$(command -v qemu-arm-static)" /usr/local/bin/qemu-arm
	fi
	if ! command -v qemu-aarch64 >/dev/null 2>&1 && command -v qemu-aarch64-static >/dev/null 2>&1; then
		sudo ln -sf "$(command -v qemu-aarch64-static)" /usr/local/bin/qemu-aarch64
	fi

	docker run --rm --privileged tonistiigi/binfmt --install arm,arm64
}

run_preflight() {
	require_file "$STAGE_DIR/EXPORT_IMAGE"
	require_file "$STAGE_DIR/prerun.sh"
	require_file "$STAGE_DIR/00-run-chroot.sh"
	require_file "$STAGE_DIR/00-files/usr/local/bin/kpanel-set-mode"
	require_file "$STAGE_DIR/00-files/usr/local/bin/kpanel-client-launcher.sh"

	if ! grep -q 'copy_previous' "$STAGE_DIR/prerun.sh"; then
		echo "Expected $STAGE_DIR/prerun.sh to call copy_previous" >&2
		exit 1
	fi

	chmod 755 "$STAGE_DIR/prerun.sh"
	bash -n "$STAGE_DIR/prerun.sh"
	bash -n "$STAGE_DIR/00-run-chroot.sh"
	bash -n "$STAGE_DIR/00-files/usr/local/bin/kpanel-set-mode"

	"$ROOT_DIR/scripts/build_deb.sh" "$VERSION"
	mkdir -p "$PAYLOAD_DEB_DIR"
	cp "$ROOT_DIR/build/kpanel-client_${VERSION}_all.deb" "$PAYLOAD_DEB_DIR/kpanel-client.deb"

	echo "Preflight passed. Deb payload prepared at $PAYLOAD_DEB_DIR/kpanel-client.deb"
}

ensure_pi_gen_checkout() {
	if [[ -d "$PI_GEN_DIR/.git" ]]; then
		git -C "$PI_GEN_DIR" fetch --depth=1 origin bookworm
		git -C "$PI_GEN_DIR" checkout bookworm
		git -C "$PI_GEN_DIR" reset --hard origin/bookworm
	else
		rm -rf "$PI_GEN_DIR"
		git clone --depth=1 --branch bookworm --single-branch https://github.com/RPi-Distro/pi-gen.git "$PI_GEN_DIR"
	fi
}

patch_pi_gen_for_local_arch() {
	if [[ "$(uname -m)" != "aarch64" ]]; then
		return
	fi

	# On arm64 hosts, keep pi-gen's i386 base image but force the build and run
	# platform to linux/386 so armhf bootstrap can run in a 32-bit container.
	if ! grep -q -- '--platform linux/386' "$PI_GEN_DIR/build-docker.sh"; then
		sed -i 's#^\${DOCKER} build --build-arg BASE_IMAGE=\${BASE_IMAGE} -t pi-gen "\${DIR}"$#${DOCKER} build --platform linux/386 --build-arg BASE_IMAGE=${BASE_IMAGE} -t pi-gen "${DIR}"#' "$PI_GEN_DIR/build-docker.sh"
		sed -i '/^time \${DOCKER} run \\$/a\  --platform linux/386 \\' "$PI_GEN_DIR/build-docker.sh"
	fi

	# In that 32-bit container, setarch linux32 still fails and prevents stage0
	# from creating rootfs. Run capsh directly for this local-only path.
	sed -i 's/^\([[:space:]]*\)setarch linux32 capsh /\1capsh /' "$PI_GEN_DIR/scripts/common"
}

configure_pi_gen() {
	cp -r "$STAGE_DIR" "$PI_GEN_DIR/"
	chmod 755 "$PI_GEN_DIR/stage-kpanel/prerun.sh" "$PI_GEN_DIR/stage-kpanel/00-run-chroot.sh"
	cat >"$PI_GEN_DIR/config" <<EOF
IMG_NAME='${IMAGE_NAME}'
RELEASE='bookworm'
TARGET_HOSTNAME='kpanel'
FIRST_USER_NAME='pi'
FIRST_USER_PASS='kpanel'
DISABLE_FIRST_BOOT_USER_RENAME=1
ENABLE_SSH=1
DEPLOY_ZIP=0
STAGE_LIST='stage0 stage1 stage2 stage3 stage-kpanel'
EOF
}

run_full_build() {
	ensure_host_build_dependencies
	require_command docker
	require_command git
	require_command qemu-arm-static

	run_preflight
	ensure_pi_gen_checkout
	patch_pi_gen_for_local_arch
	configure_pi_gen
	register_arm_binfmt
	cleanup_stale_pi_gen_container

	(
		cd "$PI_GEN_DIR"
		sudo ./build-docker.sh
	)

	echo "Full build finished. Artifacts are under $PI_GEN_DIR/deploy"
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