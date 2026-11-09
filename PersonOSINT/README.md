# EagleEye PersonOSINT 1.0

**Personensuche · Vermisstenrecherche · Verbindungsanalyse · Word-Dossiers**

EagleEye PersonOSINT ist eine lokale OSINT-Plattform, die auf den Grundsätzen von EagleEye Build 380 aufbaut
(nur öffentliche Quellen, menschliche Prüfung, Zweckbindung, Protokollierung). Sie wurde als schlankes,
eigenständiges Nischenprodukt für drei Aufgaben neu programmiert:

| Aufgabe | Was die Plattform liefert |
|---|---|
| **Personensuche** | Automatische Abfrage öffentlicher Quellen, Benutzernamen-Check auf 13 Plattformen, nachvollziehbare Treffer-Bewertung (Score 0–100 mit Begründung), über 40 vorbereitete Recherchelinks |
| **Vermisstenfälle** | Vermisstenprofil, automatische Gefährdungseinschätzung, Zeitleiste mit Karte und Bewegungslinie, Leitfaden-Checkliste, **Suchplakat als Word-Datei**, INTERPOL Yellow Notices |
| **Verbindungsanalyse** | Interaktiver Netzwerkgraph, Pfadsuche zwischen zwei Personen, Schlüsselakteure (Zentralität), automatische Verbindungsvorschläge |
| **Dossier** | Strukturiertes **Word-Dossier (.docx)** mit Deckblatt, Foto, Netzwerkgrafik, Zeitleiste, Erkenntnissen mit Quellenbelegen und Protokoll |

## Start

Voraussetzung: **Python 3.11 oder neuer**.

* **Windows:** Doppelklick auf `START_PERSONOSINT.bat`
* **Linux/macOS:** `./start_personosint.sh`

Beim ersten Start wird automatisch eine Python-Umgebung eingerichtet. Danach öffnet sich der Browser mit
`http://127.0.0.1:8380/`. Wer nichts installieren möchte, kann direkt starten:

```bash
pip install -r requirements.txt
python -m personosint                 # Optionen: --port 8380 --data <Ordner> --no-browser
```

Daten liegen lokal in einer SQLite-Datei (`%APPDATA%\EagleEye-PersonOSINT` bzw. `~/.local/share/EagleEye-PersonOSINT`,
änderbar über `--data` oder die Umgebungsvariable `EAGLEEYE_PERSONOSINT_DATA`).
Zum Ausprobieren gibt es auf der Startseite einen **fiktiven Beispielfall**.

## Arbeitsablauf in der Oberfläche

1. **Neuer Fall** – Assistent in drei Schritten: Fallart → Zweck & Rechtsgrundlage (Pflicht) → Zielperson.
2. **Personen & Profile** – Profil, Identifikatoren (Name, Alias, Benutzername, E-Mail, Telefon, Orte, Arbeitgeber), Foto, Recherchelinks.
3. **Suche & Treffer** – Quellen wählen, Suche starten, Treffer mit Score und Begründung prüfen.
   *Bestätigen* übernimmt den Treffer automatisch als Knoten/Kante in den Graphen.
4. **Verbindungen** – Graph (ziehen, zoomen, filtern), Pfadsuche, Vorschläge, Schlüsselakteure, PNG-Export.
5. **Zeitleiste & Karte** – Sichtungen und Bewegungen mit automatischer Verortung (OpenStreetMap).
6. **Aufgaben** – Leitfaden-Checklisten je Fallart, eigene Aufgaben.
7. **Dossier & Export** – Word-Dossier, Suchplakat, Netzwerkgrafik, vollständiger JSON-Export.
8. **Protokoll** – lückenlose Aufzeichnung aller Arbeitsschritte.

Die Übersicht zeigt jederzeit den **nächsten sinnvollen Schritt** und den Fortschritt des Falls.

## Quellen (ohne API-Schlüssel)

