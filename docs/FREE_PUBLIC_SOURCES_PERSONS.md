# Öffentliche Quellen und Personenrecherche

Implementiert am 12. November 2026 auf dem aktiven Build-500-Integrationsstand
`e8507bb1278a176542c53af24df95b58f0704374` / PR #93. Diese Erweiterung ist durch
den neuen Nutzerauftrag nach dem bisherigen Funktionsstopp autorisiert.
Die Paketversion bleibt bis zur nächsten gemeinsam geprüften Paketierung 500.0.0.

## Bedienung

1. Einen Fall öffnen, dann **Geführte Recherche → Öffentliche Quellen und Personenrecherche**.
2. Rechercheart und Suchbegriff wählen. Quelle, Abdeckung und Zugangsvoraussetzungen lesen.
3. Bis zu acht verfügbare Adapter auswählen und den fallbezogenen Zweck dokumentieren.
4. Das vorbereitete Paket zeigt jede exakte Suchanfrage. Eine berechtigte Person kann
   den Plan und separat die konkreten Abfragen mit Prüfbegründung freigeben.
5. Jede Quelle einmalig live abfragen oder eine vorhandene Antwort offline wiedergeben.
6. Einen Treffer im Original öffnen. Mit Zuordnungsgrund und offenen Fragen als
   ungeprüften Recherchefund in denselben Fall übernehmen. Anschließend den bestehenden
   Webbeleg-/Dokumenten-/Evidence-Ablauf nutzen.

Die neue Ansicht liegt unter `/workbench/public-sources`. Der fallautorisierte
Katalog ist unter `/api/research/public-sources` auch maschinenlesbar.
Katalogaufruf und Vorbereitung führen keine externen Anfragen aus.

## Architektur und Provenienz

- Vorhandener ProviderCollection120-Motor, Hostlisten, Größenlimits, Ratenbegrenzung,
  Transport und gemeinsamer Kandidateneingang bleiben maßgeblich.
- Sechs zusätzliche Adapter: GND/lobid-Personen, Abgeordnetenwatch-Personen,
  HDX-Katalog, Crossref-Themen, OpenAlex-Veröffentlichungen und Common-Crawl-URL-Index.
  Zusammen mit den bestehenden Adaptern sind 36 Provider registriert.
- 55 Quellen im kuratierten Recherchekatalog: 20 Adaptereinträge und 35 ausdrücklich
  gekennzeichnete Recherche-/Download-/Einrichtungszugänge. Vorhandene Adapter außerhalb
  dieses kuratierten Katalogs bleiben erreichbar.
- Planung verwendet `case_plans_496` und `case_plan_steps_496`; konkrete Anfragen liegen
  in `search_intents_114` und `search_queries_114`. Ausführung und Reservierung verwenden
  `case_plan_runs_497`, `provider_runs_120` und `provider_intake_120`.
- Ein Abfrage-Fingerabdruck bindet die Suchanfrage an den integritätsgeprüften Planschritt.
  Die Freigabe prüft zusätzlich den Snapshot der angezeigten Abfragen.
- Keine zweite Fall-, Identitäts- oder Belegdatenbank. Keine automatisch bestätigten
  Personenidentitäten, Beziehungen, Claims oder Evidence.
- Der Treffer behält seinen Provider, Quellbezug, Lauf, Abrufzeit und Kandidatenstatus.
  Bei der Übernahme in `research_leads_483` werden Kandidaten- und Laufkennung sowie der
  manuelle Zuordnungsgrund weitergegeben. Derselbe URL-Fund wird dort idempotent aufgenommen.
- Personen-Normalisierung übernimmt gezielt öffentliche Namen, Kennungen, Varianten und
  berufliche Kontextangaben; zusätzliche personenbezogene Felder des API-Datensatzes
  werden nicht in den normalisierten Personen-Kandidaten übernommen. JSON-Replays können
  die vom Anbieter gelieferte Antwort enthalten und unterliegen dem bestehenden Schutzkonzept.

