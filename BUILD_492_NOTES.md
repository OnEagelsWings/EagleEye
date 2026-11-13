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
* Weiterleitungen auf **denselben Server** (auch http→https und mit/ohne `www.`) werden bis zu dreimal
  verfolgt und als eigene Einträge in der WARC-Datei mitgesichert. Weiterleitungen auf einen **anderen
  Server** werden angezeigt und erst nach Bestätigung abgerufen, höchstens drei Schritte hintereinander.
  Relative Ziele werden aufgelöst; Schleifen und nicht-öffentliche Ziele werden abgelehnt.
* Alle aufgelösten Adressen werden zuerst geprüft und dann der Reihe nach versucht (z. B. IPv6, dann IPv4).
* Abruflimit: höchstens 12 Abrufe pro Minute je Nutzer und 6 je Zielserver; abgelehnte Versuche erreichen das Netz nicht.
* Grenzen: Webseiten bis 3 MB (auch nach dem Entpacken), PDFs bis 12 MB, 15 s. gzip/deflate wird entpackt;
  WARC-Datei und Hash enthalten die Bytes genau so, wie sie empfangen wurden.
* Zeichensatz in dieser Reihenfolge: Byte-Order-Mark, HTTP-Header, `<meta charset>` der Seite, UTF-8,
  eingeschränkte automatische Erkennung, windows-1252. Das Ergebnis steht im Dokumentkopf.
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

`trafilatura` (Apache-2.0), `warcio` (Apache-2.0), `numpy` (BSD-3, war über opencv schon installiert),
`rapidfuzz` (MIT), `anyascii` (ISC), `networkx` (BSD-3). Für alle gibt es Wheels für Windows und Linux.
`datasketch` und damit `scipy` (rund 107 MB) sind seit der Härtung entfallen.
Texterkennung braucht ein lokal installiertes **Tesseract** (Windows: Installer der UB Mannheim mit
Sprachpaket Deutsch). Ohne Tesseract funktionieren Tabellen und Überschriften trotzdem, und die Seite
nennt den Installationsweg.

## Härtung (Stufe 1 aus docs/PLAN_NACH_492.md)

| Befund | Umsetzung | Messung / Nachweis |
|---|---|---|
| F1 Texterkennung nicht nachholbar | Zweiter Lauf nur für OCR, wenn beim ersten Mal kein Tesseract installiert war; Struktur wird nicht doppelt angelegt | Test `test_text_recognition_can_be_caught_up_after_installation` |
| F2 Relative Weiterleitungen | Siehe Sicherheit oben | 4 Tests zu Kette, Bestätigung, Schleife, Grenze |
| F3 Komprimierte Antworten | gzip/deflate mit hartem Limit (Schutz gegen Entpack-Bomben) | Bombe, Brotli und defekte Daten werden abgelehnt |
| F4 Nur erste IP versucht | Alle geprüften Adressen der Reihe nach | Test mit nicht erreichbarem IPv6 |
| F5 Kein Abruflimit | 12 je Nutzer, 6 je Zielserver und Minute | Test: gedrosselter Versuch erreicht das Netz nicht |
| F6 Zeichensatz | Reihenfolge siehe oben | Latin-1 mit Meta-Angabe, cp1251 ohne Angabe, falscher Header |
| F7 PDF-Adressen | WARC + regulärer PDF-Import mit Titel, Autor und Datum aus dem PDF | Defekte, falsch deklarierte und zu große PDFs ohne interne Details abgelehnt |
| P1 Entitätenabgleich langsam | Vorberechnung je Name, Vorauswahl über Namensbestandteile, Zwischenspeicher je Fallstand | **1000 Entitäten: 33 s → 0,4 s**; Ergebnis identisch mit dem Vollvergleich auf vier erzeugten Datensätzen |
| P2 Quellfamilien bei jedem Aufruf neu | Fingerabdruck je Dokument gespeichert, neu nur bei geänderten Fundstellen | **500 Dokumente: 1,2 s einmalig, danach 0,03 s je Ansicht** |
| P3 Texterkennung blockiert die Seite | Hintergrundauftrag auf der vorhandenen Job-Engine, Fortschritt je Seite, Abbruch zwischen Seiten, Neustart setzt unterbrochene Aufträge zurück | Chromium-Test beobachtet „Seite n von 3“ und das selbstständige Ende |
| P4 scipy für MinHash | Eigener MinHash auf numpy | Mittlere Abweichung vom exakten Wert 0,011 bei 40 Zufallspaaren |
| S5 Backup ungeprüft | Wiederherstellungstest | Web-Belege, Texterkennung und Fingerabdrücke nach Wiederherstellung unverändert; Manipulation der wiederhergestellten WARC-Datei wird erkannt |

