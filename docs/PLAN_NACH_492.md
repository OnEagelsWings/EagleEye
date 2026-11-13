# Plan nach Build 492 – Härten, Zusammenführen, Vertiefen

Stand 10. Nov. 2026. Grundlage: Selbstprüfung des Build-492-Codes, Messungen in der Entwicklungsumgebung,
Abgleich mit `ROADMAP_481_500_AI_RESEARCH_ORCHESTRATION.md` (Leitentscheidung „Ein Stamm“) und die vier
übertragbaren Punkte aus [PALANTIR_GOTHAM_ARCHITEKTURANALYSE.md](PALANTIR_GOTHAM_ARCHITEKTURANALYSE.md).
Jeder Befund ist gekennzeichnet: **[gemessen]** = Laufzeit/Größe hier gemessen (synthetische Daten, ein Lauf),
**[Code]** = am Quelltext nachvollzogen.

## Kernaussage

Build 492 funktioniert, ist aber an vier Stellen noch nicht belastbar: Es läuft **neben** bestehenden
Kontrollmechanismen statt durch sie, es **skaliert** bei großen Fällen nicht, einzelne Abläufe haben
**Sackgassen**, und die Qualität ist **an echten Daten nicht gemessen**. Deshalb zuerst härten und
zusammenführen, parallel messen, erst danach neue Fähigkeiten.

Die Gotham-Analyse ergänzt eine fünfte Schwäche, die älter ist als Build 492: Das **Datenmodell der
Entitäten ist zu dünn**. Eine Entität ist nur ein Name mit Notizfeld. Das begrenzt Abgleich, Auswertung
und Bericht stärker als jede fehlende Einzelfunktion. Deshalb bekommt das Datenmodell eine eigene Stufe,
vor dem Umbau der Oberfläche und vor neuen Fähigkeiten.

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

### 1.6 Datenmodell (aus der Gotham-Analyse)

| # | Befund | Folge | Beleg |
|---|---|---|---|
| G1 | Eine Entität besteht aus Art, Bezeichnung und einem freien Notizfeld. Geburtsdatum, Anschrift, Registernummer haben keinen eigenen Platz, keine Fundstelle und keinen Gültigkeitszeitraum. | Der Abgleich kann nur Namen vergleichen. Widersprüchliche Angaben sind nicht sichtbar. Der FollowTheMoney-Export enthält praktisch nur Namen. | [Code] `entity_registry461` (Tabelle `entity461`) |
| G2 | Sechs fest einprogrammierte Entitätsarten. Beziehungsarten sind Freitext bis 128 Zeichen. | „Geschäftsführer“, „GF“ und „managing director“ sind drei verschiedene Beziehungen. Auswertungen nach Beziehungsart sind unzuverlässig. | [Code] `KINDS`, `create_relation` |
| G3 | Rechte gelten je Fall und Rolle. Einzelne Dokumente, Befunde und Entitäten tragen keine Schutzmarkierung. Arbeitsbericht und Vier-Augen-Export kennen keine Empfängerstufe. | Ein Bericht für den Mandanten lässt sich nicht automatisch von internen Arbeitsnotizen und besonders schutzwürdigen Daten trennen. | [Code] `report479`, `human_review449`: keine Schwärzung, keine Empfängerangabe |
| G4 | Das Entitätenregister ist eine eigene SQLite-Datei. Acht Stellen im Code öffnen sie jeweils per zusammengesetztem Dateipfad. Dokumente, Fundstellen und Prüfentscheidungen liegen in der Hauptdatenbank. | Keine Transaktion kann Entität, Fundstelle und Prüfung gemeinsam absichern. Verweise zwischen den Dateien werden nicht geprüft. | [Code] `app462`–`app466`, `app470`, `entities488`, `intel492` |

Bereits vorhanden und deshalb wiederzuverwenden statt neu zu bauen:

* **Schutzklassen:** Ältere Module führen eine Schutzklasse je Dokumentkandidat (`sensitivity_class`, u. a.
  `ordinary_public`, `special_category`, `high_impact_sensitive`) und eine rechtliche Einstufung je Claim. [Code] `build273`, `build277`, `build251`
