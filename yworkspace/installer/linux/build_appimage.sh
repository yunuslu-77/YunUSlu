#!/usr/bin/env bash
# Builds dist/yWorkspace-x86_64.AppImage. Needs appimagetool (https://github.com/AppImage/appimagetool).
set -euo pipefail
[ -d dist/yworkspace ] || pyinstaller --noconfirm installer/yworkspace.spec
APPDIR=$(mktemp -d)/yWorkspace.AppDir
mkdir -p "$APPDIR/usr/bin"
cp -R dist/yworkspace/. "$APPDIR/usr/bin/"
cat > "$APPDIR/AppRun" <<'RUN'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/yworkspace" "$@"
RUN
chmod +x "$APPDIR/AppRun"
cat > "$APPDIR/yworkspace.desktop" <<DESKTOP
[Desktop Entry]
Name=yWorkspace
Exec=yworkspace
Icon=yworkspace
Type=Application
Categories=Development;
Terminal=true
DESKTOP
cp installer/icon.png "$APPDIR/yworkspace.png" 2>/dev/null || python -c "
import base64,sys; open(sys.argv[1],'wb').write(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkqG+oBwAEhgGAWkW3sgAAAABJRU5ErkJggg=='))" "$APPDIR/yworkspace.png"
appimagetool "$APPDIR" dist/yWorkspace-x86_64.AppImage
