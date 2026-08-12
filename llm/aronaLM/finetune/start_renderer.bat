@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist "D:\Miniconda\Scripts\activate.bat" call "D:\Miniconda\Scripts\activate.bat" arona
python training\train.py --config config\config_renderer.yaml --no-gguf %*
if errorlevel 1 exit /b 1
python export\export_gguf.py --config config\config_renderer.yaml
if errorlevel 1 exit /b 1
python export\deploy_renderer_v21.py
echo.
echo Next: eval old vs new, then edit backend config.yaml gguf_path
echo   python eval\eval_renderer.py --gguf ..\..\..\models\AronaLM-Generator-V2.0\AronaLM-Generator-V2.0.Q4_K_M.gguf --tag v20
echo   python eval\eval_renderer.py --gguf ..\..\..\models\AronaLM-Renderer-V2.1\AronaLM-Renderer-V2.1.Q4_K_M.gguf --tag v21
