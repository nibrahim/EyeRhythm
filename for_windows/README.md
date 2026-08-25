# EyeRhythm on Windows

The shareable Windows app is a freeze of the same code as the Mac `.app`. Recipients do **not** install Python or Node.

```
for_windows/
├── README.md                         ← this file
├── just_use_for_nondevelopers/       ← run from source (needs Python)
│   ├── README.md
│   ├── EyeRhythm_Launch.bat
│   └── create_desktop_shortcut.bat
│
└── for_developers/                   ← rebuild the freeze / installer
    ├── README.md
    ├── build_exe.bat                 ← PyInstaller → dist\EyeRhythm\
    ├── build_installer.bat           ← freeze + Inno Setup
    ├── EyeRhythm.iss
    └── BUILD_INSTALLER.md
```

---

## Share this with someone (no extra software)

1. Produce **`EyeRhythm-Windows.zip`** (see below).
2. Send that zip (email, Drive, USB).
3. They unzip it and double-click **`EyeRhythm.exe`**.

```
EyeRhythm\
  EyeRhythm.exe      ← this
  _internal\         ← libraries, model, dashboard (leave this next to the exe)
```

First launch:

* Windows may show SmartScreen (“Windows protected your PC”) because the exe is unsigned → **More info → Run anyway**.
* Allow **camera** access when Windows asks (Settings → Privacy & security → Camera).

If the window fails to open, the crash log is:

```
%LOCALAPPDATA%\EyeRhythm\crash.log
```

`EyeRhythm-Setup.exe` is the same freeze as a next-next-finish installer (per-user, no admin). Optional.

### How you produce the zip

You cannot freeze a Windows `.exe` on a Mac (MediaPipe / OpenCV are native). Use either:

**GitHub Actions (from this Mac)**

1. Push the commit you want to ship.
2. GitHub → **Actions → Build Windows app → Run workflow**.
3. Download the `EyeRhythm-Windows-zip` artifact.

Pushing a tag `v1.0.0` also attaches the zip (and Setup.exe) to that GitHub Release.

**A Windows PC**

```bat
for_windows\for_developers\build_exe.bat
```

Then zip the folder `dist\EyeRhythm`.

---

## Run from source (developers)

Go to **`just_use_for_nondevelopers/`** and follow its README. You need Python once.

---

## Rebuild after code changes

Go to **`for_developers/`**. Use GitHub Actions or a Windows machine with Python 3.11.

See `for_developers/BUILD_INSTALLER.md` for the release checklist.
