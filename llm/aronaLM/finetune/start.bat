@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

REM ============================================================
REM  一键启动 Qwen3-1.7B QLoRA 微调（阿洛娜）
REM  用法:
REM    start.bat
REM    start.bat --resume
REM    start.bat --no-gguf --epochs 2
REM ============================================================

cd /d "%~dp0"

echo ========================================
echo   Arona Qwen3-1.7B QLoRA Fine-tune
echo ========================================
echo.

REM 若存在虚拟环境则自动激活
if exist ".venv\Scripts\activate.bat" (
    echo [INFO] 激活虚拟环境 .venv ...
    call ".venv\Scripts\activate.bat"
) else if exist "venv\Scripts\activate.bat" (
    echo [INFO] 激活虚拟环境 venv ...
    call "venv\Scripts\activate.bat"
) else (
    echo [WARN] 未找到 .venv / venv，使用当前 Python 环境
)

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未找到 python，请先安装 Python 3.10+ 并加入 PATH
    pause
    exit /b 1
)

echo [INFO] Python:
python --version
echo.

echo [INFO] 开始训练...
python training\train.py --config config\config.yaml %*

if errorlevel 1 (
    echo.
    echo [ERROR] 训练失败，请查看 logs\train.log
    pause
    exit /b 1
)

echo.
echo [INFO] 训练流程结束。LoRA / GGUF 输出见 outputs\
pause
endlocal
