# Plan nach Build 492 – Härten, Zusammenführen, Vertiefen

Stand 10. Nov. 2026. Grundlage: Selbstprüfung des Build-492-Codes, Messungen in der Entwicklungsumgebung
und Abgleich mit `ROADMAP_481_500_AI_RESEARCH_ORCHESTRATION.md` (Leitentscheidung „Ein Stamm“).
Jeder Befund ist gekennzeichnet: **[gemessen]** = Laufzeit/Größe hier gemessen (synthetische Daten, ein Lauf),
**[Code]** = am Quelltext nachvollzogen.

## Kernaussage

Build 492 funktioniert, ist aber an vier Stellen noch nicht belastbar: Es läuft **neben** bestehenden
Kontrollmechanismen statt durch sie, es **skaliert** bei großen Fällen nicht, einzelne Abläufe haben
**Sackgassen**, und die Qualität ist **an echten Daten nicht gemessen**. Deshalb zuerst härten und
zusammenführen, parallel messen, erst danach neue Fähigkeiten.

## 1. Befunde

### 1.1 Lücken und Fehler in Build 492

| # | Befund | Folge | Beleg |
|---|---|---|---|
| F1 | Wurden Fundstellen ohne installiertes Tesseract ergänzt, ist das Dokument als „bereits ergänzt“ gesperrt. | OCR lässt sich nach der Tesseract-Installation nicht nachholen. | [Code] `docstructure.enrich_document` |
| F2 | Relative Weiterleitungen (`Location: /de/`) bekommen keinen „Ziel sichern“-Knopf. | Sehr häufiger Fall endet ohne Handlungsmöglichkeit. | [Code] `intel492.web_page` |
| F3 | Server, die trotz `Accept-Encoding: identity` komprimieren, werden abgelehnt. | Ein Teil realer Seiten ist nicht sicherbar. | [Code] `webcapture._check_response` |
| F4 | Es wird nur die erste aufgelöste IP-Adresse versucht. | Bei nicht erreichbarem IPv6 schlägt der Abruf fehl, obwohl IPv4 ginge. | [Code] `PinnedTransport.get` |
| F5 | Kein Abruflimit. Die Sammler aus 469 drosseln pro Sitzung. | Versehentliches Dauerfeuer auf einen Zielserver möglich. | [Code] Vergleich mit `app469` |
| F6 | Zeichensatz nur aus dem HTTP-Header, nicht aus `<meta charset>`. | Umlaute/Kyrillisch können im Haupttext falsch ankommen. | [Code] `webcapture._charset` |
| F7 | Nur HTML/Text sicherbar. PDF-Adressen (Register, Berichte) werden abgelehnt. | Die wichtigste Dokumentart der Registerrecherche fehlt. | [Code] `TEXT_TYPES` |

### 1.2 Neben statt durch den Stamm

| # | Befund | Beleg |
|---|---|---|
| S1 | Die Web-Sicherung hat eine eigene OPSEC-Bestätigung. Das Freigabemodell für Live-Abrufe (genehmigte Suchabsicht, in Build 491 vor jedem Netzzugriff neu geprüft) und der Preflight des gesteuerten Crawlers werden nicht benutzt. | [Code] `collection/service.py`, `crawler/engine.py` |
| S2 | Quellfamilien (492) arbeiten auf Dokumenten. Die Zählung unabhängiger Quellen für Claims (456) arbeitet auf Evidence und erkennt nur **exakt** gleiche Texte. Beides ist nicht verbunden; Claims profitieren noch nicht. | [Code] `entity_lineage456._publication_fingerprint` |
| S3 | Der Arbeitsbericht (479) nennt den Dokument-Hash, aber WARC-Hash, Abrufzeit und Server-IP eines Web-Belegs nicht als eigene Angaben. | [Code] `report479.py` |
| S4 | Gesicherte Recherchefunde (483/487) haben keinen direkten Weg „diesen Treffer als Beleg sichern“. | [Code] |
| S5 | Backup erfasst die WARC-Dateien (ganzer Arbeitsordner), aber kein Test prüft ihre Integrität nach einer Wiederherstellung. | [Code] `recovery479.collect_files` |

### 1.3 Skalierung und Gewicht

