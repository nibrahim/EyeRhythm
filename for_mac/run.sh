#!/bin/bash
# =============================================================================
# EyesRhythm — launch the app from source (macOS / Linux)
# =============================================================================
#
# 1. Activates the EyeRhythm/ virtualenv
# 2. Builds the React UI if frontend/dist is missing
# 3. Starts:  python -m app.main
#
# Examples:
#   ./for_mac/run.sh
#   ./for_mac/run.sh --camera 1
#   ./for_mac/run.sh --browser
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
    echo "Run setup first:  ./for_mac/setup.sh"
    exit 1
fi

# Build React UI on demand (requires Node.js once).
if [ ! -f frontend/dist/index.html ]; then
    if ! command -v npm >/dev/null 2>&1; then
        echo "React UI not built and npm is not installed."
        echo "Install Node.js, then:  cd frontend && npm install && npm run build"
        exit 1
    fi
    echo "Building React UI (first run)…"
    (cd frontend && npm install && npm run build)
fi

echo "EyesRhythm  ·  $(pwd)"
echo "Keys in UI: B beep  ·  A alert  ·  T on-top  ·  C camera panel"
echo

exec python -m app.main "$@"
