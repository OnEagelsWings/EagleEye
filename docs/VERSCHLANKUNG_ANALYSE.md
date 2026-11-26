# Verschlankung: Was ist wirklich tot, und was fiele weg?

Stand 26.11.2026, Gesamtversion 500 (`main` 2adbd32) plus Windows-Installer. Es wurde **nichts gelöscht**.
Dieses Dokument ist die Entscheidungsgrundlage für Schritt 2 (Aufräumen).

## Kurzfassung

| | Module | Zeilen | Anteil |
|---|---:|---:|---:|
| Programmcode gesamt (Fallakte `eagleeye` + `eagleeye_pro` + PersonOSINT) | 2.038 | 256.965 | 100 % |
| **sicher entbehrlich, ohne jeden Funktionsverlust** (Klassen A, B, C1) | **1.198** | **117.373** | **46 %** |
| lebt, wird bei Bedarf geladen (C2) | 183 | 42.488 | 17 % |
| lebt, wird beim Start geladen (D) | 657 | 97.104 | 38 % |

- **PersonOSINT hat keinen toten Code.** Alles Tote liegt in der Fallakte (`eagleeye`, `eagleeye_pro`).
- Die Oberfläche hat 687 Adressen. **90 davon** erreicht man über Menü, Links, Formulare und Downloads. Rund
  500 sind Maschinenschnittstellen früherer Builds, und 17 sind alte Seiten, die nur per direkter Adresse aufrufbar sind.
- Die App besteht aus **128 aufeinander aufbauenden Schichten** (`app364` … `app500`). 23 weitere App-Dateien
  gehören zu keiner Schicht.
- Prüfstand: volle Testsuite unter Python 3.14 (das Python des neuen Installers): 2.139 + 8 Browsertests bestanden,
  PersonOSINT 118 bestanden. Die Tests unter Windows mit genau den Paketbibliotheken: bestanden.

**Korrektur früherer Zahlen:** Ich hatte von „151 Schichten“ und „zwei Drittel nie geladen“ gesprochen. Genauer
gemessen sind es 128 Schichten. Sicher tot sind 46 %. Weitere 17 % werden zwar nicht beim Start geladen, sind aber
erreichbar und gelten deshalb als lebendig.

## Methode: drei unabhängige Prüfungen

1. **Importgraph** aller 2.038 Module, auch Importe innerhalb von Funktionen und Modulnamen in Texten
   (`importlib`, Dienstregister). Ausgangspunkte sind alle echten Startpunkte: Fallakte (alter Starter und neues
   Startmenü), Vault/PersonOSINT, Kommandozeile `eagleeye`, Quellenprüfung, Installer. Getrennt davon wurden alle
   Tests, Werkzeuge und Skripte im Hauptordner betrachtet.
2. **Laufzeit:** Fallakte und Vault werden wirklich gestartet. Gemessen wird, welche Module geladen werden und welche
   der **676 Dienste im Dienstregister** von geladenem Code überhaupt angefordert werden (Attributzugriff, `get("…")`,
   `getattr`), einschließlich ihrer Abhängigkeiten.
3. **Klick-Roboter:** Angemeldet, mit Fall und Dokument, läuft er alle Menüs, Links, Formulare, Downloads und Skripte
   ab (83 Seiten). Jede aufgerufene Adresse wird der Stelle im Code zugeordnet, die sie beantwortet.

Neu erzeugen mit `tools/verschlankung/run.sh <Arbeitsordner>`. Die vollständigen Listen liegen in
`docs/verschlankung/module.csv` (jedes Modul mit Klasse und Zeilen) und `docs/verschlankung/adressen.csv`
(jede Adresse mit Erreichbarkeit).

## Die Klassen im Einzelnen

