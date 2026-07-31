@echo off
REM EyeRhythm — one-click launch for Windows
REM Creates the virtual environment named "EyeRhythm" on first run, then starts the app.
cd /d "%~dp0"

if not exist EyeRhythm (
    echo Creating virtual environment "EyeRhythm"...
    python -m venv EyeRhythm
    if errorlevel 1 (
        echo.
        echo ERROR: Could not create virtual environment.
        echo Make sure Python 3.10+ is installed and "Add python.exe to PATH" was checked.
        echo Download: https://www.python.org/downloads/
        pause
        exit /b 1
    )
    call EyeRhythm\Scripts\activate
    echo Installing dependencies (first run only)...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERROR: pip install failed. Check your internet connection and try again.
        pause
        exit /b 1
    )
) else (
    call EyeRhythm\Scripts\activate
)

echo.
echo Starting EyeRhythm...
python -m app.main %*
if errorlevel 1 (
    echo.
    echo The app exited with an error. See messages above.
)
pause