Nebenbefunde während der Arbeit, mit behoben:
* warcio entpackt gzip-komprimierte Antworten beim Lesen still. Die Integritätsprüfung liest jetzt die
  Rohbytes, sonst wäre jede komprimierte Antwort als „verändert“ gemeldet worden.
* Ein erster eigener MinHash mit kleinen linearen Multiplikatoren lag bei 0,95 statt 0,78. Die
  Hashfunktionen waren nicht unabhängig. Ersetzt durch splitmix64-Mischung.
* Kandidaten brauchen jetzt einen echten gemeinsamen Namensbestandteil. „M. B.“ zu „Max Beispiel“ oder
  „A. GmbH“ zu „Alpha GmbH“ wurden vorher vorgeschlagen.

Weiterhin nicht gemessen: echte Live-Abrufe, Zeichensatz- und PDF-Verhalten realer Server, Laufzeit der
Texterkennung an echten 160-Seiten-Scans auf dem Windows-Laptop.

## Zusammenführen (Stufe 2 aus docs/PLAN_NACH_492.md)

| Punkt | Umsetzung | Nachweis |
|---|---|---|
| S3 Herkunft in Evidence und Dossier | Beim Übergang „Quelle → Evidence“ trägt das Abrufereignis jetzt einen Block `web_capture` (Adresse, Archivquelle, Abrufzeit, HTTP-Status, Server-IP, SHA-256 von Antwort und WARC, Integritätsprüfung). Die URL gilt nicht mehr als „vom Nutzer angegeben“. Eine manipulierte WARC-Datei verhindert die Übernahme. Claim-Snapshots enthalten die Evidence-Herkunft, damit trägt auch der JSON-Export des Dossiers den Block – ohne Änderung am Dossier-Format. | `test_web_capture_provenance_travels_into_evidence`, `test_tampered_warc_blocks_promotion_to_evidence` |
| S3 Herkunft im Arbeitsbericht | Markdown-Export und Prüfseite zeigen Web-Herkunft und den WARC-Zustand zum Exportzeitpunkt. | `test_working_report_shows_web_capture_provenance` |
| S4 Recherchefund → Web-Beleg | Jeder Recherchefund bietet „Als Web-Beleg sichern“; die Adresse wird übernommen, abgerufen wird erst nach Bestätigung. Der Bezug bleibt über bestätigte Weiterleitungen erhalten. Der Fund zeigt danach, wann er gesichert wurde. | 5 Tests, u. a. fremde Funde vor jedem Netzkontakt abgelehnt |
| S2 Quellfamilien → Claims | Die Seite „Quellenunabhängigkeit“ zeigt je Familie den Evidence- und Herkunftsstand und warnt, wenn fast gleiche Texte verschiedenen Ursprüngen zugeordnet sind. Wer Quellen prüfen darf, bestätigt den gemeinsamen Ursprung mit Begründung; das schreibt die reguläre Herkunftsprüfung aus 456. | Ende-zu-Ende: Claim mit 3 übernommenen Texten + 1 eigenem zählt vorher 4, nachher 2 unabhängige Ursprünge |
| S1 Freigabemodell | **entfällt** – Entscheidung 13.11.2026: weiter OPSEC-Bestätigung je Abruf, keine vorherige Freigabe | – |

Nebenbefunde, mit behoben:
* Im Formular der Recherchefunde (483) waren Beschriftungen und Felder nicht verknüpft; Screenreader und
  Klick auf die Beschriftung erreichten die Felder nicht.
* Die Herkunftsprüfung aus 456 war nur als JSON-Schnittstelle erreichbar; Quellfamilien sind jetzt ein
  bedienbarer Weg dorthin.

## Schutzklassen und Empfängerstufen (Schritt 3.4)

