# Stand aller Zweige auf GitHub

Stand: 19. Nov. 2026 · Gemeinsamer Branch: `claude/osint-platform-person-search-r875rx` (PR #94).

## Zusammengeführt (aktive Stränge)

| Zweig | Inhalt | Stand |
|---|---|---|
| `release/build500-internal-rc1` | ChatGPT: Build 493–501, Windows-Installer | bis `affd7f8` enthalten |
| `claude/spiderfoot-reverse-engineering-dn8lpd` | zweiter Claude-Chat: Build-492-Konvergenz, Büroverwaltung (PR #96, #98) | enthalten |
| `feature/firecrawl-public-research` | ChatGPT: Firecrawl-Anbindung (PR #95) | enthalten, mit Fehlerbehebung und neuen Tests |
| `feature/research-exchange-bridge` | ChatGPT: Austausch-Schnittstelle, Prototyp (PR #97) | enthalten |
| `integration/build493-unified-personosint` | ChatGPT: Build 493–499 | über `release/build500-internal-rc1` enthalten |
| `main` und alle älteren, schon zusammengeführten Zweige | – | enthalten |

## Ältere Zweige, die nicht zusammengeführt sind

Geprüft wurde je Zweig: Gibt es Dateien, die der Zweig angelegt hat und die im gemeinsamen Stand **fehlen**? Die Commits selbst haben meist kein Gegenstück, weil die Builds später zusammengefasst (gesquasht) oder neu aufgesetzt wurden – das allein bedeutet keinen Verlust.

### Inhalt vollständig im gemeinsamen Stand (spätere Fassung)

Jede Datei dieser Zweige existiert im gemeinsamen Stand, meist in einer weiterentwickelten Fassung. Ein Zusammenführen würde nur ältere Fassungen einmischen. Diese Zweige können archiviert oder gelöscht werden.

| Zweig | Commits ohne Gegenstück | vom Zweig geänderte Dateien | davon heute anders (weiterentwickelt) |
|---|---|---|---|
| `build-421-acquisition-source-registry` | 14 | 14 | 9 |
| `build-422-acquisition-events` | 26 | 22 | 13 |
| `build-423-content-fingerprinting` | 42 | 33 | 19 |
| `build-424-source-health` | 55 | 41 | 23 |
| `build-425-crawler-core` | 80 | 50 | 27 |
| `build-426-crawl-prioritization` | 94 | 58 | 30 |
| `build-427-incremental-change-detection` | 108 | 66 | 34 |
| `build-428-archives-historical-web` | 122 | 74 | 38 |
| `build-429-news-connector-layer` | 136 | 82 | 42 |
| `build-436-surface-onion-correlation-opsec` | 29 | 21 | 15 |
| `build-437-cross-source-entity-resolution` | 21 | 19 | 11 |
| `build-438-temporal-relationship-fusion` | 43 | 28 | 12 |
| `build-439-ai-investigation-loop` | 62 | 37 | 14 |
| `build-440-phase19-hard-checkpoint` | 83 | 46 | 16 |
| `build-441-controlled-surface-retrieval` | 108 | 55 | 19 |
| `build-442-surface-hardening-validation` | 132 | 65 | 22 |
| `build-442-surface-retrieval-hardening` | 108 | 55 | 19 |
| `build-443-live-news-acquisition` | 155 | 74 | 25 |
| `build-444-controlled-public-social` | 179 | 83 | 28 |
| `build-445-data-acquisition-checkpoint` | 206 | 92 | 31 |
| `build-446-live-ai-investigation-loop` | 231 | 101 | 34 |
| `build-447-evidence-claims-dossier-closure` | 259 | 110 | 37 |
| `build-448-investigator-workspace-ui-audit` | 309 | 120 | 40 |
| `build-450-hardening-all-tests` | 13 | 6 | 5 |
| `build-450-investigation-workflow-hard-checkpoint` | 97 | 33 | 25 |
| `build-450-investigation-workflow-hard-checkpoint-linear` | 27 | 26 | 19 |
| `build-451-retrieval-isolation` | 12 | 44 | 33 |
| `build-452-deployment-installer` | 65 | 58 | 18 |
| `build-453-historical-web-recovery` | 95 | 69 | 17 |
| `build-454-xref-domain-infra` | 120 | 79 | 17 |
| `build-455-full-operations-gate` | 180 | 93 | 16 |
| `build-456-multilingual-entity-source-lineage` | 235 | 103 | 16 |
| `build-457-workspace-reliability` | 259 | 115 | 30 |
| `build-457-workspace-reliability-consolidated` | 219 | 104 | 19 |
| `build-457-workspace-reliability-final` | 3 | 3 | 3 |
| `build-458-document-intelligence` | 13 | 13 | 11 |
| `build-459-workspace-document-navigation` | 3 | 3 | 1 |
| `build-461-provenance-entity-model` | 3 | 3 | 3 |
| `build-476-480-operational-research-workspace` | 12 | 34 | 26 |
| `eagleeye/build-400` | 11 | 2499 | 24 |
| `release/build-476-operational-candidate` | 2 | 11 | 10 |
| `release/build-477-operational-candidate` | 3 | 15 | 12 |
| `release/build-478-operational-candidate` | 4 | 19 | 15 |
| `release/build-479-operational-candidate` | 5 | 23 | 18 |

### Überholte Parallelversuche – bewusst nicht übernommen

| Zweig | Dateien, die es nur dort gibt | Grund |
|---|---|---|
| `build-415-ai-review` | 1: `BUILD_415_CHECKPOINT.md` | nur Prüfnotiz `BUILD_415_CHECKPOINT.md`; die KI-Prüfung selbst ist in späteren Builds (471–475) neu gebaut |
| `build-459-field-workflow-readiness` | 6: `EAGLEEYE_PRO_459_0.py`, `INSTALL_EAGLEEYE_459.py`, `eagleeye_pro/phase20/field_readiness459.py`, `src/eagleeye/application/build459/__init__.py`, `src/eagleeye/application/build459/service.py`, `tests/test_build459_field_readiness.py` | Parallelversuch zu Build 459 (eigener Installer `INSTALL_EAGLEEYE_459.py`, `field_readiness459`); übernommen wurde der andere Strang „workspace-document-navigation“ |
| `build-485-first-operational-pilot-gate` | 2: `.github/workflows/build485-hard-gate.yml`, `tests/test_build485_operational.py` | Parallelversuch zu Build 485 mit anderer `pilot485`-Schnittstelle; übernommen wurde „first-case-pilot-gate“ (der Test dieses Zweigs läuft gegen den gemeinsamen Stand nicht mehr) |
| `external-tester-15min` | 5: `QUICK_TEST.md`, `RUN_EXTERNAL_TEST.bat`, `RUN_EXTERNAL_TEST.sh`, `demo/external_test_case.json`, `tools/external_test_preflight.py` | 15-Minuten-Testpaket für externe Tester aus der Zeit von Build 400 (Sept. 2026); verweist auf alte Abläufe – Neuauflage für Build 500 sinnvoll |
| `fix/codex-build400-review` | 2: `AI_REMEDIATION_BUILD_400.md`, `tests/test_build400_ai_remediation.py` | Nachbesserung zu Build 400 (KI-Prüfung); in den späteren KI-Builds überholt |
| `integration/verified-evidence-to-dossier-guide-478` | 1: `CASE_CLOSURE_WORKFLOW_GUIDE.md` | Anleitung „vom Rechercheauftrag zum Dossier“ für Build 478; ersetzt durch `BETRIEBSHANDBUCH_BUERO.md` und `LIESMICH_KOMPLETTPAKET.md` |
| `phase18/build-405-feedback-cycle` | 5: `PHASE18_ADAPTIVE_PLAN_406_410.md`, `PHASE18_FEEDBACK_CYCLE_401_405.md`, `eagleeye_pro/phase18/bootstrap410.py`, `src/eagleeye/interfaces/web/server410.py`, `tests/test_build410_feedback_branch.py` | Planungsstand Phase 18 (Builds 401–410) mit eigenem Server `server410`; überholt |
| `planning/builds-482-500-ai-research-orchestration` | 4: `INVESTIGATION_KERNEL_ALGORITHM.md`, `ROADMAP_481_500_AI_RESEARCH_ORCHESTRATION.md`, `src/eagleeye/application/orchestrator/investigation_kernel_contract.py`, `tests/test_investigation_kernel_contract.py` | Planung 482–500 samt reinem Ablaufvertrag `investigation_kernel_contract`; umgesetzt wurden 496–499 auf anderem Weg (Rechercheplan, Freigaben, KI-Vorschläge) |

Empfehlung: Die Zweige der beiden Tabellen oben nicht mehr weiterentwickeln. Wer einen davon wieder braucht, findet ihn unverändert auf GitHub; gelöscht wird nichts ohne Ihre Entscheidung.
