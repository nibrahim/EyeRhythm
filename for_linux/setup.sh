#!/bin/bash
# =============================================================================
# EyesRhythm — one-time setup for Linux
# =============================================================================
#
# 1. Creates virtualenv EyeRhythm/
# 2. Installs Python deps from requirements.txt
# 3. Builds the React UI (frontend/) when Node.js is available
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo "  EyesRhythm  ·  Linux setup"
echo "  Project root: $ROOT"
echo "=============================================="
echo

# requirements.txt pins numpy<2, which has no wheels for Python 3.13+.
PYTHON=""
for candidate in python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
        minor=$("$candidate" -c 'import sys; print(sys.version_info.minor if sys.version_info.major == 3 else 0)' 2>/dev/null || echo 0)
        if [ "$minor" -ge 10 ] && [ "$minor" -le 12 ]; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [ -d EyeRhythm ]; then
    echo "Virtual environment 'EyeRhythm' already exists."
elif [ -n "$PYTHON" ]; then
    echo "Creating virtual environment 'EyeRhythm' with $($PYTHON --version)..."
    "$PYTHON" -m venv EyeRhythm
elif command -v uv >/dev/null 2>&1; then
    echo "Creating virtual environment 'EyeRhythm' with uv..."
    uv venv --seed --python 3.12 EyeRhythm
else
    echo "ERROR: Python 3.10, 3.11 or 3.12 not found."
    echo "Install one with your package manager, or install uv and run this again."
    exit 1
fi

echo "Installing Python dependencies..."
EyeRhythm/bin/python -m pip install --upgrade pip
EyeRhythm/bin/python -m pip install -r requirements.txt

if command -v npm >/dev/null 2>&1; then
    echo
    echo "Building React UI..."
    (cd frontend && npm ci && npm run build)
else
    echo
    echo "NOTE: npm not found — skipped React build."
    echo "Install Node.js 18+, then:  cd frontend && npm ci && npm run build"
fi

if [ -z "${WAYLAND_DISPLAY:-}" ] && ! ldconfig -p 2>/dev/null | grep -q libxcb-cursor; then
    echo
    echo "NOTE: libxcb-cursor is missing, so the window cannot open on X11 and the"
    echo "app will use your browser instead. On Debian or Ubuntu:"
    echo "  sudo apt install libxcb-cursor0"
fi

echo
echo "=============================================="
echo "  Setup complete."
echo "  Run:  ./for_linux/run.sh"
echo "=============================================="
