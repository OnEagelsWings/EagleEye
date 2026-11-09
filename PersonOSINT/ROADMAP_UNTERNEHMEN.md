# EagleEye PersonOSINT – Ausbauplan zum Werkzeug für ein kleines OSINT-Unternehmen

Stand: November 2026 · Ausgangspunkt: PersonOSINT 1.0 (Einzelplatz, lokal, SQLite)

## 1. Zielbild

Ein Team von **3–15 Personen** (Analysten, Teamleitung, Backoffice) bearbeitet parallel Aufträge zu
Personensuche, Vermisstenfällen und Verbindungsanalysen. Am Ende soll das Tool Folgendes leisten:

1. **Mehrbenutzerbetrieb:** Rollen, Fallzuweisung, Vier-Augen-Prüfung, Server-Betrieb mit Login.
2. **Gerichtsfeste Beweissicherung:** Jede Fundstelle wird archiviert (Screenshot, HTML, Hash, Zeitstempel).
3. **Mehr und bessere Quellen:** zusätzliche kostenlose Quellen und lizenzierte Kaufquellen, zentral verwaltet.
4. **Wiederkehrende Überwachung:** Gespeicherte Suchen laufen automatisch und melden Neues.
5. **Professionelle Berichte:** Firmenlayout, Berichtsvorlagen, Freigabe-Workflow, PDF und Word.
6. **Geschäftsabläufe:** Mandanten, Aufträge, Zeiterfassung, Abrechnungsgrundlagen.
7. **Nachweisbare Compliance:** DSGVO-Rechenschaft, Löschfristen, Zweckbindung und Protokoll mit Integritätsschutz.

Leitlinie bleibt: **öffentliche bzw. rechtmäßig lizenzierte Quellen, Mensch entscheidet, alles nachvollziehbar.**
Das ist auch ein Verkaufsargument gegenüber Kanzleien, Versicherungen, Unternehmen und Behörden.

## 2. Phasenüberblick

| Phase | Inhalt | Ergebnis | Aufwand (grob) |
|---|---|---|---|
| **1 Fundament** (Monat 1–2) | Server-Betrieb, Login, Rollen, PostgreSQL, Backups, Verschlüsselung | Team kann gemeinsam und sicher arbeiten | 25–35 PT |
| **2 Beweissicherung & Quellen** (Monat 2–4) | Web-Capture, Quellenverwaltung, Kaufquellen, Dokument-Import/OCR | Belastbare Fundstellen, deutlich höhere Trefferquote | 35–45 PT |
| **3 Analyse** (Monat 4–5) | Entitätsauflösung, Monitoring, Zeitgraph, Geo-Analyse, Bildanalyse (ohne Biometrie) | Weniger Handarbeit, neue Erkenntnisse | 30–40 PT |
| **4 Berichte & Geschäft** (Monat 5–6) | Berichtsvorlagen, Freigabe, Mandanten/Aufträge, Zeiterfassung | Abrechenbare Produkte | 25–30 PT |
| **5 Spezialisierung** (Monat 6–8) | Vermissten-Hinweismanagement, KI-Assistent (lokal), Kundenportal | Alleinstellungsmerkmale im Nischenmarkt | 30–40 PT |
| **Laufend** | Tests, Sicherheit, Quellenpflege, Schulung | Stabiler Betrieb | ca. 2–3 PT pro Monat |

PT = Personentage Entwicklung. Die Schätzungen sind Richtwerte für eine erfahrene Entwicklerin bzw. einen
erfahrenen Entwickler und vor jeder Phase zu verfeinern.

---

## 3. Phase 1 – Fundament für den Teambetrieb

> **Status: umgesetzt in Version 1.1** (alle Punkte 1.1–1.8). Zusätzlich: Fallart *Investigativrecherche* mit
> Leitfaden, vertrauliche Fälle (Quellenschutz) mit protokolliertem Notfallzugriff, Leserolle statt Backoffice
> (Abrechnung folgt in Phase 4). Nachweis: 34 automatisierte Tests auf SQLite **und** PostgreSQL, Browser-Abnahme
> (Ersteinrichtung → 2FA → Fall → Prüfung → Freigabe) und Docker-Stack (PostgreSQL + App + Caddy/HTTPS) inkl.
> Sicherung im Container und Wiederherstellung nach SQLite.
>
> **Ergänzt in Version 1.2 – OPSEC-Struktur** (siehe [OPSEC_KONZEPT.md](OPSEC_KONZEPT.md)): OPSEC-Stufen je Fall,
> Netzausgänge über Proxy/Tor mit *fail closed*, Expositionsklassen, Außenkontakt-Protokoll, Metadaten-Bereinigung,
> Export-Register, Briefing, Decknamen, Schnellsperre. Nachweis: 42 Tests (SQLite + PostgreSQL), davon Routing-Test
> mit echtem lokalem Proxy trotz `no_proxy`-Ausnahme, Browser-Abnahme mit Proxy-Mitschnitt (alle automatischen Abfragen
> liefen über den Ausgang).

