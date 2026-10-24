# Gemeinsamer operativer Plan – UI Audit und Windows Startproblem Build 471

Der Windows-Anwendertest hat gezeigt: Eine grüne technische Regression genügt
nicht, wenn ein frischer Nutzer keinen echten Fall anlegen kann. Der in PR #72
begonnene Fix wird deshalb vor weiteren Funktionen zusammengeführt. Die lokale
quellengebundene KI 471–475 bleibt erhalten; Vorschläge werden nicht automatisch
zu Fakten oder Identitätsverschmelzungen.

| Build | Nutzbares Ergebnis | Sichtbare Abnahme |
|---|---|---|
| 475 Hotfix | Regulären Fall ohne F12 erstellen; keine Legacy-Sackgasse | Frischer Browser → Erstkonfiguration → Login → Fall → Dokument → Reload |
| 476 | Windows-Start mit stabilem Arbeitsordner, Diagnose und Browserfallback | Installierter Prozess → Health → Launcherzulassung; Versionswechsel behält Datenordner |
| 477 | Klare fallbezogene Arbeitsübersicht mit nächsten Schritten | Fall wählen → Auftrag → Quellen → Belege/Beziehungen → Prüfung/Bericht; keine toten Standardpfade |
| 478 | Manuelle quellengebundene Erkenntnisse und Gegenbelege | Originalanker auswählen → Aussage/Unsicherheit speichern → erneut abrufen und prüfen |
| 479 | Nutzbarer Recherchebericht und nachvollziehbare Wiederherstellung | Fallbezogener Bericht → menschliche Prüfung → Export; Backup in separatem Ordner wieder öffnen |
| 480 | Vollständige operative Abnahme und Beta-Entscheidung | Windows/Linux, frischer Fall, öffentliche Quellen, Befunde/Gegenbelege, Review, Bericht, Neustart/Restore |

Zwischenbuilds: kurzer neuer Funktions-/Berechtigungs-/Browser-/Installer-Smoke,
ZIP und SHA256. Build 480: vollständige Regression plus Sicherheits- und
Wiederherstellungsprüfung. Vor jedem Merge: alle CI-Checks grün, abgeschlossene
Codex-Review des exakten Heads ohne offene P1/P2. Keine neue funktionale Exclusion.

Ein realer, unkritischer öffentlicher Beispielauftrag soll die Quellenfunktionen
prüfen. Simulierte Antworten werden getrennt von Live-Ergebnissen ausgewiesen.
Ausfälle oder nicht implementierte Schritte heißen FAIL/N/A. Die Modellgüte,
Skalierungsziele und unabhängige Produktivabnahme werden nicht aus Unit-Tests
abgeleitet. Ein normal benutzbarer Recherchefall ist von einer unabhängigen
Freigabe für sensible Aufträge zu unterscheiden.
