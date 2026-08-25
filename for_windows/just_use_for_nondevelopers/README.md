# EyeRhythm for Windows — from source

**Prefer the self-contained app** if you only want to *use* EyeRhythm: unzip **`EyeRhythm-Windows.zip`** and double-click `EyeRhythm.exe`. No Python, no Node. See [`../README.md`](../README.md).

This folder is for running **from the source tree** (contributors, or if you do not have the zip yet). You install Python once; after that a double-click is enough.

---

## Quick start (from source)

### 1. Install Python (one-time, ~2 minutes)

1. Go to: https://www.python.org/downloads/windows/
2. Download **Python 3.11** or **3.12** (not 3.13).
3. Run the installer.
4. **Important** — on the first screen tick the box:

   > ☑ **Add python.exe to PATH**

5. Click **Install Now**. Accept the defaults.

### 2. Run EyeRhythm

1. Open the `just_use_for_nondevelopers` folder.
2. Double-click **`EyeRhythm_Launch.bat`**.

The first time it will:

- create a private virtual environment named `EyeRhythm`
- download and install the Python libraries
- start the application

Later times it starts in a few seconds.

When Windows asks for camera permission → click **Allow**.

That’s it.

---

## Desktop shortcut (optional)

After the first successful launch you can create a desktop shortcut:

1. Right-click `EyeRhythm_Launch.bat`
2. Choose **Send to → Desktop (create shortcut)**
3. Rename the shortcut to **EyeRhythm** if you like

Or run the helper once:

```
create_desktop_shortcut.bat
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| “python is not recognized” | Re-install Python and **tick “Add python.exe to PATH”**. Close and re-open the folder, then try again. |
| Window opens and closes immediately | Right-click `EyeRhythm_Launch.bat` → **Edit**, or open a Command Prompt in this folder and run the bat so you can read the error. |
| Camera not working | Close Zoom / Teams / browser tabs that use the webcam. Check Windows Settings → Privacy & security → Camera. |
| “No module named mediapipe” | Delete the `EyeRhythm` folder that was created next to the project root and run `EyeRhythm_Launch.bat` again. |

---

## Self-contained zip / installer

A freeze that needs **zero** extra installs is produced by GitHub Actions (**Build Windows app**) or by `for_windows/for_developers/build_exe.bat` on a Windows PC.

- **`EyeRhythm-Windows.zip`** — unzip, run `EyeRhythm.exe`
- **`EyeRhythm-Setup.exe`** — per-user installer (Start Menu + optional Desktop shortcut)

Share those files, not this folder, with people who should not install Python.
