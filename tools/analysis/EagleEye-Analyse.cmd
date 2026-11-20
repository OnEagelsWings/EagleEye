@echo off
cd /d "%~dp0"
if exist "D:\EagleEye\" set "EAGLEEYE_ANALYSIS_HOME=D:\EagleEye\Analyseergebnisse"
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" bridge.py
) else (
  python bridge.py
)
