# EagleEye Vault – private Recherche-Station

Der Vault ist Ihre Recherche-Oberfläche im Browser. Er arbeitet wie ein Tresor: Er ist geschlossen, bis Sie ihn öffnen, und er
geht nur ins Internet, wenn Sie es für eine Recherche erlauben.

## Starten

`START_HIER.bat` → **V**, oder direkt `PersonOSINT\START_VAULT.bat`.

Beim ersten Mal richtet sich die Python-Umgebung ein (einige Minuten). Danach öffnet sich ein **eigenes Browserfenster** mit dem
Sperrbildschirm.

**Erster Start – Einrichtung in drei Schritten (ca. 3 Minuten):**

1. **Name und Passphrase.** Am besten ein Satz aus vier oder mehr Wörtern. Bisherige PersonOSINT-Daten können Sie dabei
   übernehmen (Häkchen); sie werden in den Vault kopiert und dort verschlüsselt.
2. **Zwei-Faktor-App verbinden.** QR-Code mit Microsoft Authenticator, Aegis, 2FAS o. Ä. scannen und den Code eingeben.
3. **Wiederherstellungsschlüssel notieren.** Er wird nur einmal angezeigt. Bewahren Sie ihn auf Papier und getrennt vom Rechner auf.

**Täglich:** Passphrase und den Code aus der App eingeben, dann auf **Vault öffnen** klicken.

## Arbeiten

Nach dem Öffnen sehen Sie die gewohnte Oberfläche: Fälle anlegen, Personen erfassen, Quellen abfragen, Treffer prüfen, Verbindungen
analysieren, Dossier exportieren. Darüber liegt die **Vault-Leiste**:

| Element | Bedeutung |
|---|---|
| **⛔ Netz aus** / **🌐 Netz offen · 14:59** | Ob das Programm gerade ins Internet darf, und wie lange noch |
| **Netz öffnen …** | Zeitfenster wählen (5 Minuten bis 2 Stunden), optional den Zweck. Danach schließt es sich von selbst. |
| **Verbindungen** | Jede Quellenabfrage dieser Sitzung: Ziel, Zeit, erlaubt oder blockiert |
| **✓ verschlüsselt gespeichert** | Änderungen werden alle paar Sekunden verschlüsselt auf die Platte geschrieben. |
| **Sperre in … min** | Ohne Eingabe sperrt sich der Vault nach der eingestellten Zeit selbst (Standard 15 Minuten). |
| **⚙** | Sperrzeit, Standard-Zeitfenster, Passphrase ändern, neuen Wiederherstellungsschlüssel erzeugen |
| **📁 Fallakte** | Öffnet die EagleEye-Fallakte (Büro, Mandanten, Rechnungen, beweissichere Web-Belege) in einem zweiten Fenster – ohne zweite Anmeldung. Nur im Komplettpaket. |
| **🔒 Sperren** (oder **Strg+Alt+L**) | Sofort sperren, z. B. wenn Sie den Platz verlassen |

Starten Sie eine Suche bei geschlossenem Netz, fragt der Vault nach: *„Diese Aktion braucht das Internet“*. Ohne Ihre Freigabe wird
nichts gesendet.

**Beenden:** Vault-Fenster schließen. Der Vault speichert, sperrt und beendet sich.

## Fallakte im Vault

Im Komplettpaket richtet `START_VAULT.bat` beim ersten Start auch die **EagleEye-Fallakte** ein. Ein Klick auf **📁 Fallakte** in der
Vault-Leiste öffnet sie; Sie sind dort automatisch als Inhaber angemeldet.

