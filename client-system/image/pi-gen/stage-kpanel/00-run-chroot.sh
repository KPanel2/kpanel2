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
systemctl set-default graphical.target || true
systemctl enable lightdm || true

# Use the distro-supported boot behavior so Raspberry Pi OS actually autologins
# into the desktop session instead of stopping at the LightDM greeter.
if command -v raspi-config >/dev/null 2>&1; then
  raspi-config nonint do_boot_behaviour B4 || true
fi

# Harden boot defaults in case noninteractive raspi-config does not persist.
mkdir -p /etc/systemd/system
ln -sf /lib/systemd/system/graphical.target /etc/systemd/system/default.target
if [ -f /lib/systemd/system/lightdm.service ]; then
  ln -sf /lib/systemd/system/lightdm.service /etc/systemd/system/display-manager.service
fi

install -d -m 755 -o pi -g pi /home/pi/.config /home/pi/.config/openbox
chmod +x /usr/local/bin/kpanel-client-launcher.sh
chmod +x /usr/local/bin/kpanel-xsession
chmod +x /usr/local/bin/kpanel-set-mode
chmod +x /usr/local/sbin/kpanel-pi-self-heal
chmod +x /home/pi/.config/openbox/autostart
chown pi:pi /home/pi/.config/openbox/autostart
chmod 644 /home/pi/.dmrc
chown pi:pi /home/pi/.dmrc
systemctl enable kpanel-pi-self-heal.service || true

# Apply appliance defaults in-image immediately and reassert them on every boot.
/usr/local/sbin/kpanel-pi-self-heal || true

# Ensure chromium can start with user session defaults.
if [ -f /etc/chromium-browser/default ]; then
  sed -i 's/^CHROMIUM_FLAGS=.*/CHROMIUM_FLAGS="--disable-features=TranslateUI"/' /etc/chromium-browser/default || true
fi
