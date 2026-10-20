# EagleEye — Build 466 — Document Provenance Inspection

EagleEye is a local-first, case-centered OSINT and investigation platform with source provenance, evidence review, human-governed AI assistance and auditable Evidence → Claims → Dossier workflows.

**Build 458** added Document Intelligence 2.0 and source anchors. **Build 459** integrated case-scoped document navigation into the investigator workspace. **Build 460** was the five-build full regression and installation checkpoint; **Build 461** adds guided investigation and a provenance-first entity registry; it is not a production release.

## Install and launch (Python 3.12+)

Windows: run `START_EAGLEEYE_PRO.bat`. Linux/macOS: run `sh START_EAGLEEYE_PRO.sh`. The standard launchers install and start the current isolated runtime.

For manual installation and verification:

```bash
python INSTALL_EAGLEEYE_466.py
python INSTALL_EAGLEEYE_466.py --check
```

Use **public or synthetic test data only** during development; do not import sensitive personal data until a separately approved and tested deployment is available.

## Build 466 – Fallbezogene Belegherkunft prüfen

Im Fall die Navigation **Belegherkunft & Integrität** öffnen. Für auflösbare Document-Intelligence-Belege werden der gespeicherte SHA-256-Hash, verfügbare Zeitstempel, Ursprungs-URL und Anzahl der Dokumentanker angezeigt. Fehlende Angaben und manuelle Quellenverweise bleiben ausdrücklich sichtbar. Ein Dokument-Hash beweist nicht, dass eine Behauptung wahr ist.

Zwischenbuild: kurzer Browser-Smoke-Test unter Windows/Linux. Nächster vollständiger Systemcheckpoint: Build 470.

```bash
python -m pytest -q tests/test_build466_provenance_smoke.py
```

## Vorherige Integration und Fallabnahme

Nach Anmeldung einen Fall öffnen, zunächst unter **Dokumente & Quellenprüfung** ein TXT-, MD- oder PDF-Dokument importieren, anschließend unter **Dokumentgebundene Beziehungen** eine Beziehung zwischen zwei Entitäten mit einem tatsächlich vorhandenen Fall-Dokument verknüpfen. Die Nachweis-ID wird auf Zugehörigkeit zum Fall geprüft.

Im bisherigen Entitätenarbeitsplatz kann man Personen/Organisationen anlegen. Zwei Entitäten können anschließend durch eine gerichtete Beziehung mit einer Quellen-ID verbunden werden. Die Datensätze bleiben lokal über Neustarts erhalten. **Quellenverweise sind keine automatisch verifizierten Belege.**

Build 465 ist ein vollständiger Testcheckpoint. Er prüft den integrierten Fallablauf sowie die breite Regression unter Windows und Linux. Eine unabhängige Produktivfreigabe wird damit nicht behauptet.

```bash
python -m pip install -e '.[test]'
python -m pytest -q tests/test_build465_integrated_e2e.py
```


## Ende-zu-Ende-Abnahme

1. Fall erstellen und darin ein TXT-, MD- oder PDF-Dokument unter **Dokumente & Quellenprüfung** importieren.
2. Unter **Entitäten & Beziehungen** Personen und Organisationen anlegen.
3. Unter **Dokumentgebundene Beziehungen** zwei Entitäten mit einem tatsächlich importierten Fall-Dokument als Hypothese verbinden.
4. Den **Netzwerkgraph** öffnen, Knoten und Beziehung anklicken und über den Beleglink zum Dokument zurückgehen.
5. **Integrierte Fallprüfung** öffnen: Dokumente, Entitäten, Hypothesen, unsichere und nicht auflösbare Verweise müssen sichtbar sein.
6. Ein offizieller Dossierexport ist ausschließlich nach den bereits vorhandenen menschlichen Freigaben möglich; die Fallprüfung ist kein ungenehmigter Export.

Die Build-465-Auslieferung enthält den vollständigen Quellcode und Startskripte. Python 3.12 und mögliche Dependency-Downloads sind weiterhin nötig.

## Vollständige Checkpoint-Tests

The Build-465 full checkpoint runs the governed repository regression suite, the Phase-18–20 tests, compilation and isolated-runtime installation on Linux and Windows:

```bash
python -m pip install -e '.[test]'
python tools/run_checkpoint_regression465.py
python tools/run_checkpoint_regression465.py --phase18-20
pytest -q tests/test_build465_integrated_e2e.py
```

The historical Build-455 manifest and runner are retained unchanged; Build 465 has its own documented exclusion manifest. A tested source ZIP and SHA-256 checksum are published as GitHub Actions artifacts **only after** the full checkpoint job succeeds.

- [Build-460 pull request](https://github.com/OnEagelsWings/EagleEye/pull/53)
- [GitHub Actions](https://github.com/OnEagelsWings/EagleEye/actions)
- [Build-458 document intelligence notes](README_BUILD_458_0.md)

## Governed investigation process

Acquisition → controlled AI dispatch → Evidence → independent review → Claims and alternative hypotheses → independent review → Graph/Timeline/Synthesis → Living Dossier → independent dossier review → separate export approval → authorized export → recovery and integrity verification.

Automated extraction does not constitute proof. The system must retain source records, provenance, contrary evidence, uncertainty and human approval boundaries.

## Next development checkpoints

- 460 — full integration, usability, installer and security regression gate
- 461–464 — stronger entity resolution, temporally grounded relationship graphs, visual network analysis and source-linked graph navigation
- 465 — five-build graph/security/reliability checkpoint
- 466–469 — multi-source search, event timeline, controlled source monitoring and contradiction detection
- 470 — full research-intelligence checkpoint
- 471–475 — governed local AI analyst, hypothesis comparison and red-team review
- 476–480 — unified professional case workspace, traceable dossiers, supported exports and external testing

Every intermediate build receives focused tests; every fifth build receives the full governed checkpoint. An external beta or production release remains a separate decision.
