@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo  EagleEye - Quellen pruefen (Internetverbindung noetig)
echo  Jede Quelle wird einmal mit einer unkritischen Testabfrage aufgerufen. Es wird nichts gespeichert.
echo.
set "FALLAKTE_PY=.eagleeye-runtime-500\Scripts\python.exe"
if exist "%FALLAKTE_PY%" (
    echo  --- Quellen der EagleEye-Fallakte ---
    "%FALLAKTE_PY%" tools\quellen_pruefen_fallakte.py --out Quellen-Pruefbericht-Fallakte.md
) else (
    echo  Fallakte noch nicht eingerichtet - bitte einmal "EagleEye-Fallakte starten" ^(Menue 3^) ausfuehren.
)
echo.
if exist "PersonOSINT\.venv\Scripts\python.exe" (
    echo  --- Quellen von PersonOSINT ---
    pushd PersonOSINT
    .venv\Scripts\python -m personosint check-sources --out ..\Quellen-Pruefbericht-PersonOSINT.md
    popd
) else (
    echo  PersonOSINT noch nicht eingerichtet - bitte einmal "PersonOSINT starten" ^(Menue 1^) ausfuehren.
)
echo.
echo  Die Berichte liegen in diesem Ordner: Quellen-Pruefbericht-Fallakte.md und Quellen-Pruefbericht-PersonOSINT.md
pause
