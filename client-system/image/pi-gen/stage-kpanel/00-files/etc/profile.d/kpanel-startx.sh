if [ "${USER:-}" = "pi" ] && [ -z "${SSH_CONNECTION:-}" ] && [ -z "${DISPLAY:-}" ]; then
  if [ -z "${KPANEL_STARTX_LAUNCHED:-}" ]; then
    export KPANEL_STARTX_LAUNCHED=1
    XAUTH_DIR=/tmp/kpanel-client
    mkdir -p "$XAUTH_DIR"
    export XAUTHORITY="$XAUTH_DIR/.Xauthority"
    rm -f "${XAUTHORITY}-c" "${XAUTHORITY}-l"
    touch "$XAUTHORITY"
    chmod 600 "$XAUTHORITY" 2>/dev/null || true
    xauth -q list >/dev/null 2>&1 || true

    while true; do
      startx >>/tmp/kpanel-client/startx.log 2>&1 && exit 0
      sleep 2
    done
  fi
fi