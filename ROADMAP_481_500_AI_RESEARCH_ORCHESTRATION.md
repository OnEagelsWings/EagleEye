# EAGLEEYE 500 – VERBINDLICHER KONSOLIDIERUNGS- UND EINSATZMASTERPLAN
**Stand: 01.11.2026 · Ersetzt die bisherige Reihenfolge der Roadmap 481–500, nicht deren fachliche Anforderungen.**  
**Ziel:** spätestens Build 500 ein tatsächlich arbeitsfähiges, lokales OSINT-/Ermittlungsprodukt für kleine professionelle Teams und genau definierte, rechtlich zulässige Kundenaufträge. **Keine automatische Freigabe durch eine Buildnummer.** 485 = erstes eng begrenztes Arbeitspilot-Gate, 490 = integriertes Recherche-Gate, 495 = Security-/Reliability-Gate, 500 = Produktentscheidung. Die Buildnummer ist ein Meilenstein, keine Qualitätsskala.

## 0. Die unverhandelbare Leitentscheidung

Keine neuen „Feature-Inseln“, keine zweite parallele Datenbank für dieselbe Evidenz, keine neue vereinfachte Exportalternative statt des vorhandenen Dossierkerns, keine UI-Sackgassen und kein ungerechtfertigtes „Production ready“. **Vorhandene alte, leistungsfähigere Implementierung immer zuerst inventarisieren, prüfen und einbinden.**

Der Anwender muss spätestens bei Build 485 einen normalen Fall mit echten rechtmäßig zugänglichen öffentlichen Quellen bearbeiten können, Dorks/Source Capture/Bildprüfung/Graph benutzen, beleggebundene Erkenntnisse prüfen, einen als solchen gekennzeichneten Bericht erzeugen und nach Neustart weiterarbeiten. Für vertrauliche Kundendaten müssen zusätzliche Datenschutz-/Security-/Restore-Gates ausdrücklich erfüllt sein.

### Aktueller verifizierter Repository-Ausgangspunkt

