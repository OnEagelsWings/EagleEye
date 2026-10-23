# Build 472 – Fragen an ausgewählte Fallquellen

Im Fallmenü **Lokaler KI-Ermittler** eine Arbeitsfrage eingeben, 1–3 Dokumente
wählen und lokal zusammenfassen lassen. Leer lassen erzeugt weiterhin eine Zusammenfassung.
Antworten benötigen genaue Fall-Fundstellen und wörtliche Zitate. Bei fehlender
Quellengrundlage verlangt das Schema `insufficient_evidence` ohne Tatsachenaussagen oder freie Modellprosa; Gründe werden als feste Gap-Codes gespeichert und von der Oberfläche übersetzt.
Frage, Antwort, Quellen, Modell-Digest und menschliche Prüfung werden gemeinsam gespeichert.
Kein automatischer Claim, keine Faktenbestätigung oder externe Recherche.

Start: ZIP entpacken, `START_EAGLEEYE_PRO.bat` bzw. `sh START_EAGLEEYE_PRO.sh`.
Python 3.12+; Ollama und ein bereits lokal installiertes Modell separat erforderlich.
Maximal 4 Anker pro Dokument und 1500 Zeichen je Anker; eine Nichtbeantwortung
bezieht sich auf diese Auswahl, nicht auf den gesamten Fall oder das ganze Internet.
Tests simulieren Modellantworten. Echte Modellgüte/i5-Latenz bleiben N/A;
Produktivfreigabe bleibt NEIN. Zwischenbuild mit Smoke-Tests; Vollcheckpoint bei 475.
