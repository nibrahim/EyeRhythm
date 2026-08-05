#!/bin/bash
# =============================================================================
# EyeRhythm — build a standalone macOS .app with PyInstaller
# Includes the built React UI from frontend/dist
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo "  EyeRhythm  ·  build Mac app"
echo "  Project root: $ROOT"
echo "=============================================="
echo

if [ -d "$ROOT/EyeRhythm" ]; then
    # shellcheck disable=SC1091
    source "$ROOT/EyeRhythm/bin/activate"
    echo "Using virtual environment: EyeRhythm"
elif [ -d "$ROOT/.venv" ]; then
    # shellcheck disable=SC1091
    source "$ROOT/.venv/bin/activate"
    echo "Using virtual environment: .venv"
fi

if [ ! -f frontend/dist/index.html ]; then
    if ! command -v npm >/dev/null 2>&1; then
        echo "ERROR: frontend/dist missing and npm not found."
        exit 1
    fi
    echo "Building React UI..."
    (cd frontend && npm install && npm run build)
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
  --add-data "frontend/dist:frontend/dist" \
  --add-data "quotes.json:." \
  --collect-all mediapipe \
  --collect-all cv2 \
  --hidden-import=uvicorn.logging \
  --hidden-import=uvicorn.loops \
  --hidden-import=uvicorn.loops.auto \
  --hidden-import=uvicorn.protocols \
  --hidden-import=uvicorn.protocols.http \
  --hidden-import=uvicorn.protocols.http.auto \
  --hidden-import=uvicorn.protocols.websockets \
  --hidden-import=uvicorn.protocols.websockets.auto \
  --hidden-import=uvicorn.lifespan \
  --hidden-import=uvicorn.lifespan.on \
  run_app.py

echo
if [ -d "dist/EyeRhythm.app" ]; then
  echo "SUCCESS:  dist/EyeRhythm.app"
elif [ -f "dist/EyeRhythm/EyeRhythm" ]; then
  echo "SUCCESS:  dist/EyeRhythm/EyeRhythm"
else
  echo "Build finished - check the dist/ folder."
fi
