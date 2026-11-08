#!/bin/bash
# =============================================================================
# EyesRhythm — launch the app from source on Linux
# =============================================================================
#
# 1. Activates the EyeRhythm/ virtualenv
# 2. Builds the React UI if frontend/dist is missing
# 3. Starts:  python -m app.main --browser
#
# Examples:
#   ./for_linux/run.sh
#   ./for_linux/run.sh --camera 1
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

# Prefer project-local venv names used by setup / developers.
if [ -d EyeRhythm ]; then
    # shellcheck disable=SC1091
    source EyeRhythm/bin/activate
elif [ -d .venv ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
else
    echo "No virtual environment found (EyeRhythm/ or .venv/)."
    echo "Run setup first:  ./for_linux/setup.sh"
    exit 1
fi

# A leftover process holds the webcam and the default port. Anchored so it
# only matches the app, not a shell or editor with this text in its arguments.
APP_PATTERN='^[^ ]*python[0-9.]* -m app\.main'
if pgrep -f "$APP_PATTERN" >/dev/null 2>&1; then
    echo "Stopping previous EyesRhythm (frees the camera)…"
    pkill -f "$APP_PATTERN" || true
    sleep 1
fi

# Build React UI on demand (requires Node.js once).
if [ ! -f frontend/dist/index.html ]; then
    if ! command -v npm >/dev/null 2>&1; then
        echo "React UI not built and npm is not installed."
        echo "Install Node.js, then:  cd frontend && npm ci && npm run build"
        exit 1
    fi
    echo "Building React UI (first run)…"
    (cd frontend && npm ci && npm run build)
fi

echo "EyesRhythm  ·  $(pwd)"
echo "Keys in UI: B beep  ·  A alert  ·  P practice  ·  D more/less  ·  W settings"
echo

exec python -m app.main --browser "$@"
