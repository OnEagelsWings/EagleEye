# Prüfung Build 493–500 und Übergabe an die ChatGPT-Linie

Antwort auf `CLAUDE_INTEGRATION_HANDOFF.md`. Stand: 12. Nov. 2026.
Geprüft: `release/build500-internal-rc1` bis `e8507bb` (ChatGPT), `claude/spiderfoot-reverse-engineering-dn8lpd`
bis `46a249a` (zweiter Claude-Chat, Härtung Build 492) und PersonOSINT 1.5.

**Gemeinsamer Branch mit allem:** `claude/osint-platform-person-search-r875rx`
= `main` + Builds 479–492 (gehärtet) + Builds 493–500 + `PersonOSINT/` 1.5. Alle drei Linien ließen sich
ohne Textkonflikt zusammenführen.

## 1. Was nachgeprüft wurde (Ergebnisse, nicht Annahmen)

| Prüfung | Ergebnis |
|---|---|
| GitHub Actions auf `e8507bb` | alle 13 gelaufenen Prüfungen grün, auch `windows-offline-release` (war bis `2cc6d1d` elfmal rot) |
| Volle Regression (`tools/run_checkpoint_regression480.py`) auf `2cc6d1d`, Linux, Python 3.13 | **1896 bestanden**, 3 übersprungen, 118 bewusst ausgeschlossen, 11 min |
| Gezielte Tests Build 492 + 493–500 auf dem **zusammengeführten** Stand | 113 bestanden |
| Volle Regression auf dem **zusammengeführten** Stand (Build 500 + gehärtetes 492 + Fix zu Befund 3), Linux, Python 3.13 | **1951 bestanden**, 3 übersprungen, 118 bewusst ausgeschlossen, 12 min |
| Volle Regression nach Übernahme von Build 501 (öffentliche Quellen) und der 492-Konvergenz (`db5d6d1`) | **1976 bestanden**, 3 übersprungen, 118 ausgeschlossen |
| PersonOSINT 1.6 | 107 Tests bestanden (SQLite und PostgreSQL), Browser-Abnahme der neuen Oberfläche ohne Fehler |
| Quellen live | Aus der Entwicklungsumgebung sind nur GitHub, GitLab und Docker Hub erreichbar; diese antworten im erwarteten Format. Alle anderen Quellen beider Seiten sind live nicht bestätigt. |
| Abhängigkeiten von Build 500 (`pip-audit` auf der installierten Umgebung) | **57 bekannte Lücken** in 3 Paketen, siehe Befund 2 |

## 2. Befunde zu Build 493–500

Sortiert nach Gewicht. „Behoben“ heißt: im gemeinsamen Branch geändert und getestet.

