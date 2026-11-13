# EagleEye PersonOSINT – Handbuch für die Administration

## 1. Betrieb
- Installation und Aktualisierung: README.md, Abschnitt „Teambetrieb mit Docker“. Aktualisieren: `git pull && docker compose -f deploy/docker-compose.yml up -d --build`.
- Ersteinrichtung aus der Ferne: Einrichtungscode steht im Log (`docker compose logs app | grep Einrichtungscode`).
- Optionale Dienste: `--profile tor` (Tor-Ausgang), `--profile ki` (lokales Sprachmodell über Ollama).

## 2. Benutzer
- *Verwaltung → Benutzer*: einladen (Startpasswort, Wechsel bei erster Anmeldung erzwungen), Rolle, deaktivieren.
- Notfälle auf dem Server (`docker compose exec app python -m personosint …`):
  `reset-2fa NAME` · `unlock NAME` · `reset-password NAME` · `create-user …`
- Rollen sparsam vergeben: Administration sieht keine vertraulichen Fälle, aber Sicherungen enthalten alles.

## 3. Quellen & Daten
- Jede Quelle mit „Testen“ prüfen (läuft über den Standard-Netzausgang). API-Schlüssel werden verschlüsselt gespeichert.
- Referenzdaten importieren (Download-Knopf oder Datei; große Dateien per `import-refdata NAME DATEI`). **Lizenzen** prüfen.
- Red-Flag-Regeln an die Arbeitsweise anpassen.

### Quellen prüfen (wichtig nach der Installation und nach jedem Update)
- *Verwaltung → Quellen & Daten → „Alle Quellen prüfen“* ruft jede Quelle einmal mit einer unkritischen Testabfrage auf (1–3 Minuten).
  Danach steht an jeder Quelle: liefert Treffer / erreichbar ohne Treffer / Fehler / nicht prüfbar (Schlüssel oder Daten fehlen).
- Unter Windows ohne Anmeldung: `QUELLEN_PRUEFEN.bat` – schreibt `Quellen-Pruefbericht.md` in den Programmordner.
- Der Prüfbericht gehört ins Pilotprotokoll (Abschnitt 4). Übersicht aller Quellen: `docs/QUELLEN.md`.

### Serverbetrieb unter Windows
- `START_PERSONOSINT_SERVER.bat` macht die Anwendung im eigenen Netz erreichbar und zeigt die Adresse für die anderen Rechner an.
  Zwei-Faktor-Anmeldung ist dann immer Pflicht; Rechnername und Netzadressen werden automatisch zugelassen.
- Windows fragt beim ersten Start nach der Firewall: nur „Private Netzwerke“ erlauben.
- Die Verbindung ist dabei unverschlüsselt (http) – nur im eigenen, vertrauenswürdigen Netz verwenden. Für Zugriff von außen den
  HTTPS-Betrieb mit Docker nutzen (README → Teambetrieb). Den Port niemals einfach im Router freigeben.
- Einzelplatz und Server nutzen denselben Datenordner: Sie können jederzeit zwischen beiden Startarten wechseln.

## 4. OPSEC
- Netzausgänge (HTTP-Proxy, Tor) anlegen, testen, Standard festlegen. Ab Stufe 2 blockiert das System ohne passenden Ausgang.
- Netzausgangs-Protokoll und Exportregister regelmäßig sichten.

## 5. Löschfristen
- *Verwaltung → Löschfristen*: Standardfrist (Monate nach Abschluss), fällige und bald fällige Fälle, Fälle ohne Frist. Monatlich kontrollieren (Löschkonzept).

## 6. Sicherungen
- *Verwaltung → Sicherungen* oder `python -m personosint backup`. Passphrase/Schlüssel getrennt und nach Vier-Augen-Prinzip verwahren.
- Prüfen: `verify-backup DATEI` · Wiederherstellen: `restore DATEI` (funktioniert auch von SQLite nach PostgreSQL).
- Quartalsweise Wiederherstellung auf einem Testsystem üben (Pilotprotokoll T14).

## 7. Sicherheit & Protokoll
- Audit-Kette prüfen: *Verwaltung → Sicherheit & Protokoll* oder `verify-audit`.
- Monatlich: `pip-audit -r requirements.txt` bzw. Image neu bauen; Server-Updates einspielen.
- Bei Verdacht auf Kompromittierung: Konten sperren, Sitzungen beenden (Passwort-Reset), Audit sichern, DSB informieren (72-Stunden-Frist Art. 33 DSGVO).