* **Entitäten-Bindungen mit Herkunft:** Modul 437 bindet Quellobjekte mit Zuverlässigkeit und
  Herkunftsangaben an Entitäten. Es ist im Anwendungskontext registriert, wird im aktuellen geführten Ablauf
  aber nicht benutzt. [Code] `entity_resolution437`, `app_context`
* **Übernahme mit Erhalt des Originals:** Build 478 hat ältere Notizen in die Hauptdatenbank übernommen, die
  Ursprungsdatei behalten und Übernommenes zur erneuten Prüfung markiert. Das ist die Vorlage für G4. [Code] `findings478`

## 2. Plan

Größen: **S** = klein, **M** = mittel, **L** = groß. Zuordnung zu Roadmap-Builds in Klammern.

### Stufe 1 – Härten (zuerst) – **umgesetzt 11.11.2026**, Nachweise in [BUILD_492_NOTES.md](../BUILD_492_NOTES.md#härtung-stufe-1-aus-docsplan_nach_492md)

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

Erreicht: 1000 Entitäten 0,4 s; 500 Dokumente 0,03 s nach dem ersten Aufruf (1,2 s einmalig); Texterkennung läuft im Hintergrund. Gemessen in der Entwicklungsumgebung, nicht auf dem Windows-Laptop.

### Stufe 2 – Zusammenführen („Ein Stamm“; Roadmap 491, 492, 494) – **S2, S3, S4 umgesetzt 12.11.2026; S1 entfällt (Entscheidung 13.11.2026)**

Befund bei der Umsetzung von S1: Das Freigabemodell aus 491 (genehmigte Suchabsicht und Suchanfrage) wird
in der Dienstschicht erzwungen, ist aber in der Oberfläche nirgends bedienbar; Absichten und Anfragen werden
nur in Tests angelegt. S1 ist damit eine Produktentscheidung (Pflicht-Freigabe vor Web-Abrufen, wer freigibt)
und wartet auf diese Entscheidung.

**Entscheidung 13.11.2026:** Web-Abrufe bleiben ohne vorherige Freigabe; es gilt weiter die OPSEC-Bestätigung je Abruf mit Abruflimit und Protokoll. S1 entfällt.

| Maßnahme | Behebt | Größe |
|---|---|---|
| Web-Sicherung an das Freigabemodell für Live-Abrufe binden (eine Freigabe, ein Protokoll, Widerruf wirkt sofort) | S1 | M |
| Quellfamilien als **Prüfkandidaten** in das Lineage-Register 456 geben; Claims zählen dann auch fast gleiche Übernahmen nur einmal | S2 | M |
| Web-Beleg-Herkunft (WARC-Hash, Abrufzeit, IP, Archivquelle) in Arbeitsbericht und Dossier | S3 | S |
| „Als Beleg sichern“ direkt am Recherchefund | S4 | S |

### Stufe 3 – Datenmodell stärken (Roadmap 492, 494, 496)

**Entscheidungen 13.11.2026:** 3.1–3.3 erst, wenn der Stapel 479–491 in `main` ist (er bewegt sich noch).
Bis dahin wird 3.4 für Dokumente und Befunde umgesetzt und Stufe 4 vorgezogen. Empfängerstufen:
„intern“, „Mandant“, „Behörde/Gericht“.

Reihenfolge ist zwingend: erst eine Datenbank, dann Typen, dann Eigenschaften, dann Markierungen.

| Schritt | Maßnahme | Behebt | Größe |
|---|---|---|---|
| 3.1 | **Eine Datenbank.** Entitäten und Beziehungen in die Hauptdatenbank überführen. Ein einziger Zugriffspunkt ersetzt die acht Pfadkonstruktionen. Übernahme nach dem Muster von Build 478: Ursprungsdatei bleibt erhalten, Übernahme wird protokolliert, Wiederholung ist gefahrlos. | G4 | M |
| 3.2 | **Typenregister.** Entitätsarten, Eigenschaftsarten und Beziehungsarten als Daten, mit deutscher Bezeichnung, erlaubten Endpunkten und Zuordnung zu FollowTheMoney. Vorbelegt mit den sechs heutigen Arten. Vorhandene Freitext-Beziehungen bleiben gültig und werden als „noch nicht zugeordnet“ geführt. | G2, U6 | M |
| 3.3 | **Eigenschaften als belegte Aussagen.** Je Eigenschaft: Art, Wert, normalisierter Wert, Fundstelle, Gültigkeitszeitraum, Prüfstatus, Hash. Anlegen direkt aus der Dokumentansicht („aus dieser Fundstelle übernehmen“). Abweichende Werte derselben Art stehen nebeneinander, keiner überschreibt den anderen. Erwähnungen in Quellen laufen über die vorhandenen Bindungen aus 437. | G1 | L |
| 3.4 | **Schutzmarkierung und Empfängerstufe.** Markierung je Dokument, Befund und Eigenschaft mit dem vorhandenen Schutzklassen-Vokabular; beim Anlegen Pflicht, mit sinnvoller Vorbelegung. Arbeitsbericht und Export bekommen eine Empfängerstufe und lassen alles darüber weg – sichtbar ausgewiesen, nicht stillschweigend. | G3 | M |

