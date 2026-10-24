# Build 476 – Windows-Start und wiederverwendbarer Arbeitsordner

Die operative Fallanlage aus PR #72 ist integriert: reguläre Fälle werden über
ein sichtbares Formular erstellt und öffnen direkt den aktuellen Arbeitsbereich.
Kein F12 und kein Konsolen-POST sind dafür nötig.

Der Doppelklickstart verwendet einen gespeicherten Arbeitsordner unabhängig vom
neuen ZIP-Ordner. Existiert beim ersten Start eine ältere Datenbank direkt im
aktuellen Programmordner, wird dieser Ordner weiterbenutzt. Es werden keine
bestehenden Fälle automatisch kopiert oder überschrieben. Ein verschwundener
Arbeitsordner führt zu einer erklärbaren Startstörung statt zu einer stillen
neuen leeren Installation.

- `START_EAGLEEYE_PRO.bat`: installieren/prüfen und starten.
- `EAGLEEYE_DATENORDNER_WAEHLEN.bat`: den bisherigen Arbeitsordner über ein Fenster auswählen.
- `EAGLEEYE_START_STANDARD_BROWSER.bat`: mit dem Windows-Standardbrowser öffnen.
- `EAGLEEYE_START_DIAGNOSE.bat`: Diagnose ohne Passwort, Sitzungs- oder Launcher-Token erstellen.

Der Server meldet einen gestarteten Prozess getrennt vom bestandenen Health-Check.
Browserstart wird erst nach Erreichbarkeit des richtigen Builds angefordert.
Die lokale Health-Abfrage nutzt keinen konfigurierten HTTP-Proxy. Eine noch
laufende ältere Version im gleichen Arbeitsordner wird in der Diagnose erkannt.

Windows und Linux prüfen den installierten Prozess mit echter HTTP-Verbindung
und dem vorgesehenen Launcher-Zugang. Chromium prüft zusätzlich Erstkonfiguration,
Anmeldung, echten Fall, Dokumentimport und Reload. Die Tests ersetzen keinen
Doppelklickversuch auf dem konkreten Anwendergerät. Keine Produktivfreigabe.

Der neue Einstieg **Geführte Recherche** übernimmt den Arbeitsablauf aus dem
Windows-Arbeitsstrang: Auftrag → öffentliche Quellen → Originaldokumente →
Beziehungen/Graph → Fallprüfung. Qualifikationsfälle bleiben auch bei einer
leeren Auswahl aus dem operativen Einstieg ausgeschlossen. Das Quelleninventar,
Arbeitsbefunde und der Arbeitsbericht folgen in den nächsten Builds.
