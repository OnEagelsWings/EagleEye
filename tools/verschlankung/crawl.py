"""Walk the running Fallakte like a logged-in user: follow every link (GET) reachable from the menu, collect forms."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import deque
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlsplit, parse_qsl, urlencode

sys.path[:0] = ["src", ".", "PersonOSINT", "tests"]
OUT = Path(sys.argv[1])
BASE = Path(sys.argv[2])

from fastapi.testclient import TestClient
from starlette.routing import Match

from eagleeye.interfaces.web.app500 import create_workspace_app500
from eagleeye.interfaces.web.app364 import CSRF_COOKIE
from eagleeye.interfaces.web import operations476

app = create_workspace_app500(base_dir=BASE)
ctx = app.state.context
COOKIE = None
for name in dir(sys.modules["eagleeye.interfaces.web.app364"]):
    if name == "COOKIE":
        COOKIE = getattr(sys.modules["eagleeye.interfaces.web.app364"], name)
if COOKIE is None:
    from test_build471_local_ai import COOKIE  # type: ignore
ctx.team_identity_359.create_initial_admin(username="qa471", display_name="QA", password="Build471!Password_88")
fp = hashlib.sha256(b"testclient||testclient").hexdigest()
session = ctx.team_identity_359.authenticate(username="qa471", password="Build471!Password_88", client_fingerprint=fp)
user = ctx.team_identity_359.validate_session(session.token, client_fingerprint=fp, touch=False)
case = ctx.team_governance_359.create_case(identity=user, title="Crawl case", client="QA", purpose="Synthetic crawl", legal_basis="public_data")
case_id = case["case_id"]
ctx.document_intelligence_458.import_bytes(identity=user, case_id=case_id, filename="source.txt",
    raw=b"Die Beispiel GmbH wurde 2001 gegruendet. Max Mustermann ist Geschaeftsfuehrer.", title="Quelle", source_url="https://example.org/q")

loaded_before = {n for n in sys.modules if n.split(".")[0] in ("eagleeye", "eagleeye_pro", "personosint")}

starts = ["/", "/buero", "/workbench", "/workbench?case_id=" + case_id]
for entry in operations476.MENU:
    path = entry[2]
    starts.append(path)
    starts.append(path + ("&" if "?" in path else "?") + "case_id=" + case_id)

SKIP = re.compile(r"/(logout|abmelden)\b|\.(zip|pdf|png|warc|gz|csv|json|gexf|xlsx|docx)(\?|$)|/download|/export", re.I)
seen, visited, forms, status, downloads = set(), [], set(), {}, set()
queue = deque()
for s in starts:
    queue.append(s)
with TestClient(app) as client:
    client.cookies.set(COOKIE, session.token)
    client.cookies.set(CSRF_COOKIE, session.csrf_token)
    while queue and len(visited) < 4000:
        url = queue.popleft()
        parts = urlsplit(url)
        # normalise: keep only case_id among query parameters to avoid infinite variants
        query = [(k, v) for k, v in parse_qsl(parts.query) if k in ("case_id",)]
        key = parts.path + ("?" + urlencode(query) if query else "")
        if SKIP.search(parts.path):
            downloads.add(parts.path)
            continue
        if key in seen:
            continue
        seen.add(key)
        try:
            r = client.get(url, follow_redirects=True)
        except Exception as exc:  # noqa: BLE001
            status[key] = "EXC " + type(exc).__name__
            continue
        status[key] = r.status_code
        visited.append(key)
        if "text/html" not in r.headers.get("content-type", ""):
            continue
        for href in re.findall(r'href="([^"]+)"', r.text):
            href = unescape(href)
            if href.startswith(("http://testserver", "/")) and not href.startswith("//"):
                queue.append(urljoin("http://testserver" + url, href).replace("http://testserver", ""))
        for src in re.findall(r'<script[^>]+src="([^"]+)"', r.text):
            downloads.add(urlsplit(unescape(src)).path)
        for action, method in re.findall(r'<form[^>]*action="([^"]*)"[^>]*?(?:method="(\w+)")?', r.text, re.I):
            forms.add(((method or "get").upper(), urlsplit(unescape(action)).path or parts.path))
        for method, action in re.findall(r'<form[^>]*method="(\w+)"[^>]*action="([^"]*)"', r.text, re.I):
            forms.add((method.upper(), urlsplit(unescape(action)).path or parts.path))

loaded_after = {n for n in sys.modules if n.split(".")[0] in ("eagleeye", "eagleeye_pro", "personosint")}


def route_for(method, path):
    scope = {"type": "http", "path": path, "method": method, "root_path": "", "query_string": b"", "headers": []}
    for route in app.routes:
        match, _ = route.matches(scope)
        if match == Match.FULL:
            return route
    return None


routes = [r for r in app.routes if hasattr(r, "methods")]
hit = set()
for key in visited:
    r = route_for("GET", urlsplit(key).path)
    if r is not None:
        hit.add(id(r))
for path in downloads:
    r = route_for("GET", path)
    if r is not None:
        hit.add(id(r))
form_hit = set()
for method, path in forms:
    r = route_for(method if method in ("GET", "POST") else "POST", path)
    if r is not None:
        form_hit.add(id(r))

# shadowed: same path + method registered more than once -> only the first one can ever answer
first = {}
shadowed = []
for r in routes:
    for m in r.methods:
        k = (m, r.path)
        if k in first:
            shadowed.append((m, r.path, r.endpoint.__module__, first[k]))
        else:
            first[k] = r.endpoint.__module__

report = {
    "pages_visited": len(visited),
    "status_errors": {k: v for k, v in status.items() if v != 200},
    "routes_total": len(routes),
    "routes_reached_by_links": len(hit),
    "routes_reached_by_forms_only": len(form_hit - hit),
    "routes": [{"path": r.path, "methods": sorted(r.methods), "module": r.endpoint.__module__, "name": r.endpoint.__qualname__,
                "link": id(r) in hit, "form": id(r) in form_hit} for r in routes],
    "shadowed": shadowed,
    "modules_loaded_by_crawl": sorted(loaded_after - loaded_before),
    "modules_loaded_total": sorted(loaded_after),
    "visited": visited,
}
OUT.write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
print("Seiten besucht", len(visited), "Fehlerseiten", len(report["status_errors"]))
print("Routen", len(routes), "per Link erreicht", len(hit), "nur per Formular", len(form_hit - hit))
print("verdeckte Routen (nie erreichbar)", len(shadowed))
print("Module zusaetzlich geladen durch Klicken", len(loaded_after - loaded_before), "gesamt", len(loaded_after))
