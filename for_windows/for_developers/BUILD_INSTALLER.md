# How to rebuild the Windows app after code changes

This document is for maintainers. Follow these steps whenever you update the application and want a new zip / installer for people who should not install Python.

---

## Why this pipeline?

- **Git repository** stays small (source only).
- Recipients get a freeze: unzip `EyesRhythm-Windows.zip` or run `EyesRhythm-Setup.exe`.
- You cannot produce that freeze on a Mac. Use **GitHub Actions** or a Windows PC.

---

## Path A — GitHub Actions (works from a Mac)

1. Commit and push the code you want inside the Windows app (uncommitted files are **not** included).
2. On GitHub: **Actions → Build Windows app → Run workflow**.
3. When it finishes, download:
   - `EyesRhythm-Windows-zip` → `EyesRhythm-Windows.zip`
   - `EyesRhythm-Windows-setup` → `EyesRhythm-Setup.exe`
4. Send the zip (or the Setup.exe) to the other person.

Tag `v1.0.0` (or any `v*`) to attach both files to a GitHub Release. The repo is private, so you still download and forward the files yourself.

Typical runtime: 10–20 minutes. Python is pinned to **3.11**.

---

## Path B — Windows PC

### One-time setup

1. Clone the repository.
2. Create and activate the virtual environment with **Python 3.11**:
   ```bat
   python -m venv EyeRhythm
   EyeRhythm\Scripts\activate
   pip install -r requirements.txt
   pip install pyinstaller
   ```
3. For the installer only, install **Inno Setup 6**:  
   https://jrsoftware.org/isinfo.php

### Every time you want a new freeze

1. Test from source:
   ```bat
   python -m app.main
   ```

2. If you ship Setup.exe, bump the version in `EyeRhythm.iss`:
   ```iss
   #define MyAppVersion "1.0.0"
   ```

3. From the project root, with the venv activated:
   ```bat
   for_windows\for_developers\build_exe.bat
   ```
   Portable app: `dist\EyesRhythm\` — zip that folder.

   Or the full installer:
   ```bat
   for_windows\for_developers\build_installer.bat
   ```
   Output: `for_windows\for_developers\Output\EyesRhythm-Setup.exe`

4. Test on a Windows machine:
   - Unzip / run Setup
   - Launch, allow camera, confirm blink counting
   - For Setup.exe: uninstall via Windows Settings → Apps

---

## What the end user experiences

1. Receives `EyesRhythm-Windows.zip` (or Setup.exe).
2. Unzips (or clicks through the wizard).
3. Double-clicks `EyesRhythm.exe`.
4. If SmartScreen appears → **More info → Run anyway**.
5. Allows camera permission.
6. Uses the same dashboard as the Mac app.

No Python, no Command Prompt, no extra downloads.

Crash log if it dies on start:

```
%LOCALAPPDATA%\EyesRhythm\crash.log
```

---

## Troubleshooting the build

| Symptom | Fix |
|---------|-----|
| `pyinstaller` not found | `pip install pyinstaller` inside the activated venv |
| Inno Setup not found | Install from https://jrsoftware.org/isinfo.php and re-run |
| Missing DLLs / mediapipe errors at runtime | Use `EyeRhythm.spec` (already has `--collect-all mediapipe` / `cv2`) |
| Blank window / no UI | WebView2 missing — Edge on Windows 10/11 usually provides it; the app falls back to the system browser |
| Camera fails after install | Normal – Windows asks for permission on first use |
| Large file size | Expected (MediaPipe + OpenCV) |

---

## Summary

```
code change
    → push
    → Actions → Build Windows app
    → send EyesRhythm-Windows.zip
```

Or on a Windows PC: `build_exe.bat` → zip `dist\EyesRhythm`.
