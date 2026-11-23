# Tiefenrecherche, Vermisstenregister und Tarnung

Stand: PersonOSINT 1.8 (im EagleEye Vault)

## 1. Tiefenrecherche – automatisch breit und tief suchen

Im Fall gibt es den Reiter **🔭 Tiefenrecherche**. Die Plattform baut dort aus dem Profil der Person den kompletten Suchplan:

| Was entsteht | Beispiel (Lena Hoffmann, Spitzname Leni, geb. 2003) |
|---|---|
| **Namensvarianten** | Lena Hoffmann · Hoffmann, Lena · L. Hoffmann · Leni Hoffmann · Umlaut- und ß-Schreibweisen · Zweitnamen · Umschrift aus Kyrillisch/Arabisch/Hebräisch |
| **Benutzernamen-Kandidaten** (nur mit Häkchen „erraten“) | lena.hoffmann · lhoffmann · lena_hoffmann · hoffmann.lena · lenahoffmann03 … |
| **Telefon-Schreibweisen** | +49 431 …, 0049 431 …, 0431 … |
| **Domains** | aus E-Mail-Adressen der Person (ohne Freemailer) |
| **Dorks nach Ziel** | Profile · Dokumente · Lebenslauf · Listen · Presse · Foren · Bilder · Register · Vereine · Archiv · Paste-Seiten · Benutzernamen · Kontakt · Domains · Beruf · bei Vermissten: Vermisstenmeldungen, Polizei, Suchaufrufe, unbekannte Personen, lokale Hinweise |

**So läuft es ab**

1. **Tiefe** wählen:
   - 1 = nur die Varianten
   - 2 = zusätzlich starke neue Spuren
   - 3 = maximal
2. **Abfragebudget** wählen (50–600).
3. Auf **Tiefenrecherche starten** klicken. Der Vault fragt nach dem Netz, wenn es geschlossen ist.
4. **Runde 1** fragt jede passende Quelle mit jeder Variante ab.
5. **Folgerunden:** Kennungen aus Treffern mit hoher Übereinstimmung werden automatisch weiterverfolgt. Gemeint sind Score ≥ 70 bei Benutzername, E-Mail, Domain, Webadresse oder Alias.
6. Der Fortschritt läuft live mit: Runde, Abfragen, neue Treffer, verfolgte Spuren, Protokoll.
7. Danach: **Treffer prüfen →**. Alles bleibt Kandidat, bis Sie es bestätigen.

Bereits abgefragte Kombinationen werden nicht wiederholt. OPSEC-Stufe, Anonymisierungs-Ausgang und Briefing gelten unverändert. Auf Stufe 2
und 3 startet ohne Briefing nichts, und ohne Tor- oder Proxy-Ausgang wird nichts gesendet.

### Dorks automatisch ausführen – eigene Websuche (SearXNG)

Google, Bing & Co. verbieten automatisierte Abfragen und sperren sie nach kurzer Zeit. Der saubere Weg ist eine **eigene SearXNG-Instanz**.
Das ist eine Meta-Suchmaschine, die Sie selbst betreiben. Die Tiefenrecherche schickt die Dorks dorthin und übernimmt die Treffer als
Kandidaten.

Einrichten mit Docker (Beispiel):

```
docker run -d --name searxng -p 127.0.0.1:8888:8080 searxng/searxng
```

Danach in der `settings.yml` des Containers unter `search: formats:` den Eintrag `json` ergänzen und den Container neu starten. Im Vault
unter **Verwaltung → 🎭 Tarnung & Websuche** die Adresse `http://127.0.0.1:8888` eintragen.

Wichtig für die OPSEC: SearXNG fragt die Suchmaschinen selbst ab. Für Fälle ab OPSEC-Stufe 2 muss SearXNG deshalb selbst über Tor oder
einen Proxy laufen (`outgoing: proxies` in der `settings.yml`). Setzen Sie danach das Häkchen „SearXNG fragt selbst über Tor/Proxy ab“.
Ohne dieses Häkchen nutzt die Tiefenrecherche SearXNG nur auf Stufe 1.

Ohne SearXNG erscheinen die Dorks als **abhakbare Liste** mit Ein-Klick-Links für Google, Bing, DuckDuckGo, Startpage und Yandex. Diese
Links öffnet Ihr Browser mit Ihrer normalen Verbindung. Für heikle Fälle öffnen Sie sie im Tor Browser oder kopieren sie (**Kopieren**).

## 2. Vermisstenregister

