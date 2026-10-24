# EagleEye – vom Rechercheauftrag zum belastbaren Ermittlungsdossier

**Gilt für Build 478 mit dem Integrations-PR #80 und spätere Versionen, die diese Änderung übernehmen.** Noch keine Freigabe für sensible Live-Aufträge.

## 1. Den echten Fall öffnen
EagleEye über den Windows-Launcher starten und anmelden. `Neuen Fall anlegen` auswählen oder bestehenden regulären Fall öffnen. In der Fallansicht auf `Geführte Recherche` gehen.

## 2. Originalquellen sichern
Über `Öffentliche Quellen` (aktuell: DNS A, RDAP .com, Crossref DOI) begrenzte öffentliche Metadaten erfassen. Oder eigene rechtmäßig zugängliche PDF/TXT/MD-Dokumente unter `Dokumente und Originalanker` importieren. Urheberrecht, Verarbeitungsgrundlage und Drittanbieter-Übermittlung beachten. Metadaten und Fundstellen sind noch keine Wahrheitsfeststellungen.

## 3. Canonical Evidence von Dokumenten unterscheiden
Unter `Geführte Recherche → Evidence → Claims → Dossier` stehen fünf echte, fallgebundene Fortschrittsstufen. Wichtig: Ein als PDF/TXT importiertes Dokument ist **nicht automatisch** ein Evidence-Objekt der älteren Build-447-Abnahmekette. Für diese werden registrierte Quellen und Acquisition-/Content-Beobachtungen benötigt. Der aktuelle Bildschirm erklärt diese Trennung und kennzeichnet die Lücke ausdrücklich, statt einen unvollständigen Workflow als produktiv auszugeben.

## 4. Die bestehenden Profiwerkzeuge nutzen
`Alle Ermittlungswerkzeuge` führt unverändert zu `Evidence`, `Claims & Hypothesen`, `Graph & Timeline`, `Dossier` sowie `OPSEC & Team`. Ausschließlich dort werden die vorhandenen, rollengetrennten Review- und Exportgates benutzt. Ein Entwurf oder ein Quellenzitat ersetzt weder die unabhängige Prüfung noch ein belastbares Claim.

## 5. Das Ergebnis prüfen
Die neue Statusseite zeigt die tatsächlichen gespeicherten Zahlen: Dokumente, Evidence, akzeptierte Evidence, Claims, für Dossiers akzeptierte Claims, Dossier-Revisionen, freigegebene Revisionen und formale Exportdatensätze. Bei defekter kanonischer Quellenintegrität zeigt EagleEye statt Fortschritt einen Fehler 409.

## Noch offen
- Ein expliziter, berechtigter, nachweisbarer Workflow zum Überführen geprüfter importierter Dokumente in die kanonische Beschaffungskette fehlt derzeit. **Daher nicht behaupten, dass jedes PDF direkt einen Dossier-Claim speisen kann.**
- Live-Quellenabdeckung ist auf die bereits freigegebenen Adapter begrenzt, kein allgemeiner Crawler.
- Bei Build 480 muss der vollständige Windows-Offlinerestore von Dossier-Dateien nachweisen, dass auch JSON/DOCX/PDF/Manifest nach dem Umzug erreichbar und unverändert sind; die bisherige Linux-Abnahme allein genügt nicht.
- Keine selbst erteilte Vier-Augen-Freigabe, keine Identitätsverschmelzung aus Namensähnlichkeit, keine automatische Aufwertung von KI-Texten zu Tatsachen.

**Abnahmeziel:** Nutzer kann einen regulären Fall öffnen, Originalbelege lesen, die getrennten Register sicher unterscheiden, alte Evidence-/Claims-/Dossierwerkzeuge tatsächlich öffnen und am Ende nur durch den vorhandenen formalen Review-Prozess exportieren.
