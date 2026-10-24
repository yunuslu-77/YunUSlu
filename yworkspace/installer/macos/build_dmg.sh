#!/usr/bin/env bash
# Builds dist/yWorkspace.dmg on macOS (Intel or Apple Silicon). Run from the yworkspace/ folder.
set -euo pipefail
pyinstaller --noconfirm installer/yworkspace.spec
STAGE=$(mktemp -d)
cp -R dist/yWorkspace.app "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "yWorkspace" -srcfolder "$STAGE" -ov -format UDZO dist/yWorkspace.dmg
echo "dist/yWorkspace.dmg"
# Signing and notarization need an Apple Developer account:
#   codesign --deep --options runtime --sign "Developer ID Application: ..." dist/yWorkspace.app
#   xcrun notarytool submit dist/yWorkspace.dmg --keychain-profile <profile> --wait
