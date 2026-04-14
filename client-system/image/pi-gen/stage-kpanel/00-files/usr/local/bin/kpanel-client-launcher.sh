#!/usr/bin/env bash
set -euo pipefail

CONF_FILE=/etc/default/kpanel-client
if [[ -f "$CONF_FILE" ]]; then
	# shellcheck disable=SC1090
	source "$CONF_FILE"
fi

MODE="${KPANEL_ENV_MODE:-prod}"
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

# Give desktop/network stack a moment to settle after login.
sleep 5

exec /opt/kpanel-client/.venv/bin/python -m kpanel_client.main
