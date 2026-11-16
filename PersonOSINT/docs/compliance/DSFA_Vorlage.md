# Datenschutz-Folgenabschätzung – Vorlage (Entwurf, Art. 35 DSGVO)

**Verarbeitung:** OSINT-Personenrecherche mit EagleEye PersonOSINT (VT-1/VT-2) · **Erstellt von:** […] · **Beteiligt:** DSB […] · **Stand:** […]

## 1. Ist eine DSFA nötig?

Ja, voraussichtlich. Kriterien der Datenschutzkonferenz (DSK-Liste „Muss-Liste“) bzw. EDSA-Leitlinien, die erfüllt sein können:
- umfassende Profilbildung über Personen aus vielen Quellen (Zusammenführung von Datenbeständen),
- Verarbeitung ohne Kenntnis der Betroffenen (verdeckte Recherche),
- Bewertung von Personen (Glaubwürdigkeit, Red Flags, Sanktionsnähe),
- möglicherweise schutzbedürftige Betroffene (Vermisste, Opfer, Minderjährige als Kontaktpersonen).

## 2. Systematische Beschreibung

| | |
|---|---|
| Ablauf | Fall anlegen (Zweck, Rechtsgrundlage, Auftragsprüfung) → automatische/manuelle Abfragen → Treffer prüfen → Aussagen (Fakten) bewerten → Dossier mit Belegen → Vier-Augen-Freigabe → Export (registriert) → Abschluss → Löschfrist → Löschung |
| Systeme | EagleEye-Server […Standort/Hoster], PostgreSQL, Caddy (TLS), optional Tor/Proxy, optional lokales KI-Modell (keine Datenübermittlung an KI-Anbieter) |
| Quellen | siehe *Verwaltung → Quellen & Daten* (je Quelle: Lizenz, Zuverlässigkeit, Expositionsklasse) |

## 3. Notwendigkeit und Verhältnismäßigkeit

- **Zweckbindung:** Zweck ist Pflichtangabe je Fall, steht im Dossier. Recherchen ohne Zweck sind technisch nicht möglich.
- **Datenminimierung:** Quellenwahl je Suche; Treffer müssen geprüft werden, nur bestätigte Aussagen gehen ins Dossier (Standard); verworfene Treffer bleiben nachvollziehbar, werden aber nicht exportiert.
- **Richtigkeit:** Admiralty-Bewertung, Mehrquellen-Bestätigung, Widerspruchsanzeige, Vier-Augen-Prüfung.
- **Speicherbegrenzung:** Löschfristen mit Erinnerung (Löschkonzept).
- **Betroffenenrechte:** Auskunft/Löschung über Fallexport bzw. Fall löschen; Ausnahmen der Informationspflicht (Art. 14 Abs. 5) je Fallart begründen: […].

## 4. Risiken für Betroffene

| # | Risiko | Eintritt | Schwere | Maßnahmen | Restrisiko |
|---|---|---|---|---|---|
| R1 | Missbrauch durch Auftraggeber (Stalking, Gewalt, Umgehen von Schutzanordnungen) | mittel | sehr hoch | Auftragsprüfung mit Warnsignalen, Annahme nur durch Teamleitung mit Begründung, Identitätsprüfung Auftraggeber, Dossier ohne Wohnanschrift wenn nicht erforderlich […] | […] |
| R2 | Verwechslung (falsche Person im Dossier) | mittel | hoch | Kandidatengruppen, Geburtsdatum-Abgleich, Bewertung, Vier-Augen-Freigabe, Kennzeichnung ungeprüfter Aussagen | […] |
| R3 | Unbefugter Zugriff auf Dossiers | niedrig | hoch | Rollen/Fallrechte, vertrauliche Fälle, 2FA, Verschlüsselung, Audit, Exportregister | […] |
| R4 | Aufdeckung der Recherche durch Zielperson (Gefahr für Quellen/Beschäftigte) | mittel | mittel–hoch | OPSEC-Stufen, Expositionsklassen, Netzausgang über Proxy/Tor, Sperre sichtbarer Zugriffe | […] |
| R5 | Übermittlung von Suchbegriffen an Drittland-Dienste | hoch | niedrig–mittel | lokale Referenzdaten bevorzugen, Quellen je Fall abwählbar, Proxy | […] |
| R6 | Zu lange Speicherung | mittel | mittel | Löschfristen, Erinnerung, Übersicht fälliger Fälle | […] |
| R7 | Fehlerhafte KI-Zusammenfassung | mittel | mittel | nur lokales Modell, Belegpflicht je Satz, menschliche Freigabe | […] |

## 5. Ergebnis

☐ Restrisiko vertretbar · ☐ Konsultation der Aufsichtsbehörde (Art. 36) nötig
Freigabe Geschäftsführung: […Datum/Unterschrift] · Stellungnahme DSB: […] · Überprüfung spätestens: […]
