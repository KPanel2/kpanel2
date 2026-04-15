#!/bin/bash -e

if [ ! -f /usr/local/src/kpanel-client.deb ]; then
  echo "Missing /usr/local/src/kpanel-client.deb in image stage"
  exit 1
fi

# Install package and dependencies.
dpkg -i /usr/local/src/kpanel-client.deb || apt-get -f -y install

# Package postinst enables the system service; for desktop kiosk flow we prefer autostart.
systemctl disable kpanel-client.service || true
systemctl stop kpanel-client.service || true

install -d -m 755 -o pi -g pi /home/pi/.config /home/pi/.config/openbox
chmod +x /usr/local/bin/kpanel-client-launcher.sh
chmod +x /usr/local/bin/kpanel-set-mode
chmod +x /home/pi/.config/openbox/autostart
chown pi:pi /home/pi/.config/openbox/autostart

# Ensure chromium can start with user session defaults.
if [ -f /etc/chromium-browser/default ]; then
  sed -i 's/^CHROMIUM_FLAGS=.*/CHROMIUM_FLAGS="--disable-features=TranslateUI"/' /etc/chromium-browser/default || true
fi
