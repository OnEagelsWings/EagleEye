# Verzeichnis von Verarbeitungstätigkeiten (Entwurf, Art. 30 Abs. 1 DSGVO)

**Verantwortliche Stelle:** […Firma, Anschrift, Vertretung…] · **Datenschutzbeauftragte/r:** […] · Stand: […]

---

## VT-1 Personen- und Hintergrundrecherche (OSINT) im Kundenauftrag

| Feld | Inhalt |
|---|---|
| Zweck | Identifizierung von Personen, Aufklärung von Online-Präsenz, Beziehungen zu Personen/Unternehmen, Prüfung von Sanktions-/Leak-Listen, Erstellung belegter Dossiers für Auftraggeber. |
| Rechtsgrundlage | je Fall dokumentiert (Pflichtfeld): Art. 6 Abs. 1 lit. f DSGVO (berechtigtes Interesse von Auftraggeber/in, z. B. Due Diligence, Forderungsdurchsetzung); lit. a (Einwilligung); lit. c/e (Behördenauftrag); journalistische Zwecke nach Landesrecht (Medienprivileg, Art. 85 DSGVO). Besondere Kategorien (Art. 9) nur ausnahmsweise und begründet. |
| Betroffene | Zielpersonen; Kontaktpersonen/Verbindungen der Zielperson; Auftraggeber/innen; Beschäftigte (Bearbeitung). |
| Datenkategorien | Identität (Name, Geburtsdatum, Fotos), Kontaktdaten, Wohn-/Aufenthaltsorte, Online-Konten, berufliche Funktionen, Unternehmensbeteiligungen, Sanktions-/Leak-Einträge, öffentliche Äußerungen, Beziehungen; Bewertungen der Analyse (Glaubwürdigkeit, Red Flags). |
| Herkunft | öffentlich zugängliche Quellen und Register (siehe Quellenliste in *Verwaltung → Quellen & Daten*), lokal importierte Referenzdatenbanken, Angaben der Auftraggeber/innen, manuelle Recherche. |
| Empfänger | Auftraggeber/in (Dossier), ggf. Behörden (Vermisstenfälle), Auftragsverarbeiter: Hoster […], Proxy/VPN-Anbieter […]. |
| Drittland | grundsätzlich nein. Abfragen an Quellen mit Sitz außerhalb der EU (z. B. US-Dienste) übermitteln Suchbegriffe; Bewertung in der DSFA, Minimierung über OPSEC-Stufen und lokale Referenzdaten. |
| Löschfristen | siehe Löschkonzept: Standard […12] Monate nach Fallabschluss, automatische Erinnerung, Löschung durch Verantwortliche. |
| TOM | siehe TOM.md |

## VT-2 Vermisstenrecherche

Wie VT-1, zusätzlich: Zweck Auffinden einer vermissten Person; Rechtsgrundlage meist Art. 6 Abs. 1 lit. f bzw. lebenswichtige Interessen (lit. d); Weitergabe von Ergebnissen bevorzugt an Polizei; Auftragsprüfung fragt, ob ein freiwilliger Kontaktabbruch einer volljährigen Person vorliegt. Suchplakate nur mit Zustimmung der Angehörigen/Polizei.

## VT-3 Benutzer- und Protokollverwaltung der Plattform

| Feld | Inhalt |
|---|---|
| Zweck | Zugangssteuerung, Nachvollziehbarkeit (Audit), Sicherheit. |
| Rechtsgrundlage | Art. 6 Abs. 1 lit. b/c/f DSGVO, § 26 BDSG (Beschäftigtendaten). |
| Daten | Benutzername, Anzeigename, Rolle, Passwort-Hash (argon2id), 2FA-Geheimnis (verschlüsselt), Anmeldezeitpunkte, IP-Adressen bei Fehlversuchen, Aktionen im Audit-Protokoll. |
| Löschung | Konten deaktivieren statt löschen, solange Audit-Einträge aufbewahrt werden müssen; Audit-Protokoll […Jahre]. |

## VT-4 Datensicherung

Verschlüsselte Sicherungen aller Daten; Aufbewahrung […30 Tage rollierend]; gelöschte Fälle verschwinden spätestens mit Ablauf der ältesten Sicherung.
