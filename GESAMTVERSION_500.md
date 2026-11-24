# EagleEye Gesamtversion 500 – Versionshinweise (24. Nov. 2026)

Eine feste Gesamtversion für den eigenen Bürobetrieb: alle aktiven Arbeitslinien in **einem** Stand und
**einem** Paket. Start: `START_HIER.bat` (Übersicht in `LIESMICH_KOMPLETTPAKET.md`).

## Bestandteile

| Teil | Version | Start im Menü | Anleitung |
|---|---|---|---|
| EagleEye-Fallakte mit Büro (Mandanten, Aufträge, Zeiten, Rechnungen, Datensicherung, Web-Belege mit Zeitstempel und Seitenbild, Bericht) | Build 500.0 | 3 | `BETRIEBSHANDBUCH_BUERO.md` |
| EagleEye Vault (verschlüsselte Recherche-Station, Fallakte im selben Tresor) | mit PersonOSINT 1.9 | V | `PersonOSINT/docs/VAULT.md` |
| PersonOSINT (Personen- und Firmenrecherche, Tiefenrecherche, Vermisstenregister, Dossier) | 1.9.0 | 1, 2 | `PersonOSINT/README.md`, `PersonOSINT/docs/TIEFENRECHERCHE.md` |
| Quellenprüfung | – | 4 | `LIESMICH_KOMPLETTPAKET.md` |
| Forschungs-Brücke (öffentliche Sachthemen, privater Austauschbranch, manuelle Freigabe) | 1.0.0-rc3 (Vorschau, unsigniert) | 6 | `tools/research_exchange/README.md` |
| Analyse-Arbeitsplatz (ExifTool, OCR, Video, Volltext, Sherlock, Sleuth Kit, TShark, ZAP passiv, Gitleaks, YARA, Nmap-Vergleich, Lynis) | – | 7 | `tools/analysis/README.txt` |

In der Fallakte neu in der Seitenleiste: **Auswertung → Analysewerkzeuge** (Befund aus dem Analyse-Arbeitsplatz als
Quelldokument übernehmen).

## Woraus die Gesamtversion besteht

| Linie | Inhalt | Stand |
|---|---|---|
| `claude/osint-platform-person-search-r875rx` (gemeinsamer Stand) | Build 493–503, Büro, Web-Belege, PersonOSINT 1.9, Vault, Legenden-Browser, Installer-Härtung | Grundlage (`38733c8`) |
| `build-490-synthetic-e2e-acceptance` | getrennte Einstellungen Build 490/500, Arbeitsordner außerhalb der Installation, Ablehnung umgeleiteter Datenverzeichnisse und Nicht-Dateien als Datenbank | übernommen |
| `feature/research-exchange-bridge` | Windows-Schlüsselschutz (DPAPI, ACL), Prüfprotokoll, Einzelsatz-Ablauf | übernommen |
| `feature/public-research-bridge-integration-20261120` | Desktop-Oberfläche der Forschungs-Brücke, Installer, Freigabeprüfung, Audit-Anker | übernommen |
| `main` | lokale Analysewerkzeuge, ExifTool/OCR/Poppler unter Windows | übernommen |

Beim Zusammenführen angepasst:
- **Startmenü:** die sichere Fassung mit festen Tasten bleibt; die Forschungs-Brücke kommt als Taste 6 und der
  Analyse-Arbeitsplatz als Taste 7 dazu.
- **Datenbankpfade:** beide Schutzprüfungen sind erhalten (Nicht-Dateien, Hardlinks, symbolische Links), in fester Reihenfolge.

## Bewusst nicht übernommen

Die übrigen rund 50 Branches (`build-400` … `build-489`, `release/build-476…479`, `phase18/…`,
`planning/builds-482-500-…`, `external-tester-15min` u. a.) sind **Zwischenstände** früherer Builds. Ihr Inhalt ist im
gemeinsamen Stand weiterentwickelt worden. Was dort noch als eigene Datei liegt, sind frühere Installer und Startdateien
(z. B. `INSTALL_EAGLEEYE_459.py`), Prüfprotokolle alter Builds und Planungsdokumente. Diese würden heute einen zweiten,
veralteten Start- oder Installationsweg einführen. Sie bleiben im Repository als Historie erhalten. Das Repository
`OEWsec` ist ein eigenes Projekt und kein Teil von EagleEye.

## Prüfstand

Die Ergebnisse stehen im Pull Request zu dieser Gesamtversion: volle Regression der Fallakte, PersonOSINT-Tests,
Tests der Forschungs-Brücke sowie die GitHub-Läufe unter Windows und Linux.

## Offene Punkte vor dem Einsatz mit echten Mandaten

1. **Rechtliche Prüfung** der Tarnfunktionen (Legenden, neue Netzidentität) und der Vermisstenüberwachung: in welchem
   Rahmen ihr sie als Detektei nutzen dürft. Dazu Datenschutz-Folgenabschätzung, Verarbeitungsverzeichnis und
   Löschkonzept für die Personenrecherche.
2. **Forschungs-Brücke** ist eine unsignierte Vorschau (RC3). Sie verarbeitet keine Fallakten und keine Personendaten.
3. **Analyse-Arbeitsplatz:** Die Analyseprogramme werden nicht mitgeliefert. „Werkzeug“ zeigt an, was auf dem Rechner fehlt.
4. **Erster Probebetrieb im Büro:** einmal eine Seite mit Zeitstempel sichern (echte Anfrage an DigiCert), eine Sicherung
   auf die externe Platte schreiben und wieder einspielen.