* Jeder neue Befund bekommt beim Anlegen eine Schutzklasse: „offen“, „intern“ (Vorbelegung) oder
  „besonders schutzwürdig (Art. 9/10 DSGVO)“. Quelldokumente haben ebenfalls eine Klasse (Vorbelegung
  „offen“, weil EagleEye öffentliche Quellen speichert). Wirksam ist die strengere von beiden.
* Ändern geht an jeder Karte unter „Prüfen und Arbeitsbericht erstellen“, nur mit Begründung; die
  Historie bleibt erhalten. Ältere Befunde ohne Klasse gelten als „intern“. Eine manipulierte
  Markierung gilt ebenfalls als „intern“ und wird angezeigt.
* Der Arbeitsbericht ist in drei Stufen herunterladbar:

| Stufe | Enthält |
|---|---|
| intern | alle Befunde (wie bisher) |
| Mandant | nur geprüfte Befunde (Eigen- oder Zweitprüfung) mit wirksamer Klasse „offen“ |
| Behörde/Gericht | nur von einem zweiten Konto geprüfte Befunde mit unveränderter Quelle und unveränderter WARC-Datei; „offen“ und „besonders schutzwürdig“, nie „intern“ |

* Jeder Bericht nennt Stufe, Anzahl und die Gründe aller Auslassungen; jeder Export wird protokolliert.
* Tests: `tests/test_build492_markings.py` (5 Szenarien), Chromium-Check der Berichtsseite.

## Oberfläche (Stufe 4, vorgezogen)

* **Verständliche Fehlerseiten (U2):** Fordert ein Browser eine Seite an, erscheint bei Fehlern eine Seite
  im gemeinsamen Layout mit Erklärung, Fehlercode und Rückweg (vorherige Seite derselben Herkunft,
  Arbeitsablauf, Hauptansicht). API-Aufrufe, `fetch()` und Skripte bekommen weiterhin JSON.
* **Dokumentansicht (U1)** unter `/workbench/document`, `/documents458` leitet dorthin um (Sprungmarken
  bleiben erhalten). Neu: gemeinsames Layout, Fakten (Quelle, SHA-256, Extraktionsstand, Schutzklasse,
  Web-Herkunft), nächste Schritte, Filter nach Fundstellenart, Suche mit Hervorhebung.
* **Extraktionsprüfung in der Oberfläche:** Bisher ließ sich die Extraktion nur über die JSON-Schnittstelle
  freigeben; „Quelle → Evidence“ verwies auf eine Seite ohne Prüfformular. Jetzt: Freigeben oder Verwerfen
  mit Begründung und Bestätigung, nur mit Quellenprüfungsrecht, gegen veraltete Stände geschützt.
* Die neue Ansicht nutzt die Standard-Richtlinie `Referrer-Policy: same-origin`. Unter `no-referrer`
  (Build 489 für `/documents458`) sendet Chromium bei Formularen `Origin: null`, und der Formularschutz
  lehnt sie zu Recht ab. Auch `same-origin` gibt Fall-URLs nicht an fremde Seiten weiter.
* **Deutsche Statusbezeichnungen (U6)** auf Befund- und Berichtsseite statt Rohcodes; der Markdown-Bericht
  zeigt „Bezeichnung (Code)“.
* **Arbeitsablauf mit Zustand (U4):** Jeder Schritt zeigt seinen Stand (z. B. „3 Dokumente · 1 wartet auf
  Extraktionsprüfung“), offene Arbeit ist hervorgehoben. Oben steht der nächste sinnvolle Schritt
  (Quelle sichern → Extraktion prüfen → Evidence übernehmen → Befunde prüfen).
* Noch offen aus Stufe 4: Navigation verdichten (U3; der Ablauf hat 23 Schritte und ist auf dem Handy sehr
  lang) und Fundstellen im Seitenbild markieren (U5).

## Prüfen

```bash
python -m pytest -q tests/test_build492_intel.py tests/test_build492_hardening.py tests/test_build492_convergence.py tests/test_build492_markings.py tests/test_build492_ux.py tests/test_build490_server_selection.py tests/test_build488_candidates.py
python -m pytest -q tests/test_build492_browser.py   # benötigt Playwright + Chromium
```
