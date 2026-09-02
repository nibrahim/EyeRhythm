#!/bin/bash
# =============================================================================
# EyesRhythm — wrap dist/EyesRhythm.app in a drag-to-Applications .dmg
# =============================================================================
#
# Creates a classic Mac installer window:
#   EyesRhythm.app  →  Applications
#
# Prerequisites:  ./for_mac/build_mac.sh   (produces dist/EyesRhythm.app)
#
# Output:  dist/EyesRhythm.dmg
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

APP="$ROOT/dist/EyesRhythm.app"
DMG_OUT="$ROOT/dist/EyesRhythm.dmg"
STAGING="$ROOT/dist/dmg_staging"
VOL_NAME="EyesRhythm"
TMP_DMG="$ROOT/dist/.EyesRhythm-rw.dmg"

if [ ! -d "$APP" ]; then
    echo "ERROR: $APP not found."
    echo "Build first:  ./for_mac/build_mac.sh"
    exit 1
fi

echo "=============================================="
echo "  EyesRhythm  ·  make DMG"
echo "=============================================="
echo

rm -rf "$STAGING" "$TMP_DMG" "$DMG_OUT"
mkdir -p "$STAGING"

echo "Staging app + Applications shortcut…"
cp -R "$APP" "$STAGING/EyesRhythm.app"
ln -s /Applications "$STAGING/Applications"

# HFS+ + LZMA stays under Dodo's 100 MB upload cap. APFS + zlib does not.
echo "Creating LZMA disk image…"
hdiutil create \
    -volname "$VOL_NAME" \
    -srcfolder "$STAGING" \
    -fs HFS+ \
    -format ULMO \
    -ov \
    -o "$DMG_OUT"
rm -rf "$STAGING" "$TMP_DMG"

# Drop PyInstaller leftovers so dist/ only keeps the shippable DMG
# (plus windows/ if present). Keep the .app only when KEEP_APP=1.
if [ "${KEEP_APP:-0}" != "1" ]; then
    echo "Cleaning intermediate build folders…"
    rm -rf "$ROOT/dist/EyesRhythm" "$APP"
fi

echo
echo "SUCCESS:  $DMG_OUT"
du -sh "$DMG_OUT"
echo
echo "Open it, then drag EyesRhythm → Applications."
echo