| Klasse | Module | Zeilen | Was ist das? | Was fiele beim Löschen weg? |
|---|---:|---:|---|---|
| **A** von nichts importiert | 550 | 38.010 | alte Weboberfläche `app.py` mit 34 Ansichten (Builds 136–168), `app344`–`app359`, 422 Module der Datenbankschicht `infrastructure/buildNNN` (rund 210 alte Builds), 54 Fachmodule ohne Aufrufer (z. B. `social_collection`, `missing_person_workflow`, `crime_threat_workflow`, `geospatial_intelligence`) | **nichts.** Kein Startpunkt, kein Test und kein Werkzeug lädt sie. |
| **B** nur von Tests importiert | 10 | 2.706 | `app360`–`app363`, `app460`, `app472`–`app474`, zwei Phase-20-Hilfsmodule | **nichts** in der App, nur die zugehörigen Tests |
| **C1** nur im Dienstregister eingetragen, nie angefordert | 638 | 76.657 | 327 der 676 Dienste: 199 der Form `build151`, `build152` …, dazu z. B. `adaptive_tuning_62`, `browser_capture_60`, `analyst_cockpit_70`, `contradiction_engine_118` | **nichts** in der App. Kein geladener Code fragt sie an, auch keine alte Schnittstelle. Alte Tests, die sie direkt aufrufen, fallen mit weg. |
| **C2** bei Bedarf geladen | 183 | 42.488 | Dienste, die eine Seite oder Schnittstelle bei Aufruf lädt, Teile von PersonOSINT | lebt, Entscheidung erst mit Stufe 2/3 |
| **D** beim Start geladen | 657 | 97.104 | die 128 Schichten, Büro, Belege, Vault, PersonOSINT | lebt |

## Die Oberfläche: was ein Nutzer heute erreicht

**Menü (26 Einträge) und „Alle Werkzeuge“ führen zu 56 Seiten**, zusammen 90 Adressen mit Formularen und
Downloads. Nach Themen sortiert:

| Thema | Seiten (Titel) |
|---|---|
| Büro | Übersicht, Neuer Auftrag, Auftragsdaten ergänzen, Mandanten, Team, Rechnungen, Datensicherung, Einstellungen, Mein Konto, Löschprotokoll |
| Ablauf | Geführter Ablauf („Dein Ermittlungs- und Rechercheablauf“), Klassische Fallübersicht, Neuen Ermittlungsfall anlegen |
| Recherche | Öffentliche Quellen und Personenrecherche (501), Recherchefunde/Suchhinweise (483), Dork-Recherche (482), Ermittlungsplanung (496), Öffentliche Quellen erfassen (469), Providerlauf (497) |
| PersonOSINT in der Fallakte | Kontrollierte Übernahme (493), Entitätenprüfung (494), PersonOSINT Intelligence (495), Personenanalyse (502) |
| Lokale KI (Ollama) | Lokaler KI-Ermittler (471), KI-Prüfpunkt (475), KI-Ermittlungsplan (498) |
| Belege | Webseite als Beleg sichern (492), Struktur & Texterkennung (492), Dokumente und Fundstellen (**zweimal**: 458 und Menü „Dokumente“), Quellenübergabe Original → Evidence (481), Bildakte (482), Bildvergleich (484), Quelleninventar (477), Quellenzuordnung/Provenienz (487), Beziehungen mit Dokumenten verknüpfen (463) |
| Auswertung | Befunde (478), Entity-Prüfung (488), Entitäten und Beziehungen (462), Entitäten-Übernahme (499), Intelligence Graph (464), Netzwerkanalyse (492), Quellenunabhängigkeit (492), Analysewerkzeuge |
| Bericht und Prüfung | Arbeitsbericht (479), Evidence → Claims → Dossier (478), Integrierte Fallprüfung (465), Ermittlungsweg (461) |
| Entwicklungs-Prüfseiten | Prüfpunkt 480, Pilotprüfung 485, Qualitätsprüfung 470, Bereitschaft 500, Benchmark 468 |

**Nur per direkter Adresse erreichbar (kein Link, kein Menü), 17 alte Seiten:**
Fallansicht `/cases/{id}` (364), KI-Ermittlungsbriefing (364), Operations (365), Corporate Live Data (366), Procurement/Public Money
(367), Reference Intelligence (368), Crawler Production (369), **Controlled Tor Gateway (370)**, Entity Resolution v2
(371) und Eval (372), Analyst Graph (373), Case Workflow (374), Voice → Crawler Intent (378), `/legacy` (450),
Belegprüfung `/provenance466`, „Sicherung und Wiederherstellung“ `/workbench/recovery` (479, die ältere Fassung neben
Büro → Datensicherung) und Prüfcheckpoint 489.
Ebenfalls ohne Link, aber **nicht tot**: Anmeldung und Ersteinrichtung (`/security/…`), `/health` (prüft der Starter),
`/openapi.json` (automatische Schnittstellenbeschreibung, Abschalten empfohlen).