## Kosten und tatsächlicher Anschluss

Ein kostenlos lesbares Angebot ist keine pauschale Freigabe für automatisierten Import
oder gewerbliche Weiterverwendung. Der Katalog beschreibt die jeweilige Grenze.
Kein Adapter erzeugt ein kostenpflichtiges Konto oder wechselt automatisch in einen Bezahltarif.

Media Cloud, DIP, GeoNames, ReliefWeb und Copernicus sind als einzurichtende Zugänge
erfasst. Sie erhalten keine erfundenen Schlüssel oder pauschalen Freigaben. Der aktuelle
Providertransport bleibt GET-only und ohne Zugangsdaten; TEDs öffentliche POST-Suche wird
deshalb als Recherchezugang geführt. ICIJ und amtliche Sanktionslisten sind als öffentliche
Recherche-/Downloadquellen verfügbar, ohne ungeprüften Vollimport. Aleph und ORCID werden
mit ihren jeweiligen Zugangs-/Nutzungsgrenzen angezeigt. Handelsregister-Einzelabrufe sind
von einem unzulässigen systematischen Registeraufbau zu unterscheiden.

Common Crawl erfordert eine konkrete veröffentlichte Sammlung und eine exakte öffentliche
URL. Ein Treffer verlinkt den kleinen Index; WARC-Pfad, Offset und Länge bleiben in den
Metadaten erhalten. Kein automatischer Download großer WARC-Sammeldateien. Da das
Antwortformat JSON Lines ist, bietet dieser Adapter ausdrücklich kein Replay an. Der
Provider-Motor respektiert nun `supports_replay=False` auch bei der Aufzeichnung eines
Live-Laufs. GDELT hat einen Mindestabstand von 5,1 Sekunden zwischen Abfragen.

## Prüfung des aktuellen Codes

```bash
PYTHONPATH=src:. python -m pytest -q tests/test_public_sources501.py tests/test_build500_release.py tests/test_build491_live_provider_approval.py
```

Ergebnis: **31 bestanden**. Geprüft wurden insbesondere die normalisierten Antwortschemata,
gebundene Quellenabfragen, Falltrennung, Rechte und CSRF, veränderte Freigabeansichten,
keine Netzwerkabfrage beim Vorbereiten, keine automatische Identitätsbestätigung,
einmalige Ausführung, NDJSON ohne falsches Replay sowie die idempotente Weitergabe
an den vorhandenen Recherchefund-Ablauf. Der bestehende Build-500-Anwendungs-/Paketvertrag
bleibt grün. Es wurden keine vollständigen historischen Build-Suiten wiederholt.

Zusätzliche kleine HTTP-Schemaabfragen über den HTTPS-Zugang der Entwicklungsumgebung:

| Neuer Adapter | Beobachtetes Ergebnis |
|---|---|
| GND/lobid | HTTP 200; zwei begrenzte Personenkandidaten normalisiert |
| Abgeordnetenwatch | HTTP 200; ein öffentlicher Personenkandidat normalisiert |
| HDX | HTTP 200; zwei Datensatzhinweise normalisiert |
| Crossref-Themen | HTTP 200; zwei Veröffentlichungshinweise normalisiert |
| OpenAlex-Veröffentlichungen | HTTP 200; zwei Veröffentlichungshinweise normalisiert |
| Common-Crawl-Index | HTTP 504 Gateway Timeout; kein erfolgreicher Live-Nachweis |

Diese HTTP-Schemaabfragen sind keine Fallläufe: Der reguläre EagleEye-Transport übernimmt
keine Umgebungs-Proxys; seine direkte DNS-Auflösung war in dieser Cloud-Umgebung nicht
verfügbar. Seine Schutzregeln wurden nicht abgeschwächt. Der vollständige lokale Ablauf
wurde mit kontrollierten Transportantworten geprüft. Ein aktueller Windows-/Laptoptest,
die noch erforderlichen individuellen Quellenzugänge und ein neues Installationspaket
sind dadurch nicht nachgewiesen.

