# OPSEC-Konzept – EagleEye PersonOSINT

Stand: Version 1.2 · gilt für Einzelplatz und Teamserver

Operative Sicherheit (OPSEC) schützt bei investigativer Recherche **drei Dinge**:

| Schutzziel | Frage | Beispiel für einen Schaden |
|---|---|---|
| **Die Recherche** | Merkt die Zielperson, dass recherchiert wird? | Sie löscht Profile, warnt ihr Umfeld oder klagt vorab |
| **Die Recherchierenden** | Lässt sich die Recherche einer Person oder Organisation zuordnen? | Einschüchterung, Gegenrecherche, Doxing |
| **Die Quellen** | Lassen sich Hinweisgebende aus Daten oder Dateien ableiten? | Aufnahmeort im Foto-EXIF, Name im Dokument, Rückschluss über Exportdatei |

EagleEye setzt OPSEC in **vier Schichten** um. Was die Software **technisch erzwingt**, ist mit ⚙ gekennzeichnet; was
**organisatorisch** sichergestellt werden muss, mit 👤.

---

## 1. Bedrohungen und Spurenquellen

| Spur | Wer sieht sie? | Gegenmaßnahme |
|---|---|---|
| IP-Adresse bei automatischen Abfragen | Abgefragte Plattformen und Register, deren Protokolle | ⚙ Netzausgang über Proxy/Tor, fail closed |
| Produktkennung im User-Agent | dieselben | ⚙ neutraler User-Agent ab Stufe 2 |
| DNS-Anfragen | DNS-Server des Netzes | ⚙ Bei Proxy-Ausgang löst der Proxy die Namen auf (CONNECT mit Hostname) |
| Manuell geöffnete Links | Plattform; bei LinkedIn/XING **die Zielperson selbst** (Profilbesucher) | ⚙ Expositions-Kennzeichnung, ⚙ Sperre „Sichtbar“ auf Stufe 3, 👤 getrennte Recherche-Umgebung |
| Kartenkacheln | Kartenserver (sieht betrachteten Ausschnitt) | ⚙ ab Stufe 2 nur auf ausdrücklichen Klick |
| Automatische Ortsauflösung | OpenStreetMap (sieht gesuchte Orte) | ⚙ auf Stufe 3 abgeschaltet, sonst nur über den Fall-Ausgang |
| Foto-Metadaten | Jede Person, die die Datei erhält | ⚙ EXIF/GPS/XMP werden beim Hochladen entfernt |
| Dokument-Metadaten (Autor, Software) | Empfänger der Exporte | ⚙ neutralisiert |
| Exportdateien | Empfänger, ggf. Dritte bei Abfluss | ⚙ Export-ID + Hash im Export-Register, ⚙ Exportrechte je Stufe |
| Bildschirm, Browsertitel, Fallliste | Personen im Raum, Screenshots, Screensharing | ⚙ Deckname, ⚙ Browsertitel neutral, ⚙ verschleierter Klartitel, ⚙ Schnellsperre |
| Zugriff im eigenen Team | Kolleginnen/Kollegen ohne Need-to-know | ⚙ vertrauliche Fälle, Rollen, Protokoll |
| Server / Sicherungen | Hoster, Einbrecher, Verlust | ⚙ Verschlüsselung ruhender Daten, ⚙ verschlüsselte Sicherungen, 👤 Schlüssel getrennt |

---

## 2. Schicht 1 – OPSEC-Stufen je Fall

Jeder Fall hat eine Stufe. Sie wird beim Anlegen gewählt; Investigativrecherchen starten mindestens auf Stufe 2.
**Absenken** erfordert eine Begründung und wird protokolliert; Anheben ist jederzeit möglich.

