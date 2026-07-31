@echo off
REM ============================================================
REM  Build standalone EyeRhythm.exe (Windows)
REM  Run from project root or from this folder.
REM  Requires: activated venv + pyinstaller
REM ============================================================
setlocal
cd /d "%~dp0..\.."

echo.
echo  ========================================
echo   EyeRhythm  -  Building standalone EXE
echo  ========================================
echo.

where pyinstaller >nul 2>&1
if errorlevel 1 (
    echo  PyInstaller not found. Installing...
    python -m pip install -q pyinstaller
)

echo  Cleaning previous build...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo  Running PyInstaller (this can take several minutes)...
python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --name EyeRhythm ^
  --add-data "models\face_landmarker.task;models" ^
  --add-data "assets;assets" ^
  --collect-all mediapipe ^
  --collect-all cv2 ^
  --hidden-import=PIL._tkinter_finder ^
  run_app.py

echo.
if exist "dist\EyeRhythm\EyeRhythm.exe" (
    echo  SUCCESS
    echo  Executable: dist\EyeRhythm\EyeRhythm.exe
    echo  You can zip the whole "dist\EyeRhythm" folder and distribute it.
) else (
    echo  Build finished with problems - check the output above.
)
echo.
pause