**Ziel:** Mehrere Personen arbeiten sicher am selben Datenbestand.

| # | Maßnahme | Details | Priorität |
|---|---|---|---|
| 1.1 | **Benutzerkonten & Login** | Argon2-Passwörter und Pflicht zur Zwei-Faktor-Anmeldung (TOTP oder WebAuthn). Sitzungen mit Ablauf, Sperre nach Fehlversuchen. Aus dem Altbestand übernehmbar: `src/eagleeye/security`, Abhängigkeiten `argon2-cffi` und `webauthn` | Muss |
| 1.2 | **Rollen & Rechte** | *Analyst* (eigene/zugewiesene Fälle), *Prüfer* (Freigaben), *Teamleitung* (alle Fälle, Zuweisung), *Admin* (Benutzer, Quellen), *Backoffice* (Mandanten, Abrechnung, keine Falldetails). Rechte werden pro Fall geprüft | Muss |
| 1.3 | **Fallzuweisung & Status** | Bearbeiter/in, Prüfer/in und Fälligkeit je Fall. Dashboard „Meine Fälle“, „Zur Prüfung“, „Überfällig“ | Muss |
| 1.4 | **PostgreSQL statt SQLite** | Datenzugriff hinter eine Schnittstelle legen, Migrationen mit Alembic (im Altbestand vorhanden). SQLite bleibt für den Einzelplatz | Muss |
| 1.5 | **Server-Betrieb** | Docker-Compose mit App, PostgreSQL und Reverse-Proxy (Caddy oder Traefik, automatisches TLS). Betrieb im eigenen Büro-Netz oder bei einem deutschen Hoster. Host-Prüfung und Client-Kennung bleiben, dazu echte CSRF-Tokens | Muss |
| 1.6 | **Verschlüsselung & Backups** | Festplattenverschlüsselung auf dem Server. Fotos und Belege zusätzlich verschlüsselt ablegen (Schlüssel getrennt). Tägliche verschlüsselte Backups mit Wiederherstellungstest | Muss |
| 1.7 | **Manipulationssicheres Protokoll** | Jeder Protokolleintrag erhält den Hash des Vorgängers (Hash-Kette). Eine Prüffunktion zeigt, ob nachträglich etwas verändert wurde | Soll |
| 1.8 | **Gleichzeitiges Arbeiten** | Optimistisches Sperren (Versionsnummer pro Datensatz). Live-Hinweis „Kollegin X bearbeitet gerade …“ | Soll |

**Abnahme:** Drei Benutzer mit verschiedenen Rollen bearbeiten denselben Fall. Unberechtigte Zugriffe werden
abgewiesen (automatisierte Tests). Die Wiederherstellung aus einem Backup ist dokumentiert und erprobt.

---

## 4. Phase 2 – Beweissicherung, Quellen, Dokumente

> **Status (Version 1.3):** Quellen-Baukasten mit Schlüsselverwaltung, neue Wirtschafts-/Register-/Domain-/Sanktionsquellen,
> lokale Referenzdatenbanken (OpenSanctions, ICIJ, eigene Listen) und Beweissicherung mit SHA-256, Archivverweis und
> Beweispaket sind umgesetzt. Offen: Dokument-/E-Mail-Import mit OCR (4.4), qualifizierte Zeitstempel nach RFC 3161.

**Ziel:** Ergebnisse, die vor Gericht, bei Versicherern und bei Mandanten Bestand haben, dazu eine deutlich größere Abdeckung.

### 4.1 Beweissicherung (wichtigstes Profi-Merkmal)
- Mit einem Klick auf **„Fundstelle sichern“** archiviert die App die Seite über einen Headless-Browser (Playwright):
  ganzseitiger Screenshot (PNG), HTML, optional WARC, URL, Zeitstempel, HTTP-Header und SHA-256-Hash.
