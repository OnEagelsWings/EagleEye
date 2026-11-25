# Rechtliche Vorbereitung (Entwürfe)

> **Wichtig:** Diese Unterlagen sind **Arbeitsentwürfe** auf Basis der Funktionen von EagleEye PersonOSINT. Sie ersetzen keine Rechtsberatung.
> Vor dem Produktivbetrieb müssen sie von der/dem **Datenschutzbeauftragten** und einer **Rechtsanwältin / einem Rechtsanwalt** (Datenschutz-, ggf. Presse- und Detekteirecht) geprüft, angepasst und freigegeben werden. Stellen mit `[…]` sind unternehmensspezifisch auszufüllen.

| Dokument | Zweck | Pflicht? |
|---|---|---|
| [Verarbeitungsverzeichnis.md](Verarbeitungsverzeichnis.md) | Verzeichnis von Verarbeitungstätigkeiten | ja, Art. 30 DSGVO |
| [DSFA_Vorlage.md](DSFA_Vorlage.md) | Datenschutz-Folgenabschätzung für Personenrecherchen | sehr wahrscheinlich ja, Art. 35 DSGVO (umfangreiche Profilbildung, oft ohne Wissen der Betroffenen) |
| [Loeschkonzept.md](Loeschkonzept.md) | Fristen und Ablauf der Löschung | ja (Art. 5 Abs. 1 lit. e, Art. 17 DSGVO) |
| [Auftragspruefung.md](Auftragspruefung.md) | Annahme-/Ablehnungsregeln für Aufträge, Missbrauchsschutz | dringend empfohlen (Haftung, Ruf) |
| [TOM.md](TOM.md) | Technische und organisatorische Maßnahmen | ja, Art. 32 DSGVO (Anlage zu Verzeichnis und AV-Verträgen) |

## Was die Software dafür bereits liefert

- **Zweck und Rechtsgrundlage** sind Pflichtangaben bei jedem Fall und stehen im Dossier.
- **Auftragsprüfung** mit Warnsignalen im Fall-Assistenten; Annahme trotz Warnsignalen nur durch Teamleitung mit Begründung; Ergebnis im Fallprotokoll und im Dossier (Kapitel „Auftrag“).
- **Löschfristen**: werden beim Abschluss automatisch gesetzt (Standard in *Verwaltung → Löschfristen*), Erinnerung an Verantwortliche und Teamleitung, Übersicht fälliger Fälle. Gelöscht wird bewusst nicht automatisch.
- **Protokollierung** aller Zugriffe/Änderungen in einer manipulationssicheren Kette; beim Löschen eines Falls werden Protokolltexte geschwärzt.
- **Exportregister** mit Export-ID: Wer hat wann welches Dossier/Beweispaket erzeugt.
- **Verschlüsselung** von Fotos, Belegen, Schlüsseln und Sicherungen.

## Noch durch Menschen zu erledigen

1. Unterlagen prüfen lassen, ausfüllen, unterschreiben (Geschäftsführung).
2. AV-Verträge mit Hoster, ggf. Proxy-/VPN-Anbieter abschließen; bei Behördenaufträgen Auftragsverarbeitung bzw. gemeinsame Verantwortlichkeit klären.
3. Informationspflichten (Art. 14 DSGVO) und Ausnahmen (Art. 14 Abs. 5) je Fallart festlegen – bei Recherchen ohne Wissen der Zielperson zentral.
4. Für journalistische Recherchen: Anwendbarkeit des Medienprivilegs (Landespresse-/Landesmediengesetz) bestätigen lassen.
5. Lizenzbedingungen der angebundenen Quellen (z. B. OpenSanctions nur nicht-kommerziell frei) mit dem Geschäftsmodell abgleichen.
