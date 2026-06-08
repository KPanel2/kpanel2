#!/usr/bin/env bash
set -euo pipefail

VERSION_RAW="${1:-0.1.0}"
CHANNEL="${2:-prod}"   # prod | stage | dev
COMMIT_SHA="${3:-}"   # optional short SHA to append to dev/stage versions

VERSION="${VERSION_RAW#v}"
case "$CHANNEL" in
  stage) VERSION="${VERSION}~stage${COMMIT_SHA:+.$COMMIT_SHA}" ;;
  dev)   VERSION="${VERSION}~dev${COMMIT_SHA:+.$COMMIT_SHA}" ;;
  prod)  : ;;
  *)
    echo "Unknown channel '${CHANNEL}'. Use: prod | stage | dev" >&2
    exit 1
    ;;
esac
PKG_NAME="kpanel-client"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="$ROOT_DIR/build"
PKG_ROOT="$BUILD_DIR/${PKG_NAME}_${VERSION}"

rm -rf "$PKG_ROOT"
mkdir -p "$PKG_ROOT/DEBIAN"
mkdir -p "$PKG_ROOT/usr/share/$PKG_NAME"

cp "$ROOT_DIR/debian/postinst" "$PKG_ROOT/DEBIAN/postinst"
cp "$ROOT_DIR/debian/prerm" "$PKG_ROOT/DEBIAN/prerm"

sed "s/^Version: .*/Version: ${VERSION}/" "$ROOT_DIR/debian/control" > "$PKG_ROOT/DEBIAN/control"

chmod 755 "$PKG_ROOT/DEBIAN/postinst" "$PKG_ROOT/DEBIAN/prerm"
chmod 644 "$PKG_ROOT/DEBIAN/control"

cp -r "$ROOT_DIR/kpanel_client" "$PKG_ROOT/usr/share/$PKG_NAME/"
cp "$ROOT_DIR/requirements.txt" "$PKG_ROOT/usr/share/$PKG_NAME/"
mkdir -p "$PKG_ROOT/usr/share/$PKG_NAME/systemd"
cp "$ROOT_DIR/systemd/kpanel-client.service" "$PKG_ROOT/usr/share/$PKG_NAME/systemd/"
mkdir -p "$PKG_ROOT/usr/share/$PKG_NAME/bin"
for _script in kpanel-client-launcher.sh kpanel-set-mode kpanel-show-mode kpanel-version kpanel-install-version kpanel-prod kpanel-stage kpanel-dev; do
	cp "$ROOT_DIR/image/pi-gen/stage-kpanel/00-files/usr/local/bin/$_script" \
		"$PKG_ROOT/usr/share/$PKG_NAME/bin/$_script"
done
mkdir -p "$PKG_ROOT/usr/share/$PKG_NAME/defaults"
cp "$ROOT_DIR/image/pi-gen/stage-kpanel/00-files/etc/default/kpanel-client" \
	"$PKG_ROOT/usr/share/$PKG_NAME/defaults/"

mkdir -p "$BUILD_DIR"
dpkg-deb --build "$PKG_ROOT" "$BUILD_DIR/${PKG_NAME}_${VERSION}_all.deb"

echo "Built: $BUILD_DIR/${PKG_NAME}_${VERSION}_all.deb"