- Optional ein **qualifizierter Zeitstempel** nach RFC 3161 bei einem Vertrauensdiensteanbieter als Nachweis, dass die Seite zu diesem Zeitpunkt so existierte.
- Die Kette Treffer → Sicherung → Erkenntnis → Dossier ist durchgängig verknüpft. Der Bericht verweist auf das Beweisstück (Anlagennummer).
- Das Dossier erhält eine **Anlagen-ZIP** mit allen Sicherungen und einem Hash-Verzeichnis.
- Aus dem Altbestand prüfen: `src/eagleeye/crawler`, Collection-Engine (Scrapy/Playwright).

### 4.2 Quellenverwaltung
- Quellen werden als **Plug-ins** mit einheitlicher Schnittstelle umgesetzt. Die Admin-Seite zeigt:
  aktiv/inaktiv, API-Schlüssel (verschlüsselt gespeichert), Rate-Limits, Kosten pro Abfrage, Nutzungsbedingungen,
  Erfolgsquote und letzte Störung.
- Ein **Kostenzähler** pro Fall und Mandant rechnet Kaufabfragen weiter.
- **Quellen-Gesundheitsprüfung:** Ein täglicher Selbsttest erkennt API-Änderungen frühzeitig.

### 4.3 Neue Quellen (Auswahl, rechtlich je Einsatzzweck zu prüfen)

| Bereich | Kostenlos / offen | Lizenziert / kostenpflichtig |
|---|---|---|
| Websuche | SearXNG, selbst gehostet (Metasuche) | Bing Web Search API, Brave Search API, SerpAPI |
| Firmen & Beteiligungen | Unternehmensregister, OpenCorporates (eingeschränkt), GLEIF | North Data API, Creditreform/Bürgel (Bonität, nur mit berechtigtem Interesse) |
| Sanktionen & PEP | OpenSanctions-Daten (nicht kommerziell) | OpenSanctions kommerziell, Dow Jones/Refinitiv |
| Datenlecks | – | Have I Been Pwned API (nur Domänen- bzw. Einwilligungsfälle) |
| Presse & Medien | GDELT, RSS-Feeds regionaler Medien, Presseportal Blaulicht | Archive großer Verlage (z. B. GENIOS) |
| Soziale Medien | Weitere Plattformen im Benutzernamen-Check, öffentliche Telegram-Kanäle | Offizielle Forschungs- bzw. Geschäfts-APIs, wo verfügbar |
| Wissenschaft & Beruf | Bereits vorhanden (OpenAlex, ORCID), dazu DBLP und Crossref | – |
| Vermisstenfälle | INTERPOL, Länderpolizei-Fahndungsseiten (RSS/Monitoring), Missing People UK | – |

Nicht aufnehmen: Quellen, die Logins umgehen, Daten aus Hacks oder Leaks (Rohdaten) und Personensuchmaschinen
ohne erkennbare Rechtsgrundlage für die EU.

### 4.4 Dokumente & Medien importieren
- Upload von PDF, Word, Bildern und E-Mails (.eml/.msg) mit Texterkennung (OCR, Tesseract) und Volltextsuche.
- Personen, Orte, Telefonnummern, E-Mails und IBANs werden automatisch erkannt (Regeln plus lokales NER-Modell).
  Sie landen als **Vorschlag** beim Analysten, nicht automatisch im Graphen.
- Bildmetadaten (EXIF: Aufnahmezeit, Kamera, GPS) werden ausgelesen und auf der Karte gezeigt.
- Aus dem Altbestand übernehmbar: PyMuPDF/pdfplumber/pytesseract-Pipeline, `src/eagleeye/image_intelligence`.

**Abnahme:** Gesicherte Fundstelle mit verifizierbarem Hash. Mindestens 8 neue Quellen produktiv mit
Gesundheitsprüfung. Ein PDF-Import erzeugt prüfbare Entitätsvorschläge.

---

## 5. Phase 3 – Analysefunktionen

