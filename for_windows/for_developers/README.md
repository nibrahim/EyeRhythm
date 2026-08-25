# EyeRhythm — Windows developer & release tools

This folder contains everything needed to:

1. Run the app from source while developing
2. Build a standalone `EyeRhythm.exe` (no Python required on the end-user machine)
3. Produce a Windows installer (`EyeRhythm-Setup.exe`) that installs per-user and creates Start Menu + optional Desktop shortcuts

You **cannot** freeze a Windows exe on a Mac. Use GitHub Actions (see below) or a Windows PC with **Python 3.11**.

---

## 1. Run from source (development)

```bat
cd path\to\EyeRhythm          REM project root
python -m venv EyeRhythm
EyeRhythm\Scripts\activate
pip install -r requirements.txt
python -m app.main
```

Or simply use the non-developer launcher (it works for developers too).

Useful flags:

```bat
python -m app.main --camera 1
python -m app.main --skip-checks
```

---

## 2. Build the standalone executable

From a Windows PC, at the project root, with the venv activated:

```bat
pip install pyinstaller
for_windows\for_developers\build_exe.bat
```

This uses the same `EyeRhythm.spec` as the Mac `.app` build (model, React UI, MediaPipe, OpenCV, pywebview).

Result:

```
dist\EyeRhythm\EyeRhythm.exe
```

Zip the whole `dist\EyeRhythm` folder and give it to users. They unzip and double-click the `.exe` (camera permission still required on first run). SmartScreen may warn because the binary is unsigned → **More info → Run anyway**.

---

## 3. GitHub Actions (from a Mac)

The workflow **Build Windows app** (`.github/workflows/build-windows.yml`):

1. Builds the React UI
2. Freezes `dist\EyeRhythm` with PyInstaller
3. Uploads `EyeRhythm-Windows.zip`
4. Builds `EyeRhythm-Setup.exe` with Inno Setup

Run it: GitHub → **Actions → Build Windows app → Run workflow**.  
A tag `v1.0.0` also attaches both files to the GitHub Release.

---

## 4. Build a Windows installer (optional)

```
Source code
    ↓  build_exe.bat          (PyInstaller)
Standalone folder (dist\EyeRhythm)
    ↓  build_installer.bat    (Inno Setup)
EyeRhythm-Setup.exe
```

### Prerequisites (one-time on a Windows machine)

1. Python 3.11 + the project’s virtual environment
2. PyInstaller (`pip install pyinstaller`)
3. **Inno Setup 6** (free) → https://jrsoftware.org/isinfo.php  
   Default install path is fine (`ISCC.exe` under `C:\Program Files (x86)\Inno Setup 6\`).

### One-command rebuild

From the project root (with the venv activated):

```bat
for_windows\for_developers\build_installer.bat
```

This script:

1. Builds a fresh `dist\EyeRhythm` with PyInstaller
2. Compiles `EyeRhythm.iss`
3. Produces `for_windows\for_developers\Output\EyeRhythm-Setup.exe`

End users who run Setup.exe get:

- Installation into `%LOCALAPPDATA%\EyeRhythm` (no admin)
- Start Menu entry
- Optional Desktop shortcut
- Uninstaller via Windows “Apps & features”

---

## Files in this folder

| File | Purpose |
|------|---------|
| `build_exe.bat` | PyInstaller via `EyeRhythm.spec` → `dist\EyeRhythm` |
| `build_installer.bat` | Full pipeline (exe + Setup.exe) |
| `EyeRhythm.iss` | Inno Setup script (edit version number here) |
| `BUILD_INSTALLER.md` | Release checklist |

When you change the application code, re-run Actions or `build_installer.bat`.
