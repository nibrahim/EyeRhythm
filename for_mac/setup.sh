#!/bin/bash
# One-time setup: create the "EyeRhythm" virtual environment and install dependencies.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo "  EyeRhythm  ·  macOS / Linux setup"
echo "  Project root: $ROOT"
echo "=============================================="
echo

# Prefer a 3.10–3.12 interpreter
PYTHON=""
for candidate in python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
        ver=$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)
        if [ -n "$ver" ]; then
            major=${ver%%.*}
            minor=${ver#*.}
            if [ "$major" -eq 3 ] && [ "$minor" -ge 10 ]; then
                PYTHON="$candidate"
                break
            fi
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "ERROR: Python 3.10+ not found."
    echo "Install from https://www.python.org/downloads/ or:  brew install python@3.11"
    exit 1
fi

echo "Using: $($PYTHON --version)"
echo

if [ ! -d EyeRhythm ]; then
    echo "Creating virtual environment 'EyeRhythm'..."
    "$PYTHON" -m venv EyeRhythm
else
    echo "Virtual environment 'EyeRhythm' already exists."
fi

# shellcheck disable=SC1091
source EyeRhythm/bin/activate

echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo
echo "=============================================="
echo "  Setup complete."
echo "  Run the app with:  ./for_mac/run.sh"
echo "  or:                source EyeRhythm/bin/activate && python -m app.main"
echo "=============================================="
