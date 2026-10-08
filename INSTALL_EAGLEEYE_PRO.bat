@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON=py -3"
) else (
    set "PYTHON=python"
)
%PYTHON% INSTALL_EAGLEEYE_455.py %*
exit /b %errorlevel%
