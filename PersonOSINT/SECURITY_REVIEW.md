# Sicherheitsprüfung EagleEye PersonOSINT 1.4

Stand: November 2026 · Umfang: gesamter Server-Code (`personosint/`), Weboberfläche (`static/`), Docker-Betrieb (`Dockerfile`, `deploy/`).
Art der Prüfung: interne Code-Prüfung (manuell + automatisiert) durch das Entwicklungsteam. **Kein Ersatz für einen externen Penetrationstest** – der wird vor dem Produktivbetrieb mit echten Fällen empfohlen (siehe Abschnitt 5).

## 1. Vorgehen

| Schritt | Werkzeug / Methode | Ergebnis |
|---|---|---|
| Statische Analyse | `bandit -r personosint` | keine echten Befunde (Bewertung unten) |
| Abhängigkeiten | `pip-audit -r requirements.txt` | 39 bekannte Lücken in Pillow < 13 → Mindestversion auf 13 angehoben; danach **keine bekannten Lücken** |
| Zugriffsschutz | automatischer Test über **alle** API-Endpunkte (`tests/test_security.py`) | jeder Endpunkt außer Anmeldung verlangt eine Sitzung; alle `/api/admin/*` verlangen die Rolle Administration |
| Manuelle Prüfung | Durchsicht von Authentifizierung, Sitzungen, CSRF, Rechten, Datei-Uploads, ausgehenden Abfragen (SSRF), Exporten, Tresor, Audit-Kette | 8 Befunde, alle behoben (Abschnitt 3) |
| Browser-Abnahme | Playwright-Durchläufe aller Hauptabläufe inkl. OPSEC (Proxy-Mitschnitt: keine Abfrage am Proxy vorbei) | ohne Fehler |

## 2. Bewertung der bandit-Hinweise

| Hinweis | Anzahl | Bewertung |
|---|---|---|
| B608 SQL aus Zeichenketten | 24 | Falsch-positiv: zusammengesetzt werden nur interne Tabellen-/Spaltennamen aus festen Listen; alle Werte laufen als Parameter (`?`). |
| B107/B105 „Passwort im Code“ | 8 | Falsch-positiv: leere Standardwerte bzw. Hinweistexte. |
| B311 Zufallszahlen | 4 | Nur für Graph-Layout/Demo-Daten; sicherheitsrelevante Werte nutzen `secrets`. |
| B603/B404 subprocess | 4 | Nur LibreOffice-Aufruf zur PDF/A-Erzeugung mit fester Argumentliste, ohne Shell, in temporärem Verzeichnis. |
| B110/B112 try/except | 4 | Bewusst: optionale Aufräumarbeiten; Fehler werden an anderer Stelle protokolliert. |

## 3. Behobene Befunde

| # | Befund | Risiko | Behebung | Regressionstest |
|---|---|---|---|---|
| 1 | Links aus Quellen (`javascript:`) konnten in Treffern/Fakten landen | mittel (XSS beim Klick) | `safe_url()` lässt nur http(s) zu – für Quellen, manuelle Treffer und Belegadressen | `test_javascript_links_from_sources_are_dropped` |
| 2 | Weiterleitungen bei Beweissicherung/Abfragen konnten auf interne Adressen zeigen (SSRF über Redirect) | hoch | `_SafeRedirectHandler` prüft jedes Weiterleitungsziel (`is_internal_host`) | `test_redirect_to_internal_target_is_blocked` |
| 3 | CSV-Formel-Injektion im Beweis-Manifest (Excel) | mittel | `_csv_safe()` entschärft `= + - @` am Zellanfang | `test_csv_formula_injection_in_evidence_manifest` |
| 4 | TOTP-Code innerhalb des Zeitfensters wiederverwendbar | mittel | letzter Zähler je Konto (`users.totp_last`), Wiederholung abgelehnt | `test_totp_code_cannot_be_replayed` |
| 5 | Anmelde-Drosselung nur je Konto (Passwort-Spraying über viele Konten) | mittel | zusätzlich je IP-Adresse: 20 Fehlversuche/15 min → 429 | `test_login_throttled_per_ip_address` |
| 6 | Ersteinrichtung bei frisch gestarteter, aus dem Netz erreichbarer Instanz durch Fremde möglich | hoch | Einrichtung aus der Ferne nur mit Einrichtungscode aus dem Server-Log | `test_remote_first_setup_requires_code` |
| 7 | Uploads (Fotos/Logo) wurden vollständig in den Speicher gelesen | niedrig (DoS) | begrenztes Lesen (8 MB / 2 MB) | `test_oversized_photo_rejected` |
| 8 | SHA-1 für Kennungen ohne Kennzeichnung | informativ | `usedforsecurity=False` | – |

Zusätzlich vorhanden (bereits vor dieser Prüfung, geprüft): argon2id, 2FA-Pflicht, Sitzungs-Cookies HttpOnly/SameSite=Strict, CSRF-Token + Header, Host-Allowlist, CSP ohne Inline-Skripte, Rollen- und Fallrechte, vertrauliche Fälle, Vier-Augen-Freigabe, Tresor-Verschlüsselung (Fotos, Belege, Schlüssel, 2FA-Geheimnisse), verschlüsselte Sicherungen, hash-verkettetes Audit-Protokoll, OPSEC „fail closed“.

## 4. Restrisiken (bekannt, bewusst akzeptiert oder offen)

1. **DNS-Rebinding (TOCTOU)** bei direkten Abfragen ohne Proxy: Prüfung und Verbindung lösen den Namen getrennt auf. Abhilfe im Betrieb: ausgehender Verkehr ab OPSEC 2 ohnehin über Proxy/Tor; Container ohne Zugang zu internen Netzen betreiben (`deploy/docker-compose.yml`).
2. **Administration sieht in Sicherungen alles**, auch vertrauliche Fälle (Sicherungen sind vollständig). Abhilfe: Sicherungs-Passphrase nach Vier-Augen-Prinzip verwahren; Admin-Rolle nur an wenige Personen.
3. **Live-Quellen nicht gegen echte Dienste getestet** (Testumgebung ohne Internetzugang zu den Diensten). Die Verbindungen sind gegen nachgebildete Antworten getestet; vor dem Pilot je Quelle „Testen“ in der Verwaltung ausführen.
4. **Lokales KI-Modell**: Ausgaben werden auf Belegverweise geprüft und müssen freigegeben werden, Halluzinationen innerhalb belegter Sätze sind dennoch möglich.
5. **Produktions-Image (Debian) mit LibreOffice** wurde in der Testumgebung nicht vollständig gebaut (Paketquellen gesperrt); die PDF/A-Erzeugung ist in einem gleichwertigen Ubuntu-Image getestet.

## 5. Empfehlungen vor dem Produktivbetrieb

- Externer Penetrationstest (Web-Anwendung + Server-Härtung), 3–5 Personentage.
- Server: automatische Sicherheitsupdates, Festplattenverschlüsselung, Firewall nur 443, SSH nur mit Schlüssel.
- Abhängigkeiten monatlich mit `pip-audit` prüfen (Befehl siehe oben); Docker-Basis-Image regelmäßig neu bauen.
- Wiederherstellung einer Sicherung einmal pro Quartal üben (`python -m personosint verify-backup` / `restore`).
- Audit-Kette regelmäßig prüfen (`python -m personosint verify-audit`).