> **Status (Version 1.3):** Kandidatengruppen (3.1, als Prüfhilfe statt automatischer Zusammenführung), Überwachung mit
> Benachrichtigungen (3.2), Admiralty-Bewertung, Mehrfachbelege, Widersprüche und Red-Flag-Regeln sind umgesetzt; dazu
> Top-Dossier mit Management Summary, Belegdichte, Vorlagen, Berichtslayout und PDF/A (aus Phase 4) sowie der lokale
> KI-Assistent mit Fußnotenprüfung (aus Phase 5). Offen: Zeitgraph (3.3), Graph-Import/-Export (3.5), Geo-Analyse (3.6), Bildanalyse (3.7).

| # | Funktion | Nutzen |
|---|---|---|
| 3.1 | **Entitätsauflösung (Dubletten)** | Aus „M. Mustermann“, „Max Mustermann“ und „maxmuster“ wird nach Prüfung eine Person. Zusammenführen und Trennen mit Begründung, im Protokoll sichtbar |
| 3.2 | **Monitoring / Alarme** | Gespeicherte Suchen laufen täglich oder wöchentlich (z. B. neue Konten, Presseberichte, Fahndungsmeldungen). Nur *neue* Treffer erscheinen im Posteingang, auf Wunsch mit E-Mail-Benachrichtigung. Für Vermisstenfälle besonders wertvoll |
| 3.3 | **Zeitgraph** | Verbindungen mit Gültigkeit von/bis. Ein Zeitschieberegler zeigt das Netzwerk zu einem Stichtag (z. B. „Wer kannte wen im März?“) |
| 3.4 | **Erweiterte Graph-Analyse** | Clustering sichtbar machen, „Brückenpersonen“ erkennen, Teilgraph eines Falls in einen anderen Fall übernehmen. Fallübergreifende Treffer („Diese Telefonnummer kommt in Fall X vor“) nur mit Berechtigung und protokolliert |
| 3.5 | **Import/Export** | GEXF/GraphML (Gephi), CSV, Import aus Maltego-Exporten. Gewünschtes Format nach Kundenbedarf |
| 3.6 | **Geo-Analyse** | Heatmap der Sichtungen, Radius- bzw. Laufweg-Abschätzung für Vermisste (Zeit × Gehgeschwindigkeit), POI-Suche im Umkreis (Krankenhäuser, Bahnhöfe, Gewässer) über OpenStreetMap/Overpass. Export der Karte ins Dossier |
| 3.7 | **Bildanalyse ohne Biometrie** | EXIF, Bildvergleich per Wahrnehmungs-Hash (gleiches Foto auf mehreren Profilen), Unterstützung bei Rückwärtssuchen. **Keine automatische Gesichtserkennung:** biometrische Daten nach Art. 9 DSGVO, hohes Missbrauchs- und Reputationsrisiko |
| 3.8 | **Bewertung verbessern** | Score-Gewichte anhand der Prüfentscheidungen kalibrieren (bestätigt/verworfen als Trainingsdaten). Trefferquote pro Quelle messen |

**Abnahme:** Monitoring meldet neue Treffer zuverlässig ohne Dubletten. Die Dublettenzusammenführung ist umkehrbar.
Kalibrierte Scores messbar besser als 1.0 (Präzision bei „hoch“ ≥ 85 % auf eigenen Prüfdaten).

---

## 6. Phase 4 – Berichte und Geschäftsprozesse

### 6.1 Berichtswesen
- **Berichtsvorlagen** pro Produkt, siehe Abschnitt 8 (z. B. „Aufenthaltsermittlung kurz“, „Hintergrundprüfung“,
  „Vermisstendossier“, „Netzwerkanalyse“).
- Firmenlayout (Logo, Farben, Fußzeile, Disclaimer) über eine hinterlegte Word-Vorlage (`.dotx`).
- **Freigabe-Workflow:** Entwurf → Prüfung (Vier-Augen) → Freigabe → Versand. Freigegebene Berichte sind
  versioniert, mit Hash protokolliert und unveränderlich.
- Export als Word **und PDF/A** (Archivformat), optional digital signiert.
- Bausteinbibliothek für wiederkehrende Texte (Methodik, Rechtshinweise, Einschränkungen).

### 6.2 Mandanten, Aufträge, Abrechnung
- Mandantenverwaltung mit Ansprechpartnern, Rahmenverträgen und hinterlegtem **berechtigten Interesse** bzw. Auftragsgrundlage.
- Auftrag → Fall(e): Angebotsumfang, Budget (Stunden und Fremdkosten), Frist.
- **Zeiterfassung** pro Fall (Start/Stopp und manuell), Fremdkosten aus den Quellenabfragen automatisch erfasst.
- Export für die Buchhaltung (CSV oder DATEV-Format, Rechnung im bestehenden Buchhaltungssystem).
- Kennzahlen: Durchlaufzeit, Stunden pro Produkt, Trefferquote, offene Prüfungen.

