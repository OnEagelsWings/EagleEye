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
