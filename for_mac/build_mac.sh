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
echo "Tip: if the .app is still huge, remove unused ML extras from the venv:"
echo "  pip uninstall -y jax jaxlib scipy matplotlib"
echo "  (keep opencv-contrib-python — MediaPipe requires it)"
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
    local ver
    ver="$(python3 -c 'from app.version import VERSION; print(VERSION)' 2>/dev/null || true)"
    if [ -n "$ver" ]; then
        if "$buddy" -c "Print :CFBundleShortVersionString" "$plist" >/dev/null 2>&1; then
            "$buddy" -c "Set :CFBundleShortVersionString $ver" "$plist"
        else
            "$buddy" -c "Add :CFBundleShortVersionString string $ver" "$plist"
        fi
        if "$buddy" -c "Print :CFBundleVersion" "$plist" >/dev/null 2>&1; then
            "$buddy" -c "Set :CFBundleVersion $ver" "$plist"
        else
            "$buddy" -c "Add :CFBundleVersion string $ver" "$plist"
        fi
        local info="EyesRhythm $ver"
        if "$buddy" -c "Print :CFBundleGetInfoString" "$plist" >/dev/null 2>&1; then
            "$buddy" -c "Set :CFBundleGetInfoString $info" "$plist"
        else
            "$buddy" -c "Add :CFBundleGetInfoString string $info" "$plist"
        fi
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

slim_macos_bundle() {
    # Drop unused MediaPipe solutions, OpenCV Haar XML, extra matplotlib
    # fonts, and uvicorn extras so the DMG stays under Dodo's 100 MB upload cap.
    local app="$1"
    local res="$app/Contents/Resources"
    local fw="$app/Contents/Frameworks"
    local mp="$res/mediapipe/modules"
    local d
    for d in pose_landmark pose_detection hand_landmark palm_detection \
             iris_landmark selfie_segmentation holistic_landmark objectron \
             face_detection face_landmark; do
        rm -rf "$mp/$d"
    done
    rm -rf "$res/mediapipe/model_maker" "$res/mediapipe/examples" \
           "$res/cv2/data" "$fw/sentencepiece" "$fw/uvloop" \
           "$fw/watchfiles" "$fw/httptools"
    # matplotlib → PIL._imaging needs jpeg/tiff/openjpeg. Keep those
    # dylibs; drop avif/webp extras that are not on the import path.
    local pildy="$fw/PIL/__dot__dylibs"
    if [ -d "$pildy" ]; then
        find "$pildy" -type f ! \( \
            -name 'libjpeg*' -o -name 'libtiff*' -o -name 'libopenjp2*' \
            -o -name 'libz.*' -o -name 'libxcb*' -o -name 'liblzma*' \
            -o -name 'libXau*' \
        \) -delete
    fi
    find "$app" -type d -name '*.dist-info' -exec rm -rf {} + 2>/dev/null || true
    find "$app" -type f -name '*_test.py' -delete
    local fonts="$res/matplotlib/mpl-data/fonts"
    if [ -d "$fonts" ]; then
        find "$fonts" -type f ! -name 'DejaVuSans.ttf' -delete
        find "$fonts" -type d -empty -delete
        rm -rf "$res/matplotlib/mpl-data/sample_data" \
               "$res/matplotlib/mpl-data/images"
    fi
    find "$app" -type f \( -name '*.so' -o -name '*.dylib' \) -print0 \
        | xargs -0 strip -x 2>/dev/null || true
    codesign --force --deep --sign - "$app" >/dev/null
    xattr -cr "$app" 2>/dev/null || true
}

echo
if [ -d "dist/EyesRhythm.app" ]; then
    stamp_macos_camera_usage "$ROOT/dist/EyesRhythm.app"
    slim_macos_bundle "$ROOT/dist/EyesRhythm.app"
    echo "SUCCESS:  dist/EyesRhythm.app"
    echo "First open: right-click → Open, then Allow the camera."
    echo
    echo "Drag-to-Applications installer:"
    echo "  ./for_mac/make_dmg.sh   →  dist/EyesRhythm.dmg"
elif [ -f "dist/EyesRhythm/EyesRhythm" ]; then
    echo "SUCCESS:  dist/EyesRhythm/EyesRhythm"
else
    echo "Build finished - check the dist/ folder."
fi
