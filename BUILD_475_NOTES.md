# Build 475 – Vollcheckpoint lokale KI und Sicherheit

Der Einstieg **KI-Prüfpunkt 475** im authentifizierten Fallmenü liest den gesamten
integritätsgeprüften KI-Entwurfsbestand dieses Falls: offene, verworfene und
beurteilte Entwürfe sowie vollständige Einzelprüfungen. Zählung und alle
Seiten lesen denselben reservierten Datenbank-Snapshot; gleichzeitige
Entwürfe oder Reviews können die Bestandszahlen nicht gegeneinander verschieben. Ältere Gesamtprüfungen
werden separat ausgewiesen. Die Seite behauptet keine bestandene CI-Prüfung
oder gemessene Modellqualität. `/health` nennt 480 als nächsten Prüfpunkt und
setzt `production_release_ready` weiterhin auf `false`.

## Reproduzierbare Prüfung

```sh
python -m pip install -e '.[test]'
python -m pip install 'playwright>=1.61,<2' 'bandit>=1.8,<2'
python -m playwright install chromium
python tools/run_checkpoint_regression475.py
python tools/run_checkpoint_regression475.py --phase18-20
python tools/checkpoint475.py --output checkpoint475-policy.json
python tools/benchmark468.py --output checkpoint475-search-baseline.json
python INSTALL_EAGLEEYE_475.py
python INSTALL_EAGLEEYE_475.py --check
```

Der Windows-/Linux-Checkpoint installiert Chromium **vor** der Regression;
alle vorhandenen Browserprüfungen 471–475 laufen mit nativen Formularen,
Fallnavigation, Reload, Originalankern und schmaler Ansicht. Die Browserfälle
verwenden simulierte Ollama-Antworten. Ohne Playwright sind diese optionalen
Tests lokal als übersprungen sichtbar; das ist kein Browsernachweis.

Die 24 versionierten synthetischen Antwortfälle messen ausschließlich striktes
Schema, wörtliche Quellenbindung, Enthaltungsregeln und Gegenhypothesenregeln.
Der Fixture-Hash und jede Soll-/Istentscheidung werden ausgegeben. Ein positiver
Grenzfall dokumentiert ausdrücklich, dass ein echtes Zitat eine falsche Aussage
begleiten kann. Es wird **keine** Halluzinationsrate oder automatische semantische
Folgerichtigkeit gemessen. Ein solcher Entwurf bleibt prüfpflichtig und erzeugt
keinen Claim, bestätigten Fakt oder Identitätsmerge.

Zusätzliche Sicherheitstests prüfen echte Fallrollen, Falltrennung, Rechteentzug
während des Modelllaufs, ungültiges JSON, Modellwechsel und Werkzeugaufrufe in
Modellantworten. Letztere werden ausdrücklich verworfen. Abgewiesene Zugriffe
auf fremde Fälle bleiben trotz Snapshot-Transaktion im kanonischen Audit
erhalten; die Hashkette wird im Regressionstest geprüft. Die vorhandenen Tests
prüfen außerdem CSRF/Origin, OPSEC, Belegintegrität, begrenzte Antworten, feste
numerische Loopback-Adresse, gesperrte Redirects und menschliche Einzelprüfung.
Bandit prüft gezielt die aktuellen KI-Module auf Befunde ab mittlerer Schwere,
unabhängig vom Confidence-Level. Das ist kein Sicherheitszertifikat für das gesamte
historische Repository.

Der Regressionsrunner übernimmt unverändert die 118 einzeln begründeten alten
Deselektionen aus `CHECKPOINT_REGRESSION_EXCLUSIONS_470.json` sowie die fünf
bereits ausgemusterten Testdateien 360–364. Er darf keine Tests 471–475
abwählen. Die funktionale 470-Fallabnahme bleibt erhalten; ihre Versionsprüfung
bezieht sich nun auf ihre feste App-Factory. Keine neue funktionale Exclusion.

## Offene Gates

- Reale LLM-Qualität, Prompt-Injection-Widerstand, Halluzinationsrate und i5/16-GB-Inferenzzeiten: **N/A**.
- Tatsächliche Produkt-Suchqualität, Entity Resolution F1 und skalierte Graphleistung: **N/A**. Die 100-Query-FTS5-Baseline bleibt synthetisch und isoliert.
- Immutable Rohbelegversionen/append-only Historie, Live-Quellenabnahme, genehmigter Dossierexport und Restore sowie unabhängige Praxistests: in diesem KI-Checkpoint **nicht nachgewiesen**.
- Keine Produktivfreigabe und kein neuer numerischer Reifewert. Der nächste Prüfpunkt ist Build 480.

## Start und Abnahme im Browser

ZIP vollständig in einen eigenen Ordner entpacken. Windows: `START_EAGLEEYE_PRO.bat`;
Linux: `sh START_EAGLEEYE_PRO.sh`. Python 3.12+ ist erforderlich. Der Installer
baut eine isolierte lokale Laufzeit und prüft deren Importherkunft. Ollama und
ein bereits installiertes lokales Modell werden separat benötigt; EagleEye
lädt kein Modell automatisch herunter.

Anmelden → Fall öffnen → Dokumente mit Herkunfts-URL importieren → Lokaler
KI-Ermittler → 1–3 Dokumente und lokales Modell wählen → Arbeitsfrage stellen
oder Gegenhypothesen auswählen → jede Aussage/Hypothese/Notiz am Original
prüfen → Einzelurteile samt Begründungen speichern → KI-Prüfpunkt 475 öffnen.
Pro Dokument werden höchstens vier Anker mit je 1500 Zeichen verwendet.