- **Gleicher Tresor:** Jede Datei der Fallakte liegt einzeln verschlüsselt unter `files\fallakte\`. Auch Dateinamen und Ordner sind
  nicht lesbar; die Zuordnung steht im verschlüsselten Verzeichnis `manifest.enc`.
- **Gleicher Netzschalter:** Die Fallakte läuft im selben Programm wie der Vault. Ist das Netz zu, kommt auch sie nicht ins Internet.
- **Eine Anmeldung:** Das Fallakten-Konto „inhaber“ entsteht beim ersten Öffnen mit einem Zufallspasswort, das nur verschlüsselt im
  Vault liegt. Die Anmeldung ist an dieses Browserfenster gebunden.
- **Nur dieser Rechner, nur bei offenem Vault:** Die Fallakte antwortet auf dem nächsten Port (Vault-Port + 1) nur an `127.0.0.1`.
  Ist der Vault gesperrt, zeigt sie nur „Fallakte gesperrt“.
- **Sichern und Sperren:** Änderungen werden jede Minute verschlüsselt zurückgeschrieben, beim Sperren ein letztes Mal. Danach wird
  der Arbeitsordner gelöscht.

Ehrliche Grenze: Die Fallakte öffnet ihre Datenbanken als Dateien. Solange sie offen ist, liegen diese deshalb **entschlüsselt in einem
temporären Arbeitsordner** (nicht nur im Arbeitsspeicher wie bei PersonOSINT). Dagegen schützt BitLocker. Nach einem Absturz kann der
Ordner `eagleeye-fallakte-…` im Temp-Verzeichnis zurückbleiben; löschen Sie ihn dann von Hand. Ohne Fallakte starten:
`set EAGLEEYE_OHNE_FALLAKTE=1` vor `START_VAULT.bat`.

## Tiefenrecherche, Vermisstenregister, Tarnung, Auswertung

Siehe `TIEFENRECHERCHE.md`:
- automatische Varianten, Dorks und Folgespuren (Reiter **🔭 Tiefenrecherche**),
- Vermisstenregister und die **Vermissten-Überwachung**,
- Legenden-Verwaltung, **Legenden-Browser** und neue Netzidentität je Suche (Verwaltung → **🎭 Tarnung & Websuche**),
- **Treffer-Vorprüfung** (Triage) und die Firmendaten aus **OffeneRegister**.

## Was technisch passiert (OPSEC-Konzept)

**1. Nur dieser Rechner**
- Der Server lauscht ausschließlich auf `127.0.0.1`. Andere Geräte im Netz erreichen ihn nicht.
- Anfragen mit fremdem Hostnamen (Schutz vor DNS-Rebinding) oder von fremden Seiten werden abgewiesen. Dafür braucht jede Anfrage
  eine eigene Kennung und muss aus derselben Herkunft stammen; zusätzlich gibt es CSRF-Schutz.
- Es gilt immer genau eine Sitzung. Ein zweites Fenster sieht nur „in einem anderen Fenster geöffnet“.

**2. Verschlüsselt gespeichert, nur im Arbeitsspeicher geöffnet**
- Die Passphrase wird mit Argon2id (64 MiB, 3 Durchläufe) zu einem Schlüsselschlüssel. Dieser entschlüsselt (AES-256-GCM) den
  zufälligen Datenschlüssel. Ein zweiter Weg zum Datenschlüssel führt über den Wiederherstellungsschlüssel (≈ 145 Bit).
- Die ganze Datenbank liegt als `vault.db.enc` verschlüsselt auf der Platte. Beim Öffnen wird sie direkt in den Arbeitsspeicher
  entschlüsselt; eine Klartext-Datenbankdatei entsteht nie. Fotos und Belege liegen unter `files\`, verschlüsselt mit einem
  abgeleiteten Schlüssel. Eine Schlüsseldatei gibt es nicht mehr.
- Ohne Passphrase sieht man nur, dass ein Vault existiert. Name, Fälle und Treffer sind nicht lesbar. Ein automatischer Test
  prüft das nach jeder Änderung.
- Ab dem dritten Fehlversuch (falsche Passphrase **oder** falscher Code) wachsen die Wartezeiten, bis zu 15 Minuten.
  Ein Zwei-Faktor-Code gilt nur einmal.

**3. Internet nur auf Befehl („Netzschalter“)**
- Der Schalter sitzt an der tiefsten Stelle des Programms, beim Verbindungsaufbau und bei der Namensauflösung (DNS). Er gilt für
  alles, was der Vault-Prozess tut, auch für Bibliotheken, die davon nichts wissen.
- Geschlossen ist er nach jedem Start, nach jedem Sperren und nach Ablauf des Zeitfensters. Dann scheitern Verbindungen und
  DNS-Anfragen sofort. Er prüft auch vor dem Weg über einen lokalen Anonymisierungs-Proxy (Tor auf 127.0.0.1), damit dieser nicht
  „heimlich“ ins Netz leitet.
- Die Kartenansicht holt ihre Kacheln über den Vault (nur bei offenem Netz, Zwischenspeicher im Arbeitsspeicher). Ihr Browser
  spricht OpenStreetMap nicht direkt an.
- Die OPSEC-Stufen und Ausgänge je Fall gelten weiter: Ab Stufe 2 nur über Tor oder einen Proxy, sonst wird blockiert statt direkt
  gesendet.

**4. Abgeschottetes Browserfenster**
- Edge, Chrome oder Brave starten mit einem **Wegwerf-Profil**: ohne Erweiterungen, ohne Synchronisierung, ohne Verlauf. Nach dem
  Schließen wird das Profil gelöscht.
- Strenge Sicherheitsregeln für die Seite: Inhalte kommen nur vom Vault, keine Einbettung in fremde Seiten, kein Referrer, nichts im
  Browser-Zwischenspeicher. Eine Browser-Abnahme prüft, dass die Seite selbst keine einzige Anfrage nach außen stellt.

## Ehrliche Grenzen

- Der Netzschalter wirkt **nur im Vault-Programm**. Ihr Browser, andere Programme und Windows haben eigenen Netzzugang. Externe
  Links (z. B. manuelle Recherchelinks, „Quelle öffnen“) öffnet der Browser mit Ihrer normalen Verbindung. Für heikle Fälle solche
  Links im Tor Browser oder in einer getrennten Recherche-Umgebung öffnen.
- Solange der Vault **offen** ist, liegen die Daten im Arbeitsspeicher. Wer dann Zugriff auf den entsperrten Rechner hat (oder eine
  Schadsoftware), kann sie sehen. Deshalb: sperren beim Verlassen, automatische Sperre nicht zu lang einstellen. Windows kann Teile
  des Arbeitsspeichers in die Auslagerungsdatei schreiben. Dagegen hilft die **BitLocker-Verschlüsselung** des Laufwerks
  (Windows-Einstellungen → Datenschutz und Sicherheit → Geräteverschlüsselung bzw. BitLocker).
- Ein Absturz oder Stromausfall kann die Änderungen der letzten Sekunden kosten (Zwischenspeicherung alle 2 Sekunden).
- **Passphrase und Wiederherstellungsschlüssel verloren = Daten verloren.** Das ist Absicht und lässt sich nicht umgehen.
- Der Vault ist für **eine Person** gebaut. Für ein Team bleibt der Serverbetrieb (`START_HIER.bat` → 2) mit Konten und Rollen.

## Speicherort und Sicherung

- Der Vault-Ordner liegt standardmäßig unter `%LOCALAPPDATA%\EagleEye-Vault`. Ein anderer Ort, z. B. ein verschlüsselter
  USB-Stick: Umgebungsvariable `EAGLEEYE_VAULT_DIR` setzen oder `START_VAULT.bat --vault-dir E:\Vault`.
- **Sicherung:** den ganzen Vault-Ordner kopieren, während der Vault gesperrt ist. Die Kopie ist genauso verschlüsselt und braucht
  zum Öffnen dieselbe Passphrase.
- Nach einer Übernahme alter PersonOSINT-Daten liegen diese weiter unverschlüsselt im bisherigen Datenordner
  (`%APPDATA%\EagleEye-PersonOSINT`). Löschen Sie den Ordner, sobald Sie im Vault alles geprüft haben. Auf SSDs ist „sicheres
  Löschen“ nicht garantiert; BitLocker schützt auch diese Reste.

## Für Entwickler

- `personosint/vault.py`: Speicher und Schlüssel.
- `personosint/netgate.py`: Netzschalter.
- `personosint/vault_app.py`: äußere App mit Sperrbildschirm und API unter `/vault/api/…`; leitet nach dem Öffnen an die bekannte
  PersonOSINT-App weiter. `create_fallakte_asgi()` ist der zweite lokale Zugang für die Fallakte, `/vault/fallakte` die Anmeldung.
- `personosint/fallakte.py`: verschlüsselte Ablage der Fallakte, Arbeitsordner, Anmeldung (Test: `tests/test_vault_fallakte.py` im
  EagleEye-Hauptordner).
- `personosint/persona_browser.py`: Legenden-Browser.
- `static/vault.*` (Sperrbildschirm), `static/vaultbar.*` (Leiste).
- Start: `python -m personosint vault [--vault-dir …] [--port 8377] [--no-browser] [--keep-running]`.
- Tests: `tests/test_vault.py`.
