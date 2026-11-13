# Datenquellen in PersonOSINT 1.6

Stand: 13. Nov. 2026 · 32 Online-Quellen und 3 lokale Datenbestände. Die Tabelle wird aus dem Programm erzeugt.

## Was „geprüft“ hier heißt

Alle Anbindungen sind gegen nachgebildete Antworten getestet (`tests/`). **Live** konnte in der Entwicklungsumgebung nur geprüft werden,
was deren Netzsperre durchlässt: GitHub (Namenssuche), GitLab und Docker Hub. Dabei wurden bereits zwei fehlerhafte Testabfragen gefunden
und behoben. Für alle anderen Quellen gilt: **nach der Schnittstellenbeschreibung gebaut, live noch nicht bestätigt.**

Die verbindliche Antwort gibt Ihr eigener Rechner: **Verwaltung → Quellen & Daten → „Alle Quellen prüfen“** oder `QUELLEN_PRUEFEN.bat`.
Das Ergebnis steht danach an jeder Quelle und als Prüfbericht zum Herunterladen bereit.

## Online-Quellen

| Quelle | Bereich | verarbeitet | liefert (Folgesuchen) | Exposition | Verlässlichkeit | Schlüssel | Lizenz | Live-Stand |
|---|---|---|---|---|---|---|---|---|
| Benutzernamen-Check (13 Plattformen) | Online-Präsenz | Benutzername | Benutzername, Webadresse | Plattform | D | nein | Öffentliche Schnittstelle; Nutzungsbedingungen des Anbieters beachten. | ✓ teilweise live geprüft (2 von 13 Plattformen erreichbar) |
| GitHub | Online-Präsenz | Benutzername, Name | Benutzername, Webadresse, E-Mail, Arbeitgeber/Firma, Ort/Adresse | Plattform | C | nein | Öffentliche Schnittstelle; Nutzungsbedingungen des Anbieters beachten. | ✓ Namenssuche live geprüft (13.11.2026) |
| GitLab | Online-Präsenz | Benutzername | Benutzername, Webadresse | Plattform | C | nein | Öffentliche Schnittstelle; Nutzungsbedingungen des Anbieters beachten. | ✓ live geprüft (13.11.2026) |
| Bluesky | Online-Präsenz | Name, Benutzername | Benutzername, Webadresse | Plattform | C | nein | Öffentliche Schnittstelle; Nutzungsbedingungen des Anbieters beachten. | noch nicht live geprüft |
| Mastodon (mastodon.social) | Online-Präsenz | Name, Benutzername | Benutzername, Webadresse | Plattform | C | nein | Öffentliche Schnittstelle; Nutzungsbedingungen des Anbieters beachten. | noch nicht live geprüft |
| Gravatar | Online-Präsenz | E-Mail | Benutzername, Webadresse | Passiv | C | nein | Öffentliche Schnittstelle; Nutzungsbedingungen des Anbieters beachten. | noch nicht live geprüft |
| Wikidata | Register & Wissen | Name | Alias | Passiv | C | nein | Öffentliche Schnittstelle; Nutzungsbedingungen des Anbieters beachten. | noch nicht live geprüft |
| OpenAlex | Register & Wissen | Name | Arbeitgeber/Firma | Passiv | B | nein | Öffentliche Schnittstelle; Nutzungsbedingungen des Anbieters beachten. | noch nicht live geprüft |
| ORCID | Register & Wissen | Name | Arbeitgeber/Firma | Passiv | B | nein | Öffentliche Schnittstelle; Nutzungsbedingungen des Anbieters beachten. | noch nicht live geprüft |
| INTERPOL – Vermisste (Yellow Notices) | Vermisstenfälle | Name | – | Passiv | A | nein | Öffentliche Schnittstelle; Nutzungsbedingungen des Anbieters beachten. | noch nicht live geprüft |
| Internet Archive (Wayback) | Register & Wissen | Webadresse | Webadresse | Passiv | B | nein | Öffentliche Schnittstelle; Nutzungsbedingungen des Anbieters beachten. | noch nicht live geprüft |
| OpenStreetMap Nominatim | Orte | Ort/Adresse | Ort/Adresse | Passiv | B | nein | Öffentliche Schnittstelle; Nutzungsbedingungen des Anbieters beachten. | noch nicht live geprüft |
| UK Companies House | Wirtschaft & Register | Name | Arbeitgeber/Firma, Ort/Adresse | Passiv | A | Pflicht | Open Government Licence (UK) | noch nicht live geprüft |
| OpenCorporates | Wirtschaft & Register | Name | Arbeitgeber/Firma | Passiv | B | optional | ODbL – Quellenangabe Pflicht | noch nicht live geprüft |
| GLEIF (LEI-Register) | Wirtschaft & Register | Arbeitgeber/Firma | Arbeitgeber/Firma, Ort/Adresse | Passiv | A | nein | CC0 | noch nicht live geprüft |
| Wikidata – Beziehungen | Register & Wissen | Name | Alias, Arbeitgeber/Firma, Ort/Adresse | Passiv | C | nein | CC0 | noch nicht live geprüft |
| crt.sh (Zertifikate) | Domains & Technik | Domain, Webadresse, E-Mail | Domain | Passiv | B | nein | frei nutzbar (Sectigo) | noch nicht live geprüft |
| RDAP (Domain-Register) | Domains & Technik | Domain, Webadresse | Domain, Arbeitgeber/Firma | Passiv | B | nein | öffentliche Registerauskunft | noch nicht live geprüft |
| OpenSanctions (online) | Risiko & Compliance | Name | Alias | Passiv | B | Pflicht | CC BY-NC 4.0 (nicht kommerziell) / kommerzielle Lizenz | noch nicht live geprüft |
| GND – Deutsche Nationalbibliothek (lobid) | Register & Wissen | Name | Alias, Arbeitgeber/Firma, Ort/Adresse | Passiv | B | nein | CC0 1.0 | noch nicht live geprüft |
| abgeordnetenwatch.de | Register & Wissen | Name | Arbeitgeber/Firma | Passiv | B | nein | CC0 1.0 | noch nicht live geprüft |
| Wikipedia (de/en) | Register & Wissen | Name | – | Passiv | C | nein | CC BY-SA 4.0 (Texte) | noch nicht live geprüft |
| Frankreich – Firmenregister (Annuaire des Entreprises) | Wirtschaft & Register | Name, Arbeitgeber/Firma | Arbeitgeber/Firma, Ort/Adresse | Passiv | A | nein | Licence Ouverte 2.0 (Etalab) | noch nicht live geprüft |
| ICIJ Offshore Leaks (online) | Risiko & Compliance | Name, Arbeitgeber/Firma | – | Passiv | B | nein | ODbL / CC BY-SA – Quellenangabe ICIJ Pflicht | noch nicht live geprüft |
| INTERPOL – Fahndung (Red Notices) | Risiko & Compliance | Name | – | Passiv | A | nein | öffentliche Bekanntmachung | noch nicht live geprüft |
| FBI – Wanted | Risiko & Compliance | Name | Alias | Passiv | A | nein | gemeinfrei (US-Bundesbehörde) | noch nicht live geprüft |
| Presse weltweit (GDELT) | Presse & Medien | Name, Arbeitgeber/Firma | Webadresse | Passiv | C | nein | frei nutzbar mit Quellenangabe GDELT; Artikel bleiben bei den Verlagen | noch nicht live geprüft |
| Crossref | Register & Wissen | Name | Arbeitgeber/Firma | Passiv | B | nein | CC0 (Metadaten) | noch nicht live geprüft |
| DBLP (Informatik) | Register & Wissen | Name | Arbeitgeber/Firma | Passiv | B | nein | CC0 | noch nicht live geprüft |
| Keybase | Online-Präsenz | Benutzername | Benutzername, Webadresse | Plattform | B | nein | öffentliche Profilangaben | noch nicht live geprüft |
| Codeberg | Online-Präsenz | Benutzername, Name | Benutzername, Webadresse | Plattform | C | nein | öffentliche Profilangaben | noch nicht live geprüft |
| Docker Hub | Online-Präsenz | Benutzername | Benutzername, Arbeitgeber/Firma, Ort/Adresse | Plattform | C | nein | öffentliche Profilangaben | ✓ live geprüft (13.11.2026) |