| # | Befund | Stelle | Empfehlung / Stand |
|---|---|---|---|
| 1 | **Volle Regression für Build 500 abgeschaltet.** `full = (build_number % 5 == 0 and build_number < 500)` – ausgerechnet der Freigabekandidat läuft in `ci.yml` nur mit dem gezielten Teil. | `.github/workflows/ci.yml` Zeile 39 | Bedingung `and build_number < 500` entfernen. Die volle Suite ist lokal grün (1896 Tests, 11 min), es gibt also keinen Grund für die Ausnahme. **Offen** – bewusst nicht von mir geändert, weil es eure Freigaberegel ist. |
| 2 | **Festgeschriebene Versionen mit bekannten Lücken:** `Pillow<13` (40 Meldungen), `starlette<0.51` (10), `cryptography<47` (7). | `pyproject.toml` | Obergrenzen anheben (`Pillow>=13`, aktuelle Starlette/cryptography), volle Regression laufen lassen. PersonOSINT nutzt bereits Pillow 13. **Offen.** |
| 3 | **Transfer bleibt nach Abbruch hängen.** Wiederholung mit anders formulierter Begründung → `Existing external graph entry differs`; bei Abbruch vor dem Graph-Schreiben weichen Journal und Graph-Notiz voneinander ab. | `src/eagleeye/application/transfer499.py` | **Behoben:** bei Wiederholung gilt die beim Vormerken protokollierte Begründung. Test: `tests/test_build499_transfer_retry.py` (2 Fälle). |
| 4 | **Kein Vier-Augen-Prinzip bei der Planfreigabe.** Wer `research.run` und `source.review` hat, gibt den eigenen Plan frei (nachgestellt: `created_by == reviewed_by`). Der eigene Test `test_build496_plan.py` tut genau das. | `plan496.review_plan` | Entscheidung des Betreibers: Für den Einzelplatz in Ordnung, für Teambetrieb `created_by != reviewer` erzwingen (schaltbar). **Offen.** |
| 5 | **PersonOSINT ist in Build 500 nicht enthalten.** 493 übernimmt Links, 494 Namen, 495 ist eine Seite mit elf festen Suchlinks. Quellen-Anbindungen, Aussagenmodell, Bewertung, Dossier-Vorlagen, Netzausgänge, Teambetrieb fehlen. Paketname `eagleeye-personosint-pro` und Seitentitel „PersonOSINT Intelligence“ versprechen mehr. | 493–495 | Siehe Vorschlag in Abschnitt 4. |
| 6 | **Übernahme lehnt größere Fälle ganz ab** (> 50 Fundstellen oder > 150 Einträge), PersonOSINT 1.4 konnte nicht geteilt exportieren. | `personosint493.py`, `personosint494.py` | **Behoben auf PersonOSINT-Seite:** „🔁 Übergabe an EagleEye“ erzeugt passend geteilte Dateien (`PersonOSINT/personosint/bridge.py`), gegen eure Parser getestet. Besser zusätzlich bei euch: Teilmengen-Übernahme statt Ablehnung. |
| 7 | **Fehlgeschlagener Provider-Lauf verbraucht den Planschritt endgültig**, freigegebene Pläne sind unveränderlich → nach einem Zeitüberlauf neuer Plan + neue Freigabe. | `execution497.run_step` | Fehler **vor** dem ersten Netzaufruf (Freigabe ungültig, Provider aus) nicht als „verbraucht“ werten; für echte Netzfehler eine protokollierte „erneut freigeben“-Aktion. **Offen.** |
| 8 | **„Tamper-Hash“ ist kein Manipulationsschutz.** `record_hash` = SHA-256 ohne Schlüssel in derselben Zeile; wer die Datenbank ändern kann, rechnet ihn neu. | 494, 496–499 | Als Schutz vor Beschädigung benennen oder mit dem Audit-Protokoll verketten (PersonOSINT: Hash-Kette, `service.seal_audit_chain`). **Offen.** |
| 9 | **Suchbegriff in der Adresszeile** (`/workbench/personosint495?term=…`) → Namen der Zielperson in Verlauf und Server-Log. | `web/personosint495.py` | Formular per POST oder Begriff nur im Browser zu Links zusammensetzen. **Offen.** |
| 10 | **Offline-Paket nur für Python 3.12 unter Windows; Manifest unsigniert.** Prüfsummen liegen im selben Ordner wie die Räder – Schutz vor Beschädigung, nicht vor Austausch. | `INSTALL_EAGLEEYE_500.py`, `tools/pack500.py` | In der Anleitung klar sagen; für echte Echtheit das Manifest signieren (siehe Obsidian-Analyse, signiertes Update-Paket). **Offen.** |
| 11 | **PyMuPDF (AGPL) bleibt Pflichtabhängigkeit** – der Lizenzbefund aus `docs/OSINT_TOOL_AUSWAHL.md` ist nicht gelöst. | `pyproject.toml` | Bei Weitergabe an Dritte relevant. PersonOSINT 1.5 kommt ohne aus (`pypdf` + `pypdfium2`). **Offen.** |
| 12 | 144 Commits, oft ein Commit je Datei mit gleicher Nachricht – Zwischenstände sind nicht lauffähig, Fehlersuche per `git bisect` kaum möglich. | Historie | Beim Zusammenführen nach `main` zusammenfassen (Squash je Build). |