- \`main\` = Commit \`684a87abda12e1fe9edd933dbeb88f33d032203f\`, Build **478** (Stand 01.11.2026).
- PR **#78** (479) Bericht/Recovery, PR **#79** (480) integrierter Windows-/public-source-Pilot, PR **#80** Original-Evidence→Claims→Dossier-Navigation, PR **#81** Build 481 dokumentgeprüfte Originale→Evidence, PR **#82** bisherige 482–500-Roadmap. **PRs 78–81 sind nicht sämtlich in \`main\`.**
- Der letzte Build-481-Head hat grüne GitHub-Actions Windows-/Linux-/CI-Läufe und Codex-Review ohne neue große Befunde; das ist **kein** eigener, verifizierter Kunden-Desktoptest, keine Rechtsprüfung, keine Garantie gegen unbekannte Sicherheitsfehler.
- Nachgelagerte Build-481-Code-Fixes: keine fallbezogenen Titel/URLs in globale Source-Registry, transaktionaler/identitätsgebundener Evidence-Import, Cross-Case- und Rollback-Prüfungen. Die genauen Release-Commits und Abnahmen müssen beim finalen Merge wiederholt werden.
- Überdauernde Ursachen früherer Regressionen: Build-448-Expertenansichten/Graph teilweise aus der Hauptnavigation entfernt, Build-450-Legacy-/Qualifikationsfalldrehen, Build-476–481 neuere Ersatz-/Nebenoberflächen; zahlreiche technische Komponenten sind noch im Code, aber nicht im zentralen Ablauf. Eine existierende Route oder Klasse beweist keine Live-Nutzbarkeit.

### Vor-482: Pflicht-Gate „Ein Stamm“

1. **Ein** freizugebender Branch und **ein** finaler Start-/Installations-/Arbeitsdaten-Pfad. PRs #78/#79/#80/#81 in getesteter sachlicher Reihenfolge bzw. als konfliktebereinigte Integration übernehmen; keine stillen Überschreibungen.
2. Datenmigration/Arbeitsverzeichnis/Backup/Restore; alte Fälle und zugehörige Dokumente/Graphen/Bildbelege aus früheren Releases mit Inventar und Snapshot lesbar halten. Ohne nachgewiesene Migration nur isolierte Neuinstallation anbieten, **nicht** „alte Daten kompatibel“ behaupten.
3. Canonical Service Map, echte Route- und Windows-Funktionstests, Quell-Herkunft, unabhängige Codeprüfung. Widersprüchliche alte Dossier-/Crawler-Pfade nicht parallel schreibend freischalten.
4. Zwei sichere Arbeitsvarianten: **Analysten-Arbeitsbericht mit klarer fehlender Zweitprüfung** und **formal freigegebenes Dossier nur nach vorhandener unabhängiger Vier-Augen-Freigabe**.
5. Ein einziges exakt SHA-gekennzeichnetes ZIP/Startskript mit Versions-/Recovery-Protokoll. Bei rotem Gate kein Merge, keine Kundenfreigabe.

## I. DIE EAGLEEYE-BAUMARCHITEKTUR

### WURZELWERK – starker Code
- **Ein Repository, ein installierbarer Paketstand, modulare Ports/Adapter, ein gemeinsames kanonisches Datenmodell und einheitliche Migrationsverwaltung.** Keine per-Build-Tabellen/Agenten mit konkurrierenden Bedeutungen, keine ungeschützten globalen Fallinformationen.
- Schichten: \`domain\` (Case, Entity, Evidence, Claim, Relation, Hypothesis, Review, Dossier) → \`application\` (Intake, Plan, ResearchWave, Capture, Review, Export) → \`adapters\` (Search, Retriever, Image, OCR, Registers, LLM, Graph) → \`infrastructure\` (SQLite/FTS5, File/CAS, Jobs, Audit, Windows) → \`web\`.
- Dokument und Quelle sind nicht automatisch Evidence. Evidence ist nicht automatisch akzeptierter Claim; ein Claim nicht automatisch bewiesene Schuld/Identität; ein KI-Entwurf kein bestätigter Befund.
- Jede Aussage/Relation bindet: Fall-ID, unveränderlichen Beleg-/Capture-Hash, Original-URI/Datei oder nachvollziehbaren Herkunftsvermerk, Abruf- und ggf. Publikationszeit, exakte Anker, Parser-/Modellversion, Bearbeiter, Prüfzustand und Gegenbelege.
- Laufzeitbasis auf Windows Intel i5 / 16 GB RAM: lokal, kleiner Workerpool (zunächst max. 2 parallele Netzabrufe), gedrosselte LLM-Last, kein impliziter Cloud-Datentransfer, gut sichtbare Ressourcenlimits.
- 100 % der kundenseitig als „belegt“ dargestellten Befunde müssen einen *auflösbaren* Originalanker und Hash besitzen; keine Zahlen zu Qualität ohne realen Benchmark.

### STAMM – ein definiertes Ermittlungsziel und ein Fallfluss
**Fallannahme → Zweck/Rechtsgrundlage/Scope → KI-/manueller Rechercheplan → menschliches GO → Dork-/Such-/API-Recherche → kontrollierter Abruf → Snapshot & Bild-/Dokumentmetadaten → Evidence → Review → Claims/Gegenbelege → Entitäten/Timeline/Graph → Hypothesenprüfung → Dossier → getrennte Freigabe → Export/Audit/Restore.**

Ein Nutzer sieht nur 6 verständliche Hauptbereiche: **Fälle · Recherche · Quellen & Evidence · Analyse · Prüfung · Dossier**. Weitere Werkzeuge unter einem **Expertenmodus**; der ausgewählte Fall bleibt in jeder Ansicht erhalten. Alles ist mit „Nächster sinnvoller Schritt“, Fortschritt und klarer Fehlermeldung erreichbar. KI ist ein Assistent innerhalb dieses Baums, kein zweites unverbundenes Arbeitsprogramm.

### RINDE – defensive OPSEC und Recht
- Default: loopback / local-first / least privilege, Einzelfall- und Benutzerrechte, Authentifizierung, CSRF/XSS/SSRF-Protections, Hash-Audit und unveränderliche Originale, Datenschutz/Need-to-know, Sensitivitätsklassifikation, API-Credentials nur in geschütztem Store.
- Crawler: kontrollierter HTTP(S)-Scope, Ziel-/IP-Prüfung **bei der tatsächlichen Verbindung**, DNS-Rebinding-/Redirect-/IPv6-/Cloud-Metadata-Schutz, robots.txt nach RFC 9309, Nutzungsbedingungen/Rate-Limits/429/Retry-After, Stop/Resume und Run-Budget. Kein CAPTCHA-/Paywall-/Login-Bypass, kein offenes Stealth-Scraping.
- OS-/Netzwerkanpassungen und besonders riskante Recherchefunktionen nur nach separater Freigabe; defensives OPSEC darf blockieren, pausieren, isolieren, aber nicht autonom Zugangsdaten/Firewall/Netzwerk verändern.
- Personenbezug: Zweckbindung, Art.-6-Rechtsgrundlage/Interessenabwägung wo anwendbar, Datenminimierung, Speicher-/Löschkonzept, Auftrags- und Rollenklärung, Betroffenenrechte und sichere Übermittlung. Öffentlich sichtbar ist **nicht** datenschutzrechtlich frei verwertbar. Prüfung lokaler/berufsrechtlicher Anforderungen bleibt außerhalb der Software nötig.
- Vergleichende Identitätsmerkmale/Bilder: keine automatische Personenidentifizierung oder Schuldzuweisung; Kennzeichen als *Kandidat*, unabhängige Bestätigung und Abweichungs-/Negativbefunde.
- External APIs geben Suchindikatoren an Drittanbieter preis; UI muss diese Übertragung vor jeder Freigabe offenlegen.

### FÜNF HAUPTÄSTE – vorhandene Fähigkeiten als Kanon
| Ast | Vorhandene Wurzelmodule | Fehlende/zu prüfende Verbindung |
|---|---|---|
| **KI-Ermittlung** | \`phase18/autonomous_research_waves414.py\`, Build 439/446 Research Loop, \`app471\`–\`app475\`, bestehende lokale LLM-/Hypothesenmodule | Ein einziger autorisierter Planner mit kontrolliertem Tool-Routing, Quellenzitation, Budget und Stop/Resume; nie KI→Review-Bypass |
| **Crawler & Dorks** | \`providers/dork_engine.py\`, \`src/eagleeye/crawler/engine.py\` (echter HTTP-Transport), \`phase19/crawler_core425.py\` (Planung/Provenienz), \`phase18/federated_search408.py\`, Build-441–445-Akquise, Build-469-DNS/RDAP/Crossref | Dork-Vorschläge + echte erlaubte Suche + governter Fetch/Job in *einem* Fall, originaler Capture im gemeinsamen Evidence-Vault. Dork-URL ≠ automatischer Suchtreffer |
| **Bildanalyse** | \`src/eagleeye/image_intelligence/agent.py\` (EXIF/IPTC/XMP, GPS, OCR optional), \`similarity.py\` (lokale Hash-/Deskriptorsimilarität), \`phase16/image_live_validation377.py\`, \`src/eagleeye/crawler/media.py\` | Nutzerfähiger Bildimport, Original/Metadaten, Bildvergleich, sichtbare Grenzen, ggf. lizenzierte externe Reverse-Suche als *Hinweis*, niemals ungeprüfte Personen-/Ortsbehauptung |
| **Quellen- und Aussageanalyse** | \`document_intelligence458\`, Source Registry421/Events422/Content423, Build 447 Evidence→Claims→Dossier, Build 449 human review; Source Lineage456 | Dokument-/Bild-/Web-Capture → kanonische prüfbare Evidence, unabhängige Quellen erkennen, Gegenbelege/Negativbefunde, keine zweite konkurrierende Truth-DB |
| **Graph / Timeline** | \`app464\`, \`graph130.js\`, Phase-16-Analyst-Graph373, Entity Resolution437, Temporal-Fusion438, Entity Lineage456 | Eine fallbezogene interaktive Visualisierung mit Klick bis Originalbeleg, Zeitgültigkeit und Relationstyp; keine Verknüpfung allein aus Namensähnlichkeit |

**Feinverästelungen = externe Quellen & APIs:** schon real erprobte öffentliche Adapter Google DNS-A / Verisign RDAP / Crossref; ältere Corporate/Legal/Archive/News-Konnektoren aus 366–368, 443–445 anhand echter „LIVE receipts“ individuell erneut validieren, keine simulierten Provider als real deklarieren. Zusätzliche Kandidaten (erst nach Terms/Lizenzen/Keys): eine Websuche-API, OpenAlex, Wikidata-ID/SPARQL, GLEIF, SEC, öffentliche Register, GDELT/RSS; Social/Leak/Darknet ausschließlich gesondert rechtlich und technisch freigegebene isolierte spätere Optionen, keine MVP-Blockade.

### FRUCHT – belastbares Ermittlungsdossier
Für den Auftraggeber nachvollziehbare Deckseite (Auftrag/Scope/Bearbeiter/Methodik), Executive Summary, verifizierte Tatsachen getrennt von Hypothesen, Chronologie, Entitäten/Graph, Belegregister mit Originalankern, dokumentierte Gegenbelege und Unsicherheiten, Beschaffungs- und Verarbeitungskette, Datums-/Versionen-/Reviewprotokoll, Anhang, unveränderliche Hashes, nachvollziehbare Exporte DOCX/PDF + JSON/ZIP/Manifest. Zwei **unterschiedliche** Versionen:
- **Analyst Working Report:** durch Nutzer erzeugbar, klar als „nicht unabhängig geprüft“ gekennzeichnet.
- **Reviewed Case Dossier:** nur mit existierender Rollen-/Vier-Augen-Freigabe; für Behörden ggf. zusätzliche Vorgaben, förmliche Auftragsbasis und chain-of-custody-Einzelprüfung. **Keine pauschale gerichtliche Verwertbarkeit garantiert.**

## II. BUILD-FÜR-BUILD-PFLICHTPROGRAMM

**Jeder Build muss vollständigen bestehenden Kern weiterführen.** Die unten genannten Akzeptanzen müssen aus der **installierten** Anwendung erreichbar sein; ein Unit-Test allein zählt nicht.

### PHASE A – verlorene Fähigkeiten in EINER Anwendung wiederherstellen | 482–485

**482 – Fundament und Navigationsrettung.** Architektur-/Routeninventar aller alten Generationen als „funktionsfähig / erreichbar / nicht geprüft / ersetzt / obsolet“; ein kanonischer Service-Vertrag, Rollenregeln und Verknüpfungen; migrationsfähiger SQLite/Object Store; sichtbare links für **Dorks, Bildanalyse, Graph, KI, Evidence, Dossier**; Windows-First-Run-Diagnostik. Kein riskanter „alles gleichzeitig freischalten“-Schalter. **Abnahme:** neuer normaler Fall, alle sechs Hauptbereiche erreichbar, Bild/Dork/Graph-Karten nicht mehr unsichtbar; 2 Fälle strikt getrennt; verifizierbarer Start + Neustart.

**483 – Dorks & echte Suchführung.** Vorhandene \`DorkEngine\` mit klarer Sucheingabe, Alias-/Themen-/Domainfiltern, klickbaren legitimen Suchlinks, Safe-Query-Preview und Speicherung von manuellen Trefferbelegen an normalen Fällen anbinden; bestehende Search-Provider abstrahieren; erste tatsächlich zugelassene programmatische Websuche über offizielle API nur mit gültigem Key. **Abnahme:** Anwender fragt nach Organisation/Domain, sieht generierte Dorks, öffnet mindestens 2 Suchoberflächen, übernimmt eine echte öffentliche Quelle samt Herkunft in den Fall; ohne API-Key bleibt Dork-/Manual-Research funktionsfähig.

**484 – Bild- und Graphfunktionen wieder operativ.** Bestehende Build-353/354/377-Bildpipeline mit Originalupload, SHA/EXIF/GPS/OCR-Status, lokalem Vergleich, Bildanhang im Case; \`app464\` / \`graph130.js\` mit nachvollziehbarer Knoten-/Kanten-/Quelle-Ansicht und Zeitlinie. Mensch prüft Foto-Herkunft und fehlende EXIF-Daten; keine Objekt-/Personenidentität als Tatsache aus Ähnlichkeit. **Abnahme:** echtes öffentliches Bild importieren/prüfen, Fallbeziehung mit Quellenanker anlegen, interaktiven Graph öffnen, Neustart überstehen und Bildmetadaten in Arbeitsbericht referenzieren.

**485 – HARD GATE A: erste tatsächlich arbeitsfähige öffentliche Fallbearbeitung.** Windows-Doppelklick, reale manuelle/Dork-Webrecherche, erlaubter Dokument-/Bildimport, Original-Evidence, mindestens ein akzeptierter und einer verworfener/ungeprüfter Claim, Quell-/Gegenbelege, Graph, verständlicher Bericht, Neustart und vollständiger Restore; zwei Nutzer für die *formale* Dossierfreigabe, kein P1/P2. **Abnahme:** Ein unabhängiger Anwender bearbeitet ohne F12 einen definierten öffentlichen Unternehmens-/Organisations- oder Domainfall und liefert einen überprüfbaren Analystenbericht. Bei fehlendem unabhängigen Reviewer **nur** eindeutig gekennzeichneter Arbeitsbericht. **Erst nach technischem, Datenschutz-/Auftrags- und Security-Gate** darf eine begrenzte nicht-sensitive Kundenpilotleistung in Betracht gezogen werden. Sonst Gate FAIL, Build 484 bleibt geprüfter Rückfallstand.

### PHASE B – stärkere Rechercheäste & echte APIs | 486–490

**486 – kontrollierter Live-Crawler.** Den tatsächlich vorhandenen \`src/eagleeye/crawler/engine.py\` statt eines zweiten Abrufworkers übernehmen; Build 425 für Auftrags-/Provenienzvertrag; SSRF/Redirect/robots/Terms, Origin/DNS-/TLS-Bindung, Max-Seiten/Bytes/Zeit, Status Stop/Resume; Original HTML/PDF/TXT/MD im gemeinsamen Vault. **Abnahme:** reale ausdrücklich freigegebene öffentliche Website in begrenzter Tiefe abarbeiten; jeden Fetch/Fehler und Hash sehen; private/loopback-/Metadaten-/rebindende Ziele blockiert.

**487 – Quellen- und Registeradapter.** Ältere News-/Corporate-/Legal-/Archive-Connectoren rehabilitieren und live prüfen; eine Search-API, offizielle Organisations-/Publikations-APIs, News/RSS nach Lizenzen/Keys und Nutzungsrechten; einheitliche Fehlertypen, paginierte Treffer, originale Publikations-/Abrufzeit. **Abnahme:** mindestens 3 voneinander unabhängige und tatsächlich kontaktierte öffentliche Provider liefern verknüpfte Belege, Ausfall eines Providers blockiert die übrige Fallarbeit nicht.

**488 – Bilder, Medien und Geo-Kontext stärken.** Media-Crawl/Herkunft, deduplizierte Bilder, Bildversionsvergleich, EXIF/IPTC/XMP, OCR, rechtlich zulässige Reverse-Image-**Suchhinweise** (nur über echte erlaubte Anbieter bzw. manuell geöffnete Suchlinks), separates Medienbelegregister; Geo-Hypothesen und Karten nur mit bestätigten Daten. **Abnahme:** zwei Originalbilder verschiedener Quellen mit getrenntem Hash und sichtbarer Similaritätsbegründung, Reverse-Hinweise als ungeprüft, keine automatische Identifizierung von Personen oder Orten.

**489 – KI-Orchestrator mit menschlichem GO.** Vorhandenen 414/439/446/471–475-Loop unter *einen* Planner stellen: Entwurfs-Rechercheplan, Queryexpansion, Mehrsprachigkeit DE/EN/HE, Quellenbudget, Providerscope, Freigabe, bounded Recherchewellen, Verlauf, Stop/Resume und RAG mit Click-through zu Evidence. **Abnahme:** Nutzer kann eine KI-Welle bearbeiten/freigeben, real ausführen und verwerfen; lokales Modell offline oder ohne Ollama führt zu manuell voll nutzbarem Fall statt Systemstopp.

**490 – HARD GATE B: vollständiger integrierter Baum.** Zwei realistische, öffentliche Falltypen müssen Recherche/Dorks → bewilligte Crawl-/API-Quellen → Medien → Evidence → Claims/Gegenbelege → Graph/Timeline → KI-Fallzusammenfassung → geprüften Arbeitsbericht mit reproduzierbaren Daten durchlaufen; API-Fallback, Crawl-Abbruch, Windows/Linux, USB/Offline-Restore, zwei Rechteprofile. **Abnahme:** 100 % der „belegten“ Claims öffnen einen Originalbeleg samt Hash; jede unbelegte KI-Feststellung bleibt sichtbar ungeprüft; Live-Provider-/Originaltrefferstatistik dokumentiert. Keine Produktivfreigabe bei rotem Gate.

### PHASE C – Auswertungsstärke, OPSEC, Bedienbarkeit | 491–495

**491 – Source Intelligence & Provenienz.** Original vs Repost/Syndikation trennen, Quellenqualität ohne Pseudowahrheitsprozent, Aktualitäts- und Metadatenkonflikte, unveränderliche Snapshot-Versionen, zitierbare Bild-/Dokumentanker, „nicht gefunden“ von „nicht vorhanden“ unterscheiden. **Abnahme:** widersprüchliche Original- und Zweitquelle sichtbar nebeneinander; Kette von Dossierzitat bis Originaldatei/URL vollständig und unabhängig nachvollziehbar.

**492 – Entity Resolution, Graph, Timeline & Follow the Money.** Bereits vorhandene 437/456-/Graph-Komponenten vereinen, getrennte Aliasse/Mehrsprachigkeit, Zeitgültigkeit, Register-/Förder-/Eigentumsangaben mit Quelle, gegensätzliche Beziehungen und Identitätskonflikte; keine automatische Personenverschmelzung. **Abnahme:** ein belastbarer öffentlicher Organisations-/Finanzgraph mit wenigstens einem bewusst *nicht* bestätigten Kandidaten; jede Kante klickbar bis Originalanker.

**493 – Human Hypothesis Lab + KI-Red-Team.** 447 Claims, 471–475 Hypothesen/LLM, externe Quellenkritik, konkurrierende Erklärungen, aktiv gefundene Gegenbelege und fehlende Evidenz; begründete menschliche Annahme/Zurückweisung, Versionsverlauf. **Abnahme:** zwei konkurrierende Hypothesen mit Beleg- und Gegenbelegmatrix; die KI kann keine Hypothese allein als festgestellte Wahrheit freigeben.

**494 – vollständige OPSEC- und UX-Rinde.** Geschützte API-Keys, Secret-leak-Checks, case-scoped RBAC, XSS/CSRF/SSRF/Prompt-Injection-Tests, sensible Suchindikatorwarnung, lokales Verschlüsselungs-/Backup-Konzept, Windows Daten-/Migration-/Rollback; sechs klar getrennte Hauptmenüs, echte Fehler-/Offlinehinweise, Tastatur/Responsive. **Abnahme:** normaler Nutzer bearbeitet zwei getrennte Fälle ohne tote Links; jeder unerlaubte Cross-Case-Zugriff verweigert; Migration und Restore nach frischer Windows-Installation nachweisbar.

**495 – HARD GATE C: unabhängiger Sicherheits- und Betriebscheck.** Gesamte historische Regression, Pentest/Review für Security-Grenzen und Supply Chain, Such-/Crawler-Last mit 16-GB-Windows-Rechner, Datenbankmigration, Backup-/Restore-Drill, End-to-End Browser, Rollen-/Provenienz-/Exportprüfungen, reale Anbieterfälle. **Abnahme:** kein offenes kritisches/hohes Sicherheitsproblem, keine falsche Claims-Auto-Freigabe, alle Pflicht-Backups und Datenhashes nach Umzug intakt; sonst Stopp und sicherer Rückfallstand.

### PHASE D – die Früchte werden kundenfähig | 496–500

**496 – Dossier-Produkt statt Datenablage.** Vorhandene Build-447/449-Dossier-/Vier-Augen-Funktionen konsolidieren: Methodik, Quellenverzeichnis, Bildbeleganhang, Graph/Timestamps, Fakten/Hypothesen/Gegenbelege, Risikohinweise, getrennte Analysten-/Reviewerfreigabe; Exporte DOCX/PDF/JSON/ZIP mit prüfbarem Manifest. **Abnahme:** zwei getrennte Rollen prüfen dieselbe revisionsfeste Fassung; ein nachträglich geänderter Originalbeleg invalidiert die Freigabe.

**497 – Auftragsmanagement / Kunden- und Behördenübergabe.** Aktennummer, Mandant/Zweck, Auftragsumfang, erlaubte Recherchemethoden, Abgrenzung außerhalb des Auftrags, Kunden-/Personendatenklassifikation, Wiedervorlage, Aufbewahrungs-/Löschplan, Übergabe-/Empfangslog, exportierbare prüfbare Originale. **Abnahme:** Demonstration vom schriftlich abgegrenzten Pilotauftrag zur separaten kundenfähigen Deliverable-Version; Behördenübergabe als sachlich dokumentiertes Belegpaket, keine Zusage rechtlicher oder gerichtlicher Verwertbarkeit.

**498 – echte Pilotaufträge und Produktbenchmark.** Mindestens **drei** definierte rechtmäßig zugängliche Pilotfälle: Unternehmens-/Domainstruktur, öffentliche Ausschreibungs-/Förderinformation, Publikations-/Nachrichtenanalyse; ggf. repräsentative Bildquelle. Messung Recall/Precision@10 in abgegrenzten Korpora, Quellunabhängigkeit, falsch verknüpfte Entitäten, Zeitaufwand, Erfolgs-/Fehlerquoten, Speicherbedarf. Vergleich mit Maltego, Hunchly etc. nur für tatsächlich gemeinsam getestete Aufgaben, nie erfundene Prozentwerte. **Abnahme:** reale Dossiers mit Quellenprovenienz und offen dokumentierten Nichttreffern.

**499 – finaler Windows-Release und unabhängiges Bedienerhandbuch.** Doppelklick-/Installer, sauberer Versionswechsel, Fallback, diagnostischer Selbsttest, Datenmigration, Recovery, verschlüsselbare Fallarchive, Audit/Backup UI, Schritt-für-Schritt-Handbuch, SLA/Support- und Quellenanbieter-Ausfallverhalten, sachlich korrekte Datenschutz-/Vertrags-Checklisten. **Abnahme:** zweiter Anwender kann ohne Entwickler-Konsole einen realen öffentlichen Fall anlegen, recherchieren, prüfen, exportieren und erneut öffnen.

**500 – HARD GATE D: produktiver Release Candidate / GO-NO-GO.** Alle fünf Äste aus derselben **getaggten** Codebasis, Security/Legal-/Datenschutzscope geprüft, verifizierter Windows-Build/Signatur bzw. SHA-256, unabhängige Quell-/Dossierprüfung, reales Multi-Provider-Recherche-Dossier und drei Pilotfälle, vollständige Backups/Restore, Graph-/Bild-/Crawler-/KI-Abnahme, Release Notes, dokumentierter Support/Incident-Prozess. **Abnahme:** nur bei vollständig grünem Gate **begrenztes GO für vereinbarte professionelle Aufträge**; offene kritische Punkte erzwingen **NO-GO** und gesonderten Patch-Release. Ein Build-500-Label ist kein Freibrief.

## III. DIE VERBINDLICHE BAUORDNUNG (DEFINITION OF DONE)

### Jeder Build 482–500
1. Alte Fähigkeiten im Feature-/Route-Register gegen tatsächlich vorhandene Altimplementierungen abgleichen; keine unbegründete Doppelimplementierung. Bestehende Tests bleiben grün.
2. Exakt ausgetesteter Python-/Windows-Start im vollständig entpackten ZIP; aktive Fallliste, echter operativer Fall, normaler Benutzer darf arbeiten, Test-/Qualifikationsfälle niemals einzigen Einstieg. Keine Browserkonsole erforderlich.
3. **Ein** erreichbarer nächster Schritt im echten Fall; neue Funktion muss über die sechs Hauptbereiche oder den Expertenmodus aufgerufen werden können, mit klarer Status-/Fehlerbehandlung. Keine tote Navigation, keine stillen Rechteausweitungen.
4. Echte Quelle bzw. rechtmäßig manuell importiertes Original → Hash/Anker → ungeprüfte Evidence → Review/Claim → Bericht; Bild/Dork/Graph bleiben zugänglich. Kein Modell-/Provider-Key darf das manuelle Basisprodukt deaktivieren.
5. Sicherheit: automatisierte Cross-Case-, CSRF-/SSRF-/XSS-, Datenintegritäts-, Rollen-/Audit-Tests der geänderten Oberfläche, als eigenständige Integrationsprobe. Bei P1/P2: nicht mergen.
6. Betrieb: Windows/Linux CI, Browser-Erststart, Datenpersistenz nach Neustart und **Restore-Test** von mindestens einem vorhandenen Fall. Laufender lokaler Arbeitsdatenordner außerhalb temporärer Build-ZIP; klare Versionsmigration und Rollback.
7. Lieferschein zu jedem Build: Commit, SHA-256, GitHub-Actions-Run, Testbericht, vollständiger Windows-Download, kurzer deutscher Bedienhinweis, dokumentierte bekannte Lücken, Zustände **development / test candidate / pilot-approved / customer-approved**.
8. Bei ungeklärter Abnahme unverändert bisherige *geprüfte* Arbeitsversion verwenden. **Kein Push/Merge nur um Nummer 500 zu erreichen.**

### Große Hard-Gates im bewährten Fünfer-Rhythmus
- **485 (MVP):** *Kann ein nicht-technischer Nutzer einen zulässigen öffentlichen Auftrag bearbeiten und einen ehrlichen Bericht ausgeben?*
- **490 (Recherchebaum):** *Arbeiten Dorks, Web-/API-Suche, alter Crawler, Bilder, Graph, KI und kanonische Evidence nachweislich im selben Fall zusammen?*
- **495 (OPSEC):** *Verhindern Sicherheit, Rechte und Integrität echte Fehlverwendung/Datenverlust, und bleibt Windows stabil?*
- **500 (Frucht/Release):** *Sind beauftragte, klar abgegrenzte Pilotrecherchen mit überprüfbarem Dossier, unabhängiger Freigabe und sicherer Übergabe möglich?*

**Metriken und harte Schranken:** 0 unautorisierte Cross-Case-Lese- und Schreibvorgänge; 0 Auto-Freigaben ohne berechtigte Zweitprüfung; 100 % der als verifiziert ausgegebenen Behauptungen mit zugänglichem Originalbeleg+Hash; 100 % der freigegebenen Dossierarchive prüf-/wiederherstellbar; 0 tote Pfade der sechs Hauptmenüs; alle kritischen API-/Netzwerkfehler sichtbar; dokumentierte RAM/CPU/Antwortzeiten; Suchqualität und Entity-Precision aus realen Validierungsfällen, nicht fiktiven Leistungsprozentsätzen.

## IV. ABNAHME FÜR DIE ERSTEN KUNDENAUFTRÄGE

**Stufe 1 – noch keine Kundendaten (bis Gate 485):** ausschließlich synthetische/öffentliche, nicht-sensitive Trainingsaufträge; Build 481/482 sind technisch Teststände, keine Kundenfreigabe.

**Stufe 2 – begrenztes echtes Public-OSINT-Pilotmandat (frühestens nach Gate 485):** nur definierte öffentliche, datenschutzrechtlich zulässige Unternehmens-/Domain-/Organisations-/Publikationsrecherchen, dokumentierter Kunde/Auftrag/Scope und vertretbare Datenverarbeitung; **kein** vertraulicher personenbezogener Fall ohne gesonderte Rechts-/Sicherheitsprüfung. Kunde erhält klar als Analysten-Arbeitsbericht gekennzeichnete Ergebnisse oder, bei wirklicher Zweitprüfung, formal geprüftes Dossier.

**Stufe 3 – erweiterte Recherche (nach Gate 490/495):** live Crawler, weitere APIs, Bild-/Graph- und KI-Orchestrierung nach jeweiliger Leistungs-/Rechte-/OPSEC-Freigabe. Sensible Aufgaben erst nach bestätigter Datenklassifikation, technischem Restore, sicherem Transfer und individueller Rechtsprüfung.

**Stufe 4 – freigegebener Kundenbetrieb (Build-500-GO):** klar umschriebener Leistungsumfang, belastbarer Mandats-/Methodik-/Datenschutzvertrag, vorherige unabhängige Sicherheitsabnahme, Support/Incident/Retention und nachvollziehbarer Dossierexport. Kein Anspruch auf „gerichtsfest“ allein wegen Software-Hash.

## V. REFERENZEN UND OFFENE ENTSCHEIDUNGEN

**Vorhandene historische Fachpläne:** \`PHASE_16_MASTERPLAN_BUILD_361_TO_380.md\`, \`CRAWLER_ROADMAP_BUILD_370_TO_380.md\`, \`ROADMAP_457_460_CONSOLIDATED.md\`, \`PLAN_476_480_OPERATIVE.md\`, \`OPERATIONAL_CAPABILITY_RECOVERY_AUDIT.md\`. Dieser Plan integriert ihre Fähigkeiten/Verifikationsgrenzen, ersetzt aber die frühere Reihenfolge der **zukünftigen** Builds.

**Technische Originalquellen:** [RFC 9309 robots.txt](https://www.rfc-editor.org/rfc/rfc9309.html), [OWASP SSRF Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html), [DSGVO/Art. 6 EUR-Lex](https://eur-lex.europa.eu/legal-content/DE/TXT/?uri=CELEX:32016R0679), [EDPB Leitlinien berechtigte Interessen](https://www.edpb.europa.eu/our-work-tools/our-documents/guidelines/guidelines-12024-processing-personal-data-based-article-61_en). Provider-APIs und Rechtslage **vor** Anbindung/Produktivnutzung aktuell prüfen.

**Nicht auf der kritischen Route bis 500:** Darknet/Tor-Ausweitung, autonomes IP-/E-Mail-Wechseln, Personenerkennung aus Gesichtern, verdeckte Account-/Paywall-Abfragen, unsichere Social-/Leak-Massendatensammlung, komplexe Remote-Team-Cloudmigration. Bereits vorhandene Module werden erhalten und sicher isoliert, nicht mutwillig gelöscht; ihre Aktivierung ist eine gesonderte rechtliche und operative Entscheidung.

**Produktgrenze:** Die Software organisiert Quellen, Beweisführung und Prüfung. Ob ein konkreter Beleg rechtlich verwertbar ist, hängt zusätzlich von Beschaffung, Mandat, Verfahrensrecht, Integrität der Übergabe und zuständiger Stelle ab. Eine Behörde erhält ein nachvollziehbares Quellenpaket, keine automatisierte Garantie der Anerkennung.