| Quelle | Eingabe | Zweck |
|---|---|---|
| Benutzernamen-Check | Benutzername | GitHub, GitLab, Codeberg, Reddit, Keybase, Hacker News, Chess.com, Lichess, Docker Hub, dev.to, PyPI, Telegram, Bluesky |
| GitHub, GitLab | Benutzername / Name | Profile inkl. Ort, Arbeitgeber, Webseite |
| Bluesky, Mastodon | Name / Benutzername | Soziale Profile |
| Gravatar | E-Mail | Profil und verknüpfte Konten hinter einer E-Mail |
| Wikidata | Name | Personen des öffentlichen Lebens |
| OpenAlex, ORCID | Name | Wissenschaftler/innen mit Institution |
| INTERPOL Yellow Notices | Name | Internationale Vermisstenausschreibungen |
| Internet Archive | URL | Historische Kopien von Profilen/Webseiten |
| OpenStreetMap Nominatim | Ort | Koordinaten für Karte und Graph |

Jede Quelle ist auf ihre Hosts beschränkt. Fällt eine Quelle aus (Netz, Rate-Limit), läuft die Suche mit den
übrigen weiter und zeigt den Fehler an. Zusätzlich erzeugt die Plattform **manuelle Recherchelinks**
(Suchmaschinen-Dorks, LinkedIn/XING/Facebook/Instagram/TikTok, Telefonbuch, North Data, Handelsregister,
BKA-Fahndung, Presseportal, Initiative Vermisste Kinder, NamUs, Bilder-Rückwärtssuche) – diese werden nicht
automatisch abgerufen.

## Bewertung der Treffer

Jeder Treffer erhält einen Score mit lesbaren Gründen, z. B.:

* exakte Übereinstimmung über E-Mail/Telefon (+55), Benutzername existiert (+35)
* Namensgleichheit (+40) bzw. Ähnlichkeit mit Umlaut-/Reihenfolge-Toleranz (Jaro-Winkler)
* Ort, Arbeitgeber, bekannter Benutzername oder Geburtsjahr erwähnt (+10 bis +15, nur Ganzwort-Treffer)
* deutlich abweichender Name (−15)

≥ 75 = hoch, ≥ 45 = mittel, ≥ 20 = niedrig. **Ein Score ist kein Identitätsnachweis** – entscheidend ist die menschliche Prüfung.

## Datenschutz, Ethik und Sicherheit

* Jeder Fall verlangt **Zweck und Rechtsgrundlage**; beides steht im Dossier und im Protokoll.
* Nur öffentliche Quellen, keine Logins, kein Umgehen von Zugangsschranken.
* Die Anwendung lauscht standardmäßig nur auf `127.0.0.1`, prüft den Host-Header (Schutz gegen DNS-Rebinding)
  und verlangt für schreibende API-Aufrufe eine Client-Kennung (Schutz gegen Cross-Site-Requests).
  Weitere Hostnamen nur bewusst über `EAGLEEYE_ALLOWED_HOSTS` freigeben.
* Fälle lassen sich vollständig löschen (inkl. Fotos).
* Vermisstenfälle: Die Plattform unterstützt Angehörige und Fachstellen, ersetzt aber keine Polizeiarbeit.

## Entwicklung

```bash
cd PersonOSINT
pip install -r requirements.txt
python -m pytest -q          # Ende-zu-Ende-Tests mit simulierten Quellen (kein Netz nötig)
```

API-Dokumentation: `http://127.0.0.1:8380/api/docs`

```
PersonOSINT/
├── personosint/
│   ├── api.py        HTTP-API, Sicherheits-Middleware, Exporte
│   ├── service.py    Fälle, Personen, Suche, Prüfung, Verbindungen, Vermisstenmodul
│   ├── sources.py    öffentliche Quellen + Recherchelinks
│   ├── matching.py   Normalisierung und Treffer-Bewertung
│   ├── graph.py      Zentralität, Gruppen, Pfade, Layout
│   ├── dossier.py    Word-Dossier, Suchplakat, Graph-Rendering
│   ├── demo.py       fiktiver Beispielfall
│   └── static/       Oberfläche (HTML/CSS/JS, Canvas-Graph, Leaflet-Karte)
└── tests/
```
