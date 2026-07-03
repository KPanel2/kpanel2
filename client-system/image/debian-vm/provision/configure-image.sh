#!/usr/bin/env bash
set -euo pipefail

KPANEL_USER="${1:-kpanel}"
KPANEL_PASSWORD="${KPANEL_PASSWORD:-kpanel}"
AUTOSTART_DIR="/home/$KPANEL_USER/.config/openbox"
OPENBOX_RC="$AUTOSTART_DIR/rc.xml"
XDG_AUTOSTART_DIR="/home/$KPANEL_USER/.config/autostart"
LIGHTDM_DIR=/etc/lightdm/lightdm.conf.d
XSESSIONS_DIR=/usr/share/xsessions
XSESSION_BIN=/usr/local/bin/kpanel-xsession
GRUB_DEFAULTS=/etc/default/grub
SSHD_DROPIN_DIR=/etc/ssh/sshd_config.d
CLOUD_INIT_DISABLE=/etc/cloud/cloud-init.disabled
SELF_HEAL_BIN=/usr/local/sbin/kpanel-vm-self-heal
SELF_HEAL_SERVICE=/etc/systemd/system/kpanel-vm-self-heal.service
NM_CONF_DIR=/etc/NetworkManager/conf.d
NM_CONNECTIONS_DIR=/etc/NetworkManager/system-connections
SSH_SERVICE_OVERRIDE_DIR=/etc/systemd/system/ssh.service.d

if ! id -u "$KPANEL_USER" >/dev/null 2>&1; then
	useradd -m -s /bin/bash -G sudo,video,audio,netdev,input "$KPANEL_USER"
fi

for group_name in autologin nopasswdlogin; do
	if ! getent group "$group_name" >/dev/null 2>&1; then
		groupadd --system "$group_name"
	fi
	usermod -a -G "$group_name" "$KPANEL_USER"
done

echo "$KPANEL_USER:$KPANEL_PASSWORD" | chpasswd

export KPANEL_SKIP_APT_REPO=1
dpkg -i /tmp/kpanel-client.deb || apt-get -f -y install
dpkg -i /tmp/kpanel-client.deb
/usr/local/bin/kpanel-configure-apt-repo || true
unset KPANEL_SKIP_APT_REPO

install -d -m 755 "$LIGHTDM_DIR" "$AUTOSTART_DIR" "$XDG_AUTOSTART_DIR" "$XSESSIONS_DIR" "$SSHD_DROPIN_DIR" "$NM_CONF_DIR" "$NM_CONNECTIONS_DIR" "$SSH_SERVICE_OVERRIDE_DIR"

cat > "$LIGHTDM_DIR/99-kpanel-autologin.conf" <<EOF
[Seat:*]
autologin-user=$KPANEL_USER
autologin-user-timeout=0
autologin-session=kpanel-openbox
user-session=kpanel-openbox
EOF

cat > "$XSESSIONS_DIR/kpanel-openbox.desktop" <<'EOF'
[Desktop Entry]
Name=KPanel Openbox
Comment=KPanel kiosk session using Openbox
Exec=/usr/local/bin/kpanel-xsession
Type=Application
DesktopNames=KPanel-Openbox
EOF

cat > "$XSESSION_BIN" <<'EOF'
#!/usr/bin/env bash
set -u

LOG_DIR=/tmp/kpanel-client
mkdir -p "$LOG_DIR"

{
	echo "===== $(date -Iseconds) xsession start ====="
	echo "DISPLAY=${DISPLAY:-}"
	echo "XDG_SESSION_TYPE=${XDG_SESSION_TYPE:-}"
} >>"$LOG_DIR/xsession.log"

xset s off || true
xset -dpms || true
xset s noblank || true

/usr/local/bin/kpanel-client-launcher.sh >>"$LOG_DIR/xsession.log" 2>&1 &

if command -v openbox-session >/dev/null 2>&1; then
	/usr/bin/openbox-session >>"$LOG_DIR/xsession.log" 2>&1 &
	openbox_pid=$!
	wait "$openbox_pid" || true
	echo "openbox-session exited; holding session open to avoid relogin loop" >>"$LOG_DIR/xsession.log"
fi

echo "openbox-session not found; falling back to xterm" >>"$LOG_DIR/xsession.log"
if command -v xterm >/dev/null 2>&1; then
	exec xterm -fa Monospace -fs 11 -hold -e sh -lc 'echo "KPanel desktop session fallback"; echo "openbox-session is missing."; echo "Check /tmp/kpanel-client/xsession.log and /tmp/kpanel-client/launcher.log"; exec bash'
fi

# Last-resort keepalive to avoid immediate LightDM relogin loop.
exec sh -lc 'while true; do sleep 3600; done'
EOF

cat > "$AUTOSTART_DIR/autostart" <<'EOF'
xset s off
xset -dpms
xset s noblank
/usr/local/bin/kpanel-client-launcher.sh &
EOF

