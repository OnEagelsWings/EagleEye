# EagleEye Build 486 – Windows-Erststart und Bestandsschutz (Entwicklungsstand)

**Keine Kundenfreigabe.** Dieser Build baut auf dem vollständig getesteten Build 485 auf und behält dessen Fallanlage, Recherche, Bildvergleich, Quellenintegrität, Graph, Review und Dossier bei.

## Daten- und Upgrade-Regeln

- **Build 398 nicht deinstallieren.** Keine automatisierte Löschung, Migration oder Bereinigung der vorhandenen Installation vornehmen.
- Vor jedem Upgrade den vorhandenen Arbeitsordner und dessen `data`-Verzeichnis offline sichern. Den bisherigen Arbeitsordner im neuen Launcher ausdrücklich wiederverwenden (`EAGLEEYE_DATENORDNER_WAEHLEN.bat` oder gespeicherte Workspace-Einstellung).
- Build 486 übernimmt den gespeicherten Arbeitsordner und legt bei beschädigter oder fehlender Pfadkonfiguration **nicht stillschweigend** eine neue Fallakte an. Die Konfiguration bleibt unverändert, bis der Anwender den Pfad ausdrücklich korrigiert.
- Die Laufzeitumgebung `.eagleeye-runtime` liegt installationslokal; Falldaten liegen im separat gewählten Arbeitsordner. Die Installation entfernt weder Build 398 noch Fallordner.
- Ein neuer, fallloser Arbeitsbereich führt über `/security/bootstrap` und `/new-case` zur regulären Fallanlage; kein Legacy-Notausgang.
- Der Serverstart vergleicht einen zufälligen, nur lokal gespeicherten Laufzeit-Identifikator mit der Health-Antwort. Ein fremder Dienst auf einem wiederverwendeten Port wird nicht als laufende eigene Sitzung akzeptiert. Ältere laufende Builds werden in der Diagnose als Versionskonflikt angezeigt, nicht automatisch beendet.
- Startdiagnose enthält nur erlaubte Statuswerte, Exception-Klassennamen und Portnummern; keine Sitzungstokens, Passwörter oder vollständigen Fehlerausgaben.

## Installation und Test

1. Vorhandenen Arbeitsordner sichern und die alte Installation unangetastet lassen.
2. Build-486-ZIP in einen **neuen** Ordner entpacken. Nicht über Build 398 entpacken.
3. ZIP-Hash mit der beigefügten `EagleEye_Build_486_LAPTOP.sha256` prüfen.
4. Unter Windows `START_EAGLEEYE_PRO.bat` starten (Python 3.12+); unter Linux `START_EAGLEEYE_PRO.sh`.
5. Den bisherigen Arbeitsordner auswählen bzw. kontrollieren; zuerst einen Testfall, Quellen und Dossier prüfen. Keine Kundenfälle vor vollständiger Freigabe.

## Abnahme

Der PR ist bis zum erfolgreichen Windows-/Linux-Start, installierter Fallwiederherstellung, Chromium-Erststart, UI-Audit und Codex-Review **Draft**. Die Regressionen für reale Build-398-Datenbankversionen sind noch nicht durch eine echte Build-398-Installation belegt; der synthetische Bestandsschutztest beweist nur Pfad- und Dateierhaltung. Keine Produktivfreigabe aus einem grünen CI-Status ableiten.
