; EagleEye – Windows-Installer (Inno Setup 6)
; Gebaut von .github/workflows/windows-installer.yml:
;   ISCC /DAppVersion=500.0.123 /DStageDir=build\stage /DOutputDir=build\out packaging\windows\EagleEye.iss
; Python ist im Ordner "runtime" enthalten. Auf dem Rechner muss nichts vorinstalliert sein.
; Fälle, Einstellungen und der Vault liegen NICHT im Programmordner, sondern unter
; %LOCALAPPDATA%\EagleEye-500 bzw. %LOCALAPPDATA%\EagleEye-Vault. Deinstallieren lässt sie unberührt.

#ifndef AppVersion
  #define AppVersion "500.0.0"
#endif
#ifndef StageDir
  #define StageDir "..\..\build\stage"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\build\out"
#endif
#define Py "{app}\runtime\python.exe"
#define Start "-I -m eagleeye.bootstrap.windows_start"

[Setup]
AppId={{B9B6A874-CF7A-4F78-8FF6-DF2816087837}
AppName=EagleEye
AppVersion={#AppVersion}
AppVerName=EagleEye {#AppVersion}
AppPublisher=EagleEye (internes Büro-Paket)
DefaultDirName={autopf}\EagleEye
DefaultGroupName=EagleEye
DisableProgramGroupPage=yes
; Standard: für alle Benutzer nach "Programme" (nur Administratoren können dort Programmdateien ändern).
; Ohne Administratorrechte ist eine Installation nur für den eigenen Benutzer möglich.
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#OutputDir}
OutputBaseFilename=EagleEye-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UninstallDisplayName=EagleEye {#AppVersion}
UninstallDisplayIcon={app}\runtime\python.exe
VersionInfoVersion={#AppVersion}
VersionInfoDescription=EagleEye Installationsprogramm

[Languages]
Name: "de"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Verknüpfung „EagleEye Fallakte“ auf dem Desktop"; GroupDescription: "Zusätzlich:"; Flags: unchecked

[InstallDelete]
; Bei einem Update keine Dateien der Vorversion zurücklassen (Daten liegen nicht hier).
Type: filesandordirs; Name: "{app}\runtime"
Type: filesandordirs; Name: "{app}\tools"
Type: filesandordirs; Name: "{app}\docs"

[Files]
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\EagleEye Fallakte"; Filename: "{#Py}"; Parameters: "{#Start} fallakte"; WorkingDir: "{app}"; Comment: "Büro, Aufträge, Web-Belege, Befunde, Bericht"
Name: "{group}\EagleEye Vault (empfohlen)"; Filename: "{#Py}"; Parameters: "{#Start} vault"; WorkingDir: "{app}"; Comment: "Verschlüsselte Recherche-Station, nur dieser Rechner"
Name: "{group}\PersonOSINT"; Filename: "{#Py}"; Parameters: "{#Start} personosint"; WorkingDir: "{app}"; Comment: "Personen- und Firmenrecherche"
Name: "{group}\PersonOSINT als Server"; Filename: "{#Py}"; Parameters: "{#Start} personosint-server"; WorkingDir: "{app}"; Comment: "Wie PersonOSINT, zusätzlich im eigenen Netz erreichbar"
Name: "{group}\Quellen prüfen"; Filename: "{#Py}"; Parameters: "{#Start} quellen"; WorkingDir: "{app}"; Comment: "Welche Datenquellen antworten von diesem Rechner aus"
Name: "{group}\Analyse-Arbeitsplatz"; Filename: "{#Py}"; Parameters: "{#Start} analyse"; WorkingDir: "{app}"; Comment: "Metadaten, Texterkennung, Video, Spuren in Dateien (lokal)"
Name: "{group}\Forschungs-Brücke"; Filename: "{#Py}"; Parameters: "{#Start} forschung"; WorkingDir: "{app}"; Comment: "Öffentliche Sachthemen, mit manueller Freigabe"
Name: "{group}\Werkzeuge\Arbeitsordner wählen"; Filename: "{#Py}"; Parameters: "{#Start} datenordner"; WorkingDir: "{app}"
Name: "{group}\Werkzeuge\Startdiagnose"; Filename: "{#Py}"; Parameters: "{#Start} diagnose"; WorkingDir: "{app}"
Name: "{group}\Anleitung"; Filename: "{win}\notepad.exe"; Parameters: """{app}\docs\LIESMICH.md"""
Name: "{group}\Betriebshandbuch Büro"; Filename: "{win}\notepad.exe"; Parameters: """{app}\docs\BETRIEBSHANDBUCH_BUERO.md"""
Name: "{group}\EagleEye deinstallieren"; Filename: "{uninstallexe}"
Name: "{autodesktop}\EagleEye Fallakte"; Filename: "{#Py}"; Parameters: "{#Start} fallakte"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
; Als ursprünglicher Benutzer starten, nicht mit den Administratorrechten des Installationsprogramms.
Filename: "{#Py}"; Parameters: "{#Start} fallakte"; WorkingDir: "{app}"; Description: "EagleEye Fallakte jetzt starten"; Flags: nowait postinstall skipifsilent runasoriginaluser

[UninstallDelete]
Type: filesandordirs; Name: "{app}\runtime"
Type: filesandordirs; Name: "{app}\tools"
Type: filesandordirs; Name: "{app}\docs"
