# Pilotbetrieb und Abnahme (Plan + Protokoll)

Ziel: In 4 Wochen mit 2–3 Analyst/innen und echten (unkritischen) Fällen prüfen, ob EagleEye im Alltag trägt, und Nachbesserungen sammeln.

## 1. Vorbereitung (Woche 0)

| # | Aufgabe | Wer | erledigt |
|---|---|---|---|
| V1 | Server bereitstellen, `deploy/init-secrets.sh`, `docker compose up -d` (README → Teambetrieb) | Admin | ☐ |
| V2 | Ersteinrichtung (Einrichtungscode aus `docker compose logs app`), 2FA für alle | Admin | ☐ |
| V3 | Netzausgang (Proxy/Tor) anlegen und in *Verwaltung → OPSEC* testen | Admin | ☐ |
| V4 | Jede Quelle in *Verwaltung → Quellen & Daten* mit „Testen“ prüfen; Ergebnis in Tabelle 4 eintragen | Admin | ☐ |
| V5 | API-Schlüssel hinterlegen (Companies House, OpenCorporates, ggf. weitere) | Admin | ☐ |
| V6 | Referenzdaten importieren (OpenSanctions – Lizenz beachten, ICIJ Offshore Leaks) | Admin | ☐ |
| V7 | Berichtslayout (Logo, Firmenname, Fußzeile) einstellen, Probe-Dossier als Word und PDF | Admin | ☐ |
| V8 | Standard-Löschfrist festlegen | Leitung/DSB | ☐ |
| V9 | Sicherung erstellen und Wiederherstellung auf Testsystem üben | Admin | ☐ |
| V10 | Schulung (docs/schulung) + OPSEC-Briefing | Leitung | ☐ |
| V11 | Rechtliche Unterlagen freigegeben (docs/compliance) | GF/DSB | ☐ |

## 2. Testfälle (Woche 1–3)

Je Testfall: Fallart, OPSEC-Stufe, verwendete Quellen, Dauer, Ergebnisqualität (1–5), Probleme.

| # | Szenario | Erwartung | Ergebnis | ok |
|---|---|---|---|---|
| T1 | Personensuche mit Name + Ort + Benutzername (OPSEC 1) | Treffer aus mehreren Quellen, Kandidatengruppen sinnvoll | | ☐ |
| T2 | Due Diligence Unternehmen/Geschäftsführer (Register, GLEIF, Wikidata, Sanktionslisten) | Beteiligungen im Graph, Red Flags nachvollziehbar | | ☐ |
| T3 | Investigativfall OPSEC 2 mit Deckname über Proxy | keine Abfrage am Proxy vorbei (Netzausgangs-Protokoll), Deckname im Dossier | | ☐ |
| T4 | OPSEC 3: sichtbare Quellen blockiert, Export nur Verantwortliche/Prüfung | Sperren greifen, verständliche Meldungen | | ☐ |
| T5 | Vermisstenfall mit Zeitleiste, Karte, Suchplakat | Plakat druckfähig, Zeitleiste korrekt | | ☐ |
| T6 | Verbindungsanalyse 3+ Personen, Pfadsuche | Pfade plausibel, Graph lesbar | | ☐ |
| T7 | Beweissicherung von 3 Webseiten, Beweispaket | Hashes im Manifest, Wayback-Link | | ☐ |
| T8 | Dossier-Vorlagen (Voll, Kurzprofil, Due Diligence, Vermisst) Word + PDF/A | Belegverweise vollständig, Layout korrekt | | ☐ |
| T9 | Vier-Augen-Freigabe inkl. Rückgabe mit Kommentar | Status/Benachrichtigung korrekt | | ☐ |
| T10 | Überwachung (täglich) über 1 Woche | nur neue Treffer gemeldet | | ☐ |
| T11 | Auftragsprüfung mit Warnsignal (Analyst/in → blockiert; Leitung → mit Begründung) | Dokumentation im Dossier | | ☐ |
| T12 | KI-Zusammenfassung (falls lokales Modell vorhanden) | nur belegte Sätze, Freigabe nötig | | ☐ |
| T13 | Fall abschließen → Löschfrist; Frist manuell in Vergangenheit → Erinnerung | Benachrichtigung einmalig | | ☐ |
| T14 | Wiederherstellung einer Sicherung | Daten vollständig, Audit-Kette gültig | | ☐ |

## 3. Kennzahlen

Zeit je Fall vorher/nachher · Anteil verworfener Treffer · Anzahl Quellen je Dossier · Fehler/Abstürze · Zufriedenheit (1–5) je Person.

## 4. Quellen-Livetest

| Quelle | Netzausgang | erreichbar | Treffer plausibel | Bemerkung |
|---|---|---|---|---|
| … | | ☐ | ☐ | |

## 5. Mängelliste

| # | Beschreibung | Schwere (A blockierend / B störend / C kosmetisch) | gemeldet von | behoben in Version |
|---|---|---|---|---|

## 6. Abnahme

Abnahmekriterien: alle Testfälle T1–T14 bestanden oder nur C-Mängel offen; keine offenen A-Mängel; rechtliche Unterlagen freigegeben; Sicherung/Wiederherstellung geübt.

☐ abgenommen · ☐ abgenommen mit Auflagen: […] · ☐ nicht abgenommen
Datum / Unterschrift Geschäftsführung: ____________ · Teamleitung: ____________
