@echo off
REM ============================================================
REM  Full Windows release pipeline
REM  1. Build standalone EXE with PyInstaller
REM  2. Compile Inno Setup script → EyesRhythm-Setup.exe
REM
REM  Prerequisites (one-time):
REM    - Python venv activated
REM    - pyinstaller installed
REM    - Inno Setup 6 installed
REM      https://jrsoftware.org/isinfo.php
REM ============================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0..\.."

echo.
echo  ========================================
echo   EyesRhythm  -  Full Installer Build
echo  ========================================
echo.

REM ---------- Step 1: PyInstaller ----------
echo  [1/2] Building standalone executable...
set "EYERHYTHM_NOPAUSE=1"
call "%~dp0build_exe.bat" --no-pause
if not exist "dist\EyesRhythm\EyesRhythm.exe" (
    echo.
    echo  ERROR: PyInstaller did not produce dist\EyesRhythm\EyesRhythm.exe
    echo  Fix the errors above and try again.
    if not defined GITHUB_ACTIONS pause
    exit /b 1
)

REM ---------- Step 2: Inno Setup ----------
echo.
echo  [2/2] Compiling Windows installer with Inno Setup...

set "ISCC="
where iscc >nul 2>&1
if not errorlevel 1 (
    set "ISCC=iscc"
) else if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
)

if "%ISCC%"=="" (
    echo.
    echo  ERROR: Inno Setup compiler (ISCC.exe) not found.
    echo.
    echo  Install Inno Setup 6 from:
    echo  https://jrsoftware.org/isinfo.php
    echo.
    echo  After installation, re-run this script.
    echo  (You already have a working standalone folder in dist\EyesRhythm)
    if not defined GITHUB_ACTIONS pause
    exit /b 1
)

echo  Using: %ISCC%
"%ISCC%" "%~dp0EyeRhythm.iss"
if errorlevel 1 (
    echo.
    echo  Inno Setup compilation failed.
    if not defined GITHUB_ACTIONS pause
    exit /b 1
)

echo.
echo  ========================================
echo   SUCCESS
echo  ========================================
echo.
echo  Installer created:
echo    for_windows\for_developers\Output\EyesRhythm-Setup.exe
echo.
echo  Share either:
echo    dist\EyesRhythm\                 ^(zip this folder^)
echo    for_windows\for_developers\Output\EyesRhythm-Setup.exe
echo.
if not defined GITHUB_ACTIONS pause
exit /b 0