| # | Befund | Messwert |
|---|---|---|
| P1 | Entitätenabgleich vergleicht jedes Paar, bei jedem Seitenaufruf und erneut bei jeder gespeicherten Entscheidung. | [gemessen] 100 Entitäten 0,6 s · 300: 2,8 s · **1000: 33 s** (488: 9 s) |
| P2 | Quellenunabhängigkeit wird bei jedem Aufruf komplett neu berechnet. | [gemessen] 200 Dokumente 1,8 s · 500: 4,8 s, zuzüglich Laden aller Fundstellen |
| P3 | Texterkennung läuft im Seitenaufruf, ohne Fortschritt. Bis 160 Seiten bei 300 dpi möglich. | [Code] Minutenlange Wartezeit ohne Rückmeldung; die vorhandene Job-Engine wird nicht genutzt |
| P4 | `datasketch` zieht `scipy` nach. | [gemessen] 107 MB zusätzliche Installation nur für MinHash |
| P5 | Erster Aufruf der Netzwerkanalyse lädt NetworkX. | [gemessen] 1,6 s Importzeit |
| P6 | Integritätsprüfung aller Web-Belege bei jeder Listenansicht. | [gemessen] 50 Belege à 1,3 MB: 0,14 s – derzeit unkritisch |

### 1.4 Oberfläche

| # | Befund | Beleg |
|---|---|---|
| U1 | Die Dokumentansicht (`/documents458`) hat ein eigenes, helles Layout ohne Navigation. Wer aus den neuen Seiten ein Dokument öffnet, landet in einer Sackgasse. | [Code] `app458.document_browser` |
| U2 | Abgelehnte Formulare zeigen rohes JSON (`{"detail": "…"}`) statt einer Seite mit Erklärung und Rückweg. | Im Chromium-Test beobachtet |
| U3 | Kopfnavigation hat 9 Einträge, der geführte Ablauf rund 20 Schritte, dazu die neue Übersicht. Die Roadmap (494) verlangt sechs klare Hauptmenüs. | [Code] `operations476.page` |
| U4 | Der Ablauf zeigt Schritte, aber keinen Zustand („2 PDFs ohne Texterkennung“, „4 ungeprüfte Kandidaten“). | [Code] |
| U5 | Fundstellen haben Seitenkoordinaten, die Ansicht zeigt sie aber nicht im Seitenbild. Tabellen/OCR sind nicht filterbar. | [Code] |
| U6 | Typbezeichnungen sind nur in der Netzwerkanalyse deutsch, sonst `person`/`company`. | [Code] |

### 1.5 Messung und Recht

| # | Befund |
|---|---|
| M1 | Kein einziger echter Live-Abruf geprüft (Umgebung sperrt externe Seiten). |
| M2 | Prüfsätze sind klein: 27 Namenspaare, je ein Testfall für Quellfamilien, OCR und Haupttext. |
| M3 | Build 492 nutzt PyMuPDF stärker als vorher (Tabellenerkennung). Die offene AGPL-Frage wird dadurch gewichtiger. |

## 2. Plan

Größen: **S** = klein, **M** = mittel, **L** = groß. Zuordnung zu Roadmap-Builds in Klammern.

### Stufe 1 – Härten (zuerst)

| Maßnahme | Behebt | Größe |
|---|---|---|
| OCR-Nachlauf erlauben, wenn Texterkennung beim ersten Mal fehlte | F1 | S |
| Relative Weiterleitungen auflösen; bis zu 3 Schritte nacheinander bestätigbar | F2 | S |
| gzip/deflate annehmen und dekodieren; WARC behält die Originalbytes | F3 | S |
| Alle geprüften Adressen der Reihe nach versuchen | F4 | S |
| Abruflimit je Nutzer und Zielserver, wie 469 | F5 | S |
| Rohbytes an Trafilatura geben (eigene Zeichensatzerkennung) | F6 | S |
| PDF-Adressen sichern: WARC + regulärer PDF-Import mit Fundstellen | F7 | M |
| Entitätenabgleich: Vorauswahl über Namensbestandteile statt aller Paare; Ergebnis je Fallstand zwischenspeichern | P1 | M |
| Quellfamilien: Fingerabdruck je Dokument einmal berechnen und speichern | P2 | S |
| Eigene MinHash-Berechnung, `datasketch`/`scipy` entfernen | P4 | S |
| Texterkennung über die vorhandene Job-Engine, mit Fortschritt und Abbruch | P3 | M |
| Wiederherstellungstest für WARC-Belege | S5 | S |

Ziel: 1000 Entitäten unter 2 s; 500 Dokumente unter 1 s nach dem ersten Aufruf; kein Seitenaufruf über 5 s.

### Stufe 2 – Zusammenführen („Ein Stamm“; Roadmap 491, 492, 494)

| Maßnahme | Behebt | Größe |
|---|---|---|
| Web-Sicherung an das Freigabemodell für Live-Abrufe binden (eine Freigabe, ein Protokoll, Widerruf wirkt sofort) | S1 | M |
| Quellfamilien als **Prüfkandidaten** in das Lineage-Register 456 geben; Claims zählen dann auch fast gleiche Übernahmen nur einmal | S2 | M |
| Web-Beleg-Herkunft (WARC-Hash, Abrufzeit, IP, Archivquelle) in Arbeitsbericht und Dossier | S3 | S |
| „Als Beleg sichern“ direkt am Recherchefund | S4 | S |

