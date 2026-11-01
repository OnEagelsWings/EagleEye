# EagleEye – integrierter Entwicklungsfahrplan Build 481–500
**Planstand:** 1. November 2026 · **Status:** Plan, keine Behauptung über bereits implementierte künftige Builds

## 0. Ausgangslage und verbindliche Übernahme bestehender Arbeiten

GitHub-`main` steht bei Build 478 (Commit `684a87abda12e1fe9edd933dbeb88f33d032203f`). Die Build-479- bis -481-Arbeit liegt in offenen PRs:

- **#78** – 479: menschliche Quellenprüfung, Arbeitsbericht, Backup/Wiederherstellung.
- **#79** – 480: integrierter operativer Windows-Checkpoint, echter öffentlicher Quellenfall, Dossier-Restore.
- **#80** – Original-Evidence→Claims→Dossier-Bedienpfad / Katalog.
- **#81** – 481: kontrollierte PDF/TXT/MD→kanonische Evidence-Übernahme, UI und Windows-Testarchiv. Der letzte geprüfte Head `349629ef6ea717f973a38b1e3400c0a6a6bad61d` hat nach GitHub-Actions-Auskunft grüne CI, UI, fokussierte Tests und Windows-/Linux-Abnahmen; PR ist dennoch Draft und nicht gemergt.

**Gate 481→482 (verpflichtend):** 478–481 in sachlich korrekter Reihenfolge bzw. unter vollständiger Konfliktprüfung auf *ein* `main` konsolidieren, historische Funktionen beibehalten, Workflow des exakt gemergten Heads neu testen, Codex-/Security-Review schließen, installierbares Windows-ZIP mit SHA-256 und Restore-Nachweis veröffentlichen. Keine Abkürzung über einen funktionierenden Build-Branch: der Download ist nicht identisch mit einer freigegebenen Version.

### Aus der bisherigen Roadmap erhalten

- 401–420: Source Registry, Data Fabric/Federated Search, Research Waves, Temporal Graph, Multi-Agent Planner und Evidenz-Hypothesen-Matrix; Altmodule *wiederverwenden und verifizieren*, statt doppeln.
- 421–425: Quelle → Acquisition Event → Content Store → Crawler Core; im Status von `crawler_core425.py` ist noch kein echter Netzwerkexecutor belegt.
- 437–456: Entity/Alias Resolution, Graph/Timeline, Quellenlinien, kontrollierte öffentlich verfügbare Nachrichten-/Sozial-/Register-Recherche, Evidence→Claims→Dossier, separates Vier-Augen-Exportgate.
- 457–460: Workspace Reliability, Document Intelligence mit Textankern, Wiederaufnahme, harte Quellen- und UI-Prüfung.
- 461–470: Fall-/Rechteverwaltung, Graph, Data Collection (Build 469 bisher nur Google DNS-A, Verisign-.com-RDAP, Crossref DOI).
- 471–475: lokaler KI-Ermittler, Quellenfragen, Hypothesen, Revisions- und Halluzinationsgrenzen.
- 476–481: Windows-Start, geführte Fallführung, Quelleninventar, eigene beleggebundene Befunde, Bericht/Restore, kontrollierte Übernahme geprüfter Dateien in originale Evidence-Kette.
- Ursprüngliche Phasen bleiben: 481–485 lokaler KI-Ermittler; 486–490 Rechercheadapter & Mehrsprachigkeit; 491–495 Rollen/Sicherheit/Backup/UX; 496–500 echte Pilotfälle & Releasequalifikation. Die neue Planung ergänzt konkrete Such-/Crawlerintegration **ohne die vorherigen Fachziele zu ersetzen**.

## 1. Produkt- und Architekturvertrag

Ein **Ermittlungsfall** hat genau einen durchgehenden Bedienpfad und Kontext:

`Auftrag/Intake → Suchplan (Freigabe) → Suchanbieter/Registry → begrenzter Retriever/Crawler → Original-Snapshots/Archiv → Quellen-/Textanker → ungeprüfte Evidence → Review → Claims/Gegenbelege → Entitäten/Graph/Timeline → Hypothesen/Red Team → Dossierrevision → unabhängiger Review → JSON/DOCX/PDF/ZIP-Export → Backup/Restore/Audit`.

Unterstützende Dienste haben *separate Rollen*, keine undifferenzierte Mega-Crawler-Klasse:

1. **Search Provider Adapters:** Suchmaschine bzw. öffentliche Register-API liefert Treffer und Metadaten, aber keine automatisch bewiesenen Inhalte.
2. **Source Retrieval Worker:** holt ausschließlich freigegebene öffentliche URLs unter Scope-, Zeit-/Byte-/Ratenlimits, DNS/IP-Schutz, robots.txt- und Nutzungsbedingungen. Kein Login-/Paywall-/CAPTCHA-Bypass, keine privaten Adressen.
3. **Capture/Provenance Service:** Zeitpunkt, UTC, Suchanfrage/Provider, finale geprüfte URL, Originalbytes, MIME, SHA-256, Textanker, Lizenz-/Nutzungsrecht und Fall-ID.
4. **AI Investigator/Planner:** fragt die eigene Evidence-Datenbank ab, schlägt nächste Suchwellen/Hypothesen/Gegenbelege vor und nutzt nach Freigabe zugelassene Werkzeuge; kein stilles unbeschränktes Crawlen.
5. **Evidence/Claims/Human Review:** nur bestehende kanonische Stores und Audit/Freigaben; KI liefert Vorschläge, nie Fakt- oder Identitätsbestätigung.
6. **Local-first Operator UI:** *eine* Firefox/Chromium-Arbeitsoberfläche, Fallliste, Auftrag, Recherche, Quellen, Graph/Timeline, Prüfungen, Dossier, Export/Audit. Progressiver Expertenmodus; keine parallele Legacy-Sackgasse.

Auf 16 GB RAM/Intel i5: Browser-Renderer und LLM lokal optional, standardmäßig seriell/2 gleichzeitige Retrievers; 3–5 browserbasierte Tabs nur unter budgetierter Operatorfreigabe. Keine stillschweigende Cloudübertragung. Schlüssel per OS Secret Store oder lokal gesichertem Konfigurationsweg, niemals im Git/Export/Audit-Text.

**Recht/Sicherheit:** Zugriff nur auf öffentlich/rechtmäßig zugängliche Daten und lizenzierte APIs mit passender Erlaubnis. robots.txt nach RFC 9309 plus Site Terms, HTTP-429/Retry-After, Drosselung. SSRF-Schutz gegen DNS-Rebinding, IPv4/IPv6-private Netze, Loopback/Metadaten-IPs, Redirects, IP-Wechsel bis zum Connect und unsichere Dateischemata; untrusted HTML/PDF und Prompt Injection als Daten behandeln. Anti-CAPTCHA-Bypass/Account-Scraping ausgeschlossen. Audit und unabhängige Prüfung bleiben durchgehend.

## 2. Konkreter Buildplan und Akzeptanzkriterien

### Phase A – lokaler KI-Ermittler als Recherche-Orchestrator (482–485)

| Build | Kernimplementierung | Abnahme aus Nutzerperspektive |
|---|---|---|
| **482** | *Research Provider Contract*: eine stabile Provider-Schnittstelle (`search`, `fetch`, Kosten/Budget, Terms, Licence, Provenance), 1 echte rechtmäßige Suchmaschinen-API (z.B. Brave Search API, Zugang nur mit Betreiberkey), vorhandene Source Registry und drei Build-469-Adapter integrieren. Kein erneutes Nachbauen vorhandener Search/Fabric-Module. | In einem normalen Fall eine Suchanfrage eingeben; echte Treffer mit URL, Provider, Zeit und Fehlerstatus sehen und manuell Quelle übernehmen. Falls Key fehlt: verständliche Einrichtung/alternativer bereits verfügbarer öffentlicher Adapter; normale Fallarbeit bleibt nutzbar. |
| **483** | *AI Query Planner & Research Waves*: lokales Modell über vorhandenen Ollama-/LLM-Adapter, mehrsprachige Synonyme/Operatoren, gezielte Suche nach Gegenbelegen, „Plan anzeigen → Suchumfang/Kosten prüfen → Go“. Resumierbare Queue, keine planlose Autonomie. | KI zeigt eine überprüfbare Rechercheplanung mit Suchbegriffen/Quellenpriorität; die Freigabe löst eine reale begrenzte Suche aus, Abbruch/Weiterarbeit funktionieren. |
| **484** | *Safe Network Retrieval/Crawler Executor*: vorhandenen Crawler425/Acquisition422/Content423 integrieren; öffentliche HTML/PDF/MD/TXT abrufen, URL-/Robots-/SSRF-/Redirect-/Byte-/Time-/Rate-/MIME-Grenzen, Duplikate, Retry/Stop/Resume; Originalhash und Quellenanker. | Anwender wählt einen Suchtreffer und sichert genau eine öffentlich zulässige Seite als überprüfbare Evidence-Vorstufe; Fehler sind sichtbar, keine lokalen/private-IP-Ziele erreichbar. |
| **485** | **Hard Gate I – funktionierende Recherchewelle**: Erststart, Provider-Suche, freigegebener Abruf, Fundstellen, ungeprüfte Evidence, Claim/Gegenbeleg, Dossier-Entwurf, Neustart, Offline-Restore, zwei Rollen, Windows/Linux und UI-Screenreader/Tastatur. | Ein realer unkritischer öffentlicher Recherchefall erreicht ein exportierbares, nicht stillschweigend freigegebenes Arbeitsergebnis; kein F12, kein toter Link, alle Quellanker prüfbar. Fehlende Teile = FAIL, keine Freigabe. |

