# EagleEye – Universeller Ermittlungsalgorithmus (Investigation Kernel 1.0)

**Status:** Architektur- und Schnittstellenvertrag. Die ergänzende Python-Zustandsmaschine ist ein *reiner, nicht vernetzter Vertragskern*, keine bereits angeschlossene Live-KI. Implementierung/Abnahme in der zukünftigen Releasekette, keine Produktivfreigabe.

## A. Der Baum und seine feste Aufgabenteilung

- **Wurzelwerk:** klarer, deterministischer State- und Ereigniskern, ein Fall-/Datenmodell, nachhaltige Datenbankmigration, Zugriffskontrolle, unveränderliche Originale, Jobs, Tests.
- **Stamm:** ein einziger Fallprozess mit Mensch/Kern-KI/Fachagenten/Belegprüfung und Rückkopplung.
- **Rinde:** OPSEC, Rechtsgrundlage, Budget, Credential-Schutz, Case-Scope, Provenienz, kontrollierte externe Datenübertragung.
- **Äste:** Recherche-/Suchagent; Crawl- und Extraktionsagent; Dokumentenagent; Bild-/Medienagent; Entitäts-/Graphagent; Finanz-/Registeragent; Quellen-/Gegenbelegagent; optional gesondert autorisierter isolierter Darknet-Agent. **Nur benötigte Äste werden für den Auftrag aktiviert.**
- **Frucht:** quellengebundener Arbeitsbericht oder nach unabhängiger Prüfung formal freigegebenes Dossier DOCX/PDF mit Evidenzregister/Hash-Manifest und Audit-Trail.

Der leitende Ermittler ist der **Mensch**. Die Kern-KI ist ein fallbezogener *Chief Research Analyst* ohne administrative Sonderrechte. Der deterministische Kernel regelt Zustandswechsel und Freigaben. Fachagenten dürfen nur ein zugelassenes Werkzeug in definiertem Scope ausführen. Der KI-Entwurf **kann keine rechtlichen, fachlichen oder formalen Review-Gates selbst abnehmen**.

## B. Der Hauptalgorithmus

