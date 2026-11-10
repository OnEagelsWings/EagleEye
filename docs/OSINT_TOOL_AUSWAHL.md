# Auswahl externer Systeme für EagleEye (Stand 9. Nov. 2026)

> **Umsetzungsstand:** A1–A5 und B1 sind in Build 492 umgesetzt, mit begründeten Abweichungen (Docling zurückgestellt, Tesseract direkt statt OCRmyPDF, FtM-Format ohne PyICU-Paket). Siehe [BUILD_492_NOTES.md](../BUILD_492_NOTES.md).

**Grundlage:** Lücken aus `BUILD_455_GOAL_GAP_AUDIT.md`, `OPERATIONAL_CAPABILITY_RECOVERY_AUDIT.md`
und `PLAN_476_480_OPERATIVE.md`, abgeglichen mit dem vorhandenen Code (`pyproject.toml`, `src/`).
Die Lizenzen wurden am 9.11.2026 direkt bei den Quell-Repositories abgefragt.

**Auswahlkriterien:**
1. Das System schließt eine **dokumentierte Lücke** und ist nicht schon vorhanden.
2. Der Nutzen lässt sich **messen**, mit einer Kennzahl und einem Testdatensatz.
3. Es ist **quelloffen**. Wird es in EagleEye eingebunden, muss die Lizenz freizügig sein. GPL/AGPL nur als getrennter Prozess.
4. Es passt zu den Grundsätzen von EagleEye: Original und Interpretation bleiben getrennt, Ergebnisse sind nur Kandidaten, nichts wird automatisch bestätigt, OPSEC vor Reichweite.

---

## 1. Ergebnis auf einen Blick

| Prio | System | Lizenz | Schließt Lücke (Audit-Reifegrad) | Einbindung |
|---|---|---|---|---|
| **A1** | **Docling** + **OCRmyPDF** (Tesseract ist schon vorhanden) | MIT / MPL-2.0 | Document Intelligence (50–65 %) | Bibliothek / Unterprozess |
| **A2** | **Trafilatura** | Apache-2.0 | Web-Erfassung, Haupttext, Metadaten; ersetzt den fehlenden Crawler-Executor teilweise | Bibliothek |
| **A3** | **warcio** (+ Wayback-CDX-API) | Apache-2.0 | Historisches Web (75–85 %), gerichtsfeste Web-Belege | Bibliothek |
| **A4** | **datasketch** (MinHash/LSH) | MIT | Unabhängigkeit der Quellen (55–70 %), Build-456-Ziel „20 Erwähnungen / 3 Ursprünge“ | Bibliothek |
| **A5** | **FollowTheMoney** + **nomenklatura** + **RapidFuzz** | MIT | Entity Resolution / mehrsprachige Aliase (70–80 %), Organisationen (55–70 %) | Bibliothek |
| **B1** | **NetworkX** | BSD-3 | Analyse im Beziehungsgraphen (70–80 %) | Bibliothek |
| **B2** | **spaCy** (+ mehrsprachige Modelle) | MIT | Entitäten aus Dokumenten vorschlagen (für Document Intelligence und den KI-Ermittler) | Bibliothek |
| **B3** | **Bellingcat auto-archiver** (nutzt yt-dlp) | MIT | Social Media und Videos als Beleg sichern | isolierter Prozess |
| **B4** | **OpenSanctions**-Daten (FtM-Format) | Code MIT, **Daten CC BY-NC 4.0** | Abgleich mit Sanktions- und PEP-Listen | Offline-Datenimport |
| **B5** | **libpostal** | MIT | Adressen normalisieren und abgleichen | Bibliothek (C, Bindings) |
| **C1** | **subfinder** (nur passiv) + Certificate Transparency (crt.sh) | MIT | Domain-/Infrastruktur-OSINT (65–80 %) | isolierter Prozess |
| **C2** | **Maigret** + WhatsMyName-Definitionen | MIT / CC BY-SA 4.0 | Benutzernamen-Kandidaten für Personen-OSINT | isolierter Prozess (wie in Build 213 vorgesehen) |
| **C3** | **changedetection.io** | Apache-2.0 | Quellen dauerhaft auf Änderungen überwachen | eigener Dienst (Docker), Import per API |

Die Prioritäten bedeuten:
- **A:** größter Hebel, geringes Risiko, reine Python-Bibliotheken.
- **B:** deutlicher Mehrwert, aber mehr Integrationsaufwand oder Lizenzauflagen.
- **C:** das Ziel wird direkt kontaktiert oder es läuft ein eigener Dienst. Erst nach einem OPSEC-Runbook.

## 2. Begründung und Messgrößen je System

