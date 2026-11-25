# Löschkonzept (Entwurf)

## 1. Grundsatz

Personenbezogene Daten aus Recherchen werden nur so lange gespeichert, wie es der Auftrag, gesetzliche Aufbewahrungspflichten oder die Abwehr von Rechtsansprüchen erfordern.

## 2. Fristen

| Datenart | Frist | Auslöser | Umsetzung in EagleEye |
|---|---|---|---|
| Falldaten (Personen, Treffer, Aussagen, Fotos, Belege, Dossier-Entwürfe) | Standard **[12] Monate** nach Abschluss (einstellbar 1–120) | Status „abgeschlossen“ oder „archiviert“ | Löschfrist wird automatisch gesetzt; im Fall unter „Fall & Team“ änderbar (Begründung in den Notizen) |
| Ausgelieferte Dossiers beim Unternehmen | wie Falldaten; Rechnungsrelevante Unterlagen (Auftrag, Rechnung) gesondert: 6/10 Jahre (HGB/AO) | Abschluss | Dossier-Dateien außerhalb der Plattform sind manuell zu löschen; Exportregister zeigt, was erzeugt wurde |
| Audit-Protokoll | [3] Jahre | Eintrag | Bei Fall-Löschung werden Freitexte geschwärzt, die Kette bleibt prüfbar |
| Benutzerkonten | bis Ausscheiden + [3] Jahre (Nachvollziehbarkeit) | Deaktivierung | Konto deaktivieren |
| Sicherungen | [30] Tage rollierend | Erstellung | Gelöschtes verschwindet spätestens mit der ältesten Sicherung |
| Lokale Referenzdatenbanken | bis zum nächsten Import / solange lizenziert | Import | *Verwaltung → Quellen & Daten → Löschen* |

**Längere Speicherung** nur bei konkretem Anlass (laufendes Verfahren, Aufbewahrungspflicht, Auftrag zur Fortsetzung) – Frist im Fall verlängern und Grund in den Notizen festhalten.

## 3. Ablauf

1. Beim Abschluss setzt das System die Löschfrist (Fallkopf zeigt „🗑 Löschfrist TT.MM.JJJJ“).
2. Bei Erreichen der Frist erhalten verantwortliche Person und Teamleitung (bei vertraulichen Fällen nur die verantwortliche Person) **einmalig** eine Benachrichtigung.
3. Die verantwortliche Person prüft: löschen oder begründet verlängern.
4. Löschen über *Fall & Team → Fall löschen*. Das System entfernt Falldaten, Fotos und Belege und schwärzt Protokolltexte.
5. Die Teamleitung kontrolliert monatlich *Verwaltung → Löschfristen* (fällige Fälle, Fälle ohne Frist).

## 4. Verantwortlichkeiten

Verantwortliche Person des Falls: Löschung · Teamleitung: monatliche Kontrolle · Administration: Standardfrist, Sicherungsrotation · DSB: jährliche Stichprobe.
