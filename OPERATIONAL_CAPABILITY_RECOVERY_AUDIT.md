# EagleEye – Funktionskonsolidierung (Ist-Stand Build 477)

**Auftrag:** bestehende leistungsfähige Ermittlungsfunktionen wieder nutzbar machen, statt sie durch isolierte Mini-Funktionen zu ersetzen. Diese Untersuchung basiert auf tatsächlich vorhandenen Routen und Quellmodulen; ein vorhandener GET-Pfad ist **kein** Nachweis einer erfolgreichen Live-OSINT-Recherche.

## Nachgewiesener Codebestand und operative Oberfläche

| Fachfunktion | Vorhandener Code | Status im Build 477 | Integration dieses PR |
| --- | --- | --- | --- |
| Recherche & Acquisition | `app448._research`, ältere Phase-19-Arbeitsketten | Panels vorhanden; Live-Abdeckung nicht belegt | Fallgebundener Direktlink |
| KI-Ermittlung | `app448._ai`, `app471` ff. | Lokale Analyse nur mit Ollama/Modell und Belegen; nicht als Fakt | Fallgebundener Direktlink |
| Evidence | `app448._evidence`, `phase20/evidence_claims_dossier447.py` | Evidence/Review implementiert | Fallgebundener Direktlink |
| Claims & Hypothesen | `app448._claims`, `phase20/evidence_claims_dossier447.py` | Claims- und Review-Unterbau vorhanden | Fallgebundener Direktlink |
| Graph/Timeline | `app448._analysis`, `app464` | Mehrere Analysefunktionen vorhanden; Qualität und Darstellung separat prüfen | Fallgebundener Direktlink |
| Living Dossier | `app448._dossier`, `phase20/evidence_claims_dossier447.py` | Dossierrevisionen implementiert | Fallgebundener Direktlink |
| Vier-Augen-Dossierfreigabe | `phase20/human_review449.py` | `execute_approved_export` prüft Freigabe und Rollentrennung; unabhängiger Live-Fall nicht abgenommen | Sichtbar über bestehende Dossier/Team-Ansichten; **keine** neue Export-API |
| Öffentliche API-Metadaten | `application/collectors469.py` | **Nur** Google DNS A, Verisign .com RDAP, Crossref DOI | Bestehende Routen nur verlinkt |
| Lokale Quelldokumente | `app458`, `app477` | Dokumente, Originalanker, Hash und Quelleninventar | Bestehende Routen nur verlinkt |
| Allgemeiner Crawler | `phase19/crawler_core425.py` | `network_executor_implemented: False` im Status des Moduls | **Nicht** als funktionierender Live-Crawler ausgegeben |
| KI-Qualität, Suchpräzision und Wiederherstellung | verschiedene Build-Checkpoints | Durch synthetische Tests allein nicht nachgewiesen | **Keine** Einsatzfreigabe behauptet |

## Erkannter Rückschritt

`app448.render_workspace` zeigt den vollständigen sechsstufigen Prozess `Recherche → KI → Evidence → Claims → Graph/Timeline → Dossier`. Gleichzeitig wird aus mehreren Ansichten zum historischen `/legacy` verlinkt. Spätere Build-450-Fall-/Qualifikations-Gates haben diesen Weg für den leeren Erststart zur bekannten Sackgasse gemacht. Im Build 476–477 entstand als Ersatz eine einfachere Schritt-für-Schritt-Seite, die zwar hilft, aber nicht alle bereits vorhandenen Fachansichten direkt nennt.

## Durchgeführte Konsolidierung

- Eigener **fallautorisierter** Werkzeugkatalog `/workbench/expert?case_id=...` mit Originalansichten statt Ersatzimplementierungen.
- Bestehende Legacy-Verweise in der Hauptansicht führen auf diese Werkzeugzentrale; dabei bleibt der aktive Fall erhalten.
- Über die Hauptnavigation und den geführten Ermittlungsablauf sichtbar, auch für wenig technikaffine Anwender.
- Ein Spezialwerkzeug wird **nur** als Link angezeigt, wenn der GET-Pfad in der aktuellen App tatsächlich registriert ist. Nicht registrierte Werkzeuge werden als noch nicht angebunden bezeichnet.
- Es werden keine bestehenden Autorisierungen, Review-Gates oder Audit-Trails umgangen; der Dossierexport bleibt an die bestehende Build-449-Freigabe gebunden.

## Abnahmekriterien des nächsten Integrationsschritts

1. Jeder der sieben ursprünglichen Experten-Tabs muss in einem echten Fall aus Firefox/Chromium laden; sichtbare Aktionen benötigen mindestens einen End-to-End-Test.
2. Bei einem öffentlichen Beispielauftrag müssen echte Treffer, Quellen-Provenienz, Gegenbelege, Claims, Graph und ein genehmigtes Dossier **ohne synthetische Netzwerk-Antworten** erprobt werden. FAIL/N/A statt erfundener Daten.
3. Wiederherstellung eines Fall-Arbeitsordners einschließlich Quelldateien, Sidecar-DBs und Freigabevermerken in neuem Programmordner nachweisen.
4. Keine personengebundene oder vertrauliche Auftragsverarbeitung ohne diese Sicherheits-, Restore- und Rechtsprüfung.

**Wichtig:** Dieser PR stellt die Navigation und das Verständnis vorhandener Funktionen wieder her; er ist keine pauschale Erklärung ihrer Einsatzreife.
