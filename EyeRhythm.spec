# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller recipe for the EyesRhythm desktop app
================================================

This file is *not* run by users. Developers run it via::

    pyinstaller EyeRhythm.spec

It tells PyInstaller: start at ``run_app.py``, bundle the face model, the
built React dashboard, icons, quotes, and the heavy native libraries
(MediaPipe + OpenCV), then wrap everything as a macOS ``.app`` or a
Windows folder/exe.

Nothing here changes how blinks are counted — it only packages the same
code you already run from source.
"""
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

# Dock / taskbar icon: .icns on Mac, .ico on Windows.
_ICON = Path("assets") / ("EyeRhythm.icns" if sys.platform == "darwin" else "EyeRhythm.ico")
ICON = str(_ICON) if _ICON.is_file() else None


def _collect(package: str) -> None:
    """Pull data files, native libs, and hidden imports for a package."""
    tmp_ret = collect_all(package)
    datas.extend(tmp_ret[0])
    binaries.extend(tmp_ret[1])
    hiddenimports.extend(tmp_ret[2])


# Extra files copied next to the frozen binary (not discovered from imports).
datas = [
    ('models/face_landmarker.task', 'models'),
    ('assets', 'assets'),
    ('frontend/dist', 'frontend/dist'),
    ('quotes.json', '.'),
]
binaries = []
# Uvicorn loads some modules by name at runtime — list them so they are not
# stripped from the freeze.
hiddenimports = [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.loops.asyncio',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.protocols.websockets.websockets_impl',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'h11',
    'websockets',
    'anyio',
    'anyio._backends._asyncio',
    'starlette',
    'sniffio',
]
# MediaPipe and OpenCV ship many .so/.dll files; collect_all grabs them all.
_collect('mediapipe')
_collect('cv2')

# Windows desktop window is Edge WebView2 via pywebview. Those backends are
# imported by name at runtime, so a freeze that only sees `import webview`
# will miss them (and pythonnet). Skip on macOS — they are not installed.
if sys.platform == "win32":
    _collect('webview')
    _collect('pythonnet')
    _collect('clr_loader')
    hiddenimports += [
        'webview.platforms.edgechromium',
        'webview.platforms.winforms',
        'pythonnet',
        'clr',
        'clr_loader',
        'clr_loader.netfx',
        'clr_loader.coreclr',
        'bottle',
        'proxy_tools',
    ]


# Analysis = “what to include”. Entry script is the crash-logging wrapper.
a = Analysis(
    ['run_app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[
        str(Path("for_windows") / "rthook_unblock_dlls.py"),
    ],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# The actual executable (no console window — this is a desktop app).
# UPX is off: compressing OpenCV / MediaPipe DLLs is a known crash source.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='EyesRhythm',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
)
# Fold the exe + libraries + data files into one folder (Windows) /
# one .app bundle (macOS).
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='EyesRhythm',
)
# macOS-only wrapper: Dock name, icon, and the camera-permission sentence.
# BUNDLE is not valid on Windows; the COLLECT folder *is* the Windows app.
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name='EyesRhythm.app',
        icon=ICON,
        bundle_identifier='com.eyerhythm.app',
        info_plist={
            'CFBundleDisplayName': 'EyesRhythm',
            'CFBundleName': 'EyesRhythm',
            'CFBundleShortVersionString': '1.0.0',
            'NSHighResolutionCapable': True,
            # Required: without this, macOS SIGABRTs the app on the first
            # OpenCV camera open (Retry / Ignore / Report crash dialog).
            'NSCameraUsageDescription': (
                'EyesRhythm uses the camera to count your blinks. '
                'Video never leaves this Mac.'
            ),
        },
    )