**Abnahme:** Ein Auftrag läuft vollständig durch: Mandant, Fall, Zeit und Kosten, freigegebener Bericht als PDF/A, Abrechnungsexport.

---

## 7. Phase 5 – Spezialisierung (Nischenstärke)

| # | Funktion | Beschreibung |
|---|---|---|
| 5.1 | **Hinweismanagement für Vermisstenfälle** | Öffentliches Hinweisformular pro Fall (eigene URL oder QR-Code auf dem Suchplakat), auf Wunsch anonym. Hinweise landen in einer Warteschlange: Dringlichkeit, Dubletten, Verortung auf der Karte, Übernahme in die Zeitleiste. Schutz vor Spam (Rate-Limit, Captcha ohne Tracking). Weiterleitung an Polizei mit Export |
| 5.2 | **Lokaler KI-Assistent** | Lokales Sprachmodell (z. B. über Ollama, im Altbestand ab Build 471 vorbereitet). Fasst Quellen zusammen, schlägt Hypothesen und Prüffragen vor und entwirft Berichtsabschnitte, **immer mit Quellenbindung und menschlicher Freigabe**. Keine Fall-Daten an Cloud-KI ohne Auftragsverarbeitungsvertrag (AVV) |
| 5.3 | **Kundenportal** | Mandanten sehen Auftragsstatus und laden freigegebene Berichte herunter (2FA, zeitlich begrenzte Links). Keine Rohdaten |
| 5.4 | **Mobile Erfassung** | Responsive Erfassungsmaske bzw. PWA für den Außendienst: Sichtung mit GPS, Foto und Zeit direkt in die Zeitleiste, offline zwischengespeichert |
| 5.5 | **Fallvorlagen & Leitfäden** | Checklisten je Produkt und Landesrecht. Qualitätssicherung über Pflichtschritte vor der Freigabe |

---

## 8. Produkt- und Leistungsangebot (Vorschlag)

Die Funktionen sollten auf verkaufbare Leistungen einzahlen:

| Produkt | Kunde | Bausteine im Tool |
|---|---|---|
| **Aufenthaltsermittlung** | Kanzleien, Inkasso, Erbenermittlung | Personensuche, Register, Bericht „kurz“ |
| **Hintergrundprüfung (Pre-Employment, Geschäftspartner)** | Unternehmen, HR (nur mit Einwilligung bzw. zulässigem Umfang) | Beruf/Bildung, Firmenbeteiligungen, Sanktionen, Medien |
| **Vermisstenunterstützung** | Angehörige, Hilfsorganisationen | Vermisstenmodul, Monitoring, Hinweismanagement, Suchplakat |
| **Netzwerk- und Beteiligungsanalyse** | Versicherer (Betrugsverdacht), Compliance | Graph, Firmenquellen, Pfadsuche, Netzwerkbericht |
| **Digitale Spurensicherung** | Kanzleien | Beweissicherung, Hash/Zeitstempel, Anlagen-ZIP |

---

## 9. Recht und Compliance (begleitend, vor Phase 1 starten)

Vor der kommerziellen Nutzung sind diese Punkte mit Fachanwalt bzw. Datenschutzbeauftragtem zu klären:

- **Gewerberecht:** Ermittlungs- bzw. Detektivtätigkeit anmelden. Berufshaftpflicht prüfen.
- **DSGVO:** Verzeichnis der Verarbeitungstätigkeiten. Je Produkt eine Rechtsgrundlage (Art. 6, ggf. Art. 9/10).
  **Datenschutz-Folgenabschätzung** für die Personenrecherche. Umgang mit Informationspflichten (Art. 14) und
  ihren Ausnahmen. Betroffenenrechte (Auskunft, Löschung) im Tool unterstützen.
- **Löschkonzept:** Fristen je Falltyp, automatische Löschvorschläge nach Abschluss, nachweisbare Löschung (Protokolleintrag ohne Inhalt).
- **Auftragsprüfung:** Pflichtfeld „berechtigtes Interesse geprüft durch“ plus Ablehnungsgründe. Typische
  Ausschlüsse: Stalking-Verdacht, Ex-Partner ohne Rechtsgrund, Suche nach Personen in Schutzprogrammen bzw. Frauenhäusern.
  Das Tool sollte bei Hinweisen auf häusliche Gewalt **aktiv warnen**.