### Phase B – Quellabdeckung, mehrsprachige Entitäten und Korrelation (486–490)

| Build | Kernimplementierung | Abnahme aus Nutzerperspektive |
|---|---|---|
| **486** | Nachrichten/Publikationen: vorhandene Build-443-Nachrichtenadapter + öffentlich zugelassene RSS/GDELT-Schnittstellen, Publikationsdatum vs Abrufdatum, Dubletten und syndizierte Texte trennen. | Ein Thema samt Zeitfenster recherchieren und Ergebnisse nach Originalpublikation/Veröffentlichungszeit filtern. |
| **487** | Offizielle Register/Forschungsquellen: vorhandene RDAP/Crossref-Adapter ergänzen um OpenAlex, Wikidata-IDs/SPARQL und ausgewählte lizenz-/zugangsgeprüfte Unternehmens-/Organisationsregister. Registry- und Identifier-Präzision vor Zahl der Anbieter. | Zu einer Organisation/Publikation echte Register-IDs und konkrete Quellnachweise finden; ein „kein Treffer“ bleibt erkennbar. |
| **488** | Mehrsprachiger Recherchemodus DE/EN/HE (optionale weitere Sprachen), transliterierte Namen, historische Namensformen, Alias-Kandidaten; Human Review vor Personenzusammenführung. | Mehrsprachige Suchstrategie findet Varianten; mögliche Aliasbeziehungen bleiben explizit „unbestätigt“. |
| **489** | Source Lineage + Temporal Graph + „Follow the Money“ als *quellengebundene* Hypothesen: Beziehungen, Zeitgültigkeit, Registereinträge, dokumentierte Förder-/Eigentumsangaben, Gegenbelege. | Im Fall Graphkanten anklicken → belegte Textstelle und Zeitraum sehen; unbelegte Assoziationen werden nicht als Schuld/Kausalität ausgegeben. |
| **490** | **Hard Gate II – Recherchebreite und Quellqualität**: definierte zwei reale öffentliche Falltypen (z.B. Unternehmenseintrag/Presse/Publikation), Suchanbieter-Comparison, Sprachvarianten, Rechte/Cache/Dubletten, Anbieter-Ausfälle, Windows/Linux. | Reproduzierbare Quellenquote, belegtes und unbelegtes Ergebnis getrennt; interaktive Graph-/Timeline-Sicht bis zum Dossier. Keine erfundene Abdeckung. |

### Phase C – Sicherheit, KI-Qualität, Rollen, UI, Langläufer (491–495)

| Build | Kernimplementierung | Abnahme aus Nutzerperspektive |
|---|---|---|
| **491** | *Evidence-grounded Analyst*: bestehende 471–475-LLM- und Hypothesenmodule vereinheitlichen, RAG über Fall-Evidence, nummerierte Originalanker, strukturierter „was ist sicher/unsicher?“-Dialog; lokaler Fallback bei Modell-/Netzausfall. | Jede faktische Antwort hat anklickbare Fundstellen oder wird als ungeprüft markiert; keine auto-bestätigten Claims. |
| **492** | *Hypothesis Lab/Red Team*: konkurrierende Erklärungen, fehlende Belege, unabhängige Quellenlinie, Widersprüche, Frage „welcher Befund würde Hypothese X widerlegen?“, Provenienzprüfung. | Ermittler kann zu einer Hypothese mindestens eine relevante Prüfung und sichtbare Gegenbelege dokumentieren. |
| **493** | UX-Funktionalkonsolidierung: einheitliche Primärnavigation, präzise nächste Aktion, Status nach Quellen-/KI-/Review-Schritten, Tastatur, responsive, klare Fehlermeldung, Accessibility. Keine versteckten Legacy-Ansichten. | Ungeübter Tester durchläuft Erststart→Fall→Suche→Quelle→Claim→Bericht ohne Entwicklerwerkzeuge, mit zwei unterschiedlichen Fällen ohne Kontextverlust. |
| **494** | Defensive OPSEC, Teamrollen, Budgetierung und vollständige Datensicherheit: least privilege, Credential Store, Warnungen vor personenbezogenen Query-Leaks, Backups/Manifest/Restore, Versionsmigration, stabile Windows-Pfade und ZIP-Installer. | Neustart, Quellverfügbarkeit, Modellfehler, falscher Benutzer oder abgebrochene Migration führen nicht zu Datenverlust oder Berechtigungsausweitung. |
| **495** | **Hard Gate III – Sicherheits-/Reliability-Checkpoint**: Attack-Regression (SSRF, Prompt Injection, XSS, CSRF, Cross-Case, DNS-Rebinding), Wiederaufnahme, Offline-Backup, 16-GB-Windows-Dauerlauf, UI, unabhängiges Reviewergebnis. | Null unautorisierte Fallzugriffe, nachvollziehbare Auditketten; Warnungen statt stiller Fehlschläge; keine bekannten offenen P1/P2. |

