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

**Bedienung:** Links steht immer dieselbe Seitenleiste. Oben der aktuell geöffnete Auftrag
(Aktenzeichen, Titel, Stand) mit einer Auswahl, um zu einem anderen offenen Auftrag zu wechseln.
Darunter die Bereiche **Büro, Auftrag, Recherche, Belege, Auswertung, Bericht** und
**Weitere** (alle Werkzeuge, klassische Fallübersicht, Mein Konto) sowie „Abmelden“.
Mit der Tab-Taste erreichst du zuerst „Zum Inhalt springen“.

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

**Büro → Einstellungen → Beweissicherung (Web-Belege)**

| Feld | Wofür |
|---|---|
| Zeitstempeldienst (RFC 3161) | Vorgabe `http://timestamp.digicert.com` (kostenlos). Für qualifizierte Zeitstempel nach eIDAS die Adresse eines qualifizierten Anbieters eintragen. An den Dienst geht nur eine Prüfsumme. |
| Browser für Seitenbilder | Leer lassen: EagleEye nimmt das vorhandene Microsoft Edge (oder Chrome). Nur bei abweichender Installation den Pfad zu `msedge.exe`/`chrome.exe` eintragen. |

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

### 3.3 Arbeitsliste der Auftragsart
Jede Auftragsart (Due Diligence, Hintergrundprüfung, Wirtschaftsermittlung, Personen- oder
Anschriftenermittlung, Vermisstensuche, Online-Recherche) bringt eine feste Arbeitsliste mit, die
in der Auftragsakte steht. Jeder Punkt hat einen Link zum passenden Werkzeug und wird als
**erledigt** oder **entfällt** (mit kurzer Begründung) markiert. Das Büro zeigt den Fortschritt
(z. B. „4/11“). Im Mandantenbericht erscheint die Liste als **Prüfumfang**: geprüft, nicht geprüft
oder entfällt mit Grund – so ist für den Mandanten nachvollziehbar, was geprüft wurde und was nicht.

### 3.4 Recherchieren
**Auftragsakte → Zur Recherche** öffnet den geführten Arbeitsablauf dieses Falls:

1. Webseiten und PDFs als Beleg sichern (WARC mit SHA-256, Haupttext, frühere Fassungen
   über das Internet Archive). **OPSEC:** Der Abruf geht von eurer Internetverbindung aus;
   die Gegenseite sieht eure IP-Adresse. EagleEye anonymisiert nicht – bei Bedarf eine
   eigene, dafür vorgesehene Verbindung verwenden.
   Beim Sichern zwei Zusätze (siehe 3.4.1): **Zeitstempel** (Vorgabe an) und **Seitenbild**.
2. Dokumente importieren (PDF, Word, Scans mit Texterkennung), Extraktion prüfen.
3. Befunde schreiben – jeder Befund hängt an seiner Originalfundstelle – und mit einer
   **Schutzklasse** versehen: offen, intern, besonders schutzwürdig (Art. 9/10 DSGVO).
4. Befunde prüfen (selbst oder durch ein zweites Konto).
5. Quellenunabhängigkeit, Entitäten-Abgleich und Netzwerkanalyse nutzen.

Suchbegriffe (Namen) werden in Formularen übertragen, nicht in der Adresszeile – sie
landen nicht im Browserverlauf.

#### 3.4.1 Zeitstempel, Seitenbild und Prüfpaket

- **Unabhängiger Zeitstempel (RFC 3161).** EagleEye schreibt zu jedem Web-Beleg ein kurzes
  *Beweismanifest* (Fall, Adresse, Abrufzeit, SHA-256 der WARC-Datei, der Serverantwort und
  des Seitenbilds) und lässt dessen Prüfsumme von einem Zeitstempeldienst signieren. Damit
  ist belegt, dass genau diese Sicherung zu diesem Zeitpunkt vorlag – auch gegenüber Dritten,
  die EagleEye nicht vertrauen. Der Dienst sieht nur die Prüfsumme, keine Adresse und keinen
  Inhalt. Die Antwort wird vor dem Speichern geprüft (Signatur, Prüfsumme, Einmalwert,
  Zertifikat für Zeitstempel). War der Dienst nicht erreichbar, bleibt die Sicherung
  vollständig; der Knopf **Zeitstempel einholen** in der Liste holt ihn nach. Ein später
  eingeholter Stempel wird als „nachträglich“ gekennzeichnet.
