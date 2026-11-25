# Build 479 – zusammengeführte Arbeitsberichte und Offline-Wiederherstellung

Fortsetzung des UI Audits und von „Windows Startproblem Build 471“. Bestehende Expertenfunktionen aus PR #77 bleiben erhalten.

- Menschliche Prüfentscheidung: eigengeprüft, durch ein zweites Konto geprüft, Überarbeitung nötig oder verworfen. Originalbeleg und Fallrechte werden erneut geprüft. Keine formale Dossierfreigabe.
- Befund-Hashes werden bei Änderungen fortgeschrieben; Prüfhistorie wird verkettet und beim Lesen/Export geprüft. Veraltete Formulare liefern 409.
- Vollständiger Markdown-Arbeitsbericht bis 1000 Befunde / 20 MiB; darüber explizite Ablehnung statt Abschneiden. Fremde Markdown-/HTML-Inhalte und URLs werden als literaler Text exportiert.
- Offline-Sicherung: alle regulären Dateien innerhalb des gewählten Arbeitsordners, einschließlich historischer Root-Artefakte und Entity-Register; ausgenommen Laufzeit-/Virtualenv-Dateien, Git-Metadaten und regenerierte Sitzungsdateien; SQLite-Backup, Datei-Hashes, Budget 2 GiB/100000 Dateien. Laufende Anwendung, Verknüpfungen, Pfadtraversal, doppelte Windows-Pfade und überschreibende Restore-Ziele werden abgewiesen.
- EAGLEEYE_SICHERUNG.bat / EAGLEEYE_WIEDERHERSTELLEN.bat: eigene Sicherung außerhalb des Arbeitsordners; Restore immer neuer Ordner, GUI wählt ihn für den nächsten Start. Alle Fälle/Benutzer werden gesichert; unverschlüsselt, kein fallbezogener Export. Alte Sitzungen werden widerrufen.
- INSTALL_EAGLEEYE_PRO.bat/.sh zeigen nun wie START auf den aktuellen Installer (vorher noch 470).

Validierung erfolgt wegen ausgefallener lokaler Ausführungsumgebung in Windows/Linux-CI: reale Fälle, Rollen/CSRF, Quellenänderung, konkurrierende Prüfung, Historien-Manipulation, 251 Befunde, Unicode, beschädigte Archive, Chromium-Workflow, installierter isolierter Desktop und installierter isolierter Backup/Restore. Keine Produktivfreigabe oder reale Modellgüte daraus abgeleitet.
