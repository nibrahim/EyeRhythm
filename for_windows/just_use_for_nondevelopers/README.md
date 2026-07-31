# EyeRhythm for Windows — Non-developers

**Goal:** Get the app running with the least possible steps.  
You only need to install Python once. After that everything is automatic.

---

## Quick start (recommended)

### 1. Install Python (one-time, ~2 minutes)

1. Go to: https://www.python.org/downloads/windows/
2. Download the latest **Python 3.11** or **3.12** installer.
3. Run the installer.
4. **Important** — on the first screen tick the box:

   > ☑ **Add python.exe to PATH**

5. Click **Install Now**. Accept the defaults.

### 2. Run EyeRhythm

1. Open the `just_use_for_nondevelopers` folder.
2. Double-click **`EyeRhythm_Launch.bat`**.

The first time it will:

- create a private virtual environment named `EyeRhythm`
- download and install the four open-source libraries
- start the application

Later times it starts in a few seconds.

When Windows asks for camera permission → click **Allow**.

That’s it. No other software is required.

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
| “No module named mediapipe” | Delete the `EyeRhythm` folder that was created next to the bat and run `EyeRhythm_Launch.bat` again. |

---

## About the “full offline installer”

A true Windows Setup.exe (installs into Program Files, creates Start-menu + Desktop shortcuts, and needs **zero** extra installs) is produced by the project maintainers and published on the **GitHub Releases** page.

If you prefer that style of installation, download the latest `EyeRhythm-Setup.exe` from Releases instead of using the files in this folder.

The scripts and documentation that create that Setup.exe live in the sibling folder `for_developers/`.