- **Nutzungsbedingungen der Quellen** in der Quellenverwaltung dokumentieren und einhalten.
- **IT-Sicherheit:** Rollen, 2FA, Verschlüsselung, Patch-Management. Optional eine Orientierung an ISO 27001 bzw. BSI-Grundschutz (Verkaufsargument).

---

## 10. Technische Leitplanken

- **Architektur:** Die bestehende Schichtung beibehalten (API → Service → Quellen/Persistenz). Quellen und
  Exporte als Plug-ins. Hintergrundaufgaben (Suchen, Monitoring, Web-Capture) über eine Job-Queue
  (z. B. eine Postgres-basierte Warteschlange oder RQ/Redis), damit die Oberfläche nie blockiert.
- **Frontend:** Ab Phase 3/4 schrittweise auf ein Komponenten-Framework umstellen (z. B. Vue oder Svelte),
  da Formulare, Workflows und Echtzeit-Updates wachsen. Der Graph kann bei > 500 Knoten auf WebGL (z. B. Sigma.js) wechseln.
- **Tests:** Jede Quelle mit aufgezeichneten Beispielantworten. Ende-zu-Ende-Browsertests (Playwright) für
  die Hauptabläufe. Sicherheitstests für Rechte. CI auf GitHub Actions.
- **Altbestand nutzen, aber gezielt:** Aus EagleEye Build 380–478 nur geprüfte, gut getestete Module übernehmen
  (Security, Collection/Crawler, Bild- und Dokumentpipeline, lokaler KI-Ermittler) und in die neue Struktur überführen,
  statt die Versionen parallel weiterzuführen.
- **Betrieb:** Versionierte Releases, Changelog, Update-Skript mit Datenbankmigration, Monitoring (Health-Check, Fehlerprotokoll).

---

## 11. Messbare Erfolgskriterien

| Kennzahl | Zielwert nach Phase 5 |
|---|---|
| Durchlaufzeit Standard-Aufenthaltsermittlung | −40 % gegenüber manueller Recherche |
| Präzision „hoch“ bewerteter Treffer | ≥ 85 % (gemessen an Prüfentscheidungen) |
| Anteil Erkenntnisse mit gesicherter Fundstelle | ≥ 95 % in freigegebenen Berichten |
| Berichte mit Vier-Augen-Freigabe | 100 % |
| Fälle mit dokumentierter Rechtsgrundlage und Löschfrist | 100 % |
| Verfügbarkeit Server-Betrieb (Arbeitszeit) | ≥ 99 % |

---

## 12. Risiken und Gegenmaßnahmen

| Risiko | Gegenmaßnahme |
|---|---|
| Quellen ändern APIs oder sperren Zugriffe | Plug-in-Architektur, tägliche Gesundheitsprüfung, mehrere Quellen pro Bereich |
| Rechtliche Angreifbarkeit (Datenschutz, Missbrauch) | Auftragsprüfung, DSFA, Löschkonzept, Protokoll mit Hash-Kette, keine Biometrie |
| Datenabfluss / Angriff auf den Server | 2FA, Verschlüsselung, minimale Rechte, Backups offline, regelmäßige Updates |
| Funktionsüberfrachtung (wie im Altbestand) | Strikte Phasen mit Abnahmekriterien, jede Funktion muss einem Produkt (Abschnitt 8) dienen |
| Überschätzung automatischer Ergebnisse | Score-Begründungen, Prüfpflicht, Schulung „gleicher Name ≠ gleiche Person“ |

---

## 13. Nächste konkrete Schritte (die ersten 4 Wochen)

1. Produktentscheidung: 2–3 Startprodukte aus Abschnitt 8 festlegen. Sie bestimmen die Prioritäten der Quellen.
2. Rechtliche Klärung beauftragen (Abschnitt 9), DSFA-Entwurf erstellen.
3. Phase 1.1–1.5 umsetzen: Login, Rollen, PostgreSQL, Docker-Betrieb.
4. Beweissicherung (4.1) als ersten Mehrwert für zahlende Kunden vorziehen.
5. Pilotbetrieb mit 2–3 echten Aufträgen, Rückmeldungen der Analysten sammeln, Plan anpassen.