Was danach unmittelbar besser wird:

* Der Entitätenabgleich kann Geburtsdatum, Registernummer oder Anschrift als starke Hinweise werten, statt
  nur Namen zu vergleichen.
* Der FollowTheMoney-Export enthält echte Eigenschaften und einheitliche Beziehungsarten.
* Die Netzwerkanalyse kann nach Beziehungsart filtern.

Abnahme:

| Schritt | Kriterium |
|---|---|
| 3.1 | Anzahl und Inhalt von Entitäten und Beziehungen vor und nach der Übernahme identisch (Hash über den Export). Ein erzwungener Fehler beim Speichern einer Prüfentscheidung macht auch die zugehörige Entitätsänderung rückgängig. Sicherung und Wiederherstellung bestehen. |
| 3.2 | Jede Entität hat eine registrierte Art. Im Referenzfall sind mindestens 90 % der Beziehungen einer registrierten Art zugeordnet. |
| 3.3 | Keine Eigenschaft ohne Fundstelle (technisch erzwungen). Auf einem erweiterten Prüfsatz mit Zusatzangaben steigt die Präzision des Abgleichs bei gleicher Trefferquote. |
| 3.4 | Ein Export für die Stufe „Mandant“ enthält nachweislich kein als intern oder besonders schutzwürdig markiertes Element; der Bericht nennt, wie viele Elemente ausgelassen wurden. |

Risiko: 3.1 ist eine Datenübernahme auf dem Arbeitsrechner. Sie braucht vorher eine Sicherung, einen
Probelauf auf einer Kopie und einen Rückweg. Erst nach bestandener Wiederherstellungsprüfung ausliefern.

### Stufe 4 – Oberfläche gesund halten (Roadmap 494)

| Maßnahme | Behebt | Größe |
|---|---|---|
| Dokumentansicht ins gemeinsame Layout; Filter nach Fundstellenart; Suche im Dokument | U1, U5 | M |
| Fundstelle im Seitenbild markiert anzeigen | U5 | M |
| Verständliche Fehlerseiten für Browser-Aufrufe, mit Rückweg | U2 | S |
| Navigation auf sechs Hauptmenüs verdichten; Übersicht 492 darin aufgehen lassen | U3 | M |
| Arbeitsablauf mit Zustand je Schritt und einem „nächster sinnvoller Schritt“ | U4 | M |
| Einheitliche deutsche Bezeichnungen (kommen aus dem Typenregister, Schritt 3.2) | U6 | S |
| Entitätsseite mit Eigenschaften, Fundstellen und „Umfeld anzeigen“ (alle verknüpften Dokumente, Fundstellen, Entitäten) | G1 | M |
| Fallübersicht von oben: filtern und zählen nach Art, Quelle, Zeitraum, Prüfstatus, Schutzklasse | – | M |
| Seiten über Vorlagen mit automatischem Escaping statt verketteter Zeichenketten, beginnend bei neuen Seiten | – | M, schrittweise |

Abnahme wie in 492: Chromium bei 1280 px und 390 px, kein horizontales Scrollen, keine Konsolenfehler,
alle Felder beschriftet, jeder Weg per Klick erreichbar. Neu: kein Seitenende ohne Rückweg.

### Parallel – Messen (ab sofort; Roadmap 495, 498)

