#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR=/opt/kpanel-client
STATE_DIR=/var/lib/kpanel-client
SERVICE_NAME=kpanel-client.service
LAUNCHER_NAME=kpanel-client-launcher.sh
MODE_HELPER_NAME=kpanel-set-mode

if apt-cache show chromium >/dev/null 2>&1; then
	CHROMIUM_PACKAGE=chromium
else
	CHROMIUM_PACKAGE=chromium-browser
fi

sudo apt-get update
sudo apt-get install -y python3-venv python3-tk python3-xdg network-manager "$CHROMIUM_PACKAGE"

sudo mkdir -p "$INSTALL_DIR"
sudo cp -r kpanel_client requirements.txt "$INSTALL_DIR/"

python3 -m venv "$INSTALL_DIR/.venv"
export PYTHONPATH="$INSTALL_DIR${PYTHONPATH:+:$PYTHONPATH}"
"$INSTALL_DIR/.venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

sudo cp systemd/$SERVICE_NAME /etc/systemd/system/$SERVICE_NAME
sudo cp image/pi-gen/stage-kpanel/00-files/usr/local/bin/$LAUNCHER_NAME /usr/local/bin/$LAUNCHER_NAME
sudo cp image/pi-gen/stage-kpanel/00-files/usr/local/bin/$MODE_HELPER_NAME /usr/local/bin/$MODE_HELPER_NAME
sudo chmod 755 /usr/local/bin/$LAUNCHER_NAME /usr/local/bin/$MODE_HELPER_NAME
sudo mkdir -p "$STATE_DIR"
RUNTIME_OWNER="$(id -un)"
sudo chown -R "$RUNTIME_OWNER":"$(id -gn)" "$INSTALL_DIR" "$STATE_DIR"
RUNTIME_HOME="$(getent passwd "$RUNTIME_OWNER" | cut -d: -f6 || true)"
if [[ -n "$RUNTIME_HOME" && -e "$RUNTIME_HOME" ]]; then
	sudo chown -R "$RUNTIME_OWNER:$RUNTIME_OWNER" "$RUNTIME_HOME"
	sudo install -d -m 700 -o "$RUNTIME_OWNER" -g "$RUNTIME_OWNER" "$RUNTIME_HOME/.cache"
fi
if [[ ! -f /etc/default/kpanel-client ]]; then
	sudo cp image/pi-gen/stage-kpanel/00-files/etc/default/kpanel-client /etc/default/kpanel-client
fi
if [[ -x /usr/local/sbin/kpanel-pi-self-heal ]]; then
	sudo /usr/local/sbin/kpanel-pi-self-heal || true
	sudo systemctl disable "$SERVICE_NAME" --now 2>/dev/null || true
else
	sudo systemctl daemon-reload
	sudo systemctl enable "$SERVICE_NAME"
	sudo systemctl restart "$SERVICE_NAME"
fi

echo "KPanel client installed and service started."
