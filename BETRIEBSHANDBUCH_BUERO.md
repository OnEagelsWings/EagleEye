# EagleEye im Büroalltag – Betriebshandbuch

Für kleine Detekteien, OSINT- und Intelligence-Büros (1–10 Personen). Stand: 16.11.2026,
Build 500 mit Büroverwaltung. Dieses Handbuch beschreibt, was die App heute kann – und wo
ihre Grenzen liegen.

## 1. Installieren und starten (Windows)

1. ZIP vollständig entpacken, z. B. nach `C:\EagleEye`.
2. `START_EAGLEEYE_PRO.bat` doppelklicken. Beim ersten Start wird die Laufzeitumgebung
   eingerichtet (einige Minuten), danach öffnet sich der Browser.
3. Beim allerersten Start legst du das Konto der **Büroleitung** an (alle Rechte).
4. Die Arbeitsdaten liegen getrennt vom Programmordner (siehe Startmeldung). Ein Update
   ersetzt den Programmordner, nicht die Daten.

Nach der Anmeldung öffnet sich das **Büro**. Es ist ab jetzt die Startseite.

## 2. Einmal einrichten (Büroleitung)

**Büro → Einstellungen**

| Feld | Wofür |
|---|---|
| Name, Anschrift, Kontakt | Briefkopf von Bericht und Leistungsnachweis |
| Fußzeile für Berichte | z. B. „Vertraulich – nur für den genannten Empfänger bestimmt.“ |
| Standard-Stundensatz, Kilometersatz | Vorgabe für neue Aufträge und Fahrtkosten |
| Umsatzsteuer | Regelbesteuerung (Satz) oder Kleinunternehmer (§ 19 UStG) |
| Präfix für Aktenzeichen | z. B. `DA` → `DA-2026-0001` |
| Aufbewahrung nach Abschluss | Vorgabe 36 Monate – an das eigene Löschkonzept anpassen |

**Büro → Team**: Mitarbeitende mit Anmeldename, Anzeigename, Rolle und Startpasswort
anlegen. Rollen im Büro:

| Rolle | Darf |
|---|---|
| Büroleitung | alles, sieht alle Aufträge, Einstellungen, Team, Löschung |
| Ermittler/in | Aufträge anlegen, in zugeordneten Aufträgen recherchieren und buchen |
| Prüfer/in | Befunde zugeordneter Aufträge prüfen (Vier-Augen) |
| nur lesen | zugeordnete Aufträge ansehen |

Wer welchen Auftrag sieht, legst du in der **Auftragsakte → Team dieses Auftrags** fest
(Fallleitung, Ermittler/in, Analyst/in, Prüfer/in, Berichtsautor/in, nur lesen).

Konten: Jede Person ändert ihr Passwort unter **Büro → Mein Konto**. Die Büroleitung kann
unter **Team** ein Passwort zurücksetzen (die Person muss beim nächsten Anmelden ein eigenes
wählen) und Konten sperren – gesperrte Konten werden sofort abgemeldet.

## 3. Ein Auftrag von Anfang bis Ende

### 3.1 Auftrag anlegen
**Büro → Neuen Auftrag anlegen.** Mandant wählen oder neu erfassen, Titel, Auftragsart,
Auftrag und Zweck, Rechtsgrundlage (mit Erläuterung), Eingang, Abgabefrist, Honorar
(Stundensatz oder Pauschale, optional Budget-Obergrenze), Ergebnisempfänger und
Empfängerstufe des Berichts. Fall und Auftragsakte entstehen in einem Schritt, das
Aktenzeichen wird fortlaufend vergeben.

### 3.2 Auftragsprüfung (Pflicht vor der Recherche)
Schützt Zielpersonen vor Missbrauch der Ergebnisse und dich vor einer Mitverantwortung.