### Phase D – Endprodukte, reale Pilotfälle und Build-500-Kandidat (496–500)

| Build | Kernimplementierung | Abnahme aus Nutzerperspektive |
|---|---|---|
| **496** | Living-Dossier-Endprodukt: vorhandener Build-447-/449-Freigabekern, genaue Quellenanker, Unsicherheit, Gegenbelege, Methodenanhang, JSON/DOCX/PDF/ZIP, exportierte Checksums und Verantwortliche. | Zwei getrennte Nutzer können eine Revision unabhängig prüfen und freigeben; sonst bleibt Export gesperrt. |
| **497** | Reale interne Pilotfälle und vergleichende Evaluationsmatrix (u.a. Hunchly, Maltego, i2) auf *Aufgaben*, nicht Fantasie-Prozentwerten; echte Quellen, Trefferqualität, Fehler/Fallbearbeitungszeit, Provenienz. | Drei dokumentierte öffentliche Testfälle, relevante Quellen gefunden, Fehl-/Nichttreffer sichtbar, exportierbare Dossiers. |
| **498** | Windows-Releasequalifizierung: Doppelklickstart, Self-Check, Updater/Rollback, Datenmigration, Offline-Modus, dokumentierte API-Key-Konfiguration, gestützte ZIP-/Installer-Übergabe. | Frische Windows-Installation auf üblicher i5/16-GB-Hardware; Fall nach Upgrade aus altem Build erhalten, erneuter Start/Restore erfolgreich. |
| **499** | Operative Dokumentation und Abnahme: Intake-Checklisten, Datenschutz/Quellenrechte, Analysten-Handbuch, Fehlermeldungen, Reviewerchecklisten, reproduzierbare Daten-/Quellenbeispiele, externe Testergonomie. | Neuer Bediener kann aus der Kurzanleitung einen Fall ohne F12 abschließen und überprüft jeden Zitatanfang. |
| **500** | **Hard Gate IV – Release Candidate, keine automatische Produktivfreigabe**: vollständige Regression, realistischer öffentlicher End-to-End-Fall, unabhängiger Security-/Review-Audit, echte Multi-Provider-Provenienz, Backups, ZIP-/Hashes, Recovery, Schnittstellenverträge, Windows/Linux. | **Nur wenn alle Gates bestanden sind**: geeigneter, klar eingegrenzter Release Candidate für genehmigte professionelle Recherche. Bei kritischer Lücke bleibt „Nicht freigegeben“ und wird im nächsten Fixbuild geschlossen. |

## 3. In JEDEM Build erforderlicher lieferbarer Mindestumfang

**Nutzbar heißt:** Ein einziger klar gekennzeichneter ZIP-/Windows-Start aus einem vollständig entpackten Ordner; echter normaler Fall, lesbare Quellen und Originalanker, eine funktionierende manuelle Ermittlung, vorhandene Evidence/Claims/Graph/Timeline/Dossier und Exportrechte, Neustart und Datenverbleib. Die neue Funktion darf optional oder hinter Feature-Flag sein, die bewährte Fallarbeit aber **nicht** einschränken. Kein separater nur synthetischer Qualifikationsmodus als einziger Einstieg. Fehler dürfen keine „grün“ gefärbten Fakten erzeugen.