**Rund 500 Maschinenschnittstellen** (`/api/buildNNN/…`, `/api/cases/…`) werden von keiner erreichbaren Seite per
Link oder Formular genutzt. Einen Teil ruft die alte Fallansicht `/cases/{id}` per JavaScript auf. Vor dem Entfernen
prüfe ich jede Seite einzeln mit einem Mitschnitt im echten Browser.

## Was bei einer Verschlankung wegfiele, in drei Stufen

### Stufe 1: ohne jeden Funktionsverlust (Empfehlung: sofort)

- Klassen A, B und C1: **1.198 Module, 117.373 Zeilen**
- die Tests, die nur diese Module prüfen
- die Ablage im Hauptordner: 1.033 Dateien, davon 438 Markdown-Dokumente, 369 JSON-Prüfprotokolle, 168
  Python-Skripte (z. B. `EAGLEEYE_ACCEPTANCE_BUILD_360_0.py`), 73 Installer/Starter, davon nur 6 für die heutige ZIP-Fassung
- 40 `tools/benchmark_build*.py` und 42 der 53 GitHub-Läufe (Builds 452–489)
- **Sichtbar ändert sich nichts.** Nachweis: volle Testsuite vorher und nachher. Alles bleibt in der Git-Historie
  (Markierung `historie-500`).

### Stufe 2: alte, versteckte Teile (Empfehlung: ja, nach deinem OK zur Liste)

Wegfallen würden die 17 nur direkt erreichbaren Seiten oben und die Schnittstellen ohne Aufrufer, mit den Diensten,
die nur sie benutzen. Wer heute nicht gezielt eine dieser Adressen eintippt, merkt davon nichts.
**Bitte prüfen:** Brauchst du davon etwas bewusst? Kandidaten wären „Controlled Tor Gateway“, „Corporate Live Data“
oder „Procurement/Public Money“. Die Funktion, die du behalten willst, hole ich dann in das aktuelle Menü.

### Stufe 3: Entscheidungen über sichtbare Funktionen (deine Wahl)

Das ist kein toter Code, aber Doppelungen und Entwicklungsreste im Menü:

| Bereich | Überschneidung | Vorschlag |
|---|---|---|
| Entitäten | vier Seiten: 462, 488, 494, 499 | eine Seite „Personen & Firmen prüfen“ |
| Graph | Intelligence Graph (464) und Netzwerkanalyse (492) | Netzwerkanalyse behalten |
| Dokumente | zweimal „Dokumente und Fundstellen“ | eine Seite |
| Fall anlegen | „Neuen Ermittlungsfall anlegen“ und Büro → „Neuer Auftrag“ | nur der Büro-Weg (mit Auftragsprüfung) |
| Prüfseiten | 470, 475, 480, 485, 489, 500, 468 | aus dem Menü nehmen, sie sind Entwicklungswerkzeuge |
| Lokale KI | drei Seiten (471, 475, 498) | behalten oder ganz weglassen, solange kein Ollama im Büro läuft |
| PersonOSINT doppelt | PersonOSINT-App/Vault und vier Übernahmeseiten in der Fallakte | Entscheidung „wer führt“ (Empfehlung: Fallakte führt, Vault als Speicherart) |
| Rechtlich offen | Legenden/Tarnidentität, Vermisstenüberwachung (Vault/PersonOSINT) | bis zur Rechtsprüfung ausblenden |

Erst nach Stufe 3 lohnt das Zusammenführen der 128 Schichten zu **einem** Startpunkt mit fachlichen Bereichen.

## Grenzen der Analyse

- „Nie angefordert“ (C1) beruht auf allen Stellen, an denen Code einen Dienst namentlich anfordert. Ein Dienst,
  dessen Name zur Laufzeit zusammengesetzt oder aus der Datenbank gelesen wird, wäre nicht erkannt. Die einzige
  solche Stelle ist die alte Governance-Freigabe (Build 132). Deshalb gilt: **Erst die volle Testsuite nach dem
  Löschen ist der Nachweis.** Fällt ein Test um, kommt das Modul zurück.
- Der Klick-Roboter folgt Links, Formularen und Skripten, nicht JavaScript-Aufrufen im Seitentext. Für Stufe 2
  folgt deshalb ein Mitschnitt im echten Browser.
- Seiten, die erst mit bestimmten Daten erscheinen (z. B. eine Rechnung als PDF), gelten als erreichbar, weil sie
  im selben Modul wie erreichbare Seiten liegen.