### Stufe 3 – Oberfläche gesund halten (Roadmap 494)

| Maßnahme | Behebt | Größe |
|---|---|---|
| Dokumentansicht ins gemeinsame Layout; Filter nach Fundstellenart; Suche im Dokument | U1, U5 | M |
| Fundstelle im Seitenbild markiert anzeigen | U5 | M |
| Verständliche Fehlerseiten für Browser-Aufrufe, mit Rückweg | U2 | S |
| Navigation auf sechs Hauptmenüs verdichten; Übersicht 492 darin aufgehen lassen | U3 | M |
| Arbeitsablauf mit Zustand je Schritt und einem „nächster sinnvoller Schritt“ | U4 | M |
| Einheitliche deutsche Bezeichnungen | U6 | S |

Abnahme wie in 492: Chromium bei 1280 px und 390 px, kein horizontales Scrollen, keine Konsolenfehler,
alle Felder beschriftet, jeder Weg per Klick erreichbar. Neu: kein Seitenende ohne Rückweg.

### Parallel – Messen (ab sofort; Roadmap 495, 498)

| Maßnahme | Behebt | Größe |
|---|---|---|
| Auswertungsordner `eval/build492/` mit Skript, das Kennzahlen als JSON-Nachweis schreibt | M2 | M |
| Prüfsätze: 200 Namenspaare, 50 Webseiten mit markiertem Haupttext, 20 Scans mit Solltext, Agenturtext-Korpus mit Übernahmen | M2 | M (Daten braucht Zuarbeit) |
| Live-Abnahme gegen eine freigegebene Liste öffentlicher Seiten und das Internet Archive | M1 | S, braucht Netzfreigabe oder Lauf auf dem Laptop |

### Stufe 4 – Vertiefen (nach Stufe 1–3)

Nach Nutzen geordnet:

1. **Beweiswert erhöhen:** Zeitstempel einer unabhängigen Stelle auf den WARC-Hash (RFC 3161; die Stelle sieht nur den Hash). Seitenbild der gerenderten Seite als zusätzlicher Beleg (Playwright ist bereits optionale Abhängigkeit), damit auch JavaScript-Seiten sicherbar werden.
2. **Beobachten statt einmal sichern:** erneute Sicherung mit Vergleich zur letzten Fassung. Deckt den Grundfall von changedetection.io ohne eigenen Dienst.
3. **Entitäten aus Dokumenten vorschlagen**, mit Fundstelle, als Prüfmaterial. Verbindet Dokument- und Graphseite; heute werden Entitäten von Hand angelegt.
4. **Abgleich mit Kontext:** gemeinsame Verbindungen und gemeinsames Vorkommen im selben Dokument als Zusatzhinweis neben dem Namen.
5. **Netzwerk im Graph statt daneben:** Gruppen und Brücken im interaktiven Graph (464) einfärben, Zeitscheiben über die Gültigkeitsdaten, Klick bis zur Fundstelle.
6. **Übernommene Passagen** innerhalb längerer Texte markieren, nicht nur ganze Dokumente.
7. **Texterkennung:** Sprachwahl (u. a. Hebräisch, Russisch, Arabisch), gemischte Seiten, Tabellen ohne Linien.
8. **Restliche Werkzeuge der Auswahl** (OpenSanctions, libpostal, auto-archiver, subfinder, Maigret) – erst mit OPSEC-Runbook und Lizenzentscheidung.

## 3. Offene Entscheidungen

| Frage | Warum sie zählt |
|---|---|
| Bleibt EagleEye rein privat, oder soll es weitergegeben bzw. für Kunden betrieben werden? | Bestimmt, ob PyMuPDF (AGPL) ersetzt werden muss und ob OpenSanctions-Daten (nur nicht-kommerziell frei) nutzbar sind. |
| Live-Tests: Netzfreigabe für die Entwicklungsumgebung oder Abnahmeskript auf dem Laptop? | Ohne eines von beiden bleibt M1 offen. |
| Entitätenvorschläge über spaCy-Modelle oder über das vorhandene lokale Ollama? | spaCy ist schneller und reproduzierbar, braucht aber Modell-Downloads; Ollama ist schon da, aber langsamer und schwankender. |
| Pull Request für Build 492 jetzt öffnen? | Erst dann laufen die Windows-Prüfungen. Zusätzlich hängt alles an dem noch nicht gemergten Stapel 479–491. |
