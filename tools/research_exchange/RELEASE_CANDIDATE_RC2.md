# EagleEye Forschungs-Brücke – Abnahmeprotokoll 1.0.0-rc2

**Datum:** 20.11.2026 · **Entscheidung:** **HOLD – noch kein Release 1.0**
**Quellbranch:** `feature/public-research-bridge-integration-20261120` (Draft PR #100, basiert auf dem laufenden Integrations-PR #94).
**Quellcommit des ausführbaren Windows-Pakets:** `991753fc5faac703263eea8852c61c0d2be56ba2`.

## Bereitgestelltes Paket

- **Typ:** Portable Windows-x64-Version mit eigenständiger PyInstaller-Anwendung, ohne Python-Laufzeitinstallation auf dem Zielrechner. Git ist für synchronisierte Datenübertragung weiterhin erforderlich.
- **Status:** Unsigned Internal Release Candidate – **nicht** digital signiert und nicht öffentlich freigegeben.
- **Archiv:** `EagleEyeResearchBridge-1.0.0-rc2-Windows-x64.zip`
- **SHA-256:** `e8974769d0ed9814dd448eddaa7a4f9856f8ad7eecc0edd2d174478253d5de82`
- **Archivgröße:** 12.770.165 Bytes · **Manifest:** 993 SHA-256-geprüfte Paketdateien.
- **Lokale Ablage auf DoMi313:** `D:\EagleEyeResearchBuild\rc2\`
- **Programm:** `%LOCALAPPDATA%\Programs\EagleEyeResearchBridge\versions\1.0.0-rc2\ResearchBridge.exe`
- **Programmverknüpfung:** Desktop → *EagleEye Forschungs-Brücke (Vorschau)*.
- **Unberührte Forschungsdaten:** `%LOCALAPPDATA%\EagleEyeResearchBridge\workspace`; DPAPI-Schlüssel unter `secrets\approval.dpapi`.

## Tatsächlich ausgeführte Prüfungen

| Prüfung | Beobachtung |
| --- | --- |
| Python/Tk-Start ohne Datenübertragung | Windows-Selbsttest Exit 0 |
| Windows-Regression vor dem Packaging | 104 Tests, 90 bestanden, 14 übersprungen, keine Fehler |
| Installations-Testfälle, Update, Rollback, Deinstallation, Manipulation | 4 Testfälle bestanden |
| Build aus Git-Quellstand `991753f` | PyInstaller erfolgreich, 993 Paketdateien |
| Archiv prüfen und entpacken | SHA-256 und Einträge bestätigt |
| Entpacktes RC2 zweimal installieren | Manifestprüfung, kein Überschreiben, bestanden |
| Entpackte eigenständige `ResearchBridge.exe --self-test` | Exit 0 |
| Offline-Version umschalten, Testinstallation deinstallieren | Bestanden; Schlüssel unverändert |
| Nutzerinstallation von RC1 auf RC2 aktualisieren | Bestanden; RC1 als Rollback erhalten |
| Tatsächlicher Rollback RC2 → RC1 → RC2 auf DoMi313 | Bestanden; Desktop-Verknüpfung zeigt auf RC2 |
| Datenaustausch zu privatem GitHub | Synthetisches Hin-/Zurück, Duplikat- und Konfliktschutz bestanden |
| ChatGPT → GitHub → Windows | Synthetischer Datensatz `00000000-0000-4000-8000-00000000e502` freigegeben, Audit bestätigt |
| GitHub Research-Regression Windows/Linux auf `991753f` | Erfolgreich (Windows und Linux bestätigt) |
| Gesamter EagleEye-CI-Gate auf `991753f` | Zum Erstellungszeitpunkt noch in Arbeit |

**Sicherheit:** Keine personenbezogenen Fälle, privaten Dokumente, Kennwörter oder laufende Observationen transferiert. Keine automatische Synchronisation und kein automatischer Merge. Die Klassifizierung `public-topic` ist **keine** automatische Datenschutzprüfung.

## Release-HOLD: Pflichtprüfungen, die noch fehlen

1. **Benutzerabnahme:** Desktop-Fenster auf dem Zielgerät tatsächlich bedienen und Layout/Barrierefreiheit bestätigen. Die zwei Tk-Smoke-Tests ersetzen keine visuelle Nutzerabnahme.
2. **Unabhängiger Audit-Anker:** Die HMAC-Kette erkennt Änderungen innerhalb einer Protokollkette, aber eine vollständige Entfernung ihres Endes kann ohne separat aufbewahrten Prüfan­ker unentdeckt bleiben.
3. **Signierung oder Risikofreigabe:** Der ausführbare RC ist nicht code-signiert. Für ein allgemeines Release braucht es eine vertrauenswürdige Signatur; alternativ ist für ausschließlich interne Nutzung eine informierte, ausdrücklich dokumentierte Freigabe dieser Einschränkung notwendig.
4. **Integrationsfreigabe:** Der parallele EagleEye-Entwicklungsauftrag muss Draft PR #100 prüfen. Nicht ungeprüft in PR #94 oder `main` übernehmen.
5. **Gesamte CI-Abnahme:** Alle verpflichtenden Builds auf dem tatsächlichen Freigabecommit müssen grün sein; übersprungene freiwillige Jobs sind nicht bestanden.
6. **Ausdrückliche Freigabe:** Ohne manuelle Releasefreigabe bleibt dieser Kandidat auf HOLD.

## Manuelle Nutzerabnahme (noch offen)

Im Windows-Desktop die Verknüpfung **EagleEye Forschungs-Brücke (Vorschau)** öffnen. Anschließend ausschließlich ein *synthetisches* Sachthema erstellen, die Vorschau ansehen, den Freigabeprozess **ohne Veröffentlichung** prüfen und den Audit-Bereich öffnen. Danach unter *Eingang* zunächst ausschließlich die Git-Metadaten aufrufen, bewusst eine synthetische ID auswählen und den Eintrag prüfen; keine vorhandenen privaten Forschungsdatensätze ohne gesonderte Prüfung öffnen.

Erst nach dokumentierter Abnahme, Sicherheitsentscheidung, Integrationsfreigabe und grünem CI wird aus diesem RC eine freizugebende Version. **Das Gate führt keine Veröffentlichung, kein Tagging, keinen Merge und keine automatische Freigabe durch.**

Maschinenlesbarer Gate-Stand: `tools/research_exchange/acceptance_rc2.json`. Prüfung: `python tools/research_exchange/release_gate.py tools/research_exchange/acceptance_rc2.json`; Exit-Code 2 bedeutet **HOLD**.
