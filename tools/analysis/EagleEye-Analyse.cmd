@echo off
cd /d "%~dp0"
if exist "D:\EagleEye\" set "EAGLEEYE_ANALYSIS_HOME=D:\EagleEye\Analyseergebnisse"
if exist "native\Library\bin" set "PATH=%~dp0native\Library\bin;%~dp0native\Scripts;%~dp0native;%PATH%"
for /d %%F in ("%~dp0tsk\sleuthkit-*") do if exist "%%F\bin\fls.exe" set "PATH=%%F\bin;%PATH%"
if exist "native\Library\share\tessdata\eng.traineddata" set "TESSDATA_PREFIX=%~dp0native\Library\share\tessdata"
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" bridge.py
) else (
  python bridge.py
)
