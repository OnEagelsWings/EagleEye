# Zusammenführung in Version 1.5 – was woher kommt

PersonOSINT 1.5 vereint drei Arbeitslinien: PersonOSINT 1.4, den Chat „SpiderFoot Reverse Engineering“
(Analysen von SpiderFoot und Obsidian, Tool-Auswahl, EagleEye Build 492) und die von ChatGPT gebauten
EagleEye-Builds 493–500. Diese Seite zeigt, welche Idee wo gelandet ist – und was bewusst anders gelöst wurde.

## Aus EagleEye Build 492 (Tool-Auswahl A1–A5, B1)

| Fähigkeit | In PersonOSINT | Wo in der Oberfläche | Abweichung und Grund |
|---|---|---|---|
| Webseite als WARC sichern, Haupttext | `webarchive.py`, `evidence.py` | Dossier & Export → Belege | Abruf läuft über den **Netzausgang des Falls** (Proxy/Tor) statt direkt – OPSEC-Regeln gelten auch für Belege. |
| Frühere Fassungen (Internet Archive) | `evidence.wayback_versions` | Belege → „🕰 Frühere Fassungen“ | – |
| Dokumente mit Struktur und Texterkennung | `documents.py` | Belege → „📄 Dokument importieren“ | **Ohne PyMuPDF** (AGPL, Lizenzbefund der Tool-Auswahl); Text über pypdf, Seitenbilder über pypdfium2, Tesseract direkt. Tabellen/Überschriften-Erkennung entfällt vorerst. |
| Quellfamilien (unabhängige Ursprünge) | `lineage.py` | Belege → „🧬 Quellenunabhängigkeit“; Fakten → „gleicher Ursprung“ | **Exakte** Ähnlichkeit statt MinHash – bei der Größe eines Falls schnell genug, ohne numpy. Wirkt direkt auf die Bewertung. |
| Entitätenabgleich mit Begründung | `namematch.py` | Verbindungen → Vorschläge („Mögliche Dublette“) | Gleiche Messwerte wie Build 492 am unabhängigen Prüfsatz (0,93 / 0,93). Zusätzlich findet die Suche jetzt Namen in anderen Schriften. |
| Netzwerkanalyse, GEXF, FollowTheMoney | `network.py` | Verbindungen → „🕸 Netzwerkanalyse“, „⇄ Austausch“ | Ohne NetworkX – vorhandene Graphfunktionen erweitert. FollowTheMoney auch als **Import**. |

## Aus der SpiderFoot-Analyse (Abschnitt 6 „Übertragbare Muster“)

| Muster | Umsetzung |
|---|---|
| Module erklären, was sie verarbeiten und liefern | Jede Quelle hat `kinds` (verarbeitet) und `produces` (liefert) – sichtbar unter Verwaltung → Quellen & Daten. |
| Automatische Verkettung von Modulen | **Folgesuchen** (`pivot.py`): nur als Vorschlag aus bestätigten Treffern, Ausführung erst nach Freigabe, höchstens 3 Stufen. |
| Herkunftskette jedes Datenpunkts | „🧭 Herkunft“ an jedem Treffer: Zielperson → Suche → Treffer → Kennung → Folgesuche → Treffer. |
| Deklarative Korrelationsregeln | `correlation.py`: sechs eingebaute Regeln, eigene Regeln als Beschreibung – erzeugen nur Prüfhinweise. |
| Konfigurations-Snapshot je Scan | Jeder Suchlauf speichert Version, OPSEC-Stufe, Netzausgang und Quellen mit Verlässlichkeit. |
| Passiv/invasiv je Modul | War bereits vorhanden (Expositionsklassen, OPSEC-Stufen). |

Nicht übernommen (wie in der Analyse empfohlen): Klartext-Schlüssel, fehlende Anmeldung, frei ausführbares SQL,
Fremdmodule im Anwendungsprozess.

## Aus der Obsidian-Analyse

| Muster | Umsetzung |
|---|---|
| Offene Formate (JSON Canvas, Markdown mit Wikilinks) | Export des Graphen als Canvas und des Falls als **Obsidian-Vault** (mit Warnhinweis: unverschlüsselt). |
| Ungeklärte Verweise ausdrücklich führen | Folgesuchen und Dubletten bleiben als offene Vorschläge sichtbar, bis jemand entscheidet. |

## Zusammenspiel mit EagleEye Build 493–500

| Richtung | Weg |
|---|---|
| PersonOSINT → EagleEye | Dossier & Export → „🔁 Übergabe an EagleEye“: passend geteilte Dateien für die Übernahme (Build 493: Fundstellen, Build 494: Einträge). Enthält nur, was EagleEye verarbeitet. |
| EagleEye → PersonOSINT | Verbindungen → „⬆ FollowTheMoney einlesen“: Graph-Export aus Build 492/500 – alles bleibt ungeprüft. |

Prüfbericht zu Build 493–500 und der Vorschlag, PersonOSINT als Recherche-Bibliothek in EagleEye zu nutzen:
[../../CLAUDE_REVIEW_UND_UEBERGABE_500.md](../../CLAUDE_REVIEW_UND_UEBERGABE_500.md).

## Neue Bausteine und Lizenzen

warcio (Apache-2.0), trafilatura (Apache-2.0), rapidfuzz (MIT), anyascii (ISC), pypdf (BSD-3), pypdfium2 (Apache-2.0/BSD-3),
pytesseract (Apache-2.0). Texterkennung braucht das Programm Tesseract (Apache-2.0) – im Docker-Image mit
`EAGLEEYE_WITH_OCR=1` enthalten; ohne Tesseract funktioniert alles andere, und die Verwaltung zeigt den Hinweis.