## Offizielle Quellen und Dokumentation

- [GND/lobid](https://lobid.org/gnd/api), [GND-Lizenz und Abdeckung](https://lobid.org/gnd)
- [Abgeordnetenwatch API](https://www.abgeordnetenwatch.de/api), [Personenfelder](https://www.abgeordnetenwatch.de/api/entitaeten/politician)
- [HDX API](https://centre.humdata.org/ufaqs/about-the-humanitarian-data-exchange-api/)
- [Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/)
- [OpenAlex Zugang](https://help.openalex.org/api/authentication/)
- [Common-Crawl-Index](https://index.commoncrawl.org/), [Nutzungsbedingungen](https://commoncrawl.org/terms-of-use)
- [Lobbyregister-Personensuche](https://www.lobbyregister.bundestag.de/personensuche-im-lobbyregister)
- [EU Whoiswho](https://op.europa.eu/de/web/who-is-who)
- [Handelsregister-Nutzungsordnung](https://www.handelsregister.de/rp_web/information/welcome.xhtml)
- [ORCID Bedingungen](https://info.orcid.org/documentation/integration-and-api-faq/)
- [ICIJ Download/Lizenz](https://offshoreleaks.icij.org/pages/database)
- [GLEIF API](https://www.gleif.org/en/lei-data/gleif-api)
- [TED API](https://docs.ted.europa.eu/api/latest/search.html)
- [DIP Bedingungen](https://dip.bundestag.de/documents/nutzungsbedingungen_dip.pdf)

## Ergänzung: Bund, Bundestag und öffentliche Register

Die Rechercheart **Bund, Bundestag und öffentliche Register** bündelt Bundesanzeiger,
Unternehmensregister, Handelsregisterportal der Länder, DIP, Lobbyregister, Bundestag
Open Data und Wissenschaftliche Dienste, Bundesrat, GovData, Bundesgesetzblatt,
Gesetze/Rechtsprechung/Verwaltungsvorschriften im Internet, Bundeshaushalt,
Förderdatenbank und Bundesarchiv. Dies ist ein erweiterbarer Einstieg in öffentliche
Quellen, kein Anspruch auf Vollständigkeit aller Behördenangebote.

13 neue Recherche-/Downloadzugänge; kein neuer Live-Adapter und keine automatische
Bestellung kostenpflichtiger Unterlagen. Ein „Bundeshandelsregister“ ist keine eigene
zusätzliche Datenbank: Das gemeinsame Registerportal der Länder und das Unternehmensregister
werden als getrennte Zugänge geführt. Amtliche Registerkennungen, Registergericht,
Dokumentart, Veröffentlichungsdatum und Originalfundstelle sind beim Übernehmen zu
dokumentieren. Personenrollen bleiben nach Zeitraum und Identität prüfpflichtig.

Bundesanzeiger-Trefferlinks können sitzungsgebunden sein; für reproduzierbare Recherche
Fundstelle und Originaldokument sichern. Im Unternehmensregister sind hinterlegte
Jahresabschlussunterlagen und Beglaubigungen kostenpflichtig, obwohl die Recherche und
Registerinformationen kostenlos sind. Freie Einsicht bedeutet keine pauschale
Erlaubnis zum Aufbau eines vollständigen Parallelregisters.

Quellen: [Bundesanzeiger Suche](https://www.bundesanzeiger.de/pub/de/howto-search),
[Unternehmensregister Kosten](https://www.unternehmensregister.de/de/so-gehts/kosten),
[Bundestag Open Data](https://www.bundestag.de/services/opendata),
[Wissenschaftliche Dienste](https://www.bundestag.de/dokumente/analysen).
