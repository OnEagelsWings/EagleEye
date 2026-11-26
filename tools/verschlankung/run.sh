#!/usr/bin/env bash
# Verschlankungsanalyse neu erzeugen (Linux, im Repository-Hauptordner, Python mit allen Abhängigkeiten).
# Ergebnis: <arbeitsordner>/classes.json, crawl.json; Bericht: docs/VERSCHLANKUNG_ANALYSE.md
set -euo pipefail
PY=${PY:-python}
W=${1:?Arbeitsordner angeben}
mkdir -p "$W/ws1" "$W/ws2" "$W/ws3"
HERE=tools/verschlankung
$PY $HERE/graph.py . "$W/static.json"                      # A/B: Importgraph aller Startpunkte und Tests
$PY $HERE/runtime_loaded.py "$W/runtime.json" "$W/ws1"     # D: beim Start geladene Module, Adressen
$PY $HERE/frontier.py . "$W"                               # warum statisch erreichbar, aber nicht geladen
$PY $HERE/crawl.py "$W/crawl.json" "$W/ws2"                # Klick-Roboter über Menü, Links, Formulare
$PY $HERE/registry.py "$W" && $PY $HERE/registry2.py "$W"  # angeforderte Dienste des Registers
$PY $HERE/classify.py . "$W"                               # Klassen A, B, C1, C2, D
$PY $HERE/hidden_titles.py "$W/crawl.json" "$W/ws3"        # Titel der nur direkt erreichbaren Seiten