| Regel | Stufe 1 · Standard | Stufe 2 · Erhöht | Stufe 3 · Streng |
|---|---|---|---|
| Typischer Einsatz | öffentliche Personen, Vermisstensuche mit Angehörigen | Zielperson soll nichts bemerken | gefährdete Quellen, wehrhafte Zielpersonen |
| ⚙ Anonymisierungs-Ausgang Pflicht | – | ✓ | ✓ |
| ⚙ Erlaubte automatische Quellen | alle | Passiv, Plattform | Passiv, Plattform |
| ⚙ Recherchelinks bis Exposition | Zielkontakt | Sichtbar (gekennzeichnet) | Plattform (Sichtbar gesperrt) |
| ⚙ Automatische Ortsauflösung | ✓ | ✓ (über Ausgang) | – |
| ⚙ Kartenhintergrund automatisch | ✓ | – | – |
| ⚙ Fall zwingend vertraulich | – | – | ✓ |
| ⚙ Deckname in Listen und Fallkopf | – | ✓ | ✓ |
| ⚙ Briefing-Bestätigung je Person | – | ✓ | ✓ |
| ⚙ Neutraler User-Agent | – | ✓ | ✓ |
| ⚙ Export durch | alle mit Zugriff | Bearbeitung, Prüfung, Teamleitung | nur Bearbeitung und Prüfung |

### Expositionsklassen

| Klasse | Bedeutung | Beispiele |
|---|---|---|
| **Passiv** | Register/Archive, keine Plattform der Zielperson wird kontaktiert | Wikidata, OpenAlex, ORCID, Internet Archive, INTERPOL, Gravatar, Suchmaschinen |
| **Plattform** | Plattform, auf der die Person ein Konto haben kann; Plattform protokolliert, Person sieht nichts | GitHub, Bluesky, Mastodon, Benutzernamen-Check, Profilaufrufe ohne Login |
| **Sichtbar** | Zielperson kann den Zugriff bemerken | LinkedIn/XING-Profilbesuche, Facebook mit Login |
| **Zielkontakt** | Infrastruktur, die die Zielperson selbst kontrolliert | eigene Webseite, eigener Mail-/Mastodon-Server |

---

## 3. Schicht 2 – Kontrollierter Netzausgang

* Die Administration legt **Netzausgänge** an (Verwaltung → OPSEC): HTTP-Proxys mit CONNECT, z. B. **Tor**
  (`HTTPTunnelPort`, im Docker-Stack: `docker compose --profile tor up -d`, Adresse `http://tor:9080`), ein VPN-Gateway
  oder ein kommerzieller Recherche-Proxy. Zugangsdaten werden verschlüsselt gespeichert und in der Oberfläche maskiert.
* Jeder Fall nutzt einen Ausgang (oder die Voreinstellung der Organisation).
* ⚙ **Fail closed:** Verlangt die Stufe Anonymisierung und ist kein Proxy gewählt oder der Proxy nicht erreichbar,
  wird die Abfrage **blockiert** – es gibt keinen stillen Rückfall auf den Direktzugang.
* ⚙ Systemweite Proxy-Ausnahmen (`no_proxy`) werden für Proxy-Ausgänge ignoriert.
* ⚙ **Ausgang testen** zeigt die öffentliche Ausgangs-IP und warnt, wenn sie der Direkt-IP entspricht.
* 👤 Der Ausgang schützt nur die **automatischen** Abfragen. Für manuelle Links ist die Recherche-Umgebung zuständig (Schicht 4).

---

## 4. Schicht 3 – Spurenkontrolle

* ⚙ **Außenkontakt-Protokoll** je Fall: jede automatische Außenabfrage mit Zeit, Person, Quelle, Host, Exposition und Ausgang.
  Damit lässt sich jederzeit beantworten: *„Wer konnte was von dieser Recherche sehen?“* (Reiter **🛡 OPSEC**).
* ⚙ **Metadaten-Bereinigung:** Hochgeladene Fotos werden neu codiert; EXIF (u. a. GPS-Position, Kamera, Aufnahmezeit), XMP,
  Kommentare und Farbprofile werden entfernt. Das Protokoll vermerkt, *was* entfernt wurde.
* ⚙ **Export-Register:** Jede Datei, die EagleEye verlässt (Dossier, Grafik, JSON, Plakat), erhält eine Export-ID
  (Dateiname + Fußzeile) und wird mit Person, Zeit und SHA-256-Hash registriert. Dokument-Metadaten werden neutralisiert,
  ab Stufe 2 trägt die Fußzeile einen Weitergabevermerk.
