#!/bin/bash
# =============================================================================
# EyesRhythm — stop opening automatically at login
# =============================================================================
set -e

LABEL="com.eyerhythm.app"
AGENTS_DIR="${HOME}/Library/LaunchAgents"
PLIST="${AGENTS_DIR}/${LABEL}.plist"
UID_NUM="$(id -u)"
DOMAIN="gui/${UID_NUM}/${LABEL}"

if launchctl print "$DOMAIN" >/dev/null 2>&1; then
    launchctl bootout "gui/${UID_NUM}" "$PLIST" >/dev/null 2>&1 || \
        launchctl bootout "$DOMAIN" >/dev/null 2>&1 || true
fi
if [ -f "$PLIST" ]; then
    launchctl unload "$PLIST" >/dev/null 2>&1 || true
    rm -f "$PLIST"
fi

echo "EyesRhythm will no longer start at login."
echo "The app itself is unchanged — run it anytime with:  ./for_mac/run.sh"
