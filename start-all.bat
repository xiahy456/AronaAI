@echo off
setlocal
cd /d "%~dp0"

REM Double-click entry for start-all.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-all.ps1" %*
set ERR=%ERRORLEVEL%
if %ERR% neq 0 (
  echo.
  echo start-all failed with exit code %ERR%.
  pause
)
exit /b %ERR%
