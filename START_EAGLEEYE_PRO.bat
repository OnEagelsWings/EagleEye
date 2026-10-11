@echo off
setlocal
cd /d "%~dp0"
title EagleEye Build 455

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

%PYTHON% INSTALL_EAGLEEYE_455.py
if errorlevel 1 goto :failed

set "RUNTIME_PY=.eagleeye-runtime\Scripts\python.exe"
if not exist "%RUNTIME_PY%" goto :failed

set "EAGLEEYE_WORKSPACE_ROOT=%CD%"
"%RUNTIME_PY%" -I -c "import os; from eagleeye.interfaces.web.server import serve_workspace; raise SystemExit(serve_workspace(base_dir=os.environ['EAGLEEYE_WORKSPACE_ROOT']))"
if errorlevel 1 goto :failed
exit /b 0

:failed
echo.
echo EagleEye Build 455 did not install or start successfully.
echo Run: %PYTHON% INSTALL_EAGLEEYE_455.py --check
echo.
pause
exit /b 1
