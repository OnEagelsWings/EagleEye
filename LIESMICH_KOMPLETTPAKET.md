# EagleEye – Komplettpaket (Stand 23. Nov. 2026)

Ein Ordner, ein Start: **`START_HIER.bat`** doppelklicken und auswählen.

| Auswahl | Was startet | Wofür |
|---|---|---|
| **V** | **EagleEye Vault** (empfohlen) | Ihre private Recherche-Station im Browser: verschlüsselt (Passphrase + Zwei-Faktor-App), nur auf diesem Rechner erreichbar, Internet nur, wenn Sie es für eine Recherche freigeben. Darin die volle PersonOSINT-Oberfläche mit **Tiefenrecherche** (automatische Varianten, Dorks, Folgespuren), **Vermisstenregistern** und **Tarnung** (Legenden, neue Netzidentität je Suche). Anleitungen: `PersonOSINT\docs\VAULT.md`, `PersonOSINT\docs\TIEFENRECHERCHE.md` |
| 1 | **PersonOSINT** (Einzelplatz) | Person oder Firma suchen: 37 Datenquellen, Treffer prüfen, Verbindungen, Belege, Dossier in Word/PDF |
| 2 | **PersonOSINT als Server** | wie 1, zusätzlich von anderen Rechnern im eigenen Netz erreichbar (Zwei-Faktor-Anmeldung Pflicht) |
| 3 | **EagleEye-Fallakte** (Build 500) | Büro und Fallakte: Mandanten, Aufträge, Zeiten, Rechnungen, Datensicherung; Web-Belege, Dokumente, Rechercheplan mit Freigaben, Prüfregister, Bericht (Bedienung: `BETRIEBSHANDBUCH_BUERO.md`) |
| 4 | **Quellen prüfen** | Zeigt, welche Datenquellen von diesem Rechner aus wirklich antworten |

## Voraussetzungen

- Windows 10 oder 11, **Python 3.12** (python.org; beim Installieren „Add python.exe to PATH“ ankreuzen).
- Internetverbindung beim ersten Start von PersonOSINT (lädt die benötigten Bibliotheken) und für die Datenquellen.
- Optional: Tesseract (Texterkennung für Scans), LibreOffice (Dossier als PDF/A).

## Erster Start (PersonOSINT)

1. `START_HIER.bat` → **1**. Beim ersten Mal wird die Umgebung eingerichtet (einige Minuten).
2. Im Browser das erste Konto anlegen und die Zwei-Faktor-Anmeldung einrichten.
3. `START_HIER.bat` → **4**: Quellen prüfen. Die Berichte `Quellen-Pruefbericht-PersonOSINT.md` und `Quellen-Pruefbericht-Fallakte.md`
   im Hauptordner zeigen, welche Quellen von Ihrem Rechner aus antworten. Für den Fallakten-Teil vorher einmal **3** starten.
4. Mit dem Beispielfall auf der Startseite vertraut machen (Handbuch: `PersonOSINT\docs\schulung\Analysten_Handbuch.md`).

## Später mit mehreren Personen (Serveroption)

- **Im eigenen Büro-Netz:** `START_HIER.bat` → **2**. Das Fenster zeigt die Adresse für die anderen Rechner. Jede Person bekommt ein
  eigenes Konto mit Rolle. Dieselben Daten wie im Einzelplatz – Sie können jederzeit wechseln.
- **Dauerbetrieb oder Zugriff von außen:** Server mit Docker, PostgreSQL und HTTPS – Anleitung in `PersonOSINT\README.md`,
  Abschnitt „Teambetrieb“. Die Daten ziehen per Sicherung/Wiederherstellung um.

## Wie die beiden Teile zusammenarbeiten

| Richtung | Weg |
|---|---|
| PersonOSINT → EagleEye-Fallakte | In PersonOSINT: *Dossier & Export → „Übergabe an EagleEye“*. Die Dateien in der Fallakte unter „PersonOSINT-Quellen importieren“ einlesen. |
| EagleEye-Fallakte → PersonOSINT | In der Fallakte den Graphen im FollowTheMoney-Format exportieren, in PersonOSINT unter *Verbindungen → „FollowTheMoney einlesen“* laden. |
| **PersonOSINT in der Fallakte** (neu) | Ohne Umweg: In der Fallakte unter *Recherche → Quellen & Personen* stehen 13 zusätzliche Quellen des PersonOSINT-Motors (Benutzernamen-Check auf 13 Plattformen, Keybase, Codeberg, Docker Hub, Gravatar, crt.sh, Wikipedia, Nominatim, Firmenregister Frankreich, ICIJ Offshore Leaks, INTERPOL, FBI). Sie laufen über denselben Freigabeweg wie alle anderen Quellen. Die Auswertung – Widersprüche, Warnhinweise, Querbezüge, Bewertung jeder Aussage – steht unter *Auswertung → Personenanalyse*. Beschreibung: `docs\PERSONOSINT_IN_EAGLEEYE.md`. |

## Ehrlicher Stand

- **Geprüft:** PersonOSINT mit 90 automatischen Tests (dazu PostgreSQL-Läufe) und Browser-Abnahme; EagleEye mit der vollen Regression
  (rund 2130 Tests, Linux) und der Windows-Abnahme auf GitHub. Alle Bibliotheken sind auf Stand ohne bekannte Sicherheitslücken
  (Prüfung mit `pip-audit`, 20. Nov.).
- **Enthalten sind alle aktiven Entwicklungsstränge** (ChatGPT, beide Claude-Chats). Welcher ältere Zweig wo steht: `docs\ZWEIGE_STAND.md`.
- **Zusammenwachsen:** PersonOSINT ist der Recherche-Motor der Fallakte. Seine Quellen und seine Auswertung sind dort eingebaut.
  Namensabgleich, Quellfamilien und Netzwerkanalyse gibt es nur noch einmal; beide Oberflächen nutzen dieselbe Fassung. Beide
  Oberflächen bleiben vorerst nebeneinander bestehen. Einzelheiten: `docs\PERSONOSINT_IN_EAGLEEYE.md`.
- **Noch offen:** Die meisten Datenquellen sind live noch nicht bestätigt. Von der Entwicklungsumgebung aus erreichen sie das Internet
  nicht, deshalb ist Schritt 3 oben (`QUELLEN_PRUEFEN.bat`, prüft jetzt Fallakte und PersonOSINT) auf Ihrem Rechner wichtig.
  `START_HIER.bat` und die Server-Startdatei wurden auf Windows noch nicht von Hand ausprobiert.
- EagleEye Build 500 ist ein interner Kandidat (Kennzeichnung der Entwickler: „HOLD“ bis zur Abnahme durch Sie).
- Zwei Bausteine von ChatGPT sind enthalten, aber ausdrücklich noch Vorstufen: die Firecrawl-Anbindung (kostenpflichtig, nur mit eigenem
  Schlüssel, nur für freigegebene Behördenseiten) und die Austausch-Schnittstelle unter `tools\research_exchange` (Prototyp, nur mit
  Testdaten verwenden).
- Rechtliches vor echten Fällen: `PersonOSINT\docs\compliance\` (Entwürfe, von Datenschutzbeauftragten und Anwalt prüfen lassen).
