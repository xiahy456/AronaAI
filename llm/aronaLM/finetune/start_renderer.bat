@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist "D:\Miniconda\Scripts\activate.bat" call "D:\Miniconda\Scripts\activate.bat" arona
python training\train.py --config config\config_renderer.yaml --no-gguf %*
if errorlevel 1 exit /b 1
python export\export_gguf.py --config config\config_renderer.yaml
if errorlevel 1 exit /b 1
echo.
echo V2.3: GGUF is in outputs\AronaLM-Renderer-V2.3-gguf
echo Do NOT copy over V2.2 until human review + eval.
echo   python eval\eval_renderer.py --gguf ..\..\..\models\AronaLM-Renderer-V2.2\AronaLM-Renderer-V2.2.Q4_K_M.gguf --tag v22 --llm-judge
