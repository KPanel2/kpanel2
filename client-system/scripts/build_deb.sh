#!/usr/bin/env bash
set -euo pipefail

VERSION_RAW="${1:-0.1.0}"
VERSION="${VERSION_RAW#v}"
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
cp "$ROOT_DIR/image/pi-gen/stage-kpanel/00-files/usr/local/bin/kpanel-client-launcher.sh" \
	"$PKG_ROOT/usr/share/$PKG_NAME/bin/"
cp "$ROOT_DIR/image/pi-gen/stage-kpanel/00-files/usr/local/bin/kpanel-set-mode" \
	"$PKG_ROOT/usr/share/$PKG_NAME/bin/"
mkdir -p "$PKG_ROOT/usr/share/$PKG_NAME/defaults"
cp "$ROOT_DIR/image/pi-gen/stage-kpanel/00-files/etc/default/kpanel-client" \
	"$PKG_ROOT/usr/share/$PKG_NAME/defaults/"

mkdir -p "$BUILD_DIR"
dpkg-deb --build "$PKG_ROOT" "$BUILD_DIR/${PKG_NAME}_${VERSION}_all.deb"

echo "Built: $BUILD_DIR/${PKG_NAME}_${VERSION}_all.deb"