| Register | Anbindung |
|---|---|
| INTERPOL – Gelbe Ausschreibungen | automatisch (offene Schnittstelle) |
| FBI – Vermisste | automatisch (offene Schnittstelle, nur Einträge der Art „missing“) |
| Vermisstenmeldungen in der Presse (GDELT) | automatisch: Name + „vermisst/missing/disparu/desaparecido/scomparso/zaginiony …“ in 14 Sprachen, weltweit |
| Polizeien aller 16 Bundesländer + Presseportal Blaulicht | Direktsuche (eine Suche über alle Portale) |
| BKA-Fahndung, Unbekannte Tote (BKA) | Direktlink |
| Österreich (Bundeskriminalamt, Polizei), Schweiz (fedpol, Kantonspolizeien) | Direktsuche |
| NamUs (USA), NCMEC (vermisste Kinder, USA), Charley Project, Doe Network | Direktsuche bzw. Suchmaske |
| Kanada (Canada's Missing), Australien (National Missing Persons) | Direktsuche |
| IKRK-Verzeichnis der Suchdienste, DRK-Suchdienst | Direktlink (Vermisste nach Flucht, Krieg, Katastrophen) |
| Missing Children Europe (Hotline 116 000), Initiative Vermisste Kinder, Missing People (UK) | Direktlink |
| Suchaufrufe in sozialen Netzwerken | Direktsuche („bitte teilen“, „wer hat“, „wird vermisst“) |

Warum nicht alles automatisch? BKA, Länderpolizeien, NamUs und NCMEC bieten keine frei zugängliche Schnittstelle. NCMEC verlangt eine
Registrierung, NamUs gibt Daten nur eingeschränkt heraus. Automatisches Auslesen dieser Seiten würde ihre Bedingungen verletzen. Die
Direktsuchen führen mit einem Klick genau zur richtigen Abfrage. Die Links stehen im Reiter **Suche & Treffer** unter „Vermisstenfälle“,
die Dorks in der Tiefenrecherche unter „Vermisst“.

**Bei Vermisstenfällen gilt: Polizei zuerst.** Hinweise auf den Aufenthalt gehören an die zuständige Polizeidienststelle.

## 3. Tarnung (Sockpuppet-Prinzip)

**Was ohnehin gilt:** Alle automatischen Abfragen laufen ohne Konto und ohne Anmeldung. Übertragen wird nur die Suchanfrage, nichts über
Sie.

**Neue Netzidentität je Suche** (Häkchen in der Tiefenrecherche):
- Jedes Abfragepaket geht mit einer anderen, gängigen Browserkennung hinaus.
- Ist ein **Tor-Steuerport** eingetragen (Verwaltung → Tarnung & Websuche: Adresse, Port, Passwort aus `HashedControlPassword`), fordert
  der Vault vor jedem Paket bei Tor einen **neuen Ausgang** an (`SIGNAL NEWNYM`).
- So lassen sich Ihre Abfragen untereinander nicht verknüpfen.
- Voraussetzung: Der Fall läuft über den Tor-Ausgang (Reiter OPSEC).

**Legenden** (Verwaltung → 🎭 Tarnung & Websuche):
- **Legende vorschlagen:** Der Vault erfindet eine fiktive Person mit Name, Benutzername, Geburtsjahr, Wohnort und Kurzprofil.
- **Alias-E-Mail:** Nach Ihrem Muster entsteht eine eigene Adresse je Legende, z. B. `{user}@alias.ihre-domain.de` (Catch-all auf
  eigener Domain) oder `recherche+{token}@ihre-domain.de`. Alias-Dienste wie SimpleLogin oder addy.io funktionieren ebenso.
- **Zugangsdaten** liegen verschlüsselt im Vault. Jedes Anzeigen wird protokolliert.
- **Einsatz je Fall** wird im Reiter Tiefenrecherche unten unter „Legenden in diesem Fall“ eingetragen. Es gibt eine Warnung, wenn eine
  Legende schon in anderen Fällen benutzt wurde, denn das birgt Verknüpfungsgefahr.
- **Status:** aktiv, ruhend oder verbrannt. Eine verbrannte Legende lässt sich nicht mehr einsetzen.

**Bewusst nicht eingebaut: automatisches Anlegen von Konten bei Plattformen.**
- Automatisch erzeugte Konten fallen auf (gleiche Muster, gleiche Herkunft, CAPTCHA- und Telefonprüfungen) und werden gesperrt. Das
  verrät die Recherche, statt sie zu tarnen.
- Es verstößt gegen die Nutzungsbedingungen der Plattformen und kann Ihr Büro haftbar machen.
- Glaubwürdige Legenden entstehen von Hand:
  - mit eigenem Browserprofil je Legende,
  - über den Anonymisierungs-Ausgang,
  - mit etwas Vorlauf und Aktivität, bevor sie für eine Recherche genutzt werden.
- Keine echten Personen nachahmen, und keine Täuschung, die über die stille Beobachtung hinausgeht. Für Detekteien gelten zusätzlich
  Datenschutzrecht und Standesregeln.

## Für Entwickler

| Datei | Inhalt |
|---|---|
| `personosint/deepsearch.py` | Varianten, Dorks, Plan, Hintergrundlauf, SearXNG-Quelle `websuche` |
| `personosint/personas.py` | Legenden (Tabellen `personas`, `persona_use`, Migration 10) |
| `personosint/connectors2.py` | Quellen `fbi_missing` und `gdelt_missing` |
| `Platform.renew_identity()` | Tor `SIGNAL NEWNYM` |
| `Platform.run_search(queries=…, user_agent=…)` | Abfrageliste für die Tiefenrecherche, wechselnde Browserkennung |

- API: `/api/cases/{id}/entities/{eid}/deep/plan|start`, `/api/cases/{id}/deep/{job}`, `/api/admin/websearch`, `/api/personas…`
- Oberfläche: `static/deep.js`
- Tests: `tests/test_deep.py`