- **Seitenbild.** Auf Wunsch nimmt EagleEye mit dem vorhandenen Edge (unsichtbar, ohne
  Anmeldung, mit frischem Profil) ein Bild der ganzen Seite auf – sinnvoll bei Seiten, die
  erst im Browser entstehen (Soziale Netzwerke, Shops). **OPSEC:** Der Browser lädt die Seite
  mit allen eingebundenen Inhalten; auch Werbe- und Statistikanbieter sehen den Abruf. Ein
  Filter lässt nur öffentliche Adressen auf Port 80/443 zu und nur Server, die die Seite selbst
  anfordert: Die Seite kann den Browser weder ins Büronetz (Router, Drucker, NAS) schicken
  noch laufen Hintergrunddienste des Browsers mit. Gesperrte Anfragen werden in der Liste
  gezählt. Wird ein Seitenbild später ergänzt, zeigt es den *heutigen* Stand der Seite; der
  vorhandene Zeitstempel wird dann automatisch durch einen neuen ersetzt.
- **Prüfpaket.** Je Web-Beleg als ZIP: WARC-Datei, Seitenbild, Manifest, Zeitstempel
  (`.tsr`), Zertifikatskette, Prüfsummen und eine Anleitung, wie man alles ohne EagleEye
  nachprüft (`certutil -hashfile …`, `openssl ts -verify …`). Das Paket ist für Anwalt,
  Gericht oder Gutachter gedacht.
- Im **Mandantenbericht** steht beim Quellenverzeichnis, ob ein Seitenbild und ein gültiger
  Zeitstempel vorliegen.

Was das nicht leistet: Ein Zeitstempel belegt den Zeitpunkt der Sicherung, nicht die
Richtigkeit des Inhalts. Ein einfacher (nicht qualifizierter) Zeitstempel unterliegt der
freien Beweiswürdigung.

### 3.5 Zeit, Auslagen, Wiedervorlagen
In der Auftragsakte:

- **Zeit buchen**: Datum, Dauer (`1,5` oder `1:30`), Tätigkeit, Beschreibung, abrechenbar ja/nein.
- **Auslage buchen**: Fahrtkilometer (mit km-Satz) oder Betrag (Gebühren, Datenbankabfragen, Reisekosten).
- Falsche Einträge werden **storniert** (mit Grund), nicht gelöscht – sie bleiben durchgestrichen sichtbar.
- **Wiedervorlagen** mit Datum. Fällige und überfällige erscheinen im Büro unter „Braucht Aufmerksamkeit“.
- Ab 80 % des Budgets warnt das Büro.

### 3.6 Abrechnung und Rechnung
Einmalig unter **Büro → Rechnungen → Rechnungsangaben** Steuernummer (oder USt-IdNr.), IBAN,
BIC, Bank, Zahlungsziel und den Präfix der Rechnungsnummer eintragen; Name und Anschrift des
Büros stehen in den Einstellungen, die Anschrift des Mandanten in der Mandantenliste.

In der Auftragsakte zeigt **Abrechnung**, was noch nicht abgerechnet ist, und die Positionen der
nächsten Rechnung (Zeit je Tätigkeit × Stundensatz bzw. das Pauschalhonorar einmalig,
Fahrtkilometer, Auslagen). **Rechnung erstellen** vergibt die nächste fortlaufende Nummer
(z. B. `RE-2026-0001`), sperrt die abgerechneten Einträge und erzeugt die Rechnung als PDF mit
den Angaben nach § 14 UStG und dem Leistungsnachweis als Anlage. Fehlt eine Pflichtangabe, sagt
die App, welche – eine unvollständige Rechnung entsteht nicht.

- **Korrektur:** „stornieren“ erzeugt eine Stornorechnung mit eigener Nummer; die Nummern
  bleiben lückenlos, die Einträge werden wieder frei und können neu abgerechnet werden.
