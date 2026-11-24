@echo off
chcp 65001 >nul
cd /d "%~dp0"
:menu
cls
echo.
echo   EagleEye - Komplettpaket
echo   ========================
echo.
echo    V   EagleEye Vault         EMPFOHLEN: verschluesselt, nur dieser Rechner, Internet nur auf Ihren Befehl
echo.
echo    1   PersonOSINT starten        Personensuche, Quellenabfragen, Verbindungen, Dossier  (dieser Rechner)
echo    2   PersonOSINT als Server     wie 1, zusaetzlich fuer andere Rechner im eigenen Netz erreichbar
echo    3   EagleEye-Fallakte starten  Beweissicherung, Pruefablaeufe, Recherche-Plan, Bericht
echo    4   Quellen pruefen            zeigt, welche Datenquellen von diesem Rechner aus antworten
echo    5   Anleitung oeffnen
echo    6   Forschungs-Bruecke        oeffentliche Sachthemen, mit manueller Freigabe
echo    0   Beenden
echo.
rem CHOICE accepts only the listed keys; do not interpolate untrusted console input into CMD commands.
choice /c V1234560 /n /m "   Auswahl (V, 1-6, 0=Beenden): "
if errorlevel 8 exit /b 0
if errorlevel 7 goto action6
if errorlevel 6 goto action5
if errorlevel 5 goto action4
if errorlevel 4 goto action3
if errorlevel 3 goto action2
if errorlevel 2 goto action1
if errorlevel 1 goto actionV
goto menu
:actionV
start "EagleEye Vault" cmd /k "PersonOSINT\START_VAULT.bat"
goto menu
:action6
start "Research Bridge" cmd /k "tools\research_exchange\START_RESEARCH_BRIDGE_WINDOWS.cmd"
goto menu
:action5
start "" "LIESMICH_KOMPLETTPAKET.md"
goto menu
:action4
start "Quellen pruefen" cmd /k "QUELLEN_PRUEFEN.bat"
goto menu
:action3
start "EagleEye Fallakte" cmd /k "START_EAGLEEYE_PRO.bat"
goto menu
:action2
start "PersonOSINT Server" cmd /k "PersonOSINT\START_PERSONOSINT_SERVER.bat"
goto menu
:action1
start "PersonOSINT" cmd /k "PersonOSINT\START_PERSONOSINT.bat"
goto menu
