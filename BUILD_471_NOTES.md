# Build 471 – quellengebundener lokaler KI-Ermittler

Fortsetzung von Roadmap #61 nach dem gemergten Checkpoint 470 (`048f55a5cf23`).
Zwischenbuild: gezielte Smoke-/Negativtests; vollständiger KI-/Security-Checkpoint bei 475.

## Bedienung
1. ZIP vollständig entpacken. Python 3.12 oder neuer installieren.
2. Windows: `START_EAGLEEYE_PRO.bat`; Linux: `sh START_EAGLEEYE_PRO.sh`.
   Der Installer benötigt beim ersten Start Zugriff auf Python-Abhängigkeiten.
3. Lokal anmelden, Fall öffnen und Dokumente mit Quellen-URL importieren.
4. Im Fallmenü **Lokaler KI-Ermittler** öffnen, 1–3 Dokumente auswählen.
5. Ollama mit einem bereits lokal installierten Modell starten. Den exakten Modellnamen
   aus `ollama list` angeben (z. B. `mistral:latest`). Kein Modell/Runtime im ZIP enthalten.
6. **Auswahl lokal zusammenfassen**. Auf dem i5/16-GB-Laptop ist ein kleines quantisiertes
   Modell vorgesehen; Geschwindigkeit und Ergebnisqualität müssen dort erst gemessen werden.
7. Vorschläge, Unsicherheiten und Originalfundstellen prüfen. Mit Begründung verwerfen
   oder als gelesen/geprüft kennzeichnen; beides erzeugt keine bestätigten Fakten/Claims.

## Umfang und Grenzen
- Bestehende Document458-Daten sind die Quelle; keine zweite Belegablage.
- Persistente Entwürfe/Prüfungen im bestehenden lokalen SQLite-Speicher; letzte 20 sichtbar.
- Je Dokument maximal die ersten vier Textanker, je 1500 Zeichen. Explizite Teilabdeckung.
- Zu jeder Aussage verlangt das Schema mindestens eine zulässige Anchor-ID mit wörtlichem
  Zitat. Zugehörigkeit, Zitattext, Dokument-/Anker-Hashes und Originalbytes werden geprüft.
- Quellen-/Modelländerungen während eines Laufs verwerfen das Ergebnis. Frühere Entwürfe
  sind historische Snapshots; spätere Änderungen erfordern einen neuen Lauf.
- Modell-Digest, Eingabe-Hash, Erstellungszeit, Autor und Prüfentscheidung werden gespeichert.
- Fallberechtigung vor Modellzugriff und vor Speicherung; separate `research.run` und
  `source.review`, aktive Benutzeridentität, CSRF und Origin-Prüfung. Kein automatisches
  Promoten von Fakten, keine Modellwerkzeuge und keine neue externe Sammlung.
- Fester numerischer Loopback-Endpunkt `127.0.0.1:11434`, keine Proxies/Redirects,
  keine Cloud-Modelle/Remote-Modelleinträge und kein automatischer Modell-Download.
- Prompt-Injection-Abgrenzung, striktes JSON-Schema und genaue Zitate begrenzen den
  Eingabekanal. Das ist kein Nachweis vollständiger Halluzinations-/Injection-Sicherheit:
  ein passendes Zitat kann eine Modellbehauptung trotzdem nicht tragen.
- Lokale Ollama-Installation muss vertrauenswürdig und lokal konfiguriert sein.
- Modell-/Livequalität sowie i5-Laufzeiten bleiben N/A ohne echten Modelltest.
- Produktivfreigabe bleibt NEIN. Offene 470-Gates (immutable Rohbelege, dossier/export,
  restore, reale Suchgüte und unabhängige Praxistests) bleiben bestehen.

## Reproduzierbare gezielte Prüfung
```sh
python -m pytest -q tests/test_build471_local_ai.py
python -m pytest -q tests/test_build458_document_intelligence.py tests/test_build459_workspace_navigation.py -k 'not test_build458_current_installer_and_next_checkpoint'
python INSTALL_EAGLEEYE_471.py --check
```

Die automatisierten Funktionstests simulieren Modellantworten. Ein erfolgreicher Test
belegt den technischen Workflow, nicht die Qualität eines tatsächlichen Sprachmodells.
Linux-/Windows-GitHub-Läufe und Codex-Review müssen vor Merge am exakten Head erfolgreich sein.
