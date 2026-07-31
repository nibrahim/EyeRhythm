# How to rebuild the Windows installer after code changes

This document is for maintainers. Follow these steps whenever you update the application and want to publish a new version for non-technical users.

---

## Why this pipeline?

- **Git repository** stays small (source only).
- **GitHub Releases** hosts the large binary (`EyeRhythm-Setup.exe` ≈ 80–120 MB).
- End users get a classic Windows experience: next-next-finish installer, Program Files, Desktop shortcut, uninstaller.
- Rebuild is fully automatic once the tools are installed on a Windows machine.

---

## One-time setup on the maintainer’s Windows PC

1. Clone the repository.
2. Create and activate the virtual environment:
   ```bat
   python -m venv EyeRhythm
   EyeRhythm\Scripts\activate
   pip install -r requirements.txt
   pip install pyinstaller
   ```
3. Install **Inno Setup 6** (free):  
   https://jrsoftware.org/isinfo.php  
   Use the default installation path so `ISCC.exe` is easy to find.

---

## Every time you want a new release

1. Make your code changes and test them:
   ```bat
   python -m app.main
   ```

2. Bump the version number inside the Inno Setup script:
   ```
   for_windows\for_developers\EyeRhythm.iss
   ```
   Change the line:
   ```iss
   #define MyAppVersion "1.0.0"
   ```
   to the new version (e.g. `"1.1.0"`).

3. From the project root, with the venv activated, run:
   ```bat
   for_windows\for_developers\build_installer.bat
   ```

4. The script will:
   - Clean previous builds
   - Run PyInstaller (creates `dist\EyeRhythm\`)
   - Compile the Inno Setup script
   - Place the finished installer at:
     ```
     for_windows\for_developers\Output\EyeRhythm-Setup.exe
     ```

5. Test the installer on a clean Windows machine (or a VM):
   - Run `EyeRhythm-Setup.exe`
   - Confirm it appears in Start Menu and (if chosen) on Desktop
   - Launch the app and check camera permission + blink counting
   - Uninstall via Windows Settings → Apps and confirm clean removal

6. Upload `EyeRhythm-Setup.exe` to the GitHub repository’s **Releases** page.  
   Tag it with the same version number you put in the `.iss` file.

---

## What the end user experiences

1. Downloads `EyeRhythm-Setup.exe` from Releases.
2. Double-clicks it.
3. Clicks through the wizard (optional desktop icon).
4. App is installed under `C:\Program Files\EyeRhythm`.
5. Starts from Desktop / Start Menu.
6. First launch asks for camera permission → Allow.
7. Can uninstall later from Windows Settings.

No Python, no Command Prompt, no extra downloads.

---

## Portable alternative (no installer)

If you only need a zip that users can extract and run:

```bat
for_windows\for_developers\build_exe.bat
```

Then zip the folder `dist\EyeRhythm` and distribute that.  
Users unzip → double-click `EyeRhythm.exe`.  
This is useful for testing or for users who prefer portable apps.

---

## Troubleshooting the build

| Symptom | Fix |
|---------|-----|
| `pyinstaller` not found | `pip install pyinstaller` inside the activated venv |
| Inno Setup not found | Install from https://jrsoftware.org/isinfo.php and re-run |
| Missing DLLs / mediapipe errors at runtime | Always use `--collect-all mediapipe --collect-all cv2` (already in the bat) |
| Camera fails after install | Normal – Windows asks for permission on first use |
| Large file size | Expected (MediaPipe + OpenCV). Compresses well with LZMA in Inno Setup |

---

## Summary

```
code change
    → edit version in EyeRhythm.iss
    → run build_installer.bat
    → upload Output\EyeRhythm-Setup.exe to GitHub Releases
```

That is the complete, repeatable process for shipping updated Windows builds to non-developer users.
