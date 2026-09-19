@echo off
setlocal
cd /d "%~dp0"
title EagleEye 15-Minute External Test

where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON=py -3"
) else (
    set "PYTHON=python"
)

echo.
echo EagleEye 15-Minute External Test
echo --------------------------------
echo Running local preflight. No telemetry is sent.
echo.
%PYTHON% tools\external_test_preflight.py
set "PREFLIGHT=%errorlevel%"
echo.
echo Read QUICK_TEST.md, then use the normal EagleEye launcher.
echo Your report is external_test_report.txt.
echo.
if not "%PREFLIGHT%"=="0" echo Preflight found a blocker. Please report it rather than repairing it for us.
pause
exit /b %PREFLIGHT%
