@echo off
REM Creates a Desktop shortcut that points to EyeRhythm_Launch.bat
cd /d "%~dp0"

set "TARGET=%~dp0EyeRhythm_Launch.bat"
set "SHORTCUT=%USERPROFILE%\Desktop\EyesRhythm.lnk"

echo Creating desktop shortcut...
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $s = $ws.CreateShortcut('%SHORTCUT%'); ^
   $s.TargetPath = '%TARGET%'; ^
   $s.WorkingDirectory = '%~dp0'; ^
   $s.Description = 'EyesRhythm - Blink companion'; ^
   $s.Save()"

if exist "%SHORTCUT%" (
    echo.
    echo  Desktop shortcut created successfully:
    echo  %SHORTCUT%
) else (
    echo.
    echo  Could not create the shortcut automatically.
    echo  You can still right-click EyeRhythm_Launch.bat
    echo  and choose "Send to → Desktop (create shortcut)".
)
echo.
pause
