#!/bin/bash
# =============================================================================
# EyesRhythm — build a standalone macOS .app with PyInstaller
# Includes the built React UI from frontend/dist
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo "  EyesRhythm  ·  build Mac app"
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

echo "Building app icon from assets/logo.svg..."
chmod +x "$SCRIPT_DIR/make_app_icon.sh"
"$SCRIPT_DIR/make_app_icon.sh"

echo "Installing PyInstaller if needed..."
python3 -m pip install -q pyinstaller

echo
echo "Building EyesRhythm (this can take a few minutes)..."
# Prefer the checked-in spec so macOS privacy keys (camera) are baked in.
# Fall back to the equivalent CLI if the spec is missing.
if [ -f "$ROOT/EyeRhythm.spec" ]; then
    python3 -m PyInstaller --noconfirm --clean "$ROOT/EyeRhythm.spec"
else
    python3 -m PyInstaller \
      --noconfirm \
      --clean \
      --windowed \
      --osx-bundle-identifier com.eyerhythm.app \
      --name EyesRhythm \
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
fi

stamp_macos_camera_usage() {
    # Double-clicking a .app is not the same as running from Terminal.
    # macOS kills any app that opens the camera without this Info.plist key.
    local app="$1"
    local plist="$app/Contents/Info.plist"
    local buddy="/usr/libexec/PlistBuddy"
    local msg="EyesRhythm uses the camera to count your blinks. Video never leaves this Mac."
    if [ ! -f "$plist" ]; then
        return 0
    fi
    if "$buddy" -c "Print :NSCameraUsageDescription" "$plist" >/dev/null 2>&1; then
        "$buddy" -c "Set :NSCameraUsageDescription $msg" "$plist"
    else
        "$buddy" -c "Add :NSCameraUsageDescription string $msg" "$plist"
    fi
    if "$buddy" -c "Print :CFBundleIdentifier" "$plist" >/dev/null 2>&1; then
        "$buddy" -c "Set :CFBundleIdentifier com.eyerhythm.app" "$plist"
    else
        "$buddy" -c "Add :CFBundleIdentifier string com.eyerhythm.app" "$plist"
    fi
    local icns="$ROOT/assets/EyeRhythm.icns"
    if [ -f "$icns" ]; then
        mkdir -p "$app/Contents/Resources"
        cp "$icns" "$app/Contents/Resources/EyeRhythm.icns"
        cp "$icns" "$app/Contents/Resources/icon-windowed.icns"
        if "$buddy" -c "Print :CFBundleIconFile" "$plist" >/dev/null 2>&1; then
            "$buddy" -c "Set :CFBundleIconFile EyeRhythm" "$plist"
        else
            "$buddy" -c "Add :CFBundleIconFile string EyeRhythm" "$plist"
        fi
    fi
    codesign --force --deep --sign - "$app" >/dev/null
    xattr -cr "$app" 2>/dev/null || true
}

echo
if [ -d "dist/EyesRhythm.app" ]; then
    stamp_macos_camera_usage "$ROOT/dist/EyesRhythm.app"
    echo "SUCCESS:  dist/EyesRhythm.app"
    echo "First open: right-click → Open, then Allow the camera."
elif [ -f "dist/EyesRhythm/EyesRhythm" ]; then
    echo "SUCCESS:  dist/EyesRhythm/EyesRhythm"
else
    echo "Build finished - check the dist/ folder."
fi