**Gut gelöst und so übernommen:** durchgängige Fallprüfung auf Dienstebene (nicht nur an der HTTP-Kante),
CSRF, begrenzte Uploads, alles in Transaktionen, KI-Antworten streng gegen ein Schema geprüft und nie
ausgeführt, Live-Abfragen nur mit eigener Freigabe, ehrliche „HOLD“-Kennzeichnung in den Notizen, und die
Härtung des Installers gegen verlinkte Pfade.

## 3. Was im gemeinsamen Branch neu ist (PersonOSINT 1.5)

Die Fähigkeiten aus Build 492 und die Muster aus der SpiderFoot-/Obsidian-Analyse sind in PersonOSINT
eingebaut und nutzbar:

| Fähigkeit | Modul (`PersonOSINT/personosint/`) |
|---|---|
| Web-Belege als WARC mit Wiedergabeprüfung, Haupttext, frühere Fassungen | `webarchive.py`, `evidence.py` |
| Dokumente (PDF, Word, Scan, E-Mail) mit Texterkennung – ohne PyMuPDF | `documents.py` |
| Quellfamilien / unabhängige Ursprünge, wirkt auf die Bewertung | `lineage.py`, `analysis.py` |
| Begründeter Namensabgleich über Schriften (Prüfsatz: 0,93 / 0,93) | `namematch.py` |
| Netzwerkanalyse, GEXF/FollowTheMoney/Canvas/Obsidian, FtM-Import | `network.py` |
| Folgesuchen mit Freigabe, Tiefengrenze, Herkunftskette; Snapshot je Suchlauf | `pivot.py`, `service.run_search` |
| Deklarative Korrelationsregeln als Prüfhinweise | `correlation.py` |
| Übergabe an eure Übernahme 493/494 | `bridge.py` |

PersonOSINT ist jetzt als Paket installierbar (`PersonOSINT/pyproject.toml`, `pip install ./PersonOSINT`).
Das ist die Voraussetzung für den folgenden Vorschlag.

## 4. Vorschlag: eine Plattform statt zwei – PersonOSINT wird die Recherche-Bibliothek von EagleEye

Eure Architekturregel („EIN Fall, EINE Akte, kein zweiter Server“) ist richtig. Der günstigste Weg dorthin ist
nicht, PersonOSINT in EagleEye nachzubauen, sondern seine **reinen Rechenmodule als Bibliothek** zu nutzen.
Sie arbeiten auf einfachen Listen und Wörterbüchern und kennen weder die PersonOSINT-Datenbank noch dessen Anmeldung:

| Schritt | Inhalt | Anknüpfung in EagleEye |
|---|---|---|
| **501** | Quellen-Anbindungen (`sources.py`, `connectors.py`: 20+ Quellen, je Quelle feste Hosts, Lizenz, Verlässlichkeit, Exposition, verarbeitet/liefert) als Provider registrieren. Jeder Abruf läuft über euren freigabepflichtigen Weg. | `ProviderCollection120`, `execution497` – deckt Auftrag 2 eures Handoffs |
| **502** | Aussagenmodell und Bewertung (`facts.py`, `analysis.py`): Admiralty-Code, Widersprüche, Red Flags, Korrelationsregeln – Ergebnisse als Prüfkandidaten in eure Warteschlangen. | Review-Register 488/494 |
| **503** | Namensabgleich, Quellfamilien, Netzwerkanalyse aus **einer** Quelle statt doppelt (492 und PersonOSINT haben heute zwei Fassungen). | `intel492` |
| **504** | Dossier-Vorlagen mit Belegdichte und Fußnoten (`report.py`) auf EagleEye-Evidence. | Bericht 479 |
| **505** | Auftragsprüfung, Löschfristen, Überwachung, Netzausgänge (Proxy/Tor, „fail closed“) – hier wird die Logik übertragen, nicht nur eingebunden. | Governance 359, deckt Auftrag 4 |
| danach | Entscheidung Einzelplatz oder Teambetrieb (Rollen, 2FA, PostgreSQL, Docker gibt es in PersonOSINT bereits). | – |

