#!/bin/bash
# =============================================================================
# EyeRhythm — start from a macOS Login item / Launch Agent
# =============================================================================
#
# Waits until the desktop session is up, skips if EyeRhythm is already
# running, then hands off to run.sh (venv + python -m app.main).
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="${HOME}/Library/Logs"
mkdir -p "$LOG_DIR"
LOG="${LOG_DIR}/EyeRhythm.log"

{
    echo "----------------------------------------"
    echo "$(date '+%Y-%m-%d %H:%M:%S')  start_at_login: begin"
} >>"$LOG"

# Wait until the Aqua session is actually on screen (Dock is a reliable signal).
# After a reboot this can take a few seconds; after a normal install it is instant.
for _ in $(seq 1 60); do
    if pgrep -qx Dock; then
        break
    fi
    sleep 1
done
sleep 3

# Already running — do not open a second window / camera session.
if pgrep -fq "[p]ython -m app.main"; then
    echo "$(date '+%Y-%m-%d %H:%M:%S')  start_at_login: already running, skip" >>"$LOG"
    exit 0
fi

if lsof -nP -iTCP:8742 -sTCP:LISTEN >/dev/null 2>&1; then
    echo "$(date '+%Y-%m-%d %H:%M:%S')  start_at_login: port 8742 already in use, skip" >>"$LOG"
    exit 0
fi

echo "$(date '+%Y-%m-%d %H:%M:%S')  start_at_login: launching" >>"$LOG"
exec "$SCRIPT_DIR/run.sh"