- Fragen zu persönlicher Beziehung, Schutzsuche, Schutzanordnung/Auskunftssperre,
  Anschriftenermittlung ohne Anspruch, freiwilligem Kontaktabbruch (nur Vermisstensuche),
  geprüfter Identität des Auftraggebers. **„Unklar“ zählt als Warnsignal.**
- Warnsignal → Annahme nur mit schriftlicher Begründung (mindestens 30 Zeichen) durch die
  Fallleitung oder Büroleitung.
- Bekannte Schutzanordnung oder Auskunftssperre → **nur Ablehnung möglich**, außer ein
  Gericht oder eine Behörde ist Auftraggeber.
- Checkliste Identitätsprüfung (Ausweis eingesehen – keine Kopie ohne Rechtsgrundlage,
  Vollmacht, Anspruchsunterlagen, Zweck, Ergebnisempfänger).

Bis zur Annahme – und wieder nach Abschluss, Ablehnung oder Anhalten – sperrt EagleEye für
diesen Fall Web-Sicherungen und Live-Abfragen über die Quellen-Adapter. Suchlinks, die du
selbst im Browser öffnest, kann die App nicht sperren. Taucht später ein
Warnsignal auf (z. B. Hinweis auf ein Frauenhaus): **Auftragsakte → Warnsignal melden**.
Der Auftrag ruht, bis die Prüfung wiederholt ist.

### 3.3 Recherchieren
**Auftragsakte → Zur Recherche** öffnet den geführten Arbeitsablauf dieses Falls:

1. Webseiten und PDFs als Beleg sichern (WARC mit SHA-256, Haupttext, frühere Fassungen
   über das Internet Archive). **OPSEC:** Der Abruf geht von eurer Internetverbindung aus;
   die Gegenseite sieht eure IP-Adresse. EagleEye anonymisiert nicht – bei Bedarf eine
   eigene, dafür vorgesehene Verbindung verwenden.
2. Dokumente importieren (PDF, Word, Scans mit Texterkennung), Extraktion prüfen.
3. Befunde schreiben – jeder Befund hängt an seiner Originalfundstelle – und mit einer
   **Schutzklasse** versehen: offen, intern, besonders schutzwürdig (Art. 9/10 DSGVO).
4. Befunde prüfen (selbst oder durch ein zweites Konto).
5. Quellenunabhängigkeit, Entitäten-Abgleich und Netzwerkanalyse nutzen.

Suchbegriffe (Namen) werden in Formularen übertragen, nicht in der Adresszeile – sie
landen nicht im Browserverlauf.

### 3.4 Zeit, Auslagen, Wiedervorlagen
In der Auftragsakte:

- **Zeit buchen**: Datum, Dauer (`1,5` oder `1:30`), Tätigkeit, Beschreibung, abrechenbar ja/nein.
- **Auslage buchen**: Fahrtkilometer (mit km-Satz) oder Betrag (Gebühren, Datenbankabfragen, Reisekosten).
- Falsche Einträge werden **storniert** (mit Grund), nicht gelöscht – sie bleiben durchgestrichen sichtbar.
- **Wiedervorlagen** mit Datum. Fällige und überfällige erscheinen im Büro unter „Braucht Aufmerksamkeit“.
- Ab 80 % des Budgets warnt das Büro.

### 3.5 Bericht und Leistungsnachweis
- **Bericht für Mandant (PDF)**: Briefkopf, Empfänger, Aktenzeichen, Auftrag, Ergebnisse
  mit nummerierten Quellenangaben, Methodik und Grenzen, Quellenverzeichnis mit Abrufzeit
  und SHA-256. Enthalten sind nur Befunde, die für die Empfängerstufe freigegeben sind:
  - *Mandant*: geprüfte Befunde mit Schutzklasse „offen“,
  - *Behörde/Gericht*: von einem zweiten Konto geprüfte Befunde mit unveränderter Quelle,
  - *intern*: alles (nicht zur Weitergabe).
  Was zurückgehalten wird, zeigt die Auftragsakte – nicht die Kopie des Mandanten.