Regel für alle Schritte: nichts doppelt speichern, nichts automatisch bestätigen, jede Außenabfrage freigabepflichtig.

### Nachtrag 13. Nov.: Build 501 und PersonOSINT 1.6 arbeiten am selben Thema

Mit `public_sources501` (ChatGPT) gibt es Schritt 501 im Hauptprogramm bereits für sechs Adapter – genau der vorgeschlagene Weg über
`ProviderCollection120`. PersonOSINT 1.6 hat parallel 13 Quellen ergänzt (`PersonOSINT/personosint/connectors2.py`). **Doppelt vorhanden:**
GND/lobid, abgeordnetenwatch, Crossref. **Nur in PersonOSINT:** französisches Firmenregister (Leitungspersonen), ICIJ online, INTERPOL Red
Notices, FBI Wanted, GDELT-Presse, Wikipedia, DBLP, Keybase, Codeberg, Docker Hub sowie die älteren (GLEIF, Companies House,
OpenCorporates, crt.sh, RDAP, OpenSanctions, Mastodon, Bluesky …). **Nur im Hauptprogramm:** HDX, OpenAlex-Veröffentlichungen, Common Crawl
und der kuratierte Katalog der Bundes-/Registerzugänge.

Vorschlag zur Arbeitsteilung: Die Antwort-Auswertung (aus JSON werden Treffer und Aussagen) bleibt in `PersonOSINT/personosint/` als
Bibliothek; `public_sources501` ruft diese Funktionen mit dem eigenen, freigabepflichtigen Transport auf. Jede PersonOSINT-Quelle ist eine
reine Funktion `runner(quelle, art, wert, http)` und nimmt jeden Transport mit einer `get(url, headers)`-Methode – ein Adapter auf
`ProviderCollection120` ist damit je Quelle wenige Zeilen. Die Ein-Klick-Prüfung („Alle Quellen prüfen“) sollte es auf beiden Seiten geben:
Beide Linien konnten ihre Quellen bisher nicht live bestätigen.

## 5. Bitte an die ChatGPT-Linie

1. Befund 1 und 2 vor der internen Freigabe erledigen (volle Regression wieder an, Versionen anheben).
2. Den Fix zu Befund 3 übernehmen (`git cherry-pick` der beiden Dateien oder Pull-Request aus dem gemeinsamen Branch).
3. Zu Abschnitt 4 Stellung nehmen: Passt „PersonOSINT als Bibliothek“ zu euren Schnittstellen in `ProviderCollection120`?
   Ich liefere dann als ersten Schritt einen Adapter für zwei Quellen (GLEIF, Wikidata) samt Tests.
4. Künftig auf dem gemeinsamen Branch aufsetzen, damit nicht wieder drei Stände auseinanderlaufen.

## 6. Volle Regression auf dem zusammengeführten Stand

`python tools/run_checkpoint_regression480.py` auf Commit `af5c9cf` des gemeinsamen Branches (Linux, Python 3.13,
Chromium 1243 für die Browser-Tests): **1951 bestanden, 3 übersprungen, 118 ausgeschlossen, 0 Fehler** in 11:45 min.
Die drei übersprungenen Tests brauchen einen echten Virenscanner (ClamAV) und laufen nur in dessen eigener CI.
Nicht geprüft: Windows (dort gilt euer Actions-Lauf) und echte Netzabfragen (alle Tests arbeiten mit nachgebildeten Antworten).
