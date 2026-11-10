# EagleEye Internal 1.0 – Build 500 RC

**Entwicklungsfreigabe:** interner Release-Kandidat, noch **keine** operative Freigabe.

## Windows-Installation aus dem Offline-ZIP

1. Entpacke `EagleEye-500-Internal-Windows-RC.zip` in einen neuen Programmordner,
   beispielsweise `C:\\EagleEye500\\`. Nicht im bestehenden Fall-Datenordner
   installieren.
2. Installiere Python **3.12.x** (das Offline-Wheelpaket ist für CPython 3.12 auf Windows gebaut) und achte auf einen verfügbaren
   `py`- bzw. `python`-Befehl.
3. Starte `START_EAGLEEYE_PRO.bat`. Der Installer legt seine eigene,
   nicht-editierbare Python-Laufzeit `.eagleeye-runtime-500` an und verwendet
   die bereits mitgelieferten `wheelhouse/*.whl` **ohne Internetzugriff**.
4. Verwende die bestehende externe Datenordnerauswahl. Wichtig: Der
   Konfigurationspfad `EagleEye-490` bleibt **absichtlich** als
   Kompatibilitätsanker erhalten, damit Fälle nicht unbemerkt verschwinden.
5. Prüfe zuerst die Startdiagnose und arbeite in einer **synthetischen Testakte**.
   Erst nach eigener OPSEC-/Datenschutzprüfung und Restore-Abnahme sollten
   echte Mandatsdaten erwogen werden.

## Wichtige Grenzen

- Quellen- und KI-Aktionen laufen nur nach den passenden Fallfreigaben.
- Ein KI-Plan bestätigt keine Fakten, Personen oder Verbindungen.
- Ein Kandidat wird nur mit vorhandenem Falldokument und manueller Prüfung
  als **unbestätigter** Graphknoten erfasst.
- `INSTALL_EAGLEEYE_500.py --check` überprüft die isolierte installierte
  Anwendung. Für reproduzierbare Installationen:
  `INSTALL_EAGLEEYE_500.py --offline`.
- Die Integritätsliste liegt in `RELEASE_MANIFEST_500_SHA256.json`,
  die Hashliste der Windows-Räder in `wheelhouse/MANIFEST-SHA256.json`.
- Eine erfolgreiche GitHub-Windows-CI ist keine externe Sicherheitsabnahme
  und keine Garantie für jede lokale Windows-Konfiguration.

## Weiterentwicklung mit Claude Code

Quellcode-Stand: `release/build500-internal-rc1`.
Aus der GitHub-Releasestruktur können die Quellen entnommen werden. Keine
automatische Zusammenführung mit `main`; die bisherigen abgenommenen Builds
bleiben unverändert.

## Prüfreihenfolge

Start → anmelden → Testfall → Rechercheplan 496 → Quellenlauf 497 (Replay) →
KI-Vorschläge 498 → Entitätenprüfung und Übernahme 499 → Quellennachweise →
Bericht → Backup und Restore → Schlussabnahme 500.
