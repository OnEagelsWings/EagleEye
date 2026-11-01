# Build 480 – gemeinsamer operativer Prüfpunkt

Führt „EagleEye UI Audit“ und „Windows Startproblem Build 471“ in einer Hauptlinie zusammen. 475-Hotfix und 476–479 liefern reguläre Fälle ohne Konsole, stabilen Arbeitsordner, Windows-Startdiagnose, Quelleninventar, originale Fundstellen, Befunde, nachvollziehbare Prüfung, Arbeitsbericht und Offline-Restore. Die bestehenden Evidence-/Claims-/Graph-/Timeline-/Dossierwerkzeuge aus #77 bleiben erreichbar.

## Abnahme
- Vollständige Windows/Linux-Regression und Phase-18/20-Kette bis **480**; unveränderte historische Exclusion-Liste, keine neuen funktionalen Ausschlüsse.
- Frischer Chromium-Start → Erstkonfiguration → echter Fall → Datei-Upload → Befund → begründete Prüfung → tatsächlicher Markdown-Download; Expertenansichten; schmale Ansicht.
- Installierter isolierter Desktop-Prozess und installierter isolierter Backup/Restore.
- Echter öffentlicher Metadatenabruf: DNS example.com, RDAP example.com, Crossref DOI 10.1038/195899a0. Ausfall heißt FAIL; keine simulierten Antworten als Ersatz.
- Bei erreichbaren Quellen: Originale, Befunde, Hypothesengraph und bestehende Evidence→Claim→Dossier-Exportkette technisch mit zwei Testkonten prüfen. Das sind programmierte Testentscheidungen und **keine unabhängige menschliche Freigabe**.
- Live-Pilot und eigener deterministischer Dossiertest entfernen den alten Arbeitsordner vor dem Wiederöffnen der Wiederherstellung. Originale und exportierte Dateien müssen am neuen Ort denselben Hash haben; Prüfhistorie bleibt gültig.
- Alte absolute Pfade der Build-447-Exportkataloge werden beim Lesen aus dem aktuellen verwalteten Exportordner aufgelöst. Gespeicherte historische Datensätze und Freigaben werden nicht umgeschrieben.
- Aktuelle Statusseite zählt nur die gespeicherten fallbezogenen Befunde und passenden geprüften Originale. Nächster Prüfpunkt: 485.

## Grenzen
Lokale Modellinferenz/-qualität und i5-Zielgerätleistung N/A; synthetische Suchmessung und Policy-Prüfung bleiben separat. Allgemeiner Crawler nicht implementiert; Quellenabdeckung nur drei Metadatenadapter. Hashes sind keine Wahrheitszertifizierung. Restore-Prüfung deckt die genannten tatsächlichen Arbeitsketten und Dateien ab, nicht jede historische Spezialoberfläche. Keine Produktivfreigabe für sensible Live-Aufträge.
