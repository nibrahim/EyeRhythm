#!/bin/bash
# Build a standalone EyeRhythm.app / binary (macOS)
# Requires:  pip install pyinstaller  (preferably inside the EyeRhythm venv)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo "  EyeRhythm  ·  build Mac app"
echo "  Project root: $ROOT"
echo "=============================================="
echo

# Prefer the project venv if it exists
if [ -d "$ROOT/EyeRhythm" ]; then
    # shellcheck disable=SC1091
    source "$ROOT/EyeRhythm/bin/activate"
    echo "Using virtual environment: EyeRhythm"
elif [ -d "$ROOT/.venv" ]; then
    # shellcheck disable=SC1091
    source "$ROOT/.venv/bin/activate"
    echo "Using virtual environment: .venv"
fi

echo "Installing PyInstaller if needed..."
python3 -m pip install -q pyinstaller

echo
echo "Building EyeRhythm (this can take a few minutes)..."
python3 -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name EyeRhythm \
  --add-data "models/face_landmarker.task:models" \
  --add-data "assets:assets" \
  --collect-all mediapipe \
  --collect-all cv2 \
  run_app.py

echo
if [ -d "dist/EyeRhythm.app" ]; then
  echo "SUCCESS:  dist/EyeRhythm.app"
elif [ -f "dist/EyeRhythm/EyeRhythm" ]; then
  echo "SUCCESS:  dist/EyeRhythm/EyeRhythm"
else
  echo "Build finished - check the dist/ folder."
fi
