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
sudo apt-get install -y python3-venv python3-tk network-manager "$CHROMIUM_PACKAGE"

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
sudo chown -R "$(id -un)":"$(id -gn)" "$INSTALL_DIR" "$STATE_DIR"
if [[ ! -f /etc/default/kpanel-client ]]; then
	sudo cp image/pi-gen/stage-kpanel/00-files/etc/default/kpanel-client /etc/default/kpanel-client
fi
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl restart $SERVICE_NAME

echo "KPanel client installed and service started."
