# EagleEye Build 487 — fallgebundene Quellenzuordnung (Draft)

Neue echte, manuelle Aktion: `/workbench/sources487?case_id=<Fall-ID>` verbindet vorhandene Build-483-Recherchehinweise mit real importierten, extraktionsgeprüften Build-458-Originalen. Fallberechtigungen, CSRF/Origin, Audit, Bearbeiter, Zeitpunkt, Begründung, URL-/Record-Hashes und Original-SHA-256; beim Lesen werden Originalbytes und Zuordnung erneut geprüft. Keine Netzwerkabfrage, keine automatisch erzeugte Evidence, keine bestätigten Claims. **Die URL als tatsächliche Herkunft der Bytes ist nicht bewiesen.**

**Bestandsschutz:** Build 398 nicht deinstallieren; Fälle und Arbeitsordner erhalten. Eine reale Build-398-Datenbankmigration ist noch nicht nachgewiesen. Keine Kundenfreigabe.

Windows: ZIP in separaten Ordner entpacken, `START_EAGLEEYE_PRO.bat` starten. Linux: `sh START_EAGLEEYE_PRO.sh`. Python >= 3.12. Runtime prüfen: `python INSTALL_EAGLEEYE_487.py --check`.

Das Windows-/Linux-Actions-Gate erstellt `EagleEye_Build_487_LAPTOP.zip` und die dazugehörige `.sha256`-Datei. Produkt-ZIP-Hash gegen diese Datei prüfen, nicht mit dem Digest des GitHub-Artefaktcontainers verwechseln. Freigabe erst nach exakter SHA: Windows/Linux, UI, Codex und 0 valide offene P1/P2.