### A1 – Docling + OCRmyPDF: Dokumente fundstellengenau erschließen
* **Lücke:** Im Audit steht „page/paragraph/table/footnote anchors; OCR/document provenance“ offen.
  Vorhanden sind pdfplumber, pypdf, PyMuPDF und pytesseract. Diese liefern Text, aber keine
  Dokumentstruktur.
* **Nutzen:**
  * Docling zerlegt PDF, DOCX, PPTX und HTML in Seiten, Absätze, Überschriften, Tabellen und Fußnoten, jeweils mit Positionsrahmen. Jede Aussage lässt sich damit auf „Seite 7, Tabelle 2, Zeile 3“ zurückführen.
  * OCRmyPDF legt bei Scans eine durchsuchbare Textebene an. Das Original-PDF bleibt dabei unverändert als Beleg erhalten.
* **Messen:**
  * Anteil der Dokumentseiten mit Text und Strukturankern, Ziel: ≥ 95 % bei digital erzeugten PDFs.
  * Zeichenfehlerrate der OCR an einem gelabelten Testsatz aus 20 Scans.
  * Anteil der Befunde mit Anker auf Absatz- oder Tabellenebene statt nur auf Dokumentebene.

### A2 – Trafilatura: sauberer Haupttext und Metadaten aus Webseiten
* **Lücke:** Zur Webseiten-Erfassung meldet der Status von `phase19/crawler_core425.py`
  `network_executor_implemented: False`. Für Web-Belege fehlt also eine zuverlässige Extraktion.
* **Nutzen:** Trafilatura trennt den eigentlichen Artikeltext von Navigation und Werbung. Es liefert Titel,
  Autor, Datum, Sprache und Kanonische URL und verarbeitet Sitemaps und Feeds.
* **Messen:** Precision und Recall der Haupttext-Extraktion an 50 gelabelten Seiten. Anteil der Web-Belege mit
  erkanntem Veröffentlichungsdatum. Weniger Fehlalarme bei Entitäten, weil kein Text aus der Navigation mehr mitgezählt wird.

### A3 – warcio (+ Wayback-CDX): Web-Belege im Archivstandard
* **Lücke:** Historisches Web ist zu 75–85 % erreicht. Es fehlt die Beweisqualität der Webaufnahmen.
* **Nutzen:** Jede Webabfrage wird als **WARC** gespeichert, also Anfrage und Antwort mit allen Headern und
  Zeitstempel. Das ist das Format der Internet-Archive. Über die CDX-API der Wayback Machine lassen sich
  historische Fassungen auflisten und als WARC sichern. Zusammen mit den vorhandenen SHA-256-Hashes ist
  das ein nachprüfbarer Beleg.
* **Messen:** Anteil der Web-Belege mit WARC und Hash, Ziel 100 %. Anteil der Belege, die sich erneut abspielen lassen
  (Replay-Test). Anzahl gefundener historischer Fassungen je URL.

### A4 – datasketch: Unabhängigkeit der Quellen statt bloßer Trefferzahl
* **Lücke:** Build 456 verlangt, dass Claims unabhängige Quellfamilien zählen statt Artikel.
  Gespiegelte oder übernommene Meldungen dürfen nicht als unabhängige Bestätigung gelten.
* **Nutzen:** MinHash und LSH finden nahezu gleiche Texte auch in großen Beständen sehr schnell. Daraus entsteht
  die Anzeige „20 Erwähnungen / 3 unabhängige Ursprünge“. Das ist der analytisch wichtigste Einzelgewinn
  gegen Zirkelberichterstattung.
* **Messen:** Precision und Recall der Duplikat-Cluster an einem gelabelten Satz aus Agenturmeldungen und ihren Übernahmen.
  Anteil der Claims, deren Unterstützung nach Quellfamilien statt nach Artikeln gezählt wird.

### A5 – FollowTheMoney + nomenklatura + RapidFuzz: Entitäten wie im investigativen Journalismus
* **Lücke:** Gefordert sind mehrsprachige Transliteration und Aliase (Hebräisch, Arabisch, Kyrillisch), Konfliktprüfung
  und ein Datenmodell für Organisationen und Eigentum.
* **Nutzen:**
  * **FollowTheMoney** ist das Datenmodell von OCCRP/Aleph und OpenSanctions. Es kennt Person, Unternehmen, Eigentum, Mitgliedschaft, Zahlung und weitere Typen, jeweils mit Zeitraum.
  * **nomenklatura** liefert Kandidaten für Entitäten-Abgleiche und einen Arbeitsablauf für menschliche Entscheidungen (zusammenführen / nicht zusammenführen / unklar). Das entspricht dem EagleEye-Grundsatz, nie automatisch zusammenzuführen.
  * **RapidFuzz** liefert schnelle Ähnlichkeitsmaße für Namen.
  * Ein weiterer Vorteil: Fälle werden mit Aleph, OpenSanctions und anderen FtM-Datenbeständen austauschbar.