cat > "$OPENBOX_RC" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<openbox_config xmlns="http://openbox.org/3.4/rc">
	<keyboard>
		<keybind key="C-A-T">
			<action name="Execute">
				<command>xterm -fa Monospace -fs 12</command>
			</action>
		</keybind>
		<keybind key="C-A-N">
			<action name="Execute">
				<command>xterm -fa Monospace -fs 12 -e nmtui</command>
			</action>
		</keybind>
		<keybind key="C-A-R">
			<action name="Execute">
				<command>xterm -fa Monospace -fs 12 -e sudo /usr/local/bin/kpanel-set-mode dev</command>
			</action>
		</keybind>
	</keyboard>
</openbox_config>
EOF

cat > "$XDG_AUTOSTART_DIR/kpanel-client.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=KPanel Client
Comment=Start KPanel kiosk client at login
Exec=/usr/local/bin/kpanel-client-launcher.sh
X-GNOME-Autostart-enabled=true
NoDisplay=false
Terminal=false
EOF

cat > "$SSHD_DROPIN_DIR/99-kpanel-appliance.conf" <<EOF
PasswordAuthentication yes
KbdInteractiveAuthentication no
PermitRootLogin no
UsePAM yes
AllowUsers $KPANEL_USER
EOF

cat > "$NM_CONF_DIR/10-kpanel-managed.conf" <<'EOF'
[main]
plugins=ifupdown,keyfile

[ifupdown]
managed=true
EOF

cat > "$NM_CONNECTIONS_DIR/10-kpanel-wired.nmconnection" <<'EOF'
[connection]
id=KPanel Wired DHCP
type=ethernet
autoconnect=true
autoconnect-priority=100

[ipv4]
method=auto

[ipv6]
method=auto
addr-gen-mode=default
EOF
chmod 600 "$NM_CONNECTIONS_DIR/10-kpanel-wired.nmconnection"

cat > "$SSH_SERVICE_OVERRIDE_DIR/10-kpanel.conf" <<'EOF'
[Service]
ExecStartPre=/usr/bin/ssh-keygen -A
Restart=always
RestartSec=5
EOF

ssh-keygen -A

cat > "$SELF_HEAL_BIN" <<EOF
#!/usr/bin/env bash
set -euo pipefail

KPANEL_USER="$KPANEL_USER"

touch /etc/cloud/cloud-init.disabled
rm -f /etc/ssh/sshd_config.d/60-cloudimg-settings.conf
rm -f /etc/network/interfaces.d/50-cloud-init /etc/netplan/50-cloud-init.yaml
install -d -m 755 /etc/ssh/sshd_config.d /etc/lightdm/lightdm.conf.d /etc/NetworkManager/conf.d /etc/NetworkManager/system-connections /etc/systemd/system/ssh.service.d

for group_name in autologin nopasswdlogin; do
	if ! getent group "\$group_name" >/dev/null 2>&1; then
		groupadd --system "\$group_name"
	fi
	usermod -a -G "\$group_name" "\$KPANEL_USER"
done

cat > /etc/ssh/sshd_config.d/99-kpanel-appliance.conf <<HEALSSH
PasswordAuthentication yes
KbdInteractiveAuthentication no
PermitRootLogin no
UsePAM yes
AllowUsers \$KPANEL_USER
HEALSSH

cat > /etc/lightdm/lightdm.conf.d/99-kpanel-autologin.conf <<HEALLIGHTDM
[Seat:*]
autologin-user=\$KPANEL_USER
autologin-user-timeout=0
autologin-session=kpanel-openbox
user-session=kpanel-openbox
HEALLIGHTDM

cat > /etc/NetworkManager/conf.d/10-kpanel-managed.conf <<HEALNMCONF
[main]
plugins=ifupdown,keyfile

[ifupdown]
managed=true
HEALNMCONF

cat > /etc/NetworkManager/system-connections/10-kpanel-wired.nmconnection <<HEALNM
[connection]
id=KPanel Wired DHCP
type=ethernet
autoconnect=true
autoconnect-priority=100

[ipv4]
method=auto

[ipv6]
method=auto
addr-gen-mode=default
HEALNM
chmod 600 /etc/NetworkManager/system-connections/10-kpanel-wired.nmconnection

cat > /etc/systemd/system/ssh.service.d/10-kpanel.conf <<HEALSSHUNIT
[Service]
ExecStartPre=/usr/bin/ssh-keygen -A
Restart=always
RestartSec=5
HEALSSHUNIT

if [[ ! -f "/home/\$KPANEL_USER/.config/openbox/rc.xml" ]]; then
cat > "/home/\$KPANEL_USER/.config/openbox/rc.xml" <<'HEALOPENBOX'
<?xml version="1.0" encoding="UTF-8"?>
<openbox_config xmlns="http://openbox.org/3.4/rc">
	<keyboard>
		<keybind key="C-A-T">
			<action name="Execute">
				<command>xterm -fa Monospace -fs 12</command>
			</action>
		</keybind>
		<keybind key="C-A-N">
			<action name="Execute">
				<command>xterm -fa Monospace -fs 12 -e nmtui</command>
			</action>
		</keybind>
		<keybind key="C-A-R">
			<action name="Execute">
				<command>xterm -fa Monospace -fs 12 -e sudo /usr/local/bin/kpanel-set-mode dev</command>
			</action>
		</keybind>
	</keyboard>
