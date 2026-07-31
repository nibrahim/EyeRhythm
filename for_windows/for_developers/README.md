# EyeRhythm — Windows developer & release tools

This folder contains everything needed to:

1. Run the app from source while developing
2. Build a standalone `EyeRhythm.exe` (no Python required on the end-user machine)
3. Produce a professional Windows installer (`EyeRhythm-Setup.exe`) that installs into Program Files and creates Desktop + Start Menu shortcuts

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

```bat
cd path\to\EyeRhythm
EyeRhythm\Scripts\activate          REM if not already active
pip install pyinstaller
for_windows\for_developers\build_exe.bat
```

Result:

```
dist\EyeRhythm\EyeRhythm.exe
```

You can zip the whole `dist\EyeRhythm` folder and give it to users.  
They only need to unzip and double-click the `.exe` (camera permission still required on first run).

---

## 3. Build a proper Windows installer (recommended for releases)

The fully automatic pipeline is:

```
Source code
    ↓  build_exe.bat          (PyInstaller)
Standalone folder (dist\EyeRhythm)
    ↓  build_installer.bat    (Inno Setup)
EyeRhythm-Setup.exe
```

### Prerequisites (one-time on the maintainer’s Windows machine)

1. Python 3.10–3.12 + the project’s virtual environment
2. PyInstaller (`pip install pyinstaller`)
3. **Inno Setup 6** (free) → https://jrsoftware.org/isinfo.php  
   Install with the default options. The compiler `ISCC.exe` will be on PATH or in  
   `C:\Program Files (x86)\Inno Setup 6\`.

### One-command rebuild

From the project root (with the venv activated):

```bat
for_windows\for_developers\build_installer.bat
```

This script:

1. Builds a fresh `dist\EyeRhythm` with PyInstaller
2. Compiles the Inno Setup script (`EyeRhythm.iss`)
3. Produces `for_windows\for_developers\Output\EyeRhythm-Setup.exe`

You can then upload that single file to GitHub Releases.  
End users download it, run it, and get:

- Installation into `%ProgramFiles%\EyeRhythm`
- Desktop shortcut
- Start Menu entry
- Clean uninstaller via Windows “Apps & features”

---

## Files in this folder

| File | Purpose |
|------|---------|
| `build_exe.bat` | PyInstaller → standalone folder |
| `build_installer.bat` | Full pipeline (exe + Setup.exe) |
| `EyeRhythm.iss` | Inno Setup script (edit version number here) |
| `BUILD_INSTALLER.md` | Detailed explanation of every step |

When you change the application code, just re-run `build_installer.bat`.  
New users who download the updated Setup.exe automatically receive the new features.
