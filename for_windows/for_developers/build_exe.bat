@echo off
REM =============================================================================
REM  Build standalone EyeRhythm.exe (Windows) with PyInstaller
REM  Uses the same EyeRhythm.spec as the Mac build.
REM  Includes the built React UI from frontend\dist
REM =============================================================================
setlocal
if /i "%~1"=="--no-pause" set EYERHYTHM_NOPAUSE=1
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
        if not defined EYERHYTHM_NOPAUSE if not defined GITHUB_ACTIONS pause
        exit /b 1
    )
)

if not exist EyeRhythm.spec (
    echo  ERROR: EyeRhythm.spec not found in the project root.
    if not defined EYERHYTHM_NOPAUSE if not defined GITHUB_ACTIONS pause
    exit /b 1
)

python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo  Installing PyInstaller...
    python -m pip install -q pyinstaller
)

echo  Cleaning previous Windows freeze...
if exist build\EyeRhythm rmdir /s /q build\EyeRhythm
if exist dist\EyeRhythm rmdir /s /q dist\EyeRhythm

echo  Running PyInstaller (EyeRhythm.spec)...
python -m PyInstaller --noconfirm --clean EyeRhythm.spec
if errorlevel 1 (
    echo  PyInstaller failed.
    if not defined EYERHYTHM_NOPAUSE if not defined GITHUB_ACTIONS pause
    exit /b 1
)

echo.
if exist "dist\EyeRhythm\EyeRhythm.exe" (
    echo  SUCCESS
    echo  Executable: dist\EyeRhythm\EyeRhythm.exe
    echo  Zip that folder to share - no Python required on the other PC.
) else (
    echo  Build finished with problems - dist\EyeRhythm\EyeRhythm.exe is missing.
    if not defined EYERHYTHM_NOPAUSE if not defined GITHUB_ACTIONS pause
    exit /b 1
)
echo.
if not defined EYERHYTHM_NOPAUSE if not defined GITHUB_ACTIONS pause
exit /b 0
