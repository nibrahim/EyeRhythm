#!/bin/bash
# =============================================================================
# EyesRhythm — start from the desktop's autostart entry
# =============================================================================
#
# Skips if EyesRhythm is already running, then hands off to run.sh.
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/EyesRhythm"
mkdir -p "$LOG_DIR"
LOG="${LOG_DIR}/EyesRhythm.log"

# Already running — do not open a second tab / camera session.
if pgrep -f '^[^ ]*python[0-9.]* -m app\.main' >/dev/null 2>&1; then
    echo "$(date '+%Y-%m-%d %H:%M:%S')  start_at_login: already running, skip" >>"$LOG"
    exit 0
fi

echo "$(date '+%Y-%m-%d %H:%M:%S')  start_at_login: launching" >>"$LOG"
exec "$SCRIPT_DIR/run.sh" >>"$LOG" 2>&1
