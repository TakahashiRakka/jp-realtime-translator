@echo off
setlocal
cd /d "%~dp0"
title JP Realtime Translator

set "PY=%~dp0.venv\Scripts\python.exe"

REM ---------- 0. copy config template if missing ----------
if not exist "%~dp0config.json" if exist "%~dp0config.example.json" (
    echo [0/4] Creating config.json from template ...
    copy /y "%~dp0config.example.json" "%~dp0config.json" >nul
)

REM ---------- 1. create venv if missing ----------
if not exist "%PY%" (
    echo [1/4] Creating virtual environment .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo [ERROR] Failed to create venv: python not found in PATH.
        echo         Install Python 3.10+ and check "Add python.exe to PATH".
        goto :fail
    )
)

REM ---------- 2. verify core deps on every start, repair if missing ----------
"%PY%" -c "import soundcard, numpy" >nul 2>&1
if errorlevel 1 (
    echo [2/4] Dependencies missing, installing requirements.txt ...
    "%PY%" -m pip install --upgrade pip >nul 2>&1
    "%PY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [INFO] Official index failed, retrying with Tsinghua mirror ...
        "%PY%" -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    )
    "%PY%" -c "import soundcard, numpy" >nul 2>&1
    if errorlevel 1 (
        echo.
        echo [ERROR] Dependencies still broken after install. Check your network.
        goto :fail
    )
) else (
    echo [2/4] Dependencies OK.
)

REM ---------- 3. numpy 2.x compat patch for soundcard (idempotent) ----------
echo [3/4] Checking soundcard patch ...
"%PY%" patch_soundcard.py

REM ---------- 4. launch ----------
echo [4/4] Starting main.py ...
"%PY%" main.py
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo ========== Startup failed. Send the error above for help. ==========
pause
exit /b 1
