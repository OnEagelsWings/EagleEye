# Technische und organisatorische Maßnahmen (Entwurf, Art. 32 DSGVO)

Bezieht sich auf den Betrieb nach `deploy/docker-compose.yml`. Organisatorische Punkte mit `[…]` ergänzen.

| Schutzziel | Technisch (EagleEye) | Organisatorisch |
|---|---|---|
| Zutrittskontrolle | – | Serverstandort […Rechenzentrum, ISO 27001…]; Arbeitsplätze in abschließbaren Räumen |
| Zugangskontrolle | Anmeldung mit argon2id-Passwort + Pflicht-2FA (TOTP, gegen Wiederverwendung gesichert); Sperre nach Fehlversuchen je Konto und je IP; Sitzungsablauf; Schnellsperre; Ersteinrichtung aus der Ferne nur mit Einrichtungscode | Passwort-Richtlinie, Verfahren bei Verlust des 2FA-Geräts (`reset-2fa` nur durch Admin) |
| Zugriffskontrolle | Rollen (Administration, Teamleitung, Analyse, Prüfung, Lesen) und Fallrechte; vertrauliche Fälle nur für das Fallteam; Notfallzugriff nur mit Begründung und Protokoll | Rechtevergabe nach Bedarf, halbjährliche Rechteprüfung |
| Weitergabekontrolle | TLS (Caddy); ausgehende Abfragen ab OPSEC 2 nur über Proxy/Tor, sonst blockiert; Exportregister mit Export-ID; Beweispakete mit SHA-256 | Dossiers nur verschlüsselt versenden […] |
| Eingabekontrolle | hash-verkettetes Audit-Protokoll, Prüfung mit `verify-audit` | Stichproben durch Teamleitung |
| Auftragskontrolle | Zweck, Rechtsgrundlage, Auftragsprüfung als Pflichtschritte; Vier-Augen-Freigabe vor Auslieferung | AV-Verträge mit Hoster/Proxy-Anbieter |
| Verfügbarkeit | verschlüsselte Sicherungen, datenbankunabhängige Wiederherstellung, `verify-backup` | Sicherung außer Haus, Wiederherstellungsübung je Quartal |
| Trennung | Fälle strikt getrennt; Referenzdaten getrennt von Falldaten | – |
| Verschlüsselung | Tresor (Fernet/AES) für Fotos, Belege, API-Schlüssel, 2FA-Geheimnisse; verschlüsselte Sicherungen | Festplattenverschlüsselung Server und Arbeitsplätze |
| Datenminimierung/Löschung | Pflicht-Prüfung von Treffern, Löschfristen mit Erinnerung, Schwärzung beim Löschen | Löschkonzept |
| Belastbarkeit/Prüfung | automatisierte Tests (inkl. Sicherheitstests), Sicherheitsprüfung (SECURITY_REVIEW.md) | externer Penetrationstest vor Produktivstart, Abhängigkeiten monatlich prüfen |
