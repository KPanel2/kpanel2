if [ -z "$SSH_CONNECTION" ] && [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
  XAUTH_DIR=/tmp/kpanel-client
  mkdir -p "$XAUTH_DIR"
  export XAUTHORITY="$XAUTH_DIR/.Xauthority"
  rm -f "${XAUTHORITY}-c" "${XAUTHORITY}-l"
  touch "$XAUTHORITY"
  chmod 600 "$XAUTHORITY" || true
  xauth -q list >/dev/null 2>&1 || true
  exec startx
fi