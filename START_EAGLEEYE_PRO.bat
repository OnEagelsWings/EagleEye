@echo off
setlocal
cd /d "%~dp0"
title EagleEye Build 480

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

%PYTHON% INSTALL_EAGLEEYE_480.py
if errorlevel 1 goto :failed

set "RUNTIME_PY=.eagleeye-runtime\Scripts\python.exe"
if not exist "%RUNTIME_PY%" goto :failed

"%RUNTIME_PY%" -I -m eagleeye.bootstrap.desktop476 --install-root "%CD%"
if errorlevel 1 goto :failed
exit /b 0

:failed
echo.
echo EagleEye Build 480 did not install or start successfully.
echo Run: %PYTHON% INSTALL_EAGLEEYE_480.py --check
echo.
pause
exit /b 1
