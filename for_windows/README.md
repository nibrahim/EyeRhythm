# EyeRhythm on Windows

Two ways to get the app running.

---

## Way 1 — Non-coders (all-in-one, recommended)

You only need **one extra install**: Python itself.

### Step-by-step

1. **Download & install Python 3.10, 3.11 or 3.12**  
   → https://www.python.org/downloads/windows/  

   On the first screen of the installer **check the box**:

   > ☑ **Add python.exe to PATH**

   Then click “Install Now”. Accept the defaults.

2. **Open the EyeRhythm folder** (the one that contains `run_windows.bat`).

3. **Double-click `run_windows.bat`**.

   - The first time it creates a virtual environment named `EyeRhythm`,  
     installs the required libraries, and starts the app.  
   - Subsequent times it just starts the app (takes a few seconds).

4. When Windows asks for **camera permission**, click **Allow**.

That’s everything. No extra tools, no command-line knowledge required.

If the window appears and then immediately closes, re-run the `.bat`  
from a Command Prompt so you can read any error messages:

```
cd path\to\EyeRhythm
run_windows.bat
```

---

## Way 2 — From source (developers)

1. Install Python 3.10–3.12 as above (with “Add to PATH”).

2. Open **Command Prompt** or **PowerShell** in the project root:

```bat
cd path\to\EyeRhythm

python -m venv EyeRhythm
EyeRhythm\Scripts\activate
pip install -r requirements.txt

python -m app.main
```

Or simply double-click `run_windows.bat` (it does the same thing).

### Useful flags

```bat
python -m app.main --camera 1          REM try a different webcam
python -m app.main --skip-checks       REM skip the startup self-check
```

### Build a standalone executable (optional)

If you want a folder you can copy to any Windows PC (no Python needed on the target machine):

```bat
python -m pip install pyinstaller
build_windows.bat
```

After a few minutes you will find:

```
dist\EyeRhythm\EyeRhythm.exe
```

Copy the whole `dist\EyeRhythm` folder anywhere and run the `.exe`.  
The first run may still ask for camera permission.

---

## Keyboard shortcuts (both ways)

| Key | Action |
|-----|--------|
| **Q** / **Esc** | Quit |
| **B** | Beep on every counted blink (ON/OFF) |
| **A** | Low-rate alert (ON/OFF) |
| **T** | Always-on-top (ON/OFF) |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| “python is not recognized” | Re-install Python and **tick “Add python.exe to PATH”**. Restart the terminal. |
| “No module named mediapipe” | Delete the `EyeRhythm` folder and run `run_windows.bat` again so it reinstalls. |
| Black screen / “camera not usable” | Close Zoom, Teams, browsers, other apps that use the webcam. Try `--camera 1`. |
| Camera permission denied | Windows Settings → Privacy & security → Camera → allow the app / desktop apps. |
| Antivirus blocks the .exe | Add an exception for the EyeRhythm folder (false positive common with PyInstaller). |

---

Enjoy healthier screen time!
