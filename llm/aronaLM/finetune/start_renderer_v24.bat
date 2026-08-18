@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist "D:\Miniconda\Scripts\activate.bat" call "D:\Miniconda\Scripts\activate.bat" arona
python training\train.py --config config\config_renderer_v24.yaml --no-gguf %*
if errorlevel 1 exit /b 1
python export\export_gguf.py --config config\config_renderer_v24.yaml
if errorlevel 1 exit /b 1
echo.
echo V2.4: GGUF is in outputs\AronaLM-Renderer-V2.4-gguf
echo Copy to models\AronaLM-Renderer-V2.4\ after human review + eval.
echo   python eval\eval_renderer.py --cases eval\renderer_cases_v24.json --gguf ..\..\..\models\AronaLM-Renderer-V2.4\AronaLM-Renderer-V2.4.Q4_K_M.gguf --tag v24 --llm-judge
