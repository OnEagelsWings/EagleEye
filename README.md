## Build 479 – Eigene Arbeitsbefunde mit Originalfundstelle

Geführte Recherche → Arbeitsbefunde: Dokument und Originalanker auswählen,
Beobachtung/Hypothese/Gegenbeleg/Unsicherheit formulieren und dauerhaft speichern.
Originaltext und Hashes bleiben getrennt von der eigenen Interpretation sichtbar.
Siehe [BUILD_479_NOTES.md](BUILD_479_NOTES.md).

## Build 477 – Fallbezogenes Quelleninventar

Geführte Recherche → Quellenbestand zeigt die gespeicherten Dokumente mit Herkunft,
Status und Originalankern in 50er-Seiten. Der gewählte Fall bleibt in Übersicht und
Rechercheablauf erhalten; Auftrag und Rechtsgrundlage sind sichtbar.
Siehe [BUILD_477_NOTES.md](BUILD_477_NOTES.md).

## Build 476 – Operativer Windows-Start

Die Arbeiten aus UI Audit und „Windows Startproblem Build 471“ sind zusammengeführt.
Echte Fallanlage ohne Entwicklerkonsole, aktueller Arbeitsbereich nach dem Anlegen,
stabiler Datenordner über Versionswechsel und Startdiagnose ohne Zugangsdaten.
Siehe [BUILD_476_NOTES.md](BUILD_476_NOTES.md) und [PLAN_476_480_OPERATIVE.md](PLAN_476_480_OPERATIVE.md).

## Build 475 – KI-/Sicherheitscheckpoint

Fallmenü → **KI-Prüfpunkt 475**: persistierte Entwürfe und Einzelprüfungen,
fallautorisiert und integritätsgeprüft. Vollständige Linux-/Windows-Regression,
Browserabnahme und reproduzierbare Antwortregel-Prüfung stehen im aktuellen
Checkpoint-Workflow. Modellgüte und Produktivfreigabe bleiben offen.
Siehe [BUILD_475_NOTES.md](BUILD_475_NOTES.md) für Start, Messgrenzen und Befehle.

# EagleEye – Build 474: Menschliche Einzelprüfung

KI-Inhalte einzeln prüfen, Gründe dauerhaft zuordnen und veränderte Quellen vor einer Bestätigung erkennen. Ältere Entwürfe über Seitennavigation wiederfinden. [Bedienung und Grenzen](BUILD_474_NOTES.md). Vollcheckpoint: 475.

---

# EagleEye – Build 473: Alternative Hypothesen

Im lokalen KI-Ermittler konkurrierende Erklärungen mit Stützen, Gegenbelegen und Prüffragen anfordern. Alles bleibt menschlich prüfpflichtig. [Bedienung und Grenzen](BUILD_473_NOTES.md). Vollcheckpoint: 475.

---

# EagleEye – Build 472: Fragen an Fallquellen

Im Fallmenü **Lokaler KI-Ermittler** jetzt eine Arbeitsfrage eingeben. Quellengebundene Antworten oder ausdrücklich ausgewiesene Quellenlücken bleiben prüfpflichtige Vorschläge. [Bedienung und Grenzen](BUILD_472_NOTES.md). Vollcheckpoint: 475.

---

# EagleEye – Build 471: Lokaler KI-Ermittler

**Entwicklungsstand, nicht produktiv freigegeben.** Neuer Fallmenü-Einstieg **Lokaler KI-Ermittler**:
1–3 Dokumente auswählen, mit bereits lokal installiertem Ollama-Modell einen quellengebundenen
Zusammenfassungsentwurf erzeugen, Originalfundstellen öffnen und mit Begründung prüfen.
Die Ausgabe bleibt KI-Vorschlag; kein automatischer Claim und keine Faktenbestätigung.

Start: `START_EAGLEEYE_PRO.bat` (Windows) oder `sh START_EAGLEEYE_PRO.sh` (Linux).
Python 3.12+ und für KI ein separat installiertes lokales Ollama-Modell erforderlich.
Details, Umfang, Testbefehle und Einschränkungen: [BUILD_471_NOTES.md](BUILD_471_NOTES.md).
Nächster vollständiger KI-/Sicherheitscheckpoint: **475**. 471 führt nur gezielte Smoke-Tests aus.

---

# EagleEye – Build 470 Vollcheckpoint

**Entwicklungsstand, nicht produktiv freigegeben.** Der freigegebene Fall zeigt unter **Qualitätsprüfung 470** den tatsächlichen Umfang des vorhandenen Dokumenten- und Entitätenregisters, Beziehungen und ungeklärte Quellen, außerdem explizit nicht gemessene Qualitätskennzahlen.

End-to-End-Praxisablauf: Anmeldung → Fall erstellen → öffentliche Quelle über **Öffentliche Quellen** auswählen (Domain oder DOI; nur unkritische Kennzeichen) → gespeicherten Dokument-Snapshot ansehen → Entitäten verknüpfen → Netzwerkgraph und Provenienz öffnen → ungeprüfte Fallprüfung → Qualitätsübersicht. Jede behauptete Bestätigung von Tatsachen erfordert menschliche Prüfung. Der vorliegende Ablauf weist weder offiziellen genehmigten Dossierexport noch Backup/Restore oder reale Suchgüte nach.

