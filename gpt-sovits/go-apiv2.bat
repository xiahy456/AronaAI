REM Start GPT-SoVITS API with UTF-8 console/stdio (Windows)
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
runtime\python.exe -X utf8 -I api_v2.py
pause
