#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR=/opt/kpanel-client
SERVICE_NAME=kpanel-client.service

sudo apt-get update
sudo apt-get install -y python3-venv python3-tk network-manager chromium-browser

sudo mkdir -p "$INSTALL_DIR"
sudo cp -r kpanel_client requirements.txt "$INSTALL_DIR/"

python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

sudo cp systemd/$SERVICE_NAME /etc/systemd/system/$SERVICE_NAME
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl restart $SERVICE_NAME

echo "KPanel client installed and service started."