Exposition: *Passiv* = die Abfrage geht an einen Dritten (Register, Archiv), die Zielperson merkt nichts. *Plattform* = der Betreiber der
Plattform sieht die Abfrage. Verlässlichkeit nach Admiralty-Code (A = amtlich … F = nicht beurteilbar).

## Lokale Datenbestände (Abfragen verlassen den Rechner nicht)

| Bestand | Inhalt | Hinweis |
|---|---|---|
| OpenSanctions (Gesamtdaten) | Sanktionslisten, politisch exponierte Personen, Fahndungslisten weltweit | Daten CC BY-NC: kommerzielle Nutzung braucht eine Lizenz von OpenSanctions |
| ICIJ Offshore Leaks | Panama/Paradise/Pandora Papers als Gesamtbestand | ODbL / CC BY-SA, Quellenangabe Pflicht |
| Eigene Referenzliste | eigene CSV-Liste (z. B. Kundenstamm, interne Warnliste) | – |

## Bewusst nicht als automatische Quelle eingebunden

| Quelle | Grund | Was stattdessen geht |
|---|---|---|
| Handelsregister, Unternehmensregister, Bundesanzeiger | Keine offene Schnittstelle; die Nutzungsordnung untersagt den automatisierten Massenabruf | Einzelrecherche im Browser, Auszug als Dokument importieren (Belege → „Dokument importieren“) |
| Insolvenzbekanntmachungen | Nur Formularsuche, uneingeschränkte Suche auf zwei Wochen begrenzt | wie oben |
| Melderegister | Auskunft nur auf Antrag bei der Meldebehörde, gebührenpflichtig | Antrag stellen, Antwort als Dokument importieren |
| Have I Been Pwned, Passwort-/Konto-Prüfdienste | Prüfen Konten über Datenlecks bzw. Anmelde-Endpunkte – rechtlich und für die Zielperson heikel | bewusst ausgeschlossen |
| Gesichtserkennung (PimEyes u. a.) | Biometrische Daten (Art. 9 DSGVO) | bewusst ausgeschlossen |
| Facebook, Instagram, LinkedIn, X, TikTok | Keine offene Suche ohne Anmeldung; Automatisierung verstößt gegen die Nutzungsbedingungen | vorbereitete Recherchelinks im Reiter „Personen & Profile“ |
| Amtliche Sanktionslisten (EU, UN, OFAC, UK) als eigener Import | Noch nicht umgesetzt – wäre die kommerziell frei nutzbare Alternative zu OpenSanctions | nächster Ausbauschritt |
| North Data, Creditreform, LexisNexis, Pipl u. a. | Kostenpflichtige Anbieter mit Vertrag | Anbindung möglich, sobald ein Zugang vorliegt |

## Überschneidung mit EagleEye (Build 501, ChatGPT)

Das EagleEye-Hauptprogramm hat seit Build 501 eigene Adapter für GND/lobid, abgeordnetenwatch, Crossref, OpenAlex, HDX und Common Crawl
(`docs/FREE_PUBLIC_SOURCES_PERSONS.md` im Hauptordner). GND, abgeordnetenwatch und Crossref gibt es damit auf beiden Seiten. Vorschlag: eine
gemeinsame Anbindung je Quelle (siehe `CLAUDE_REVIEW_UND_UEBERGABE_500.md`, Abschnitt 4).
