"""Live check with real internet and a real Tor service (GitHub runner): TED, Darknet, sources.

    python tools/live_probe.py ted|darknet

Exit code 1 when the checked function does not work against the real service.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from eagleeye.application import ted  # noqa: E402
from eagleeye.application.darknet import service as darknet  # noqa: E402
from eagleeye.application.darknet import tor  # noqa: E402
from eagleeye.application.intel492 import webcapture  # noqa: E402

TORPROJECT = "2gzyxa5ihm7nsggfxnu52rck2vv4rvmdlkiu3zzui5du4xyclen53wid.onion"


def probe_ted() -> int:
    ok = True
    cases = [("Siemens", "gewinner", "DEU", "2025-01-01", ""), ("Deutsche Bahn", "auftraggeber", "", "2025-06-01", ""),
             ("Bundeswehr", "alle", "DEU", "2025-10-01", "")]
    for term, role, country, start, end in cases:
        query = ted.build_query(term, role=role, country=country, date_from=start, date_to=end)
        body = {"query": query, "fields": ted.FIELDS + ted.VALUE_FIELDS, "page": 1, "limit": 5, "scope": "ALL",
                "paginationMode": "PAGE_NUMBER"}
        try:
            data = ted._post(body)
            value_fields = True
        except ted.TedError as exc:
            print(f"  mit Wertfeldern abgelehnt: {str(exc)[:300]}")
            body["fields"] = ted.FIELDS
            try:
                data = ted._post(body)
                value_fields = False
            except ted.TedError as exc2:
                print(f"✗ TED {role} „{term}“: {exc2}")
                ok = False
                continue
        notices = [ted.parse_notice(n) for n in data.get("notices", [])]
        print(f"✓ TED {role:12s} „{term}“ {country}: {data.get('totalNoticeCount')} Bekanntmachungen, Wertfelder {'ja' if value_fields else 'nein'}")
        for n in notices[:2]:
            print("    ", json.dumps(n, ensure_ascii=False)[:400])
        if data.get("notices"):
            print("     Rohfelder:", sorted(data["notices"][0].keys()))
        if not notices:
            ok = False
    return 0 if ok else 1


def probe_darknet() -> int:
    local = tor.probe()
    print(("✓ " if local["ok"] else "✗ ") + local["detail"])
    if not local["ok"]:
        return 1
    channel = tor.TorTransport(isolation="live-probe")
    started = time.monotonic()
    home = channel.get(f"http://{darknet.AHMIA_ONION}/")
    fields = darknet.search_form_fields(home.body.decode("utf-8", "replace"))
    print(f"✓ Ahmia über Tor: HTTP {home.status} in {time.monotonic() - started:.1f} s, versteckte Formularfelder: {[k for k, _ in fields]}")
    total = 0
    for term in ("privacy", "news"):
        url = f"http://{darknet.AHMIA_ONION}/search/?q={term}" + "".join(f"&{k}={v}" for k, v in fields)
        page = channel.get(url)
        results = darknet.parse_results(page.body.decode("utf-8", "replace"), f"http://{darknet.AHMIA_ONION}/")
        total += len(results)
        print(f"{'✓' if results else '✗'} Ahmia-Suche „{term}“: HTTP {page.status}, {len(results)} gültige v3-Treffer")
        for r in results[:3]:
            print("    ", r["title"][:70], "|", r["url"][:90])
        if not results:
            print("     Seitenanfang:", page.body[:1500].decode("utf-8", "replace").replace("\n", " ")[:1500])
    result = webcapture.capture(f"http://{TORPROJECT}/", transport=tor.TorTransport(isolation="live-probe-2"),
                                kind="Darknet-Seite (Tor)", normalize=tor.normalize_onion_url, allow_pdf=False)
    if result.get("redirect"):
        print(f"  Tor Project leitet weiter nach {result.get('location')}")
        result = webcapture.capture(result["location"], transport=tor.TorTransport(isolation="live-probe-2"),
                                    kind="Darknet-Seite (Tor)", normalize=tor.normalize_onion_url, allow_pdf=False)
    print(f"✓ Onion-Seite gesichert: „{result['title']}“, {len(result['warc'])} Bytes WARC, SHA-256 {result['body_sha256'][:16]}…, {result['ip_address']}")
    return 0 if total else 1


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "ted"
    sys.exit({"ted": probe_ted, "darknet": probe_darknet}[which]())
