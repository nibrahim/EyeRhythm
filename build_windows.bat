@echo off
REM Build a standalone EyeRhythm.exe (Windows)
REM Requires:  pip install pyinstaller
cd /d "%~dp0"

echo Installing PyInstaller if needed...
python -m pip install -q pyinstaller

echo.
echo Building EyeRhythm.exe  (this can take a few minutes)...
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
  echo SUCCESS:  dist\EyeRhythm\EyeRhythm.exe
  echo You can copy the whole dist\EyeRhythm folder anywhere and run the exe.
) else if exist "dist\EyeRhythm.exe" (
  echo SUCCESS:  dist\EyeRhythm.exe
) else (
  echo Build finished - check the dist\ folder.
)
pause
