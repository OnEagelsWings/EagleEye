# Build 492 – Quellen beweisfest sichern und auswerten

**Entwicklungsstand, nicht produktiv freigegeben.** Umsetzung der Stufen A1–A5 und B1 aus
[docs/OSINT_TOOL_AUSWAHL.md](docs/OSINT_TOOL_AUSWAHL.md). Basis ist der integrierte Stand Build 491.
Die installierte Paketnummer bleibt 490.0 (`eagleeye_pro/version.py`). Installer, Datenordner und
Release-Freigabe ändern sich nicht. Der Server startet jetzt die Fabrik `create_workspace_app492`.

## Bedienung

Geführte Recherche → neue Schritte an der passenden Stelle (durchgehend nummeriert):

| Phase | Schritt | Was passiert |
|---|---|---|
| 2 · Recherche | **Webseite als Beleg sichern** | Eine öffentliche Seite oder eine Fassung aus dem Internet Archive wird als **WARC-Original** (Archivstandard) gespeichert. Der Haupttext (ohne Menü/Werbung, mit Titel, Autor und Datum laut Seite) wird als normales Dokument mit Fundstellen angelegt. |
| 3 · Quellen | **Struktur & Texterkennung** | Ergänzt für PDFs Fundstellen für Tabellen, Überschriften und gescannte Seiten (OCR). Nur solange die Extraktion noch nicht geprüft ist. Originale und bestehende Fundstellen bleiben unverändert. |
| 3 · Quellen | **Quellenunabhängigkeit** | Zeigt „N Dokumente / M unabhängige Ursprünge“. Übernommene oder gespiegelte Texte werden zu Quellfamilien gruppiert. |
| 4 · Graph | **Netzwerkanalyse** | Zeigt Gruppen, Brückenpersonen, am stärksten vernetzte Entitäten und den am besten belegten Verbindungsweg. Export als GEXF (Gephi) und im FollowTheMoney-Format. |
| 4 · Graph | **Entity-Kandidaten prüfen** (bestehend) | Nutzt jetzt einen stärkeren Abgleich mit deutscher Begründung je Vorschlag. Entscheidungen laufen weiter über das bestehende 488-Prüfregister. |

Die Übersicht dazu liegt unter `/workbench/intel`.

## Sicherheit und OPSEC

* Webabrufe gibt es nur nach ausdrücklicher Bestätigung pro Abruf, mit CSRF- und Origin-Prüfung und nur mit der Rolle „Recherche“.
* Abrufziele:
  * Nur http/https auf den Ports 80/443, keine Zugangsdaten in der URL.
  * Keine internen, lokalen, Link-local- oder .onion-Adressen.
  * Alle DNS-Antworten müssen öffentlich sein. Die Verbindung wird an die geprüfte IP gebunden (Schutz gegen DNS-Rebinding).
* Weiterleitungen werden **nicht** verfolgt, sondern angezeigt und können bewusst einzeln gesichert werden.
* Grenzen: maximal 3 MB, 15 s, nur HTML/Text, keine Kompression.
* Gespeichert werden die WARC-Datei, ihr SHA-256 und der SHA-256 der Originalantwort. Die Liste prüft bei jedem Aufruf: Datensatz-Hash, Datei-Hash und Wiedergabe der gespeicherten Antwort. Bei Abweichung wird der Download verweigert.
* Die Wayback-Abfrage geht nur an `web.archive.org` und läuft als POST mit CSRF-Schutz.
* Kein Ergebnis wird automatisch zu Evidence, Claim, Identität oder Tatsache.

## Messwerte (reproduzierbar)

| Funktion | Messung | Ergebnis |
|---|---|---|
| Entitätenabgleich | Unabhängiger Prüfsatz `tests/benchmarks/entity_pairs_492_holdout.json` (27 Paare, nach der Abstimmung geschrieben, nie zum Nachjustieren genutzt) | Build 488: Präzision 0,61 / Trefferquote 0,73 → **Build 492: 0,93 / 0,93** |
| Entitätenabgleich | Abstimmungssatz `tests/benchmarks/entity_pairs_492.json` | 1,0 / 1,0 – **nur Entwicklungsdaten, nicht als Qualität zu werten** |
| Quellfamilien | Test-Fall: Agenturtext + 2 Übernahmen + 1 eigene Recherche | 4 Dokumente → 2 unabhängige Ursprünge, korrekt gruppiert |
| OCR | Gescannter Testsatz (Tesseract 5.3, deu+eng) | Text korrekt inkl. Umlauten, Ø-Sicherheit 95 % |
| Haupttext | Testseite mit Menü/Footer | Menü und Footer entfernt, Autor und Datum erkannt |
| UI | Chromium bei 1280 px und 390 px | kein horizontales Scrollen, keine CSP-Fehler, alle Felder beschriftet, Formularweg per Klick |

Noch **nicht** gemessen: echte Live-Websites und das Internet Archive (in der Entwicklungsumgebung
blockiert, Tests nutzen simulierte Antworten), Extraktionsgüte an 50 realen Seiten, OCR-Fehlerrate an
20 realen Scans, Duplikat-Precision/Recall an einem realen Agenturkorpus. Das ist der nächste Abnahmeschritt.

## Abweichungen vom Auswahlplan (mit Grund)

| Plan | Umsetzung | Grund |
|---|---|---|
| Docling | **zurückgestellt** | Benötigt PyTorch und Modell-Downloads von HuggingFace (mehrere GB). Weder auf dem Windows-Laptop sinnvoll noch hier testbar. Tabellen und Überschriften kommen vorerst aus dem vorhandenen PyMuPDF. |
| OCRmyPDF | **Tesseract direkt** (pytesseract, bereits Abhängigkeit) | OCRmyPDF braucht zusätzlich Ghostscript und erzeugt ein neues PDF. EagleEye braucht nur Fundstellen; das Original bleibt unverändert. |
| FollowTheMoney + nomenklatura | **FtM-Format als JSON-Export**, Abgleich mit RapidFuzz + anyascii | Das `followthemoney`-Paket braucht PyICU, das keine Standard-Wheels für Windows hat. Die Prüfentscheidungen laufen über das bestehende 488-Register. |
| B2 spaCy, B3 auto-archiver, B4 OpenSanctions, B5 libpostal, C1–C3 | **nicht in diesem Build** | B2/B4 brauchen Modell- bzw. Datendownloads und eine Lizenzentscheidung (OpenSanctions-Daten CC BY-NC). B3, B5 und C sind laut Plan erst nach einem OPSEC-Runbook vorgesehen. |

## Neue Abhängigkeiten

`trafilatura` (Apache-2.0), `warcio` (Apache-2.0), `datasketch` (MIT, zieht numpy/scipy),
`rapidfuzz` (MIT), `anyascii` (ISC), `networkx` (BSD-3). Für alle gibt es Wheels für Windows und Linux.
Texterkennung braucht ein lokal installiertes **Tesseract** (Windows: Installer der UB Mannheim mit
Sprachpaket Deutsch). Ohne Tesseract funktionieren Tabellen und Überschriften trotzdem, und die Seite
nennt den Installationsweg.

## Prüfen

```bash
python -m pytest -q tests/test_build492_intel.py tests/test_build490_server_selection.py tests/test_build488_candidates.py
python -m pytest -q tests/test_build492_browser.py   # benötigt Playwright + Chromium
```
