#!/bin/bash
# =============================================================================
# EyesRhythm — stop opening automatically at login
# =============================================================================
set -e

ENTRY="${XDG_CONFIG_HOME:-$HOME/.config}/autostart/eyesrhythm.desktop"

rm -f "$ENTRY"

echo "EyesRhythm will no longer start at login."
echo "The app itself is unchanged — run it anytime with:  ./for_linux/run.sh"
