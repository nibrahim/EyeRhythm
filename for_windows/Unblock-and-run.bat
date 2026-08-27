@echo off
REM Windows marks downloaded files as blocked; native DLLs then fail to load.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -LiteralPath '%~dp0' -Recurse -ErrorAction SilentlyContinue | Unblock-File"
start "" "%~dp0EyeRhythm.exe"