* ⚙ **Manipulationssicheres Protokoll** (Hash-Kette, seit 1.1) dokumentiert Stufenwechsel, Briefings, Notfallzugriffe und Exporte.

---

## 5. Schicht 4 – Arbeitsplatz-Disziplin

* ⚙ **Briefing:** Ab Stufe 2 bestätigt jede Person die Verhaltensregeln der Stufe, bevor sie recherchieren kann.
  Der OPSEC-Reiter zeigt, wer im Team noch nicht bestätigt hat.
* ⚙ **Decknamen** (z. B. `REIHER-125`) ersetzen Fall- und Personennamen in Listen und Dateinamen; der Klartitel im Fallkopf
  ist verschleiert und erscheint erst auf Klick. Der Browsertitel lautet immer nur „EagleEye“.
* ⚙ **Schnellsperre:** `Strg+Alt+L` oder Benutzermenü → „Sofort sperren“ leert den Bildschirm und beendet die Sitzung.
* 👤 **Recherche-Umgebung:** eigenes Browser-Profil oder VM, keine persönlichen Konten, auf Plattformen ausgeloggt,
  keine Interaktion mit der Zielperson (Likes, Follows, Anfragen).
* 👤 **Kommunikation:** nur Decknamen außerhalb von EagleEye; keine Falldaten in Messengern, Notiz-Apps oder auf privaten Geräten.
* 👤 **Bildersuche:** keine Fotos von Quellen bei Bilder-Suchmaschinen hochladen (verbleiben beim Anbieter).
* 👤 **Notfallweg:** Bei Anzeichen einer Enttarnung Arbeit einstellen, Verantwortliche/Teamleitung informieren, Stufe prüfen.

---

## 6. Rollen und Verantwortung

| Rolle | OPSEC-Aufgabe |
|---|---|
| Administration | Netzausgänge einrichten und regelmäßig testen, Voreinstellungen, Schlüssel- und Sicherungsverwahrung |
| Teamleitung | Stufe für neue Recherchen festlegen, Absenkungen genehmigen, Briefing-Stand im Team kontrollieren |
| Verantwortliche/r im Fall | Stufe und Ausgang des Falls, Team nach Need-to-know, Exporte |
| Prüfer/in | Vier-Augen-Prüfung inkl. OPSEC-Reiter (Direktabfragen? sichtbare Zugriffe? Exporte?) |
| Alle | Briefing ernst nehmen, Recherche-Umgebung nutzen, Auffälligkeiten melden |

---

## 7. Prüfliste vor Freigabe (Vier-Augen)

1. Stufe angemessen? Absenkungen begründet?
2. OPSEC-Reiter: „davon direkt“ = 0 bei Stufe ≥ 2? Ausgang anonymisiert (Test)?
3. Wurden Links der Kategorie „Sichtbar“ genutzt – und dokumentiert?
4. Briefing von allen Teammitgliedern bestätigt?
5. Export-Register: Wer hat welche Datei? Ist das nötig?
6. Fotos/Dokumente aus Quellen: Metadaten entfernt (Protokoll)?

---

## 8. Grenzen

* EagleEye anonymisiert nur seine **eigenen** automatischen Abfragen. Browser, Betriebssystem, Telefon und Konten der
  Recherchierenden liegen außerhalb – dafür sind Schicht 4 und die Recherche-Umgebung zuständig.
* Tor und Proxys verbergen die IP-Adresse, nicht das Verhalten: Wer zur selben Zeit sehr spezifisch nach einer Person sucht,
  kann über Muster auffallen. Abfragen sparsam und zielgerichtet einsetzen.
* Ein Anonymisierungs-Ausgang ändert nichts an der rechtlichen Bewertung: Zweck, Rechtsgrundlage und Datenminimierung gelten unverändert.
* Die Software umgeht keine Zugangsschranken, Captchas oder Bot-Erkennung und legt keine Tarnkonten an.
