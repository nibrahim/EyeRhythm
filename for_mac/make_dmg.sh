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

# Room for icon layout: app on the left, Applications on the right.
APP_SIZE_MB=$(du -sm "$STAGING" | awk '{print $1}')
DMG_SIZE_MB=$((APP_SIZE_MB + 40))

echo "Creating writable disk image (${DMG_SIZE_MB} MB)…"
hdiutil create \
    -volname "$VOL_NAME" \
    -srcfolder "$STAGING" \
    -ov \
    -format UDRW \
    -size "${DMG_SIZE_MB}m" \
    "$TMP_DMG" >/dev/null

echo "Mounting to set Finder layout…"
DEVICE=$(hdiutil attach -readwrite -noverify -noautoopen "$TMP_DMG" \
    | awk 'NR==1{print $1}')
MOUNT_DIR="/Volumes/$VOL_NAME"
# Wait until both icons are visible on the volume.
for _ in $(seq 1 30); do
    if [ -e "$MOUNT_DIR/EyesRhythm.app" ] && [ -e "$MOUNT_DIR/Applications" ]; then
        break
    fi
    sleep 0.5
done
if [ ! -d "$MOUNT_DIR" ]; then
    echo "ERROR: could not mount $TMP_DMG"
    exit 1
fi

# Position icons: app on the left, Applications on the right.
# Symlinks are "alias files" to Finder — set positions with a soft retry.
sleep 1
osascript <<EOF || true
tell application "Finder"
    tell disk "$VOL_NAME"
        open
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set bounds of container window to {200, 120, 760, 480}
        set theViewOptions to the icon view options of container window
        set arrangement of theViewOptions to not arranged
        set icon size of theViewOptions to 96
        delay 0.5
        try
            set position of item "EyesRhythm.app" of container window to {140, 180}
        end try
        try
            set position of item "Applications" of container window to {420, 180}
        end try
        update without registering applications
        delay 1
        close
    end tell
end tell
EOF

sync
# Prefer detaching by device node; fall back to volume path.
if [ -n "$DEVICE" ]; then
    hdiutil detach "$DEVICE" >/dev/null 2>&1 || hdiutil detach "$MOUNT_DIR" -force >/dev/null
else
    hdiutil detach "$MOUNT_DIR" -force >/dev/null
fi

echo "Compressing to UDZO…"
hdiutil convert "$TMP_DMG" -format UDZO -imagekey zlib-level=9 -o "$DMG_OUT" >/dev/null
rm -f "$TMP_DMG"
rm -rf "$STAGING"

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
