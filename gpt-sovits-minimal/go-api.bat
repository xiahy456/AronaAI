REM Start GPT-SoVITS minimal_inference API with watchdog (auto-restart on crash)
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0watch-api.ps1" %*
if errorlevel 1 pause
