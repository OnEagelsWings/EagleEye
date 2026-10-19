# EagleEye — konsolidiertes UI-Audit und Entwicklungsvertrag (19.10.2026)

## Quelle und Geltungsbereich
Konsolidiert aus den Projektentscheidungen der Chats „EagleEye UI Audit“ und „Build 452 entwickeln“ sowie den in GitHub prüfbaren PRs #41, #45, #48–#53. Historische Aussagen aus Gesprächen sind **keine** aktuellen Testnachweise. Maßgeblich sind Git-HEAD, laufende CI, dokumentierte Sicherheitsgrenzen und reale Bedienprüfungen.

## Produktziel
Lokale private OSINT-/Investigation-Plattform mit menschlicher Kontrolle über Scope, Akquisition, Identitätszuordnung, Hypothesen, Claim-Freigabe und Dossier-Export. Unterscheide Rohhinweis, Evidence, Claim, Hypothese und verifizierten Befund. Belege sind versioniert und rückverfolgbar.

## Verbindliche UI-Verträge
1. **Fallbezogener Workspace:** alle Links/Aktionen halten den autorisierten `case_id`; niemals fremde Fall-Daten über URL- oder Session-Wechsel ausgeben.
2. **Aktueller Ermittlungszyklus:** aktive Schleife vor Historie; bei fehlender aktiver Schleife „awaiting authorization“ vor abgeschlossenem Verlauf; Empfehlungen nur aus ausgewähltem Zyklus.
3. **Dispatch-Budget:** Maximalbudget, gebundene/verwendete und verfügbare Einheiten sichtbar; Backend verweigert Überziehungen; doppelte Tickets sind idempotent.
4. **Document Intelligence:** TXT/MD/PDF mit begrenzter Extraktion, seiten- und versionsgebundenen Fundstellen; OCR-Bedarf kennzeichnen, keine stillschweigende OCR; Mensch prüft Extraktion.
5. **Herkunft und Mehrfachzählung:** Duplicate Payloads zählen nie als zusätzliche unabhängige Bestätigung. Source-Families und überprüfte unabhängige Ursprünge separat ausweisen.
6. **Entitäten:** mehrsprachige Aliase und Transliteration sind Kandidaten, kein automatischer Identitätsmerge.
7. **Dossier:** nachvollziehbare Trennung: Fakten, Unsicherheiten, Hypothesen, Gegenbelege, offene Fragen. Kein Revisions- oder Autorisierungs-Bypass.
8. **Ergonomie:** alle Hauptrouten per Tastatur erreichbar; klare Lade-, Leer-, Fehler-, Berechtigungs- und Verbindungszustände; responsives Layout. Keine rein kosmetisch funktionierenden Schaltflächen.
9. **Release-Wahrheit:** `/health` ist kein Nachweis für reale Recherche- und Produktionsfreigabe. Release-Readiness eigenständig ausweisen; `production_release_ready` bleibt false, bis operative Qualifikation positiv abgeschlossen ist.

## Phasen und Prioritäten
- **458 (PR #50/#51):** Dokumentenanker und CSP-konformer Upload; Datenkonsistenz, Zugriffsrechte und Upload-Interaktion prüfen.
- **459 (PR #52):** fallbezogene Navigation, historische Hauptwege und berechtigungsabhängige Links prüfen.
- **460 (PR #53):** vollständiger Linux/Windows-Checkpoint, Querverweise, Installation außerhalb des Source-Checkout, SHA256-/ZIP-Integrität, Datei- und Startverträge, UI-Bedienprüfung, Research-Workflow.
- **461–464 (geplant, keine Implementierungsbehauptung):** Bedieneffizienz, robuste Fehlerrückmeldungen, Provenienzvisualisierung, Graph-/Hypothesen-Ansicht mit bewussten Freigaben, fallbezogene Exporte.
- **465 (geplant):** vollständiger neuer reproduzierbarer Fünf-Build-Checkpoint.

## Harte Gates vor Merge/Feldtest
- CI, UI Audit, Build-460-Gesamttests Linux+Windows grün auf **demselben Head-SHA**.
- Kein nicht erklärter historischer Test-Ausschluss; jede Ausnahme hat konkrete Referenz und begründete Ablösung.
- Download-Archiv liegt vor, SHA256 passt, ZIP ist lesbar, Installer und Starter im Archiv vorhanden.
- Neue Fall- und Dokument-Endpunkte haben objektbezogene Autorisierung.
- Keine Claim-Wahrheitsannahme, automatische Identitätsverschmelzung oder autonome Scope-Erweiterung.
- Reale Zielsystem- und Quellenqualifikation separat; nicht durch Mock-Tests ersetzen.
- Merge erst nach Prüfung der gestapelten PR-Basis und grünen erforderlichen Checks.

## Ergebnis dieser Konsolidierung
Die Build-460-Checkpoint-Workflowdatei prüft zusätzlich das erzeugte Archiv einschließlich SHA256, ZIP-Lesbarkeit und erforderlicher Startdateien. Ein laufender Workflow ist kein bestandener Test. Bis alle Gates verifiziert sind, bleibt der Build ein Entwicklungsstand.
