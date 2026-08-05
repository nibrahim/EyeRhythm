@echo off
REM =============================================================================
REM  Build standalone EyeRhythm.exe (Windows) with PyInstaller
REM  Includes the built React UI from frontend\dist
REM =============================================================================
setlocal
cd /d "%~dp0..\.."

echo.
echo  ========================================
echo   EyeRhythm  -  Building standalone EXE
echo  ========================================
echo.

if not exist frontend\dist\index.html (
    echo  Building React UI first...
    pushd frontend
    call npm install
    call npm run build
    popd
    if not exist frontend\dist\index.html (
        echo  ERROR: frontend\dist missing. Install Node.js and rebuild.
        pause
        exit /b 1
    )
)

where pyinstaller >nul 2>&1
if errorlevel 1 (
    echo  Installing PyInstaller...
    python -m pip install -q pyinstaller
)

echo  Cleaning previous build...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo  Running PyInstaller...
python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --name EyeRhythm ^
  --add-data "models\face_landmarker.task;models" ^
  --add-data "assets;assets" ^
  --add-data "frontend\dist;frontend\dist" ^
  --add-data "quotes.json;." ^
  --collect-all mediapipe ^
  --collect-all cv2 ^
  --hidden-import=uvicorn.logging ^
  --hidden-import=uvicorn.loops ^
  --hidden-import=uvicorn.loops.auto ^
  --hidden-import=uvicorn.protocols ^
  --hidden-import=uvicorn.protocols.http ^
  --hidden-import=uvicorn.protocols.http.auto ^
  --hidden-import=uvicorn.protocols.websockets ^
  --hidden-import=uvicorn.protocols.websockets.auto ^
  --hidden-import=uvicorn.lifespan ^
  --hidden-import=uvicorn.lifespan.on ^
  run_app.py

echo.
if exist "dist\EyeRhythm\EyeRhythm.exe" (
    echo  SUCCESS
    echo  Executable: dist\EyeRhythm\EyeRhythm.exe
) else (
    echo  Build finished with problems - check the output above.
)
echo.
pause
