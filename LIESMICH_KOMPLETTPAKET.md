# EagleEye – Komplettpaket (Stand 13. Nov. 2026)

Ein Ordner, ein Start: **`START_HIER.bat`** doppelklicken und auswählen.

| Auswahl | Was startet | Wofür |
|---|---|---|
| 1 | **PersonOSINT** (Einzelplatz) | Person oder Firma suchen: 35 Datenquellen, Treffer prüfen, Verbindungen, Belege, Dossier in Word/PDF |
| 2 | **PersonOSINT als Server** | wie 1, zusätzlich von anderen Rechnern im eigenen Netz erreichbar (Zwei-Faktor-Anmeldung Pflicht) |
| 3 | **EagleEye-Fallakte** (Build 500) | Beweisfeste Fallakte: Web-Belege, Dokumente, Rechercheplan mit Freigaben, Prüfregister, Bericht |
| 4 | **Quellen prüfen** | Zeigt, welche Datenquellen von diesem Rechner aus wirklich antworten |

## Voraussetzungen

- Windows 10 oder 11, **Python 3.12** (python.org; beim Installieren „Add python.exe to PATH“ ankreuzen).
- Internetverbindung beim ersten Start von PersonOSINT (lädt die benötigten Bibliotheken) und für die Datenquellen.
- Optional: Tesseract (Texterkennung für Scans), LibreOffice (Dossier als PDF/A).

## Erster Start (PersonOSINT)

1. `START_HIER.bat` → **1**. Beim ersten Mal wird die Umgebung eingerichtet (einige Minuten).
2. Im Browser das erste Konto anlegen und die Zwei-Faktor-Anmeldung einrichten.
3. `START_HIER.bat` → **4**: Quellen prüfen. Der Bericht `PersonOSINT\Quellen-Pruefbericht.md` zeigt, welche Quellen antworten.
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

## Ehrlicher Stand

- **Geprüft:** PersonOSINT 1.6 mit 107 automatischen Tests (SQLite und PostgreSQL) und Browser-Abnahme; EagleEye mit der vollen
  Regression (1976 Tests, Linux) und der Windows-Abnahme auf GitHub.
- **Noch offen:** Es sind weiterhin **zwei Anwendungen in einem Paket**, noch nicht eine. Der Plan für die Verschmelzung steht in
  `CLAUDE_REVIEW_UND_UEBERGABE_500.md`. Die meisten Datenquellen sind live noch nicht bestätigt (siehe `PersonOSINT\docs\QUELLEN.md`) –
  deshalb Schritt 3 oben. `START_HIER.bat` und die Server-Startdatei sind neu und wurden auf Windows noch nicht von Hand ausprobiert.
- EagleEye Build 500 ist ein interner Kandidat (Kennzeichnung der Entwickler: „HOLD“ bis zur Abnahme durch Sie).
- Rechtliches vor echten Fällen: `PersonOSINT\docs\compliance\` (Entwürfe, von Datenschutzbeauftragten und Anwalt prüfen lassen).
