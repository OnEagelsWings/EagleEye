# EagleEye PersonOSINT 1.5

**Investigativrecherche · Personensuche · Vermisstenrecherche · Verbindungsanalyse · Word-Dossiers**

> **Neu in 1.1 (Ausbauphase 1 – Teambetrieb):** Anmeldung mit Pflicht-Zwei-Faktor, Rollen, Fallteams, Vier-Augen-Freigabe, vertrauliche Fälle (Quellenschutz), PostgreSQL, Docker-Server mit HTTPS, verschlüsselte Fotos und Sicherungen, manipulationssicheres Protokoll. Details unten.
>
> **Neu in 1.2 – OPSEC-Struktur:** drei OPSEC-Stufen je Fall mit technisch durchgesetzten Regeln, Netzausgänge über
> Proxy/Tor mit *fail closed*, Expositionsklassen für Quellen und Links, Außenkontakt-Protokoll, Metadaten-Bereinigung
> von Fotos und Exporten, Export-Register mit Export-ID, Briefing-Bestätigung, Decknamen und Schnellsperre.
> Siehe [OPSEC_KONZEPT.md](OPSEC_KONZEPT.md).
>
> **Neu in 1.3 – Datenbanken, Auswertung, Top-Dossier:** über 20 Quellen inkl. Firmenregister und lokaler Massendaten
> (OpenSanctions, ICIJ Offshore Leaks), strukturierte Aussagen statt Textschnipsel, Kandidatengruppen gegen Namensvettern,
> Admiralty-Bewertung, Widersprüche, Red Flags, Beweissicherung mit SHA-256, Top-Dossier mit Management Summary und
> Belegdichte (Word/PDF/A), Überwachung mit Benachrichtigungen und lokale KI-Zusammenfassung mit Fußnotenprüfung.
>
> **Neu in 1.4 – Betriebsreife:** Auftragsprüfung gegen Missbrauch (Warnsignale, Annahme nur durch Teamleitung mit Begründung),
> Löschfristen mit Erinnerung und Übersicht, Sicherheitsprüfung mit acht behobenen Befunden ([SECURITY_REVIEW.md](SECURITY_REVIEW.md)),
> Entwürfe für Verarbeitungsverzeichnis, DSFA, Löschkonzept und TOM ([docs/compliance](docs/compliance/README.md)),
> Pilot- und Abnahmeplan ([docs/pilot](docs/pilot/Pilot_und_Abnahme.md)) sowie Schulungsunterlagen ([docs/schulung](docs/schulung/)).
>
> **Neu in 1.5 – Zusammenführung:** Die Fähigkeiten aus EagleEye Build 492 und die Muster aus der SpiderFoot-/Obsidian-Analyse
> sind eingebaut: Web-Belege zusätzlich als **WARC** mit Wiedergabeprüfung und sauberem Haupttext, frühere Fassungen aus dem
> Internet Archive, **Dokument-Import** mit Texterkennung, **Quellenunabhängigkeit** (übernommene Texte zählen nicht als
> Bestätigung), begründeter **Namensabgleich über Schriften**, Netzwerkanalyse mit Export für Gephi, FollowTheMoney und
> Obsidian, **Folgesuchen** mit Freigabe und Herkunftskette, Korrelationsregeln – und die **Übergabe an die EagleEye-Fallakte**
> (Build 493–500). Siehe [docs/ZUSAMMENFUEHRUNG.md](docs/ZUSAMMENFUEHRUNG.md).

EagleEye PersonOSINT ist eine lokale OSINT-Plattform, die auf den Grundsätzen von EagleEye Build 380 aufbaut
(nur öffentliche Quellen, menschliche Prüfung, Zweckbindung, Protokollierung). Sie wurde als schlankes,
eigenständiges Nischenprodukt für drei Aufgaben neu programmiert:

| Aufgabe | Was die Plattform liefert |
|---|---|
| **Investigativrecherche** | Fallart mit Leitfaden (Hypothese, Quellenschutz, Belegsicherung, Gegenrecherche, Konfrontation Betroffener), vertraulich per Voreinstellung, Vier-Augen-Freigabe |
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

Beim ersten Aufruf legen Sie das **Administrationskonto** an und richten die **Zwei-Faktor-Anmeldung**
(Authenticator-App) ein. Für einen reinen Einzelplatz ohne 2FA: Umgebungsvariable `EAGLEEYE_REQUIRE_2FA=0`.

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

## Teambetrieb (Server mit PostgreSQL und HTTPS)

Für mehrere Personen läuft EagleEye als Server im Büronetz oder bei einem (deutschen) Hoster:

```bash
cd PersonOSINT/deploy
cp .env.example .env          # EAGLEEYE_DOMAIN, TLS, Sicherungszeit, ggf. Passphrase eintragen
./init-secrets.sh             # erzeugt DB-Passwort und Anwendungsschlüssel (zusätzlich offline sichern!)
docker compose up -d --build
```

Der Stack besteht aus **PostgreSQL** (nur intern erreichbar), der **App** (läuft als unprivilegierter Benutzer,
ohne eigenen offenen Port) und **Caddy** als HTTPS-Proxy (`EAGLEEYE_TLS=internal` im Büronetz oder eine E-Mail-Adresse
für Let's Encrypt). Hinter einem Firmen-Proxy mit eigener CA: `docker build --secret id=ca_bundle,src=ca.crt ..`.

### Rollen

| Rolle | Darf |
|---|---|
| Administration | Benutzer verwalten, Sicherheit & Sicherungen, alle **nicht vertraulichen** Fälle lesen und Team zuweisen – recherchiert nicht selbst |
| Teamleitung | alle nicht vertraulichen Fälle lesen/bearbeiten, zuweisen, freigeben, löschen |
| Analyst/in | Fälle anlegen; eigene und zugewiesene Fälle bearbeiten |
| Prüfer/in | zugewiesene Fälle prüfen und freigeben (Vier-Augen-Prinzip) |
| Leser/in | zugewiesene Fälle lesen und Dossiers exportieren, nichts ändern |

Fremde Fälle sind nicht nur gesperrt, sondern **unsichtbar** (die API antwortet mit „nicht gefunden“).

### Fallteam, Status und Vier-Augen-Prinzip

* Jeder Fall hat eine **verantwortliche Person**, optional eine **Prüfperson**, weitere Mitglieder (Bearbeitung/Prüfung/nur lesen),
  **Fälligkeit** und **Priorität**. Seitenleiste: *Alle · Meine · Zur Prüfung · Überfällig*.
* Status: offen → in Bearbeitung → **zur Prüfung** → **freigegeben** → abgeschlossen → archiviert.
  Freigeben darf nur die Prüfperson oder die Teamleitung – **nie die bearbeitende Person selbst**.
  Bis zur Freigabe trägt das Dossier den Vermerk „ENTWURF“.
* **Vertrauliche Fälle (Quellenschutz):** nur das Fallteam hat Zugriff – auch Teamleitung und Administration nicht.
  Im Gesamtprotokoll erscheinen Inhalte geschwärzt. Fällt die verantwortliche Person aus, kann die Administration einen
  **Notfallzugriff** (nur lesend) mit Begründung erteilen; er wird dauerhaft im Fallprotokoll vermerkt.
* **Gleichzeitiges Arbeiten:** Hinweis „Gerade ebenfalls im Fall: …“; ältere Stände können neuere Änderungen nicht
  überschreiben (optimistisches Sperren mit Hinweis zum Neuladen).

### Sicherheit

* Passwörter mit Argon2id, Mindestlänge 12, Sperre nach 5 Fehlversuchen (15 Minuten), keine Preisgabe, ob ein Konto existiert.
* **Zwei-Faktor-Anmeldung (TOTP)** standardmäßig Pflicht; Startpasswörter müssen bei der ersten Anmeldung geändert werden.
* Sitzungen: HttpOnly-/SameSite-Strict-Cookie (im Server „Secure“), CSRF-Token, Abmeldung nach Inaktivität (Standard 120 Min.).
  Rollenwechsel, Deaktivierung und Resets beenden alle Sitzungen der Person sofort.
* Content-Security-Policy, HSTS (über Caddy), Host-Prüfung gegen DNS-Rebinding.
* **Fotos und 2FA-Geheimnisse verschlüsselt** (Fernet/AES). Schlüssel getrennt vom Datenordner ablegen (`EAGLEEYE_KEY_FILE`).
* **Manipulationssicheres Protokoll:** Jeder Eintrag enthält den Hash seines Vorgängers (Hash-Kette). Prüfung unter
  *Verwaltung → Sicherheit* oder `python -m personosint verify-audit`. Beim Löschen eines Falls werden die Protokolltexte
  geschwärzt (DSGVO), die Kette bleibt prüfbar.

### Sicherungen

* Verschlüsselte Komplettsicherung (Tabellen, Benutzer, Protokoll, Fotos) per Klick (*Verwaltung → Sicherungen*),
  per Kommandozeile oder **automatisch täglich** (`EAGLEEYE_BACKUP_HOUR`, die letzten `EAGLEEYE_BACKUP_KEEP` bleiben).
* Mit `EAGLEEYE_BACKUP_PASSPHRASE` sind Sicherungen auch ohne Anwendungsschlüssel wiederherstellbar (empfohlen; Passphrase getrennt verwahren).
* Sicherungen sind datenbankunabhängig: damit gelingt auch der **Umzug vom Einzelplatz (SQLite) auf den Server (PostgreSQL)**.

### Kommandozeile

```bash
python -m personosint create-user --username anna --name "Anna Muster" --role analyst
python -m personosint reset-password anna | unlock anna | reset-2fa anna
python -m personosint backup [--out ORDNER]
python -m personosint verify-backup DATEI [--key SCHLÜSSELDATEI]
python -m personosint restore DATEI [--source-key SCHLÜSSELDATEI] [--force]
python -m personosint verify-audit
# im Docker-Stack:  docker compose exec app python -m personosint verify-audit
```

Umzug Einzelplatz → Server: lokal `python -m personosint backup` (mit gesetzter Passphrase), Datei auf den Server
kopieren, dort `docker compose exec app python -m personosint restore /backups/DATEI`.

### Wichtige Einstellungen (Umgebungsvariablen)

| Variable | Bedeutung |
|---|---|
| `EAGLEEYE_DATABASE_URL` | leer = SQLite; sonst `postgresql://user@host:5432/db` (Passwort über `EAGLEEYE_DB_PASSWORD_FILE`) |
| `EAGLEEYE_KEY_FILE` | Anwendungsschlüssel (Standard: `secret.key` im Datenordner) |
| `EAGLEEYE_REQUIRE_2FA` | Zwei-Faktor-Pflicht (Standard `1`) |
| `EAGLEEYE_ALLOWED_HOSTS` | zusätzlich erlaubte Hostnamen (Komma-getrennt) |
| `EAGLEEYE_COOKIE_SECURE` | `1` hinter HTTPS |
| `EAGLEEYE_SESSION_IDLE_MINUTES` / `EAGLEEYE_SESSION_MAX_HOURS` | Inaktivitäts- und Höchstdauer einer Sitzung |
| `EAGLEEYE_BACKUP_DIR`, `EAGLEEYE_BACKUP_HOUR`, `EAGLEEYE_BACKUP_KEEP`, `EAGLEEYE_BACKUP_PASSPHRASE` | Sicherungen |

## Datenbanken, Auswertung und Top-Dossier (Version 1.3)

Der Weg von der Abfrage zum belastbaren Dossier hat vier Stufen:

```
Quellen ──► Treffer ──► Aussagen (Subjekt – Prädikat – Objekt, Zeitraum, Quelle)
                          │
                          ├─► Kandidatengruppen (Namensvettern trennen) ─► Prüfung durch Menschen
                          ├─► Admiralty-Code, Mehrfachbelege, Widersprüche, Red Flags
                          └─► Beweissicherung (Archiv + SHA-256) ─► Top-Dossier (Belegdichte, Fußnoten) ─► Word / PDF/A
```

### 1. Quellen & Daten (Verwaltung → 📚 Quellen & Daten)

| Bereich | Quellen | Schlüssel |
|---|---|---|
| Wirtschaft & Register | **UK Companies House** (Funktionen, Zeiträume, Geburtsmonat), **OpenCorporates** (140+ Register), **GLEIF** (Sitz, Konzernmütter) | CH: kostenlos; OC: optional |
| Register & Wissen | **Wikidata-Beziehungen** (Familie, Arbeitgeber, Ämter, Mitgliedschaften), Wikidata, OpenAlex, ORCID, Internet Archive | – |
| Domains & Technik | **crt.sh** (Subdomains, Zertifikate einer E-Mail), **RDAP** (Registrierung, Registrar, Nameserver) | – |
| Risiko & Compliance | **OpenSanctions** (online), INTERPOL Yellow Notices | OpenSanctions: Lizenz |
| Online-Präsenz | Benutzernamen-Check (13 Plattformen), GitHub, GitLab, Bluesky, Mastodon, Gravatar | – |
| **Lokale Referenzdaten** | **OpenSanctions-Gesamtdaten**, **ICIJ Offshore Leaks**, **eigene Listen (CSV)** – Abfragen verlassen den Server nicht | – |

* Jede Quelle trägt Lizenz, Kosten, Verlässlichkeit (Admiralty A–F) und Exposition; **Testen** prüft sie über den Standard-Netzausgang.
* API-Schlüssel werden verschlüsselt gespeichert. Abfragen werden je Quelle gedrosselt (Limits, Unauffälligkeit).
* Lokale Bestände: „Herunterladen & importieren“ oder Datei hochladen; große Dateien per Kommandozeile:
  `python -m personosint import-refdata opensanctions targets.simple.csv` · `… import-refdata icij full-oldb.LATEST.zip`.
  Hinweis zur Lizenz: OpenSanctions-Daten sind für kommerzielle Nutzung lizenzpflichtig; ICIJ verlangt Quellenangabe.

### 2. Auswertung (Reiter „Suche & Treffer“ → 👥 Kandidatengruppen, Reiter „📊 Fakten & Bewertung“)

* **Kandidatengruppen:** offene Treffer werden nach Geburtsdatum, Organisationen, Benutzernamen und Orten zu möglichen
  Personen gebündelt; unterschiedliche Geburtsdaten trennen immer. Die richtige Gruppe wird als Ganzes bestätigt, Namensvettern
  mit einem Klick verworfen. Bestätigte Beziehungen erscheinen automatisch im Netzwerkgraphen.
* **Admiralty-Code** je Aussage (z. B. `A1`, `B2`): Verlässlichkeit der Quelle × Glaubwürdigkeit der Information, automatisch aus
  Quelle, Prüfstatus und **Mehrfachbelegen** – manuell änderbar mit Begründung.
* **Widersprüche** (z. B. zwei Geburtsjahre) werden erkannt und lassen sich per Klick auflösen.
* **Red Flags** (Sanktion, PEP, Offshore, viele/kurze Mandate, häufige Wechsel, aufgelöste Firmen, Sammeladresse, eigene Liste,
  widersprüchliche Identität) – Schweregrad und Aktivierung je Regel in der Verwaltung.

### 3. Beweissicherung und Top-Dossier (Reiter „Dossier & Export“)

* **📎 Beleg sichern** ruft eine Fundstelle über den OPSEC-Netzausgang des Falls ab, speichert sie verschlüsselt, versiegelt sie
  mit SHA-256 und ergänzt eine Internet-Archive-Kopie. Das **Beweispaket** (ZIP) enthält alle Belege mit Manifest und Prüfanleitung.
* **Vorlagen:** Volldossier, Kurzprofil (2 Seiten), Due-Diligence-Bericht, Vermisstendossier.
* **Management Summary** mit Kernaussagen, Auffälligkeiten, Unsicherheiten und **Belegstärke**; je Kapitel die **Belegdichte**
  (Anteil mehrfach belegter, aus zuverlässiger Quelle bestätigter oder gesicherter Aussagen); jede Aussage mit Admiralty-Code und Fußnote;
  Quellenverzeichnis mit Abrufzeit, Beleg-Hash und Archivkopie.
* **Berichtslayout** (Verwaltung → 🎨): Organisation, Logo, Farbe, Fußzeile, Hinweistext. **PDF/A** über LibreOffice
  (im Docker-Image enthalten, abschaltbar mit `EAGLEEYE_WITH_PDF=0`).

### 4. Überwachung und KI-Zusammenfassung

* **🔁 Überwachung** (Reiter „Suche & Treffer“): die aktuelle Quellenauswahl läuft alle 6 h … wöchentlich im Namen der anlegenden Person –
  unter den OPSEC-Regeln des Falls (fehlt der Ausgang oder das Briefing, wird blockiert und gemeldet). Neue Treffer melden sich über die 🔔 beim Fallteam.
* **🤖 KI-Zusammenfassung** (Reiter „Dossier & Export“): ein **lokales** Sprachmodell (z. B. Ollama, Docker-Profil `ki`) formuliert aus den
  bestätigten Aussagen einen Text mit Fakten-Kennungen. EagleEye prüft jede Kennung und markiert unbelegte Sätze; erst nach Freigabe durch einen
  Menschen erscheint der Text – mit aufgelösten Fußnoten – in der Management Summary. Nur Dienste im eigenen Netz sind erlaubt; die Anfrage
  läuft nie über Proxy/Tor.

## OPSEC (Schutz von Recherche, Recherchierenden und Quellen)

Kurzfassung – vollständig in [OPSEC_KONZEPT.md](OPSEC_KONZEPT.md):

| Stufe | Wann | Was die Software erzwingt |
|---|---|---|
| 1 · Standard | unkritische Recherchen | Kennzeichnung der Exposition, Metadaten-Bereinigung, Export-Register |
| 2 · Erhöht | Zielperson soll nichts merken | zusätzlich: nur über Anonymisierungs-Ausgang (blockiert statt direkt), neutraler User-Agent, Deckname, Briefing, Karte nur auf Klick |
| 3 · Streng | gefährdete Quellen | zusätzlich: Fall zwingend vertraulich, keine sichtbaren Zugriffe, keine automatische Verortung, Export nur durch Bearbeitung/Prüfung |

* **Netzausgang einrichten:** Verwaltung → 🛡 OPSEC → „Ausgang anlegen“ (HTTP-Proxy mit CONNECT). Tor im Docker-Stack:
  `docker compose --profile tor up -d`, dann Ausgang `http://tor:9080` anlegen und **testen** (zeigt Ausgangs-IP).
* **Im Fall:** Reiter **🛡 OPSEC** – Stufe, Ausgang, Briefing, Außenkontakt-Protokoll („Wer konnte was sehen?“), Export-Register.
* **Schnellsperre:** `Strg+Alt+L`.

## Datenschutz, Ethik und Sicherheit

* Jeder Fall verlangt **Zweck und Rechtsgrundlage**; beides steht im Dossier und im Protokoll.
* Nur öffentliche Quellen, keine Logins, kein Umgehen von Zugangsschranken.
* Die Anwendung lauscht als Einzelplatz nur auf `127.0.0.1`; technische Schutzmaßnahmen siehe *Teambetrieb → Sicherheit*.
* Fälle lassen sich vollständig löschen (inkl. Fotos); Protokolltexte werden dabei geschwärzt.
* **Auftragsprüfung** im Fall-Assistenten: Fragen nach Beziehung zur Zielperson, Schutzsituation (Frauenhaus, Kontaktverbot,
  Auskunftssperre), reiner Anschriftenermittlung ohne Anspruch und – bei Vermisstenfällen – freiwilligem Kontaktabbruch.
  Bei Warnsignalen darf nur die Teamleitung den Auftrag mit Begründung annehmen; das Ergebnis steht im Protokoll und im Dossier.
* **Löschfristen:** beim Abschluss automatisch gesetzt (Standard in *Verwaltung → Löschfristen*), Erinnerung bei Erreichen,
  Übersicht fälliger Fälle. Gelöscht wird bewusst nur durch Menschen.
* Rechtliche Entwürfe (Verarbeitungsverzeichnis, DSFA, Löschkonzept, TOM, Auftragsprüfung): [docs/compliance](docs/compliance/README.md) –
  vor dem Einsatz von DSB und Rechtsberatung prüfen lassen.
* Sicherheitsprüfung und Restrisiken: [SECURITY_REVIEW.md](SECURITY_REVIEW.md).
* Vermisstenfälle: Die Plattform unterstützt Angehörige und Fachstellen, ersetzt aber keine Polizeiarbeit.

## Entwicklung

```bash
cd PersonOSINT
pip install -r requirements.txt
python -m pytest -q          # Ende-zu-Ende-Tests mit simulierten Quellen (kein Netz nötig)
# zusätzlich gegen PostgreSQL (Datenbank wird geleert!):
EAGLEEYE_TEST_PG_URL=postgresql://user@localhost:5432/eagleeye_test python -m pytest -q
```

API-Dokumentation: `http://127.0.0.1:8380/api/docs`

```
PersonOSINT/
├── personosint/
│   ├── api.py        HTTP-API, Anmeldung/Rechte, Verwaltung, Exporte
│   ├── auth.py       Benutzer, Rollen, Argon2, TOTP-2FA, Sitzungen
│   ├── service.py    Fälle, Rechte, Team, Vier-Augen, Suche, Prüfung, Verbindungen, Vermisstenmodul, Hash-Kette
│   ├── connectors.py Firmenregister, GLEIF, Wikidata-Beziehungen, crt.sh, RDAP, OpenSanctions
│   ├── refdata.py    lokale Referenzdatenbanken (OpenSanctions, ICIJ, eigene Listen)
│   ├── facts.py      Faktenmodell (Prädikate, Normalisierung)
│   ├── analysis.py   Kandidatengruppen, Admiralty-Bewertung, Widersprüche, Red Flags
│   ├── evidence.py   Beweissicherung und Beweispaket
│   ├── report.py     Top-Dossier (Vorlagen, Management Summary, Belegdichte, PDF/A)
│   ├── monitor.py    Überwachung und Benachrichtigungen
│   ├── ai.py         lokaler KI-Assistent mit Fußnotenprüfung
│   ├── opsec.py      OPSEC-Stufen, Netzausgänge, Exposition
│   ├── db.py         SQLite/PostgreSQL, Migrationen, optimistisches Sperren
│   ├── crypto.py     Verschlüsselung ruhender Daten
│   ├── backup.py     verschlüsselte, datenbankunabhängige Sicherung/Wiederherstellung
│   ├── config.py     Einstellungen (Umgebungsvariablen)
│   ├── sources.py    öffentliche Quellen + Recherchelinks
│   ├── matching.py   Normalisierung und Treffer-Bewertung
│   ├── graph.py      Zentralität, Gruppen, Pfade, Layout
│   ├── dossier.py    Word-Dossier, Suchplakat, Graph-Rendering
│   ├── demo.py       fiktiver Beispielfall
│   └── static/       Oberfläche (HTML/CSS/JS, Canvas-Graph, Leaflet-Karte)
├── deploy/           Docker-Compose (PostgreSQL + App + Caddy/HTTPS), Caddyfile, init-secrets.sh
├── Dockerfile
└── tests/
```