* **Messen:** Precision und Recall der Abgleich-Vorschläge an gelabelten Namenspaaren aus mehreren Schriften. Anteil der
  vom Prüfer abgelehnten Vorschläge. Prüfzeit je Vorschlag.
* *Später ausbaufähig:* **Splink** (MIT) für probabilistisches Record Linkage bei großen Registerimporten.

### B1 – NetworkX: Graphanalyse im aktuellen Arbeitsablauf
* **Lücke:** Im Audit steht „communities/bridges/temporal centrality and evidence-weighted paths“ offen. Im Code wird bisher keine Graph-Bibliothek genutzt.
* **Nutzen:**
  * Gemeinschaften im Netzwerk erkennen.
  * Brückenpersonen finden, also Personen, die sonst getrennte Gruppen verbinden.
  * Kürzeste Pfade so gewichten, dass gut belegte Verbindungen zählen.
  * Zentralität in Zeitfenstern berechnen.
  * Den Graphen als GEXF für Gephi oder als JSON Canvas für Obsidian exportieren.
* **Messen:** Analysezeit für typische Fallgrößen. Ob analytisch bedeutsame Knoten in einem gelösten Referenzfall wiedergefunden werden.

### B2 – spaCy: Entitäten aus Dokumenten vorschlagen
* **Nutzen:** Personen, Organisationen, Orte und Daten werden lokal und offline erkannt. Sie erscheinen als
  **Vorschläge mit Fundstelle** und nicht als Fakten. Das entlastet die manuelle Verknüpfung und den KI-Ermittler, der
  dann gezielter auf Stellen verweisen kann.
* **Messen:** F1-Wert der Entitätenerkennung auf deutschen und englischen Testdokumenten. Eingesparte Zeit beim Verknüpfen von Entitäten.

### B3 – Bellingcat auto-archiver: flüchtige Inhalte sichern
* **Nutzen:** Social-Media-Beiträge, Videos (über yt-dlp) und Screenshots werden mit Hash, Metadaten und
  optionaler Wayback-Einreichung gesichert. Das Werkzeug wurde für die Beweissicherung im Journalismus gebaut.
  Es läuft getrennt, die Ergebnisse werden als Belege in den Fall importiert.
* **Messen:** Anteil erfolgreich gesicherter URLs je Plattform. Vollständigkeit der Metadaten. Wie viele Belege
  nach 30 Tagen noch vorhanden sind, obwohl das Original gelöscht wurde.

### B4 – OpenSanctions-Daten
* **Nutzen:** Personen und Organisationen werden gegen internationale Sanktions- und PEP-Listen abgeglichen. Die Daten liegen bereits
  im FtM-Format und passen direkt zu A5.
* **Lizenz:** Der Code steht unter MIT, die **Daten unter CC BY-NC 4.0**. Für die private, nicht-kommerzielle Nutzung ist das in Ordnung.
  Eine kommerzielle Nutzung braucht eine Lizenz von OpenSanctions.
* **Messen:** Anteil der Fallentitäten, die geprüft wurden. Anzahl der Treffer-Kandidaten und wie viele davon der Prüfer bestätigt oder verwirft.

### B5 – libpostal
* **Nutzen:** Adressen werden weltweit zerlegt und normalisiert. Das hilft beim Verknüpfen von Firmen- und Personenadressen,
  einem typischen Hinweis auf Briefkastenfirmen und gemeinsame Sitze.
* **Messen:** Trefferquote beim Adressabgleich vor und nach der Normalisierung.

### C1 – subfinder (passiv) + Certificate Transparency
* **Lücke:** Das Audit verlangt die externe Qualifizierung von RDAP, CT und RIPEstat.
* **Nutzen:** Subdomains werden nur aus passiven Quellen ermittelt. subfinder arbeitet standardmäßig passiv; den Schalter `-active` (Live-Prüfung der Hosts) nicht verwenden.
  Zertifikatsdaten aus CT liefern Zeitlinien der Infrastruktur.
* **Messen:** Vollständigkeit der Subdomains im Vergleich mit einer Referenzliste. Anzahl neuer, belegbarer Infrastrukturbeziehungen.
* **Hinweis:** Amass (Apache-2.0) ist mächtiger, löst aber standardmäßig auch aktiv per DNS auf. Deshalb kommt zuerst subfinder.

### C2 – Maigret + WhatsMyName
* **Nutzen:** Zu einem Benutzernamen entstehen Profil-Kandidaten auf mehreren tausend Seiten. Laut Build 213 ist das schon als
  `external_candidate_collector` vorgesehen.
