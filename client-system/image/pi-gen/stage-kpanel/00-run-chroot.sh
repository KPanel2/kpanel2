#!/bin/bash -e

if [ ! -f /usr/local/src/kpanel-client.deb ]; then
  echo "Missing /usr/local/src/kpanel-client.deb in image stage"
  exit 1
fi

# Install package and dependencies. Defer apt repo setup so apt-get -f does not
# try to upgrade kpanel-client from the remote KumpeApps repository mid-install.
export KPANEL_SKIP_APT_REPO=1
# Restrict apt-get -f to base OS sources so a previously configured KumpeApps
# repo cannot pull kpanel-client from broken or newer remote metadata.
apt_fix_opts=(
	-o Dir::Etc::sourcelist=/dev/null
	-o Dir::Etc::sourceparts=-
)
dpkg -i /usr/local/src/kpanel-client.deb || apt-get -f -y install "${apt_fix_opts[@]}"
/usr/local/bin/kpanel-configure-apt-repo || true
unset KPANEL_SKIP_APT_REPO

# Package postinst enables the system service; for desktop kiosk flow we prefer autostart.
systemctl disable kpanel-client.service || true
systemctl stop kpanel-client.service || true
systemctl disable lightdm || true
systemctl stop lightdm || true
systemctl set-default multi-user.target || true
systemctl enable getty@tty1.service || true

# Use console autologin so tty1 can start the kiosk session via startx.
if command -v raspi-config >/dev/null 2>&1; then
  raspi-config nonint do_boot_behaviour B2 || true
fi

# Harden boot defaults in case noninteractive raspi-config does not persist.
mkdir -p /etc/systemd/system
ln -sf /lib/systemd/system/multi-user.target /etc/systemd/system/default.target
rm -f /etc/systemd/system/display-manager.service

install -d -m 755 -o pi -g pi /home/pi/.config /home/pi/.config/openbox /home/pi/.local /home/pi/.local/share /home/pi/.local/share/xorg
chmod +x /usr/local/bin/kpanel-client-launcher.sh
chmod +x /usr/local/bin/kpanel-xsession
chmod +x /usr/local/bin/kpanel-set-mode
chmod +x /usr/local/bin/kpanel-prod
chmod +x /usr/local/bin/kpanel-stage
chmod +x /usr/local/bin/kpanel-dev
chmod +x /usr/local/bin/kpanel-show-mode
chmod +x /usr/local/sbin/kpanel-pi-self-heal
chmod 644 /boot/firmware/kpanel-wifi.conf.example 2>/dev/null || true
chmod 644 /etc/profile.d/kpanel-startx.sh
chmod 644 /home/pi/.profile
chmod 755 /home/pi/.xinitrc
chmod +x /home/pi/.config/openbox/autostart
chown pi:pi /home/pi/.config/openbox/autostart
chmod 644 /home/pi/.config/openbox/rc.xml
chown pi:pi /home/pi/.config/openbox/rc.xml
chown pi:pi /home/pi/.profile /home/pi/.xinitrc
chmod 644 /home/pi/.dmrc
chown pi:pi /home/pi/.dmrc
systemctl enable kpanel-pi-self-heal.service || true

# Apply appliance defaults in-image immediately and reassert them on every boot.
/usr/local/sbin/kpanel-pi-self-heal || true

# Ensure the pi user can set the system timezone without a password (required
# by kpanel-client which runs as pi but calls timedatectl set-timezone).
mkdir -p /etc/sudoers.d
printf 'pi ALL=(root) NOPASSWD: /usr/bin/timedatectl set-timezone *\n' \
    > /etc/sudoers.d/kpanel-timedatectl
chmod 440 /etc/sudoers.d/kpanel-timedatectl

# Ensure chromium can start with user session defaults.
if [ -f /etc/chromium-browser/default ]; then
  sed -i 's/^CHROMIUM_FLAGS=.*/CHROMIUM_FLAGS="--disable-features=TranslateUI"/' /etc/chromium-browser/default || true
fi
