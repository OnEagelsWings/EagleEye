# EagleEye unter Windows installieren

`EagleEye-Setup-<Version>.exe` installiert EagleEye wie ein normales Windows-Programm. **Python muss nicht
installiert sein.** Das Paket bringt eine eigene, offizielle Python-Laufzeit mit (Python Software Foundation,
signiert), dazu alle Bibliotheken in fest geprüften Versionen.

## Installation

1. `EagleEye-Setup-<Version>.exe` ausführen. Standard ist die Installation für alle Benutzer nach
   `C:\Programme\EagleEye`. Dafür fragt Windows nach Administratorrechten. Ohne diese Rechte lässt sich
   EagleEye nur für den eigenen Benutzer installieren.
2. Im Startmenü gibt es danach den Ordner **EagleEye**:

| Eintrag | entspricht im alten Startmenü (`START_HIER.bat`) |
|---|---|
| EagleEye Fallakte | 3 |
| EagleEye Vault (empfohlen) | V |
| PersonOSINT | 1 |
| PersonOSINT als Server | 2 |
| Quellen prüfen (Berichte unter *Dokumente\EagleEye\Quellenprüfung*) | 4 |
| Anleitung, Betriebshandbuch Büro | 5 |
| Forschungs-Brücke | 6 |
| Analyse-Arbeitsplatz | 7 |
| Werkzeuge → Arbeitsordner wählen, Startdiagnose | `EAGLEEYE_DATENORDNER_WAEHLEN.bat`, `EAGLEEYE_START_DIAGNOSE.bat` |

Jeder Eintrag öffnet ein Konsolenfenster. Solange es offen ist, läuft der jeweilige Teil. Schließen beendet ihn.

## Wo liegen die Daten?

Nicht im Programmordner. Fälle, Einstellungen und der Vault liegen im Benutzerprofil:

- Fallakte: `%LOCALAPPDATA%\EagleEye-500` (oder der unter „Arbeitsordner wählen“ gewählte Ordner)
- Vault: `%LOCALAPPDATA%\EagleEye-Vault`
- Forschungs-Brücke: `%LOCALAPPDATA%\EagleEyeResearchBridge`

**Update** heißt: neues Setup darüber installieren. Der Programmordner wird vollständig ersetzt, die Daten
bleiben unberührt. **Deinstallieren** (Startmenü oder Windows-Einstellungen → Apps) entfernt nur das Programm,
nicht die Daten. Wer auch die Daten entfernen will, löscht die drei Ordner oben von Hand, nach einer Sicherung.

Wer bisher die ZIP-Fassung (`START_HIER.bat`) genutzt hat, behält seine Daten: die Fallakte findet ihren
Arbeitsordner über dieselbe Einstellung, der Vault liegt am selben Ort.

## Sicherheit

- Der Programmordner unter `C:\Programme` ist für normale Benutzer schreibgeschützt. Schadsoftware ohne
  Administratorrechte kann den Programmcode dort nicht verändern.
- Die mitgelieferte Laufzeit ist abgeschottet: Sie ignoriert `PYTHONPATH`, `PYTHONHOME`, Registry-Einträge und
  Benutzerverzeichnisse und lädt nur Code aus dem Programmordner.
- Alle Bibliotheken stammen aus `requirements-windows.lock`: feste Versionen, jede mit SHA-256-Prüfsumme, nur
  fertige Pakete (kein Übersetzen von Quellcode beim Bau), mit einer Woche Wartezeit für neue Versionen.
- Der Bau prüft die Windows-Signaturen aller Python-Programmdateien (Python Software Foundation / Microsoft).
  tkinter stammt aus dem signierten Teilpaket `tcltk.msi` von python.org. Die Tcl/Tk-Bibliotheken darin sind auch
  im Original nicht einzeln signiert; ihre Echtheit sichert die Signatur des Pakets.
- `MANIFEST-SHA256.json` im Programmordner listet jede ausgelieferte Datei mit Prüfsumme, dazu Quell-Commit,
  Python-Version und Bibliotheksversionen.

## Signieren mit dem eigenen Büro-Zertifikat

Das Setup aus GitHub ist zunächst **unsigniert**. Für den eigenen Bürobetrieb genügt ein selbst erzeugtes
Zertifikat. Der private Schlüssel bleibt auf **einem** Büro-Rechner und gelangt nie zu GitHub. Die Skripte
liegen in `packaging/windows/signing/`:

1. Einmalig auf dem Rechner, der signiert:
   `Buero-Zertifikat-erstellen.ps1 -Name "<Name des Büros>"`. Den angezeigten Fingerabdruck notieren.
2. Einmalig auf jedem Büro-Rechner (als Administrator):
   `Buero-Zertifikat-vertrauen.ps1 -Zertifikat EagleEye-Buero-Signatur.cer -Fingerabdruck <notierter Wert>`.
   Das ist eine bewusste Vertrauensentscheidung: Dieser Rechner vertraut danach allem, was mit diesem
   Schlüssel signiert ist. Nur die `.cer`-Datei weitergeben, nie den Schlüssel.
3. Bei jeder neuen Version: Setup und `.sha256` aus dem GitHub-Lauf herunterladen, dann
   `Setup-signieren.ps1 -Setup EagleEye-Setup-<Version>.exe`. Das Skript prüft zuerst die Prüfsumme und
   signiert dann mit Zeitstempel.

Das Büro-Zertifikat gilt nur auf den Rechnern, auf denen es eingetragen ist. Für fremde Rechner (Kunden,
Partner) braucht es ein öffentlich anerkanntes Zertifikat, z. B. Microsoft Azure Artifact Signing (für
Organisationen in der EU) oder ein OV-Zertifikat mit Cloud-Schlüssel. Auch dann zeigt Windows SmartScreen
anfangs noch Warnungen, bis genug Vertrauen aufgebaut ist.

## Bauen

GitHub-Lauf **„EagleEye Windows-Installer“** (`.github/workflows/windows-installer.yml`, startet bei Änderungen
an `packaging/windows/` oder von Hand). Er testet die aktuellen Funktionen mit genau den Bibliotheken des Pakets,
baut das Setup, installiert es still auf einem frischen Windows-Rechner, prüft Isolierung, Startmenü, Start,
Neustart und Datenerhalt der Fallakte, den Vault, die Forschungs-Brücke und den Analyse-Arbeitsplatz,
signiert eine Testkopie mit einem Wegwerf-Zertifikat, spielt sie als Update ein und deinstalliert zuletzt.
Ergebnis: Artefakt `EagleEye-Windows-Setup-<Version>` mit Setup, Prüfsumme und Manifest.

Sperrliste erneuern (z. B. monatlich oder bei Sicherheitsmeldungen), Befehl siehe Kopf von
`requirements-windows.in`. Danach läuft der GitHub-Lauf automatisch.