\`\`\`mermaid
flowchart TD
  A["Start EagleEye & Runtime/OPSEC-Check"] --> B["Hauptermittler: Fall, Zweck, Rechtsgrundlage, Scope"]
  B --> C["Kern-KI: Hypothesen, Teilfragen, Such-/Kostenplan"]
  C --> D{"Mensch prüft Plan, Limits und externe Datenweitergabe"}
  D -- "Ablehnen/überarbeiten" --> C
  D -- "GO im konkreten Scope" --> E["Deterministischer Kernel: Aufgaben und Berechtigungen"]
  E --> F["Such-/Dork-/Register-Agent"]
  E --> G["Crawler/Scraping-/Dokument-Agent"]
  E --> H["Bild-/Medien-/OCR-Agent"]
  E --> I["Entity/Graph/Finanz-Agent"]
  E --> J["Optional: isolierte und gesondert genehmigte Darknet-Recherche"]
  F --> K["Capture-Gateway: Originale, UTC, URI, SHA-256, Text-/Bildanker, Lizenz, Fall-ID"]
  G --> K
  H --> K
  I --> K
  J --> K
  K --> L["Evidence: Quellqualität, Duplikate, unabhängige Quellen, Gegenbelege"]
  L --> M["Kern-KI: Verknüpfen, Widersprüche, Unsicherheit, Lücken"]
  M --> N{"Beweislage ausreichend und Review vollständig?"}
  N -- "Nein: neue Forschungswelle" --> C
  N -- "Ja" --> O["Kern-KI: quellgebundener Dossierentwurf DOCX"]
  O --> P["Hauptermittler: Belege, Schlussfolgerungen, Datenschutz und Grenzen prüfen"]
  P -- "Zur Überarbeitung" --> C
  P -- "Prüffähig" --> Q["Unabhängige zweite Freigabe, falls formal erforderlich"]
  Q -- "Keine Freigabe" --> O
  Q -- "Freigabe" --> R["Versionierte Akte: PDF/DOCX/JSON/Manifest/Belegarchiv"]
  R --> S["Kontrollierte Übergabe an Auftraggeber/Behörde + Empfangs-/Auditnachweis"]
\`\`\`

## C. Nicht verhandelbare Arbeitsschritte

1. **BOOT:** Laufzeit, Schemaintegrität, verschlüsselter Datenspeicher wo aktiviert, Audit, Versionsstand, lokaler Browser; bei Fehler kein stiller Fallback in einen veralteten Workspace.
2. **CASE:** reguläre Fallakte, Auftraggeber, Fragestellung, zulässige Methoden, Scope, Betroffenen-/Datenkategorien und Rechtsgrundlage. Keine automatischen Nachforschungen aus bloßer Fallanlage.
3. **PLAN:** Kern-KI *schlägt* Teilfragen, Quellenklassen, Dork-Varianten, Agentenzuordnung, Prioritäten, Gegenhypothesen und maximale Ausgaben/Zeit/Seiten vor. Unklarer Scope = menschliche Klärung.
4. **APPROVE:** menschliches GO mit identifizierbarem Bearbeiter, Planversion/-Hash, erlaubten Agenten, Host-/Quellenliste, Budget, Außengrenzen und Offenlegung externer API-Übertragungen. Ein GO zu einer Quelle ist **kein** Pauschal-GO zu weiteren Quellen oder Darknet.
5. **DISPATCH:** Kernel erzeugt atomare, wiederaufnehmbare und fallautorisierte Agent-Jobs; keine Netzberechtigung für reine Text-KI. Jeder Job besitzt \`case_id\`, \`plan_id\`, \`task_id\`, zugelassene \`capability\`, Zeit-/Abfrage-/Bytebudget und Retry-/Stop-Regel.
6. **COLLECT:** Spezialagenten liefern nur strukturierte Funde mit Herkunft, negativen Treffern, Metadaten und Fehlerstatus; niemals direkt bestätigte Verdachtsmomente oder Identitäten. Quellen-URLs allein sind noch keine beweistauglichen Originale.
7. **CAPTURE:** bei rechtmäßigem Abruf unveränderte Rohbytes + SHA-256 + UTC-Zeit + endgültige geprüfte URL/Ort + Lizenz/Provider/Toolversion + anklickbare Text-/Bildanker + Verbindungs-/Methodenlog. Unverifizierbare Daten bleiben *Lead*.
8. **VERIFY:** kanonische Evidence, Quellunabhängigkeit, Fälschungs-/Manipulationswarnungen, zeitliche Widersprüche; menschliche Reviewentscheidung und Gegenbelege. Ohne Originalanker keine Aussage in der Rubrik „verifiziert“.
9. **SYNTHESIZE:** Kern-KI erzeugt eine Beleg-/Hypothesen-Matrix, offene Fragen und gezielte Nachrecherche-Vorschläge. Kein stilles Bestätigen eigener Agentenantworten als Wahrheit.
10. **ITERATE:** bei Lücke/Widerspruch neue Version des Plans und neues spezifisches GO, nicht automatisch unbegrenzt weiterrecherchieren. Abbruch, Pause und kontrollierte Wiederaufnahme.
11. **DRAFT:** KI erstellt einen **klar als Entwurf gekennzeichneten** strukturierten Bericht/DOCX mit Kurzfassung, Auftrag, Methodik, Tatsachen, Hypothesen, Gegenbelegen, Grenzen, Graph/Timeline und Belegliste.
12. **REVIEW:** Hauptermittler prüft Zitate gegen Originale, personenbezogene Risiken, Schlussfolgerungen, Abweichungen, Qualität der Bilder/Graphkanten und welche Feststellungen überhaupt tragbar sind. Fehlende Evidenz => zurück zur Plan-/Beschaffungsphase.
13. **RELEASE:** bei formell geprüftem Dossier echte rollengetrennte Vier-Augen-Freigabe (vorhandener Build-449-Kern). Das eigene Sign-off des Hauptermittlers ersetzt keine unabhängige Freigabe, wenn diese gefordert ist.
14. **DELIVER:** versionierte, reproduzierbare Ausgabe als DOCX/PDF/JSON/ZIP mit Originaldateien/Hashmanifest, Freigabeprotokoll, Übergabe-/Empfangslog und Aufbewahrungsregeln. Keine pauschale Zusage gerichtlicher Verwertbarkeit.

## D. Fachagenten-Kontrakt

Jede Fachfunktion implementiert denselben Adaptervertrag, gleichgültig ob Dork, Crawling, Bildauswertung, Register oder Graph.

**Task**: \`case_id, task_id, plan_hash, agent_kind, objective, inputs, allowed_tools, allowed_hosts, data_classification, network_approval, budget(max_requests,max_bytes,max_seconds,max_pages), stop_conditions, requested_by\`.

**Result**: \`case_id, task_id, agent_kind, status, raw_capture_refs, source_refs, lead_refs, candidate_entities, candidate_relations, evidence_suggestions, contradictions, negative_findings, errors, model/tool_version, started_utc, finished_utc, cost, trace_id\`.

**Kernregeln:**
- Ein Agent liefert **Kandidaten**, kein freigegebenes Dossier und keine endgültige Identitäts-/Schuldbehauptung.
- Ergebnis ohne tatsächlichen Abruf = \`lead_only\`; fehlendes Original = \`unverified\`; fehlerhafte Lizenz/Herkunft = \`quarantined\`. Keine automatische Bestätigung.
- Nulltreffer sind *nicht* der Nachweis der Nichtexistenz; Quellen können unzugänglich, veraltet, indexunvollständig oder lizenziert sein.
- KI kann Quelle und Daten *interpretieren*, aber nicht ihre eigene Antwort durch Selbstzitat verifizieren.
- Jede Agentenempfehlung zur Scope-Erweiterung muss zurück zur menschlichen Planfreigabe.

### Spezieller Darknet-Pfad

**Nicht Teil des normalen MVP-Workflows.** Nur nach ausdrücklicher gesonderter menschlicher Autorisierung, gesicherter Isolations-/Tor-Gateway-Prüfung, konkreter rechtlicher Quellenbewertung und eigener Aufbewahrungs-/Meldepolitik. Keine automatische Suche nach rechtswidrigen Inhalten, keine Anmeldung/Beschaffung über unautorisierte Zugänge und keine Verlagerung sensibler Fälle in externe KI. Scheitert die Gate-Prüfung, wird der Agent \`disabled_by_policy\` gemeldet; alle übrigen Ermittlungen funktionieren weiter.

## E. Einheitliches zustandsbasiertes Kernel-Protokoll

Der reine Python-Vertragskern unter \`src/eagleeye/application/orchestrator/investigation_kernel_contract.py\` modelliert:

\`created → scoped → plan_draft → plan_approved → agents_running → results_collected → evidence_reviewed → dossier_drafted → investigator_review → release_approved → delivered\`.

Zusätzliche Schleife: aus \`results_collected\` oder \`investigator_review\` mit dokumentiertem **REWORK** zurück zu \`plan_draft\`, dann erneut menschliches GO. Pausieren und Abbrechen mit protokolliertem Bearbeiter. Kein Schritt kann Agentenergebnisse ohne Quellenprüfung zu einem freigegebenen Dossier machen.

Der vorhandene \`IntelligenceOrchestrator127Service\` ist ein lokaler human-gated Plan- und Agentenkern, aber seine \`max_external_actions=0\`-Pläne führen noch keine reale Websuche aus. \`InvestigationPlanner413\`, \`AutonomousResearchWaves414\`, \`MultiAgentInvestigation415\` und \`MultiAgentContinuity416\` enthalten bereits Teile von Plan, Wellen, Spezialrollen und Zustandsintegrität. \`PersistentJobEngine\` verwaltet resumierbare Aufgaben. \`Build447/449\` enthält den kanonischen Evidence/Claim/Dossier-/Vier-Augen-Pfad. Diese Komponenten müssen durch **Adapter** verbunden werden, ohne parallele Agenten- oder Dossier-Datenbanken einzuführen.

## F. Konsequenzen für die Buildplanung

- **Sofort:** Dieser Kernel-Vertrag ist architekturverbindlich für die laufenden Build-482–485-Branches; deren vorhandene Dork-/Bild-/Graph-/Pilotfunktionen werden nicht zurückgesetzt.
- **Build 486:** Kernel als einheitliche echte Fall-Zustandsmaschine an 127 + 413/414/415/416 anbinden; persistente Job-/Freigabe-Logs, GUI-Fortschritt und STOP/RESUME. Bereits bestehende reale Fallarbeit bleibt nutzbar.
- **Build 487:** Agenten-Registry + Scope/Budget-/OPSEC-Gateway für Such-, Dork-, Register-, Dokumenten-, Bild-/Graph- und vorhandenen kontrollierten Crawler; nur rechtmäßig zugelassene Provider.
- **Build 488:** Agentenresultate in einem kanonischen Capture/Evidence- und Widerspruchs-Gateway, mit Negativfunden, Deduplikation, Quellunabhängigkeit und Lückenstatus.
- **Build 489:** Kern-KI als menschlich gesteuerter Research Director: *vorschlagen → GO → Agentenwelle → prüfen → Lücken → Replan*, einschließlich mehrsprachiger Suche und grafischer Ergebnisnavigation.
- **Build 490:** großer Zwei-Fall-End-to-End-Test vom Start über dynamische Agentenwahl bis zum überprüften Entwurf/Export und Restore auf Windows/Linux.
- **Build 491–500:** Quellenqualität, Temporal/Entity/Finance-Analyse, Hypothesen-Red-Team, OPSEC/UX, unabhängige Review-/DOCX-Pipeline und reale Kundenpilot-Qualifikation wie im Masterplan, **aber alle Module hängen am selben Kernel**.

Der Mindeststandard *in jedem Build* bleibt: normaler Fall startbar, Dorks/Bild/Graph/Quellen/Evidence und bestehender Bericht erreichbar, Windows-Doppelklick, Daten-/Fallrechte, Regression, Restore und klarer Fehler-/„nicht eingerichtet“-Status. Keine neuen Agentenfunktionen auf Kosten der bisherigen Nutzbarkeit.

## G. Konkrete Abnahme des Gesamtalgorithmus

Ein realer, unkritischer Beispielauftrag an \`example.com\` soll beweisen:
1. Hauptermittler eröffnet Fall und übermittelt Fragestellung an Kern-KI.
2. KI entwirft offen einen Plan mit mindestens zwei **unterschiedlichen** passenden Werkzeugen und benennt eine Gegenhypothese/Prüffrage.
3. Ohne GO **null** neue externe Abrufe. Nach GO nur erlaubte APIs/Hosts; andere Agenten bleiben deaktiviert.
4. Nach echtem Abruf liegen reproduzierbare Snapshots, Hashes und Quellenbeziehungen vor. Bloße Dork-Links sind als Leads markiert.
5. Eine absichtlich widersprüchliche Quelle führt zu Warnung/Nachrecherche, nicht stiller Bestätigung.
6. Ein Bild ohne EXIF/GPS erzeugt **keine** Ortsfeststellung; ein ähnlich benannter Rechtsträger wird nicht automatisch mit anderer Person/Organisation verschmolzen.
7. Kern-KI stellt einen gekennzeichneten Entwurf mit belegbaren Aussagen und Unsicherheiten bereit; menschlicher Prüfer kann ihn zurückweisen, dann beginnt neue genehmigte Welle.
8. Kein formaler Freigabeexport ohne getrennte Reviewerrolle. Bei gültigem Review entstehen DOCX/PDF/Hashmanifest mit vollständig verifizierbaren Quellen.
9. Programmneustart/Windows-ZIP-Versionswechsel/Offline-Restore erhalten **denselben** Fall inklusive Agenten-Jobs, Abbrüchen, Belegen, Versionen und Audit.
10. Ohne LLM/API-Key bleibt normale manuelle Fall-/Quellenarbeit benutzbar; externe Suchindikatoren werden nicht still übertragen.

**Releasekriterium:** ein dokumentierter Durchlauf in einem installierten Windows-Paket und eine unabhängige Prüfperson, nicht nur Tests einer Python-Klasse. Gerichtliche Verwertbarkeit oder rechtliche Autorisierung bleiben fallabhängig.
