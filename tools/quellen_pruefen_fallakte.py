"""Prüft, welche Datenquellen der EagleEye-Fallakte von diesem Rechner aus antworten.

Je Quelle genau **eine** unkritische Testabfrage (öffentliche Testbegriffe, keine echten Zielpersonen), über denselben
abgesicherten Abrufweg wie im Betrieb: feste Hostliste, Prüfung gegen interne Adressen, keine Zugangsdaten.
Es wird nichts in einem Fall gespeichert und nichts freigegeben – das Werkzeug zeigt nur die Erreichbarkeit.

Aufruf (Windows):  QUELLEN_PRUEFEN.bat im Hauptordner
Aufruf (direkt):   python tools/quellen_pruefen_fallakte.py [--out Bericht.md]
"""
from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT / "src", ROOT):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from eagleeye.infrastructure.providers import (  # noqa: E402
    ProviderFrameworkError, ProviderRunRequest, ProviderValidationError,
)
from eagleeye.infrastructure.providers.adapters import default_adapters  # noqa: E402
from eagleeye.infrastructure.providers.transport import UrllibPublicTransport  # noqa: E402

#: Unkritische Testbegriffe; je Quelle wird der erste genommen, den sie annimmt.
TEST_QUERIES = (
    "Albert Einstein", "benutzername: github", "github", "email: test@example.com", "Deutsche Bahn",
    "firma: Airbus", "example.org", "https://example.org/", "url: https://example.org/", "ort: Berlin", "Berlin",
    "Klimawandel", "CC-MAIN-2024-10 https://example.org/", "5299000J2N45DDNE4Y28", "10.1038/nature12373",
)
PURPOSE = "Erreichbarkeitsprüfung mit unkritischem Testbegriff"


def _query_for(adapter) -> str | None:
    for query in TEST_QUERIES:
        try:
            adapter.validate_request(ProviderRunRequest("quellenpruefung", adapter.definition.provider_key, query, PURPOSE, "pruefung"))
            if adapter.build_requests(ProviderRunRequest("quellenpruefung", adapter.definition.provider_key, query, PURPOSE, "pruefung")):
                return query
        except (ProviderFrameworkError, ValueError):
            continue
    return None


def check(adapter, transport) -> dict:
    d = adapter.definition
    row = {"key": d.provider_key, "label": d.label, "hosts": ", ".join(d.allowed_hosts) or "–"}
    if not d.enabled or not d.supports_live:
        return {**row, "state": "aus", "detail": "in dieser Installation nicht für Live-Abfragen freigeschaltet"}
    query = _query_for(adapter)
    if query is None:
        return {**row, "state": "nicht prüfbar", "detail": "kein passender Testbegriff (Quelle braucht eine besondere Eingabe)"}
    first = adapter.build_requests(ProviderRunRequest("quellenpruefung", d.provider_key, query, PURPOSE, "pruefung"))[0]
    started = time.monotonic()
    try:
        response = transport.fetch(first, allowed_hosts=d.allowed_hosts, timeout_seconds=min(d.timeout_seconds, 20.0),
                                   max_response_bytes=d.max_response_bytes)
    except ProviderValidationError as exc:
        if "DNS resolution failed" in str(exc):
            return {**row, "state": "nicht erreichbar", "query": query,
                    "detail": "Name der Quelle lässt sich nicht auflösen (keine Internetverbindung, Proxy oder Firewall)"}
        return {**row, "state": "gesperrt", "query": query, "detail": "Sicherheitsprüfung verweigert den Abruf (Details nur im geschützten Diagnoseprotokoll)"}
    except (ProviderFrameworkError, OSError) as exc:
        return {**row, "state": "nicht erreichbar", "query": query, "detail": f"{type(exc).__name__} beim Abruf (keine URLs oder Zugangsdaten im Bericht)"}
    ms = int((time.monotonic() - started) * 1000)
    status = response.status_code
    if status in (401, 403):
        return {**row, "state": "abgewiesen", "query": query, "detail": f"HTTP {status} – Quelle verlangt Anmeldung oder sperrt diesen Zugang"}
    if 200 <= status < 300 or (400 <= status < 500 and status not in (429,) and d.metadata.get("http_4xx_is_result")):
        return {**row, "state": "antwortet", "query": query, "detail": f"HTTP {status} · {ms} ms"}
    if status == 429:
        return {**row, "state": "gebremst", "query": query, "detail": "HTTP 429 – Abfragegrenze der Quelle, später erneut prüfen"}
    return {**row, "state": "Fehler", "query": query, "detail": f"HTTP {status}"}


def report(rows: list[dict]) -> str:
    order = {"antwortet": 0, "gebremst": 1, "abgewiesen": 2, "nicht erreichbar": 3, "Fehler": 4, "gesperrt": 5, "nicht prüfbar": 6, "aus": 7}
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    lines = ["# Quellen der EagleEye-Fallakte – Prüfbericht", "",
             f"Geprüft am {datetime.now():%d.%m.%Y %H:%M} · {len(rows)} Quellen · " +
             " · ".join(f"{n} {s}" for s, n in sorted(counts.items(), key=lambda kv: order.get(kv[0], 9))), "",
             "Je Quelle eine unkritische Testabfrage. „antwortet“ heißt: Der Endpunkt reagiert (auch 404 bei Existenzabfragen), nicht dass die Live-Recherche funktioniert. "
             "„nicht erreichbar“ liegt oft an Firewall, Proxy oder Virenschutz dieses Rechners – nicht unbedingt an der Quelle.", "",
             "| Quelle | Ergebnis | Einzelheiten | Testbegriff | Adressen |", "|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: (order.get(r["state"], 9), r["label"].casefold())):
        cells = [r["label"], r["state"], r["detail"], r.get("query", "–"), r["hosts"]]
        lines.append("| " + " | ".join(c.replace("|", "/") for c in cells) + " |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Erreichbarkeit der Fallakten-Quellen prüfen")
    parser.add_argument("--out", help="Prüfbericht als Markdown-Datei speichern")
    parser.add_argument("--only", help="nur Quellen, deren Schlüssel diesen Text enthält")
    args = parser.parse_args(argv)
    transport = UrllibPublicTransport()
    adapters = [a for a in default_adapters() if not args.only or args.only in a.definition.provider_key]
    print(f"Prüfe {len(adapters)} Quellen der Fallakte (je eine Testabfrage) …")
    with ThreadPoolExecutor(max_workers=6) as pool:
        rows = list(pool.map(lambda a: check(a, transport), adapters))
    for r in sorted(rows, key=lambda r: r["label"].casefold()):
        mark = {"antwortet": "✓", "gebremst": "~", "nicht prüfbar": "–", "aus": "–"}.get(r["state"], "✗")
        print(f"  {mark} {r['label'][:52]:52} {r['state']}: {r['detail']}")
    ok = sum(1 for r in rows if r["state"] == "antwortet")
    print(f"Ergebnis: {ok} von {len(rows)} Quellen antworten.")
    if args.out:
        Path(args.out).write_text(report(rows), encoding="utf-8")
        print(f"Prüfbericht gespeichert: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
