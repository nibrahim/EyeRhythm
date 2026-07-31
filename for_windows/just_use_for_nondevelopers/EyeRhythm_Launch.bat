@echo off
title EyeRhythm
color 0A
cd /d "%~dp0"

REM Move to project root (two levels up from this folder)
cd /d "%~dp0..\.."

echo.
echo  ========================================
echo   EyeRhythm  -  BlinkCounter
echo  ========================================
echo.

REM Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python was not found.
    echo.
    echo  Please install Python 3.10, 3.11 or 3.12 from:
    echo  https://www.python.org/downloads/windows/
    echo.
    echo  On the installer first screen tick the box:
    echo     "Add python.exe to PATH"
    echo.
    echo  After installing, close this window and double-click
    echo  EyeRhythm_Launch.bat again.
    echo.
    pause
    exit /b 1
)

if not exist EyeRhythm (
    echo  First run - creating private environment...
    python -m venv EyeRhythm
    if errorlevel 1 (
        echo.
        echo  Failed to create virtual environment.
        echo  Make sure you ticked "Add python.exe to PATH" when installing Python.
        pause
        exit /b 1
    )
    call EyeRhythm\Scripts\activate.bat
    echo  Installing required libraries (this takes 1-2 minutes)...
    python -m pip install --upgrade pip >nul
    pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo  Library installation failed. Check your internet connection
        echo  and try again.
        pause
        exit /b 1
    )
    echo  Setup complete.
    echo.
) else (
    call EyeRhythm\Scripts\activate.bat
)

echo  Starting EyeRhythm...
echo  (Close the window or press Q / Esc to quit)
echo.
python -m app.main %*

if errorlevel 1 (
    echo.
    echo  The application exited with an error.
    echo  See the messages above for details.
    pause
)
