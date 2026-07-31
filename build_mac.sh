#!/bin/bash
# Build a standalone EyeRhythm.app / binary (macOS)
# Requires:  pip install pyinstaller
cd "$(dirname "$0")"

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
