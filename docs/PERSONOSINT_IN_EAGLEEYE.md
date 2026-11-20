# PersonOSINT als Recherche-Motor der EagleEye-Fallakte

Stand: 20. Nov. 2026 · Schritte 501 und 502 der Zusammenführung

## Was sich für die Arbeit ändert

Bisher waren PersonOSINT und die Fallakte zwei Programme. Ergebnisse gingen über eine Exportdatei hin und her.
Jetzt sind die PersonOSINT-Quellen, die der Fallakte fehlten, direkt in der Fallakte verfügbar. Die Auswertung von PersonOSINT
läuft auf den Treffern des Falls.

1. **Recherche → Quellen & Personen**: Rechercheart wählen (Person, Unternehmen, Benutzername, E-Mail-Adresse, Webadresse, Ort),
   Suchbegriff eingeben, Quellen ankreuzen. Die Quellen des PersonOSINT-Motors sind an „PersonOSINT“ bzw. an ihrem Namen erkennbar.
2. Suchpaket anlegen → freigeben (Prüfbegründung) → je Quelle einmal abfragen. Das ist derselbe Weg wie bei allen anderen Quellen:
   Ohne Freigabe gibt es keine Abfrage. Jede Abfrage geht nur an die festen Adressen der Quelle und wird protokolliert.
3. Die Treffer landen als **ungeprüfte Kandidaten** im Prüfeingang des Falls.
4. **Auswertung → Personenanalyse** zeigt für den Fall:
   * **Warnhinweise**, z. B. Sanktionsliste, politisch exponierte Person, Offshore-Bezug, viele oder kurze Mandate, widersprüchliche
     Identitätsangaben. Ein Warnhinweis ist ein Prüfauftrag, kein Vorwurf.
   * **Widersprüche**: Angaben, die nur einen Wert haben können, mit verschiedenen Werten, etwa zwei Geburtsdaten. Das deutet oft
     auf zwei verschiedene Personen gleichen Namens hin.
   * **Querbezüge**: dieselbe Adresse oder dieselbe Firma bei mehreren Personen.
   * **Alle Aussagen** mit Bewertungscode: Der Buchstabe A–F gibt an, wie verlässlich die Quelle ist. Die Ziffer 1–6 gibt an, wie
     glaubwürdig die Aussage ist. Außerdem steht dabei, wie viele unabhängige Quellen die Aussage stützen.
5. Lehnen Sie einen Kandidaten im Prüfeingang ab oder markieren Sie ihn als Dublette, zählen seine Aussagen in der Analyse als verworfen.

Die Analyse-Seite fragt selbst nichts ab und verändert nichts.

## Die Quellen

| Quelle | Rechercheart | Hinweis |
|---|---|---|
| Benutzernamen-Check (13 Plattformen) | Benutzername | GitHub, GitLab, Codeberg, Reddit, Keybase, Hacker News, Chess.com, Lichess, Docker Hub, dev.to, PyPI, Telegram, Bluesky – nur „Konto vorhanden“, keine Inhalte |
| Keybase | Benutzername | mit kryptografisch bestätigten Verknüpfungen zu anderen Konten |
| Codeberg | Benutzername, Person | |
| Docker Hub | Benutzername | |
| Gravatar | E-Mail-Adresse | abgefragt wird nur ein Prüfwert der Adresse, nicht die Adresse selbst |
| crt.sh | Webadresse | Zertifikate und Unterdomains einer Domain |
| Wikipedia (de/en) | Person, Thema, Unternehmen | |
| OpenStreetMap Nominatim | Ort | höchstens eine Abfrage je Sekunde |
| Frankreich – Firmenregister | Unternehmen, Person | Firmen samt eingetragener Geschäftsleitung |
| ICIJ Offshore Leaks | Person, Unternehmen | ein Eintrag ist kein Straftatnachweis |
| INTERPOL – Fahndung / Vermisste | Person | Namensgleichheit ist kein Treffer |
| FBI – Wanted | Person | Namensgleichheit ist kein Treffer |

### Bewusst nicht übernommen

| Quelle | Grund |
|---|---|
| GitHub, GitLab, Bluesky, Mastodon, Wikidata, OpenAlex, Wayback, GLEIF, RDAP, GND, Abgeordnetenwatch, Crossref, DBLP, GDELT | hat die Fallakte schon als eigene Quelle |
| ORCID | Die öffentliche Schnittstelle ist nur für nichtkommerzielle Dienste erlaubt. Im Büroeinsatz bleibt deshalb die manuelle Suche im Katalog. |
| OpenCorporates, Companies House, OpenSanctions | brauchen einen Zugangsschlüssel bzw. eine Lizenz. Die Fallakte sendet grundsätzlich keine Zugangsdaten mit. |
| Wikidata-Beziehungen | Die Abfrage ist zweistufig. Die Freigabe gilt aber für genau eine vorher gezeigte Abfrage. |
| Lokale Listen (Sanktionen u. a.) | bleiben in PersonOSINT. Sie werden dort als Datei eingelesen. |

PersonOSINT als eigenes Programm (Einzelplatz oder Server) bleibt unverändert nutzbar. Es enthält zusätzlich die Quellen aus der
zweiten Tabelle.

## Technisch (für Entwickler)

* `src/eagleeye/infrastructure/providers/personosint_bridge.py` stellt je Quelle einen `ProviderAdapter` bereit:
  * `build_requests` lässt die PersonOSINT-Quelle gegen eine Attrappe laufen und merkt sich nur die Adressen. Dabei gibt es keinen Netzzugriff.
  * `normalize` wartet, bis alle geplanten Antworten da sind. Erst dann wertet die Quelle sie aus, wieder ohne eigenen Netzzugriff.
  * Ergebnis sind `NormalizedProviderItem` mit `raw_payload.claims`, `identity_confirmed=False` und `candidate_only=True`.
* `metadata["http_4xx_is_result"]` gibt 4xx-Antworten an `normalize` weiter. Für alle anderen Provider bleibt das Verhalten unverändert.
* `supports_replay=False`: Die Aufzeichnung für die Offline-Wiederholung verlangt JSON. Kontoquellen liefern oft leere 404-Antworten oder HTML.
* Die Auswertung (`application/personosint_analysis502.py`) ruft `personosint.analysis.assess`, `red_flags` und
  `personosint.correlation.evaluate` mit den eingebauten Regeln auf.
* Das Paket enthält `personosint` (siehe `pyproject.toml`). Ohne installiertes Paket wird der Ordner `PersonOSINT` neben `src` verwendet.
  Fehlt beides, ist die Brücke leer und die Analyse-Seite meldet das.
* Tests: `tests/test_personosint_engine501.py`.
