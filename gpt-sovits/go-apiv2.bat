REM Start GPT-SoVITS API with watchdog (auto-restart on stall/crash)
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0watch-apiv2.ps1" %*
if errorlevel 1 pause