</openbox_config>
HEALOPENBOX
chown "\$KPANEL_USER:\$KPANEL_USER" "/home/\$KPANEL_USER/.config/openbox/rc.xml"
chmod 644 "/home/\$KPANEL_USER/.config/openbox/rc.xml"
fi

systemctl daemon-reload >/dev/null 2>&1 || true
ssh-keygen -A
systemctl enable ssh lightdm qemu-guest-agent NetworkManager serial-getty@ttyS0.service >/dev/null 2>&1 || true
systemctl enable ssh.socket >/dev/null 2>&1 || true
systemctl try-restart NetworkManager >/dev/null 2>&1 || true
systemctl try-restart ssh >/dev/null 2>&1 || true
EOF

cat > "$SELF_HEAL_SERVICE" <<'EOF'
[Unit]
Description=Reassert KPanel VM appliance defaults
DefaultDependencies=no
After=local-fs.target systemd-user-sessions.service
Before=display-manager.service ssh.service network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/kpanel-vm-self-heal
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

mkdir -p "$(dirname "$CLOUD_INIT_DISABLE")"
touch "$CLOUD_INIT_DISABLE"
rm -f /etc/ssh/sshd_config.d/60-cloudimg-settings.conf
rm -f /etc/network/interfaces.d/50-cloud-init /etc/netplan/50-cloud-init.yaml
systemctl daemon-reload || true

chown -R "$KPANEL_USER:$KPANEL_USER" "/home/$KPANEL_USER/.config"
chmod 755 "$AUTOSTART_DIR/autostart"
chmod 644 "$OPENBOX_RC"
chmod 755 "$XSESSION_BIN"
chmod 755 "$SELF_HEAL_BIN"
chmod 755 /usr/local/bin/kpanel-client-launcher.sh /usr/local/bin/kpanel-set-mode

if [[ -f /etc/chromium/default ]]; then
	sed -i 's/^CHROMIUM_FLAGS=.*/CHROMIUM_FLAGS="--disable-features=TranslateUI"/' /etc/chromium/default || true
fi
if [[ -f /etc/chromium-browser/default ]]; then
	sed -i 's/^CHROMIUM_FLAGS=.*/CHROMIUM_FLAGS="--disable-features=TranslateUI"/' /etc/chromium-browser/default || true
fi

if [[ -f "$GRUB_DEFAULTS" ]]; then
	if grep -q '^GRUB_CMDLINE_LINUX_DEFAULT=' "$GRUB_DEFAULTS"; then
		sed -i 's/^GRUB_CMDLINE_LINUX_DEFAULT=.*/GRUB_CMDLINE_LINUX_DEFAULT="quiet console=tty0 console=ttyS0,115200n8"/' "$GRUB_DEFAULTS"
	else
		echo 'GRUB_CMDLINE_LINUX_DEFAULT="quiet console=tty0 console=ttyS0,115200n8"' >> "$GRUB_DEFAULTS"
	fi
	if grep -q '^GRUB_DEFAULT=' "$GRUB_DEFAULTS"; then
		sed -i 's/^GRUB_DEFAULT=.*/GRUB_DEFAULT=saved/' "$GRUB_DEFAULTS"
	else
		echo 'GRUB_DEFAULT=saved' >> "$GRUB_DEFAULTS"
	fi
	if grep -q '^GRUB_SAVEDEFAULT=' "$GRUB_DEFAULTS"; then
		sed -i 's/^GRUB_SAVEDEFAULT=.*/GRUB_SAVEDEFAULT=true/' "$GRUB_DEFAULTS"
	else
		echo 'GRUB_SAVEDEFAULT=true' >> "$GRUB_DEFAULTS"
	fi
	if grep -q '^GRUB_DISABLE_SUBMENU=' "$GRUB_DEFAULTS"; then
		sed -i 's/^GRUB_DISABLE_SUBMENU=.*/GRUB_DISABLE_SUBMENU=y/' "$GRUB_DEFAULTS"
	else
		echo 'GRUB_DISABLE_SUBMENU=y' >> "$GRUB_DEFAULTS"
	fi
	if command -v update-grub >/dev/null 2>&1; then
		update-grub || true
	fi
	if command -v grub-set-default >/dev/null 2>&1; then
		GENERIC_KERNEL="$(ls -1 /boot/vmlinuz-* 2>/dev/null | sed 's#.*/vmlinuz-##' | grep -E 'amd64$' | sort -V | tail -n 1 || true)"
		if [[ -n "$GENERIC_KERNEL" ]]; then
			grub-set-default "Debian GNU/Linux, with Linux $GENERIC_KERNEL" || true
		fi
	fi
fi

systemctl disable kpanel-client.service || true
systemctl stop kpanel-client.service || true
systemctl set-default graphical.target || true
systemctl enable lightdm || true
systemctl enable qemu-guest-agent || true
systemctl enable NetworkManager || true
systemctl enable ssh || true
systemctl enable ssh.socket || true
systemctl enable serial-getty@ttyS0.service || true
systemctl enable kpanel-vm-self-heal.service || true