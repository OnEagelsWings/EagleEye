# Build 481 – Integrations- und Windows-Praxisstand

- Konsolidiert die Build-478-Expertenzentrale mit der ursprünglichen Evidence→Claim→Dossier-Kette aus PR #80.
- `/workbench/bridge481`: geprüfte Build-458-Dokumente explizit als neue **unreviewed** Build-447-Evidence registrieren. Kein Netzabruf; originale SHA-256-Bytes, Anker-IDs, manueller Herkunftsvermerk und auditierte Quellenregistrierung bleiben erhalten.
- Fallautorisiert, CSRF/Origin-gesteuert, begrenzte Formulare und keine automatische Annahme von Claims.
- Hergestellte Dossier-Originaldateien auf Windows und Linux mit genauer Pfaddiagnose und Hashprüfung testen. Fehlende Dateien bleiben HARTE Fehler.
- CLI-/Windows-Batch-/Python-Runtime und Startdiagnostik nutzen dasselbe Release-481-Paket.
- Keine garantierte Live-Abdeckung jenseits Google DNS, Verisign .com RDAP und Crossref; kein allgemeiner Crawler und keine Freigabe vertraulicher Aufträge.