- **Zahlung:** „als bezahlt vermerken“. Überfällige Rechnungen erscheinen im Büro unter
  „Braucht Aufmerksamkeit“.
- **Buchhaltung:** Büro → Rechnungen zeigt das Rechnungsausgangsbuch je Jahr (netto, brutto,
  bezahlt, offen) und exportiert es samt Positionen als CSV.

Die steuerliche Einordnung (Umsatzsteuer, Kleinunternehmer, Aufbewahrung der Rechnungen) bitte
mit der Steuerberatung abstimmen.

### 3.7 Bericht und Leistungsnachweis
- **Bericht für Mandant (PDF)**: Briefkopf, Empfänger, Aktenzeichen, Auftrag, Ergebnisse
  mit nummerierten Quellenangaben, Methodik und Grenzen, Quellenverzeichnis mit Abrufzeit
  und SHA-256. Enthalten sind nur Befunde, die für die Empfängerstufe freigegeben sind:
  - *Mandant*: geprüfte Befunde mit Schutzklasse „offen“,
  - *Behörde/Gericht*: von einem zweiten Konto geprüfte Befunde mit unveränderter Quelle,
  - *intern*: alles (nicht zur Weitergabe).
  Was zurückgehalten wird, zeigt die Auftragsakte – nicht die Kopie des Mandanten.
- **Leistungsnachweis (PDF/CSV)**: Zeiten, Auslagen, Honorar, Umsatzsteuer. Er ist
  **keine Rechnung**; die Rechnung entsteht unter „Abrechnung“ (Abschnitt 3.6).
- **Büro → Zeiten für die Buchhaltung**: alle Zeiten eines Monats als CSV (für Excel).

### 3.8 Abschließen und löschen
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

**Verschlüsselt per Knopfdruck (empfohlen):** Büro → **Datensicherung** (nur Büroleitung).

1. Einmalig unter „Einstellungen“ den Sicherungsordner festlegen – am besten ein externes
   Laufwerk, z. B. `E:\EagleEye-Sicherung`. Ohne Angabe liegt er neben dem Arbeitsordner.
2. Sicherungspasswort (mindestens 12 Zeichen) zweimal eingeben, bestätigen, dass es getrennt
   aufbewahrt wird, und „Verschlüsselte Sicherung erstellen“. EagleEye muss dafür nicht
   geschlossen werden.
3. Die Datei `EagleEye-Sicherung_….eebak` ist mit AES-256 verschlüsselt. Ohne Passwort ist sie
   nicht lesbar – und nicht wiederherstellbar. Das Passwort wird nirgends gespeichert.
4. **Prüfen:** In der Liste „prüfen“ wählen und das Passwort eingeben. EagleEye entschlüsselt
   probeweise und vergleicht jede Datei mit ihrer Prüfsumme.
5. Es werden die letzten N Sicherungen aufbewahrt (Einstellung), ältere werden entfernt.
6. Ist die letzte Sicherung älter als das eingestellte Intervall (Vorgabe 7 Tage), erinnert das
   Büro unter „Braucht Aufmerksamkeit“.

**Wiederherstellen:** EagleEye schließen, `EAGLEEYE_WIEDERHERSTELLEN.bat` starten, die
`.eebak`-Datei wählen, im Fenster das Passwort eingeben und einen Zielordner wählen. Es entsteht
ein neuer Arbeitsordner; der bisherige bleibt unverändert. Alle Anmeldungen müssen danach neu
erfolgen.

**Weiterhin möglich:** `EAGLEEYE_SICHERUNG.bat` bei geschlossener App erzeugt eine
unverschlüsselte ZIP – nur auf ein verschlüsseltes Laufwerk legen.

Empfehlung: wöchentlich sichern, eine Kopie außer Haus aufbewahren, die Wiederherstellung einmal
im Quartal ausprobieren.

## 5. Was EagleEye nicht ist

- Keine Buchhaltungssoftware: Rechnungen und das Rechnungsausgangsbuch gehen als PDF/CSV an die Buchhaltung.
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
5. Freitags verschlüsselt sichern (Büro → Datensicherung).