| Maßnahme | Behebt | Größe |
|---|---|---|
| Auswertungsordner `eval/build492/` mit Skript, das Kennzahlen als JSON-Nachweis schreibt | M2 | M |
| Prüfsätze: 200 Namenspaare, 50 Webseiten mit markiertem Haupttext, 20 Scans mit Solltext, Agenturtext-Korpus mit Übernahmen | M2 | M (Daten braucht Zuarbeit) |
| Live-Abnahme gegen eine freigegebene Liste öffentlicher Seiten und das Internet Archive | M1 | S, braucht Netzfreigabe oder Lauf auf dem Laptop |

### Stufe 5 – Vertiefen (nach Stufe 1–4)

Nach Nutzen geordnet:

1. **Beweiswert erhöhen:** Zeitstempel einer unabhängigen Stelle auf den WARC-Hash (RFC 3161; die Stelle sieht nur den Hash). Seitenbild der gerenderten Seite als zusätzlicher Beleg (Playwright ist bereits optionale Abhängigkeit), damit auch JavaScript-Seiten sicherbar werden.
2. **Beobachten statt einmal sichern:** erneute Sicherung mit Vergleich zur letzten Fassung. Deckt den Grundfall von changedetection.io ohne eigenen Dienst.
3. **Entitäten und Eigenschaften aus Dokumenten vorschlagen**, mit Fundstelle, als Prüfmaterial. Verbindet Dokument- und Graphseite; heute werden Entitäten von Hand angelegt. Setzt Schritt 3.3 voraus.
4. **Abgleich mit Kontext:** gemeinsame Verbindungen und gemeinsames Vorkommen im selben Dokument als Zusatzhinweis neben Namen und Eigenschaften.
5. **Netzwerk im Graph statt daneben:** Gruppen und Brücken im interaktiven Graph (464) einfärben, Zeitscheiben über die Gültigkeitsdaten, Klick bis zur Fundstelle.
6. **Übernommene Passagen** innerhalb längerer Texte markieren, nicht nur ganze Dokumente.
7. **Texterkennung:** Sprachwahl (u. a. Hebräisch, Russisch, Arabisch), gemischte Seiten, Tabellen ohne Linien.
8. **Ereignisse mit Zeit und Ort** als eigener Datensatz, verknüpft mit Entität und Fundstelle; daraus Zeitleiste und einfache Karte.
9. **Suchanfrage als Baum:** einmal als Und/Oder/Nicht formulieren, je Quelle übersetzen.
10. **Fallpakete für Teamarbeit:** Fälle mit Hashes in eine zweite Installation einspielen, mit Konfliktanzeige statt Überschreiben.
11. **Restliche Werkzeuge der Auswahl** (OpenSanctions, libpostal, auto-archiver, subfinder, Maigret) – erst mit OPSEC-Runbook und Lizenzentscheidung. OpenSanctions und libpostal profitieren direkt von Schritt 3.3.

## 3. Offene Entscheidungen

| Frage | Warum sie zählt |
|---|---|
| Bleibt EagleEye rein privat, oder soll es weitergegeben bzw. für Kunden betrieben werden? | Bestimmt, ob PyMuPDF (AGPL) ersetzt werden muss und ob OpenSanctions-Daten (nur nicht-kommerziell frei) nutzbar sind. |
| Live-Tests: Netzfreigabe für die Entwicklungsumgebung oder Abnahmeskript auf dem Laptop? | Ohne eines von beiden bleibt M1 offen. |
| Entitätenvorschläge über spaCy-Modelle oder über das vorhandene lokale Ollama? | spaCy ist schneller und reproduzierbar, braucht aber Modell-Downloads; Ollama ist schon da, aber langsamer und schwankender. |
| Welche Empfängerstufen und Schutzklassen brauchst du in der Praxis? Vorschlag: Empfänger „intern“, „Mandant“, „Behörde/Gericht“; Schutzklassen aus dem vorhandenen Vokabular. | Bestimmt Schritt 3.4 und den Aufbau von Bericht und Dossier. |
| Datenübernahme (Schritt 3.1) vor oder nach dem Zusammenführen des Stapels 479–491 in `main`? | Eine Übernahme auf einem noch nicht gemergten Stand muss später erneut abgesichert werden. Empfehlung: erst zusammenführen. |
| Pull Request für Build 492 jetzt öffnen? | Erst dann laufen die Windows-Prüfungen. Zusätzlich hängt alles an dem noch nicht gemergten Stapel 479–491. |
