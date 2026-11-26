import sys, json, re, hashlib
sys.path[:0] = ["src", ".", "PersonOSINT", "tests"]
from pathlib import Path
from fastapi.testclient import TestClient
from eagleeye.interfaces.web.app500 import create_workspace_app500
from eagleeye.interfaces.web.app364 import CSRF_COOKIE
from test_build471_local_ai import COOKIE
app = create_workspace_app500(base_dir=Path(sys.argv[2]))
ctx = app.state.context
ctx.team_identity_359.create_initial_admin(username="qa471", display_name="QA", password="Build471!Password_88")
fp = hashlib.sha256(b"testclient||testclient").hexdigest()
s = ctx.team_identity_359.authenticate(username="qa471", password="Build471!Password_88", client_fingerprint=fp)
u = ctx.team_identity_359.validate_session(s.token, client_fingerprint=fp, touch=False)
case = ctx.team_governance_359.create_case(identity=u, title="T", client="QA", purpose="Synthetic crawl", legal_basis="public_data")["case_id"]
crawl = json.load(open(sys.argv[1]))
hidden = [r for r in crawl["routes"] if not r["link"] and not r["form"] and "GET" in r["methods"] and not r["path"].startswith(("/api", "/assets"))]
out = []
with TestClient(app) as c:
    c.cookies.set(COOKIE, s.token); c.cookies.set(CSRF_COOKIE, s.csrf_token)
    for r in hidden:
        path = r["path"].replace("{case_id}", case)
        if "{" in path: out.append((r["path"], r["module"], "Parameter nötig", "")); continue
        try:
            resp = c.get(path, params={"case_id": case}, follow_redirects=True)
            t = re.search(r"<title>(.*?)</title>", resp.text or "", re.S); h = re.search(r"<h1[^>]*>(.*?)</h1>", resp.text or "", re.S)
            out.append((r["path"], r["module"].rsplit(".",1)[-1], resp.status_code, re.sub("<[^>]+>", "", (h or t).group(1)).strip()[:90] if (h or t) else resp.headers.get("content-type","")))
        except Exception as e:
            out.append((r["path"], r["module"], "EXC", type(e).__name__))
for row in out: print(" | ".join(map(str, row)))