- **Leistungsnachweis (PDF/CSV)**: Zeiten, Auslagen, Honorar, Umsatzsteuer. Er ist
  **keine Rechnung**; die Rechnung schreibt eure Buchhaltungssoftware.
- **Büro → Zeiten für die Buchhaltung**: alle Zeiten eines Monats als CSV (für Excel).

### 3.6 Abschließen und löschen
- **Stand ändern → Abgeschlossen**: ab heute läuft die Aufbewahrungsfrist.
- Nach Fristablauf erscheint der Auftrag im Büro unter „Löschung prüfen“.
- **Löschung vorbereiten** (nur Büroleitung) zeigt, was gelöscht wird. Bestätigung durch
  Abtippen des Aktenzeichens. Vor Fristablauf nur mit Begründung (z. B. Löschverlangen).
- Vorher werden alle Datenbanken nur gelesen. Ist eine nicht lesbar, wird **nichts** gelöscht und
  die Vorschau nennt die Datei.
- Bricht die Löschung ab (z. B. Datei gesperrt), ist der Löschauftrag vermerkt: Das Büro meldet
  „Löschung unvollständig“, im **Löschprotokoll → Löschung fortsetzen** wird sie zu Ende geführt.
- Dateien, die den Fall nur im Inhalt erwähnen (z. B. gemeinsame Übersichten), werden nicht
  gelöscht, sondern in Vorschau und Löschprotokoll zur Prüfung aufgeführt.
- Gelöscht werden alle Inhalte des Falls in allen Datenbanken, Dokument- und Berichtsdateien; freie
  Datenbankseiten werden überschrieben. Bestehen bleiben: der Mandant in der
  Mandantenliste, das Löschprotokoll (nur Aktenzeichen, Daten, Umfang) und Einträge in
  zwei fallübergreifend verketteten Protokollen (nur Kennungen) – das Löschprotokoll
  weist sie aus.
- **Frühere Sicherungen enthalten den Fall weiterhin**, bis sie ersetzt werden.

## 4. Datensicherung

1. EagleEye vollständig schließen.
2. `EAGLEEYE_SICHERUNG.bat` ausführen. Es entsteht ein Sicherungsarchiv des gesamten Arbeitsbestands.
3. Das Archiv auf ein **verschlüsseltes** Laufwerk kopieren (z. B. BitLocker To Go) –
   die Sicherung selbst ist nicht verschlüsselt.
4. Wiederherstellen mit `EAGLEEYE_WIEDERHERSTELLEN.bat` in einen neuen Ordner.

Empfehlung: wöchentlich sichern, mehrere Generationen aufbewahren, die Wiederherstellung
einmal im Quartal ausprobieren.

## 5. Was EagleEye nicht ist

- Keine Rechnungs- oder Buchhaltungssoftware.
- Keine Anonymisierung von Abrufen.
- Keine automatische Wahrheitsfeststellung: KI-Vorschläge, Treffer und Beziehungen bleiben
  Hinweise, bis ein Mensch sie am Original geprüft hat.
- Kein zertifiziertes forensisches Produkt. Die App zeigt den Hinweis „Entwicklungsstand:
  keine Produktivfreigabe“. Vor dem Einsatz mit echten personenbezogenen Daten:
  Sicherungs- und Wiederherstellungsprobe auf dem Zielrechner, Festplattenverschlüsselung,
  eigenes Verzeichnis von Verarbeitungstätigkeiten und Löschkonzept.

## 6. Kurz: der Tagesablauf

1. Büro öffnen → „Braucht Aufmerksamkeit“ abarbeiten (Prüfungen, Fristen, Wiedervorlagen).
2. Im Auftrag recherchieren, Belege sichern, Befunde schreiben und prüfen.
3. Zeiten und Auslagen sofort buchen.
4. Bericht und Leistungsnachweis erzeugen, Auftrag abschließen.
5. Freitags sichern.