* **Bedingungen:**
  * Maigret läuft isoliert.
  * Es wird nur mit einem OPSEC-Preflight gestartet, weil es Hunderte Seiten kontaktiert.
  * Die Ergebnisse sind ausschließlich Kandidaten.
  * Für die WhatsMyName-Daten gilt CC BY-SA: Quellenangabe, gleiche Lizenz für abgeleitete Listen.
* **Messen:** Fehlalarmquote an Benutzernamen mit bekannter Wahrheit. Anteil der Kandidaten, die ein Prüfer bestätigt.

### C3 – changedetection.io
* **Nutzen:** Ausgewählte Quellen werden fortlaufend überwacht, z. B. Impressum, Teamseite oder Registereintrag. Bei einer Änderung erzeugt EagleEye einen neuen
  Snapshot mit Differenz zum vorherigen.
* **Messen:** Zeit zwischen der Änderung und ihrer Erkennung. Anteil der Änderungen, die als Beleg gesichert wurden.

## 3. Bewusst nicht ausgewählt

| System | Grund |
|---|---|
| Maltego, Hunchly, Lampyre, Social Links | proprietär, nicht prüf- oder einbaubar |
| SpiderFoot (Gesamtsystem) | seit 2023 kaum gepflegt, viele aktive Module, keine Fallbindung. Nur die Architekturideen übernehmen (siehe eigener Bericht) |
| holehe, GHunt | prüfen Konten über Passwort-Reset- und Login-Endpunkte. Das ist rechtlich und OPSEC-seitig heikel, GHunt steht zudem unter AGPL |
| Gesichtserkennung (z. B. PimEyes, eigene Modelle) | biometrische Daten (DSGVO Art. 9, AI Act). Für EagleEye bewusst ausgeschlossen |
| MISP, OpenCTI, TheHive/Cortex | auf Cyber-Bedrohungsinformationen ausgerichtet, schwergewichtig. Nur sinnvoll, wenn EagleEye CTI-Aufträge übernimmt |
| Social-Analyzer, Osintgram, Twint, snscrape | AGPL/GPL, aktive Plattformabfragen, teils tot |
| Aleph (Gesamtsystem) | letzter Code-Stand Feb. 2026, OCCRP setzt auf die kommerzielle Weiterentwicklung. Das Datenmodell FtM (A5) bringt den Kernnutzen ohne die Plattform |
| python-igraph | GPL-2.0. NetworkX reicht für die Fallgrößen von EagleEye |
| Browsertrix Crawler | AGPL, Docker-Pflicht. warcio + Trafilatura decken den Bedarf zunächst ab |

Bereits vorhanden und daher nicht neu ausgewählt: Tesseract, faster-whisper, sentence-transformers,
Argos Translate, Ollama, GLEIF- und Wikidata-Anbindungen, ExifTool-Bezüge.

## 4. Lizenzbefund im bestehenden Code

**PyMuPDF steht unter AGPL-3.0** (oder einer kommerziellen Lizenz von Artifex) und ist eine Pflichtabhängigkeit in
`pyproject.toml` und `requirements-runtime.txt`.
* Für die rein private Nutzung ist das unkritisch.
* Sobald EagleEye **weitergegeben** oder **als Dienst für andere** betrieben wird, muss der gesamte Quellcode unter AGPL
  offengelegt werden. Alternativ braucht es eine kommerzielle Lizenz.
* Ausweg ohne Funktionsverlust: PDF-Darstellung über **pypdfium2** (Apache-2.0/BSD-3), Text über die
  vorhandenen pdfplumber/pypdf, Struktur über Docling (A1).

Außerdem hat EagleEye selbst **keine Lizenzdatei**. Vor einer Weitergabe sollte festgelegt werden, unter welcher Lizenz das geschieht.

## 5. Vorgeschlagene Reihenfolge

| Schritt | Inhalt | Abnahme |
|---|---|---|
| 1 | A1 + A2 + A3: Dokumente und Webseiten strukturiert und archivfest erfassen | Referenzsatz: 20 PDFs/Scans, 50 Webseiten. Kennzahlen aus Abschnitt 2 |
| 2 | A4 + A5: Quellfamilien und Entitätenabgleich (deckt sich mit Build 456) | gelabelte Duplikat-Cluster und Namenspaare. Anzeige „Erwähnungen / unabhängige Ursprünge“ |
| 3 | B1 + B2 + B4 + B5: Analyse-Ebene | Referenzfall mit bekannter Netzwerkstruktur |
| 4 | B3 + C1 + C2 + C3: aktive bzw. isolierte Sammler | erst nach OPSEC-Runbook. Je Sammler Fehlalarmquote und Prüfaufwand |

Simulierte und Live-Ergebnisse werden in allen Schritten wie bisher getrennt ausgewiesen.
