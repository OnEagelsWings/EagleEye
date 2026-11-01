# EagleEye 481 – Jetzt einen echten öffentlichen Recherchefall bearbeiten

**Ziel dieses Dokuments:** Ein nicht-technischer Nutzer kann EagleEye mit Doppelklick starten und einen normalen Fall bearbeiten – ohne F12, Konsole oder Testdossiers. Diese Anweisungen gelten **für den Build-481-Release-Kandidaten** und sind keine Sicherheitsfreigabe für vertrauliche oder personenbezogene Ermittlungsaufträge.

## Windows-Start (1 Fenster)

1. Nur das **vollständig geprüfte ZIP** aus den GitHub-Actions-*Artifacts* des aktuellen Build-481-Commits herunterladen. Es enthält `EagleEye_Build_481_LAPTOP.zip`, eine SHA256-Datei, `START_EAGLEEYE_PRO.bat` und `INSTALL_EAGLEEYE_481.py`.
2. Äußeres GitHub-Artifact-ZIP und danach inneres EagleEye-ZIP **vollständig entpacken**. Nicht aus dem ZIP direkt starten; die bisherige funktionierende Installation nicht überschreiben.
3. `START_EAGLEEYE_PRO.bat` doppelt anklicken. Python 3.12+ muss installiert sein. Das schwarze Diagnosefenster geöffnet lassen, während Firefox benutzt wird.
4. Den durch den lokalen Launcher geöffneten Login benutzen; bei einer frischen Instanz einmalig Administrator anlegen. Keine direkte Navigation zu `/security/login` ohne Start-Token.
5. Im Hauptmenü `Neuen Fall anlegen` auswählen. Der Fall benötigt einen verständlichen Titel, Zweck und Rechtsgrundlage. **Keine Qualifikations-/synthetischen Musterfälle als Ausgangspunkt wählen.**

## Ein vollständiger erster Testfall ohne personenbezogene Daten

- **Falltitel:** Öffentliche Dokumentation und Domain-Infrastruktur `example.com`
- **Zweck:** Nachvollziehbare Dokumentation einer frei verfügbaren Beispieldomain und ihrer öffentlichen Quellenbelege.
- **Rechtsgrundlage:** Eigene Recherche mit offen zugänglichen, nicht-personenbezogenen Quellen; Nutzung der jeweiligen Anbieterbedingungen prüfen.

1. **Geführte Recherche** öffnen. Die Stationen erscheinen nachvollziehbar in Reihenfolge.
2. **Öffentliche Quellen erfassen**: optional DNS-A für `example.com`, .com-RDAP für `example.com` oder Crossref-DOI für ein eigenes zulässiges Publikationsbeispiel. Dies sind **die bisher belegten konkreten Live-Adapter**, kein genereller Suchmaschinen-Crawler. Anbieter können vorübergehend ausfallen; Fehler müssen sichtbar bleiben.
3. **Dokumente & Quellenprüfung**: eine rechtmäßig abrufbare, unkritische TXT- oder PDF-Quelle importieren. Datei-/Textanker prüfen und Textextraktion explizit freigeben. Ist OCR erforderlich, kann sie nicht ohne geeignete Textfassung in die Evidence-Kette übernommen werden.
4. **Quelle → Evidence**: das **zuvor freigegebene** Dokument auswählen, Herkunft und Zweck begründen, ausdrücklich bestätigen. Es entsteht nur **ungeprüfte kanonische Evidence**. Sie darf nicht automatisch als bestätigter Claim oder Identität gelten.
5. **Evidence → Claims → Dossier (Original-Workflow)**: echten Zählerstand kontrollieren; anschließend die vorhandenen Expertenansichten `Evidence`, `Claims & Hypothesen`, `Graph & Timeline` und `Dossier` verwenden. Gegenbelege markieren und fehlende zweite Quellen benennen.
6. **Quellenkritischer Arbeitsbericht**: eigene Fundstellen und Unsicherheiten dokumentieren und als Markdown-Arbeitsbericht exportieren. Ein formaler Dossierexport setzt den **separaten, unabhängigen Vier-Augen-Review** voraus.
7. EagleEye beenden und neu starten. Genau denselben Fall erneut öffnen. Originaldokumente, Fundstellen, Evidence, Audit und Bericht müssen unverändert verfügbar sein. Vor echtem späterem Auftrag vollständiges Backup/Restore gesondert abnehmen.

## Was eine erfolgreich nutzbare Version nachweisen muss

- Ein Doppelklick startet die Anwendung, Browser/Anmeldung funktionieren und die Fallliste erscheint.
- Der Nutzer kann ohne Entwicklerwerkzeuge einen Fall erstellen, einen Originalbeleg speichern, prüfen und wiederfinden.
- Der neue Evidence-Link ist *ungeprüft*, eindeutig fallzugeordnet und wiederholt sich nach erneutem Klick nicht.
- Es gibt keinen Zugriff auf fremde Fälle und keine global lesbaren Dokumenttitel/-URLs aus geschützten Fällen.
- Der vorhandene Analyst kann Graph/Dossier öffnen, unabhängig von KI- oder API-Verfügbarkeit.
- Nach einem Neustart bleibt der Fall vollständig gespeichert. Ein Fehler wird offen angezeigt; keine stillen Datenverluste.

## Sichtbare Grenzen

Der aktuelle Stand kann **noch keine frei formulierbare, umfassende Websuche** wie eine externe Suchmaschine bieten und besitzt keinen vollständig nachgewiesenen allgemeinen Crawler. KI-Ausgaben sind prüfpflichtige Entwürfe, keine Tatsachen. Öffentliche Register/APIs erhalten die eingegebenen Suchindikatoren. Für personenbezogene, vertrauliche oder kommerzielle Ermittlungsaufträge ist erst eine unabhängige Sicherheits-/Restore-Freigabe nötig.

## Wenn etwas nicht startet

Das schwarze Starter-/Diagnosefenster **offen lassen** und die letzte Fehlermeldung dokumentieren. Prüfen, dass der Ordner vollständig entpackt ist, Python 3.12+ installiert wurde und kein zweiter EagleEye-Prozess denselben Datenordner blockiert. Den Datenordner nicht löschen und alte Fall-Datenbanken nicht manuell verschieben. Falls das Fenster unmittelbar verschwindet, `START_EAGLEEYE_PRO.bat` in einer offenen Windows-Eingabeaufforderung starten, damit der Fehler sichtbar bleibt.

## Download-/Releaseregel

**Nur** Releases mit grüner CI, Windows-/Linux-Operatorabnahme, Start- und Restore-Test, erfolgreicher fachlicher Sicherheitsreview ohne offene P1/P2 und SHA256-Artefakt werden als geprüft gekennzeichnet. Ein grün getesteter Entwicklungsbranch ist noch nicht automatisch `main` oder eine Produktivfreigabe.