Vollständige Regression Windows und Linux, mit überprüftem ZIP und SHA-256:

```bash
python tools/run_checkpoint_regression470.py
python tools/run_checkpoint_regression470.py --phase18-20
python -m pytest -q tests/test_build470_integrated_e2e.py
python INSTALL_EAGLEEYE_470.py --check
```

Der vollständige Regressionslauf enthält historische Tests mit ausschließlich einzeln dokumentierten Versionsausnahmen; alle Build-470-Tests müssen ohne Ausschluss bestehen. Der Quellcode-Installer benötigt Python 3.12 und gegebenenfalls eine einmalige Online-Abhängigkeitsinstallation.


## Aktuell benutzbar: Drei öffentliche OSINT-Quellen

Im authentifizierten Fall über **Öffentliche Quellen** ein Domain- oder DOI-Kennzeichen eingeben. Die Auswahl bietet:
- **DNS-over-HTTPS:** Google DNS, A-Datensätze öffentlicher Domains.
- **RDAP:** Verisign für `.com`-Domains, kein generischer RDAP-Fallback.
- **Crossref:** öffentliches DOI-Metadatenregister.

Jede erfolgreiche Abfrage erzeugt einen unbestätigten TXT-Snapshot mit UTC-Erfassungszeit, Provider, abgefragtem Kennzeichen und exakt gespeicherter Quellen-URL **im bereits vorhandenen Document-Intelligence-Archiv des berechtigten Falls**. Der Browser öffnet anschließend das importierte Dokument.

**OPSEC:** Das Kennzeichen wird an den gewählten Drittanbieter übermittelt. Keine geheimen, persönlichen oder sensiblen Indikatoren einsetzen. Keine automatisch verifizierten Aussagen oder Identitätszusammenführungen. Die Adapter haben feste Zielhosts, deaktivierte Redirects, Eingabevalidierung, Größen-/Timeout-Grenzen, CSRF-Schutz und eine kurzlebige Sitzungs-Drosselung. Drittanbieter können vorübergehend nicht erreichbar sein.

```bash
python INSTALL_EAGLEEYE_470.py
python -m pytest -q tests/test_build469_collectors.py
```

Der Test mockt HTTP-Abfragen, bestätigt also die fallbezogene UI/Persistenz **nicht** die reale Verfügbarkeit von Drittanbietern. Vollständiger Integrationstest und produktive Verwendbarkeit werden erst mit Checkpoint 470 bewertet.


## Build 468: verifizierbares Messprotokoll
**Synthetischer Test, kein Benchmark der produktiven EagleEye-Suche.** Authentifizierte Nutzer können unter **Messprotokoll** die Precision@10, Recall@50, MRR@10, nDCG@10, P95-Latenz und den Hash eines deterministischen 100-Abfragen-Goldsets sehen. Entity Resolution und echte OSINT-Recherchequalität bleiben **N/A**, bis eine vollständige Suchschnittstelle mit beschriftetem Goldset getestet wird.

Zum Reproduzieren (nach Installation):

```bash
python tools/benchmark468.py --output benchmark468.json
python -m pytest -q tests/test_build468_benchmark.py
```

Nur der kurze Smoke-Test ist für Build 468 vorgesehen; vollständiger Checkpoint erst bei Build 470. Ein Installer oder ein bestandener Smoke-Test ist keine Produktivfreigabe.

# EagleEye — Build 467 — Document Provenance Inspection

EagleEye is a local-first, case-centered OSINT and investigation platform with source provenance, evidence review, human-governed AI assistance and auditable Evidence → Claims → Dossier workflows.

**Build 458** added Document Intelligence 2.0 and source anchors. **Build 459** integrated case-scoped document navigation into the investigator workspace. **Build 460** was the five-build full regression and installation checkpoint; **Build 461** adds guided investigation and a provenance-first entity registry; it is not a production release.

## Install and launch (Python 3.12+)

Windows: run `START_EAGLEEYE_PRO.bat`. Linux/macOS: run `sh START_EAGLEEYE_PRO.sh`. The standard launchers install and start the current isolated runtime.

For manual installation and verification:

```bash
python INSTALL_EAGLEEYE_470.py
python INSTALL_EAGLEEYE_470.py --check
```

Use **public or synthetic test data only** during development; do not import sensitive personal data until a separately approved and tested deployment is available.

## Build 467 – Korrigierter Belegprüf-Workflow

Die vier Code-Review-Befunde aus Build 466 sind adressiert: Hauptnavigation mit Fallprüfung, Dokument-Memoisierung innerhalb eines Aufrufs, Integritätsprüfung nur der referenzierten Fall-Dokumente, eindeutige Kennzeichnung jeder Beziehung durch Ausgang, Ziel und Relations-ID. Diese Funktion ist ausdrücklich keine generelle Produktionsfreigabe.

Kurzer Funktionstest: `python -m pytest -q tests/test_build467_review_fixes.py`. Full Checkpoint: Build 470.

## Vorher: Build 466 – Fallbezogene Belegherkunft prüfen

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
