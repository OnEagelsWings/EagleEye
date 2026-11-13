@echo off
chcp 65001 >nul
cd /d "%~dp0"
:menu
cls
echo.
echo   EagleEye - Komplettpaket
echo   ========================
echo.
echo    1   PersonOSINT starten        Personensuche, Quellenabfragen, Verbindungen, Dossier  (dieser Rechner)
echo    2   PersonOSINT als Server     wie 1, zusaetzlich fuer andere Rechner im eigenen Netz erreichbar
echo    3   EagleEye-Fallakte starten  Beweissicherung, Pruefablaeufe, Recherche-Plan, Bericht
echo    4   Quellen pruefen            zeigt, welche Datenquellen von diesem Rechner aus antworten
echo    5   Anleitung oeffnen
echo    0   Beenden
echo.
set "WAHL="
set /p WAHL=   Auswahl und Eingabetaste:
if "%WAHL%"=="1" start "PersonOSINT" cmd /k "PersonOSINT\START_PERSONOSINT.bat"
if "%WAHL%"=="2" start "PersonOSINT Server" cmd /k "PersonOSINT\START_PERSONOSINT_SERVER.bat"
if "%WAHL%"=="3" start "EagleEye Fallakte" cmd /k "START_EAGLEEYE_PRO.bat"
if "%WAHL%"=="4" start "Quellen pruefen" cmd /k "PersonOSINT\QUELLEN_PRUEFEN.bat"
if "%WAHL%"=="5" start "" "LIESMICH_KOMPLETTPAKET.md"
if "%WAHL%"=="0" exit /b 0
goto menu
