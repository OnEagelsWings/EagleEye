@echo off
setlocal
cd /d "%~dp0"
title EagleEye Build 500

rem Prefer the Python launcher when it can actually select 3.12.
rem A launcher installed without Python 3.12 must not mask a valid python.exe.
set "PYTHON="
where py >nul 2>nul
if not errorlevel 1 (
    py -3.12 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,12) else 1)" >nul 2>nul
    if not errorlevel 1 set "PYTHON=py -3.12"
)
if not defined PYTHON (
    where python >nul 2>nul
    if not errorlevel 1 (
        python -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,12) else 1)" >nul 2>nul
        if not errorlevel 1 set "PYTHON=python"
    )
)
if not defined PYTHON (
    echo.
    echo EagleEye requires Python 3.12.x for this offline Windows release.
    echo Install Python and then run this file again.
    echo.
    pause
    exit /b 1
)

rem The bootstrap stores settings and cases outside the program directory.
rem Do not override EAGLEEYE_SETTINGS_DIR or EAGLEEYE_DATA_DIR here.
rem Default: %%LOCALAPPDATA%%\EagleEye-500\workspace (or user-selected folder).
%PYTHON% INSTALL_EAGLEEYE_500.py
if errorlevel 1 goto :failed

set "RUNTIME_PY=.eagleeye-runtime-500\Scripts\python.exe"
if not exist "%RUNTIME_PY%" goto :failed

"%RUNTIME_PY%" -I -m eagleeye.bootstrap.desktop476 --install-root "%CD%"
if errorlevel 1 goto :failed
exit /b 0

:failed
echo.
echo EagleEye Build 500 did not install or start successfully.
echo Run: %PYTHON% INSTALL_EAGLEEYE_500.py --check
echo.
pause
exit /b 1