**Build n außer Vielfache von fünf:** gezielter Unit-/API-/Security-Test, operativer Browser-Smoke (Windows + Linux), Installation und tatsächlicher Start unter Windows, berechtigte Quelle→Evidence→Claim→Bericht, Backup/Restore-Smoke, unveränderter Datenordner nach Update, SHA-256-ZIP, Build-Notes, Codex-/Code-Review zum genauen Head. Bei Fehler **keine Freigabe**, vorherige stabile Version bleibt herunterladbar und verwendbar.

**Build 485/490/495/500:** zusätzlich komplette historische Regression, reale öffentliche Such-/Crawler-End-to-End-Tests, falsche Quellen/Manipulationsversuche, Browser-Matrix, DOS-/Rate-/Kostenbudget, Reruns unter Windows/Linux, Dossierexport und unabhängige Freigabe, kontrolliertes 16-GB-Systemprofil, Wiederherstellung nach Neustart/Umzug, README/Benutzerhandbuch und klare Gate-Entscheidung. Keine unnötigen Gesamttests nach jeder Entwicklungszeile – die vereinbarte Fünferkadenz bleibt erhalten.

### Metriken, die wir statt subjektiver Prozentwerte tatsächlich messen

- **Fall- und Sicherheitsaudit:** 0 Cross-Case-Zugriffe und ungeprüfte Identitätszusammenführungen.
- **Provenienz:** 100 % der als „belegt“ oder formal freigegeben dargestellten Claims haben auflösbare Originalanker, Inhaltshash und Quellen-/Reviewkette; Ausfall = FAIL.
- **Suchqualität:** Für jedes Pilotset Trefferquote, Precision@10, gefundene *unabhängige* Ursprungsquellen, Dublettenquote, nicht abrufbare Treffer, Fehlertypen und p50/p95-Antwortzeit aus realen Quellen.
- **Dossier:** Alle ZIP-Artefakte geprüft und mit JSON/DOCX/PDF und Manifest wiederherstellbar; Version/Export-Freigabe überprüfbar.
- **Bedienbarkeit:** kein toter Navigationspfad, kein F12, echte Erstinstallation, Wechsel zwischen zwei Fällen ohne Kontextverlust, Aufnahme/Review/Export in einem durchgehenden Arbeitsablauf.
- **Performance:** Speicher-/CPU-/Zeitmessung auf i5/16-GB-Laptop; Such- und Crawlbudget/Taskanzahl offen sichtbar.

## 4. Reihenfolge, Abhängigkeiten und Stoppregeln

1. Zuerst bestehende PRs #78→#79 und Konsolidierungen #80/#81 **ohne Funktionsverlust** auf `main` zusammenführen, vollständig neu testen, startbares Build-481-ZIP aus exakt demselben Release-Commit erzeugen. Andersfalls noch nicht Build 482 beginnen.
2. Vor jedem neuen Modul das alte Framework/den vorhandenen Adapter auf echte Verwendung prüfen; vermeiden, Build-425-Crawler, Build-447-Dossiers und Build-471-KI noch einmal separat zu bauen.
3. Kein Zugriff auf geschützte Ressourcen, keine unautorisierten Social-Daten, keine privaten Netze, keine Sicherheitsumgehung, keine verdeckten autonomen Recherchewellen und keine automatische Freigabe von Identität/Claims/Dossiers.
4. Fehlende API-Schlüssel/Lizenzen sind **sichtbare** `nicht konfiguriert`-Zustände und dürfen die übrigen manuellen Ermittlungen nicht blockieren.
5. Bei Fehler im Windows-Start, inkonsistentem persistenten Fallbestand, fehlendem Quellenhash, roten Auth-/Restore-Tests oder offenen hochkritischen Review-Befunden: **nicht mergen, nicht als einsatzbereit etikettieren**, aber die bisherige geprüfte Release weiterbereitstellen.

## 5. Externe Originalreferenzen für technische Integration

- Brave Search API / Websuche: https://api-dashboard.search.brave.com/app/documentation/web-search
- OpenAlex: https://help.openalex.org/api/
- Wikidata SPARQL: https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service
- Common Crawl URL Index: https://index.commoncrawl.org/
- GDELT Cloud Developer API: https://docs.gdeltcloud.com/API_DOCUMENTATION_GUIDE
- Robots Exclusion Standard RFC 9309: https://www.rfc-editor.org/rfc/rfc9309
- SSRF-Prävention (OWASP): https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html

Die Anbieter sind **Integrationskandidaten**, keine bereits angeschlossenen Datenquellen. Preise, Lizenz-/Weiterverarbeitungsrechte, Nutzungsbedingungen und API-Verfügbarkeit jeweils vor Coding/Deployment erneut überprüfen.
