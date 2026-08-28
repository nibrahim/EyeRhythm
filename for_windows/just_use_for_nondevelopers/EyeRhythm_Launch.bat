@echo off
REM =============================================================================
REM  EyesRhythm — one-click launcher for Windows end users
REM =============================================================================
title EyesRhythm
color 0A
cd /d "%~dp0..\.."

echo.
echo  ========================================
echo   EyesRhythm  -  Blink companion
echo  ========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python was not found.
    echo  Install Python 3.10–3.12 from https://www.python.org/downloads/windows/
    echo  Tick "Add python.exe to PATH" on the first installer screen.
    pause
    exit /b 1
)

if not exist EyeRhythm (
    echo  First run - creating private environment...
    python -m venv EyeRhythm
    if errorlevel 1 (
        echo  Failed to create virtual environment.
        pause
        exit /b 1
    )
    call EyeRhythm\Scripts\activate.bat
    echo  Installing Python libraries...
    python -m pip install --upgrade pip >nul
    pip install -r requirements.txt
    if errorlevel 1 (
        echo  Library installation failed.
        pause
        exit /b 1
    )
) else (
    call EyeRhythm\Scripts\activate.bat
)

if not exist frontend\dist\index.html (
    where npm >nul 2>&1
    if errorlevel 1 (
        echo  React UI is not built and npm was not found.
        echo  Install Node.js 18+ from https://nodejs.org/ then re-run this launcher.
        pause
        exit /b 1
    )
    echo  Building React UI (first run)...
    pushd frontend
    call npm install
    call npm run build
    popd
    if not exist frontend\dist\index.html (
        echo  UI build failed.
        pause
        exit /b 1
    )
)

echo  Starting EyesRhythm...
echo  Keys in UI: B beep  ·  A alert  ·  T on-top  ·  C camera
echo.
python -m app.main %*

if errorlevel 1 (
    echo.
    echo  The application exited with an error.
    pause
)
