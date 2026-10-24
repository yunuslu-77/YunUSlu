#!/usr/bin/env bash
# Builds dist/yworkspace_<version>_<arch>.deb from the PyInstaller folder. Run from the yworkspace/ folder.
set -euo pipefail
VERSION=$(python -c "import sys; sys.path.insert(0, 'src'); import yworkspace; print(yworkspace.__version__)")
ARCH=$(dpkg --print-architecture)
[ -d dist/yworkspace ] || pyinstaller --noconfirm installer/yworkspace.spec
PKG=$(mktemp -d)/yworkspace_${VERSION}_${ARCH}
mkdir -p "$PKG/DEBIAN" "$PKG/opt/yworkspace" "$PKG/usr/bin" "$PKG/usr/share/applications"
cp -R dist/yworkspace/. "$PKG/opt/yworkspace/"
ln -s /opt/yworkspace/yworkspace "$PKG/usr/bin/yw"
cat > "$PKG/DEBIAN/control" <<CONTROL
Package: yworkspace
Version: ${VERSION}
Architecture: ${ARCH}
Maintainer: Yunus Emre USLU <yunuslu@users.noreply.github.com>
Recommends: docker.io | docker-ce, git, ffmpeg
Section: devel
Priority: optional
Description: yWorkspace - her yapay zekaya tam bir gelistirme ortami
 A full working environment for every AI: files, sandbox, tests, deep work engine.
CONTROL
cat > "$PKG/usr/share/applications/yworkspace.desktop" <<DESKTOP
[Desktop Entry]
Name=yWorkspace
Exec=/opt/yworkspace/yworkspace web
Terminal=true
Type=Application
Categories=Development;
DESKTOP
dpkg-deb --build --root-owner-group "$PKG" dist/
ls dist/*.deb
