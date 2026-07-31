# EyeRhythm on Windows

Everything Windows-related lives in this folder.

```
for_windows/
├── just_use_for_nondevelopers/   ← end users start here
│   ├── README.md
│   ├── EyeRhythm_Launch.bat      ← one-click launcher
│   └── create_desktop_shortcut.bat
│
└── for_developers/               ← maintainers & contributors
    ├── README.md
    ├── build_exe.bat             ← build standalone .exe
    ├── build_installer.bat       ← build full Setup.exe
    ├── EyeRhythm.iss             ← Inno Setup script
    └── BUILD_INSTALLER.md        ← how to release new versions
```

---

## For people who just want to use the app

Go to **`just_use_for_nondevelopers/`** and follow its README.  
You only need to install Python once; after that a double-click is enough.

A classic Windows installer (`EyeRhythm-Setup.exe`) that needs **zero** extra software is published on the project’s GitHub Releases page. Prefer that if it is available for the version you want.

---

## For developers and release managers

Go to **`for_developers/`**.

- Run the app from source while coding.
- Rebuild a standalone executable with one command.
- Produce a professional installer (Program Files + Desktop shortcut + uninstaller) with one command whenever the code changes.

See `for_developers/BUILD_INSTALLER.md` for the complete release checklist.
