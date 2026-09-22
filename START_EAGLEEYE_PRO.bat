@echo off
setlocal
cd /d "%~dp0"
title EagleEye Build 430

where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON=py -3"
) else (
    set "PYTHON=python"
)

%PYTHON% -c "import sys; raise SystemExit(0 if sys.version_info >= (3,12) else 1)"
if errorlevel 1 (
    echo.
    echo EagleEye requires Python 3.12 or newer.
    echo Install Python and then run this file again.
    echo.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo First start: creating the local EagleEye Python environment...
    %PYTHON% -m venv .venv
    if errorlevel 1 goto :failed
)

set "VENV_PY=.venv\Scripts\python.exe"
%VENV_PY% -c "import fastapi, uvicorn, sqlalchemy, pydantic" >nul 2>nul
if errorlevel 1 (
    echo.
    echo Installing EagleEye runtime dependencies. This is required only on first setup...
    %VENV_PY% -m pip install -e .
    if errorlevel 1 goto :failed
)

%VENV_PY% EAGLEEYE_PRO_430_0.py
if errorlevel 1 goto :failed
exit /b 0

:failed
echo.
echo EagleEye did not start successfully.
echo Check logs\startup_latest.log if it was created.
echo You can also run: .venv\Scripts\python.exe -m pip install -e .
echo.
pause
exit /b 1
