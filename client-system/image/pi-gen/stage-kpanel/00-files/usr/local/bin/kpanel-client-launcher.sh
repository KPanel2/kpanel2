#!/usr/bin/env bash
set -euo pipefail

LOCK_FILE=/tmp/kpanel-client-launcher.lock
LOG_DIR=/tmp/kpanel-client
LOG_FILE="$LOG_DIR/launcher.log"

mkdir -p "$LOG_DIR"

BOOT_LOG=""
for boot_dir in /boot/firmware /boot; do
	if [[ -d "$boot_dir" && -w "$boot_dir" ]]; then
		mkdir -p "$boot_dir/kpanel-debug"
		BOOT_LOG="$boot_dir/kpanel-debug/launcher.log"
		break
	fi
done

if [[ -n "$BOOT_LOG" ]]; then
	exec > >(tee -a "$LOG_FILE" "$BOOT_LOG") 2>&1
else
	exec >>"$LOG_FILE" 2>&1
fi

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
	echo "Another KPanel launcher instance is already running"
	exit 0
fi

CONF_FILE=/etc/default/kpanel-client
MODE_PIN_FILE=/etc/kpanel/mode-set-by-user
MODE_PIN_VERSION_FILE=/etc/kpanel/mode-set-by-user.version
if [[ -f "$CONF_FILE" ]]; then
	# shellcheck disable=SC1090
	source "$CONF_FILE"
fi

# Default to prod unless explicitly pinned with kpanel-set-mode.
MODE="prod"
if [[ -f "$MODE_PIN_FILE" && -f "$MODE_PIN_VERSION_FILE" && "$(tr -d '[:space:]' < "$MODE_PIN_VERSION_FILE" 2>/dev/null || true)" == "2" ]]; then
	pinned_mode="$(tr -d '[:space:]' < "$MODE_PIN_FILE" 2>/dev/null || true)"
	case "$pinned_mode" in
		prod|stage|dev)
			MODE="$pinned_mode"
			;;
		*)
			MODE="${KPANEL_ENV_MODE:-prod}"
			;;
	esac
fi
case "$MODE" in
	prod)
		MODE_URL="${KPANEL_API_BASE_URL_PROD:-https://kpanel.kumpe.app}"
		;;
	stage)
		MODE_URL="${KPANEL_API_BASE_URL_STAGE:-https://kpanel.stage.kumpe.app}"
		;;
	dev)
		MODE_URL="${KPANEL_API_BASE_URL_DEV:-https://kpanel.dev.kumpe.app}"
		;;
	*)
		MODE_URL="${KPANEL_API_BASE_URL_PROD:-https://kpanel.kumpe.app}"
		;;
esac

# Explicit override always wins.
if [[ -n "${KPANEL_API_BASE_URL_OVERRIDE:-}" ]]; then
	export KPANEL_API_BASE_URL_OVERRIDE
else
	export KPANEL_API_BASE_URL_OVERRIDE="$MODE_URL"
fi

export PYTHONPATH="/opt/kpanel-client${PYTHONPATH:+:$PYTHONPATH}"

if [[ -f /etc/kpanel/debug-shell ]]; then
	echo "Debug shell flag present; skipping kiosk launcher"
	if command -v xterm >/dev/null 2>&1; then
		exec xterm -fa Monospace -fs 12 -hold -e sh -lc 'echo "KPanel debug shell mode active."; echo "Remove /etc/kpanel/debug-shell to resume kiosk auto-start."; exec bash'
	fi
	exit 0
fi

# Give desktop/network stack a moment to settle after login.
sleep 5

{
	echo "===== $(date -Iseconds) launcher start ====="
	echo "DISPLAY=${DISPLAY:-}"
	echo "XDG_SESSION_TYPE=${XDG_SESSION_TYPE:-}"
	echo "API_BASE=${KPANEL_API_BASE_URL_OVERRIDE:-}"
}

status=0
set +e
/opt/kpanel-client/.venv/bin/python -m kpanel_client.main
status=$?
set -e

if [[ "$status" -eq 0 ]]; then
	exit 0
fi

{
	echo "KPanel launcher exited with status $status"
	echo "===== $(date -Iseconds) launcher failure ====="
} >>"$LOG_FILE"

if command -v xterm >/dev/null 2>&1; then
	exec xterm -fa Monospace -fs 11 -hold -e sh -lc 'echo "KPanel startup failed. Recent log output:"; echo; tail -n 200 "'$LOG_FILE'"'
fi

exit "$status"
