# EagleEye 485 – erster öffentlicher Einsatzcheckpoint

**Status:** Entwicklungs-Gate; keine automatische Kundenfreigabe durch die Buildnummer.

Diese Version erbt reguläre Fallanlage, Dork-Suchlinks, manuell bestätigte Recherchehinweise, lokalen Bildimport und Vergleich, interaktiven Graphen, überprüfte Dokumente → ungeprüfte Evidence, vorhandenen KI-Ermittler und analytischen Arbeitsbericht.

## Geordneter Ablauf (über die Benutzeroberfläche)
1. Windows-Batchstarter `START_EAGLEEYE_PRO.bat` aus vollständig entpacktem ZIP. Python 3.12+ und isolierte Runtime.
2. Regulären Fall anlegen und `Geführte Recherche` öffnen, Auftrag und erlaubte Recherchemethoden dokumentieren.
3. Dork-Strategie öffnen → Treffer im Suchdienst manuell bewerten → öffentlichen Treffer als *ungeprüften* Suchhinweis speichern.
4. Rechtmäßig zugängliche TXT/PDF/Markdown-Datei in Quellenimport laden; Extraktion und Originalankern prüfen, dann ausdrücklich in die kanonische *ungeprüfte* Evidence überführen.
5. Bilddatei in der Bildakte speichern; EXIF/GPS/OCR/Hash und mögliche Ähnlichkeiten prüfen; Graphkanten nur mit tatsächlichen Fundstellen.
6. Quellen- und Evidence-Kette prüfen, Claims/Gegenbelege durch Menschen beurteilen, Analystenbericht erstellen. Formales Dossier ausschließlich über separates Vier-Augen-Gate.
7. Unter `Pilot-Abnahme und Fallfortschritt` den **echten** Bestand/Prüfstand kontrollieren.
8. Stoppen, neu starten und Archiv/Restore überprüfen. Erst dann den eigenen Fall an Kunden weitergeben – bei entsprechendem Prüf-/Rechts-/Sicherheitsfreigabestand.

## Sicherheits-/Produktgrenzen
- Der aktuelle Dork-Generator öffnet Suchmaschinenoberflächen. Er sammelt keine Treffer autonom.
- Suchhinweise sind keine Evidence. Bildähnlichkeit ist keine Personenidentität.
- Die vorhandenen echten Live-Datenadapter: DNS-A, .com RDAP und Crossref DOI. Kein vollständig freigegebener Universal-Crawler oder LLM als Tatsacheninstanz.
- Build-485-Pilot-Anzeige gibt **immer NO-GO** für Kunden-/Behördenaufträge aus, bis *separat* eine echte unabhängige Abnahme dokumentiert ist. „Technische Route existiert“ und erfolgreiche Testaccounts sind nicht mit Rechts-/Sicherheitsfreigabe gleichzusetzen.
- Große Prüfungen Windows+Linux, echte Netzwerkquellen, installierter Start, Datenpersistenz, Restore, Original-Belege, Rollen, alte Regression und Hash des Release ZIP. Roter Check ⇒ keine Freigabe.
