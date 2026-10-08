@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "MODE=%~1"
if "%MODE%"=="" set "MODE=all"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%run_vitis_hls.ps1" -Mode "%MODE%"
exit /b %ERRORLEVEL%
