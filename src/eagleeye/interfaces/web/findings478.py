"""Source-anchored human research notes; NOT confirmed claims or approved dossiers."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .operations476 import case_access, page
from .app364 import CSRF_COOKIE


@contextmanager
def notes_db(app):
    root = Path(app.state.base_dir).resolve()
    path = root / "data" / "operational_notes_478.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    created = not path.exists()
    conn = sqlite3.connect(str(path), timeout=8.0)
    conn.row_factory = sqlite3.Row
    try:
        if created and os.name != "nt":
            path.chmod(0o600)
        conn.execute("""CREATE TABLE IF NOT EXISTS operational_findings_478(
            finding_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, document_id TEXT NOT NULL,
            anchor_id TEXT NOT NULL, title TEXT NOT NULL, interpretation TEXT NOT NULL,
            source_excerpt TEXT NOT NULL, document_sha256 TEXT NOT NULL,
            source_url TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
            review_state TEXT NOT NULL DEFAULT 'unreviewed',
            review_reason TEXT NOT NULL DEFAULT '', reviewed_by TEXT NOT NULL DEFAULT ''
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS notes_478_case_idx ON operational_findings_478(case_id,created_at)")
        yield conn
        conn.commit()
    finally:
        conn.close()


def notes_for_case(app,case_id):
    with notes_db(app) as conn:
        rows=conn.execute("SELECT * FROM operational_findings_478 WHERE case_id=? ORDER BY created_at DESC LIMIT 250",
                          (case_id,)).fetchall()
        return [dict(r) for r in rows]


def verify_post(app,request,user,submitted):
    csrf = request.cookies.get(CSRF_COOKIE,"")
    if not csrf or not hmac.compare_digest(str(csrf),str(submitted or "")) or not app.state.context.team_identity_359.csrf_token_valid(user,csrf):
        raise HTTPException(403,"Ungültiger Formularschutz. Seite neu öffnen.")
    site=(request.headers.get("sec-fetch-site") or "").lower()
    if site not in ("","same-origin","none"):
        raise HTTPException(403,"Formular kommt nicht von EagleEye.")
    origin=request.headers.get("origin","")
    if origin:
        parsed=urlsplit(origin)
        if parsed.scheme not in ("http","https") or parsed.netloc != request.headers.get("host"):
            raise HTTPException(403,"Fremder Formularursprung ist nicht erlaubt.")


def get_anchor(ctx,user,case_id,document_id,anchor_id):
    docs=ctx.document_intelligence_458.documents(identity=user,case_id=case_id)
    doc=next((r for r in docs if str(r["document_id"])==document_id),None)
    if doc is None:
        raise HTTPException(403,"Dokument gehört nicht zu diesem Fall.")
    data=ctx.document_intelligence_458.anchors(identity=user,document_id=document_id)
    if str(data["document"].get("case_id"))!=case_id:
        raise HTTPException(403,"Quellenfall stimmt nicht überein.")
    anchor=next((a for a in data.get("anchors",[]) if str(a.get("anchor_id"))==anchor_id),None)
    if anchor is None:
        raise HTTPException(422,"Anker nicht vorhanden; bitte neu auswählen.")
    return doc, data["document"], anchor


def attach_findings(app,build):
    ctx=app.state.context

    @app.get("/workbench/findings",response_class=HTMLResponse)
    def findings_view(request:Request,case_id:str=""):
        user,case=case_access(app,request,case_id)
        docs=ctx.document_intelligence_458.documents(identity=user,case_id=case_id)
        choices=[]
        for doc in docs[:40]:
            try:
                data=ctx.document_intelligence_458.anchors(identity=user,document_id=str(doc["document_id"]))
            except (KeyError, ValueError):
                continue
            if str(data["document"].get("case_id"))!=case_id:
                continue
            for anchor in data.get("anchors",[])[:50]:
                ref=str(doc["document_id"])+"|"+str(anchor.get("anchor_id",""))
                label=str(doc.get("title","Dokument"))+" – Seite "+str(anchor.get("page_number","?"))+" – "+str(anchor.get("text_excerpt",""))[:110]
                choices.append('<option value="'+escape(ref,quote=True)+'">'+escape(label)+'</option>')
        token=request.cookies.get(CSRF_COOKIE,"")
        form = ('<section class="card"><h2>Neue Beobachtung / Hypothese</h2>'
                '<p>Wähle eine echte Originalfundstelle; interpretiere sie ausdrücklich als unbestätigten Arbeitsbefund.</p>'
                '<form method="post" action="/workbench/findings">'
                '<input type="hidden" name="case_id" value="'+escape(case_id,quote=True)+'">'
                '<input type="hidden" name="csrf" value="'+escape(token,quote=True)+'">'
                '<label>Fundstelle / Originalzitat</label><select name="anchor_ref" required>'
                +("".join(choices) or '<option value="">Erst ein Dokument mit lesbarer Textstelle importieren</option>')
                +'</select><label>Kurzbezeichnung</label><input name="title" required maxlength="180">'
                '<label>Eigene Beobachtung (Hypothese, Unsicherheit, Gegenbelege benennen)</label>'
                '<textarea name="interpretation" required minlength="10" maxlength="2400" rows="5"></textarea>'
                '<button type="submit">Mit Quelle als Arbeitsbefund speichern</button></form></section>')
        rows=notes_for_case(app,case_id)
        items="".join('<article class="card"><h2>'+escape(r["title"])+'</h2><p>'
            +escape(r["interpretation"])+'</p><blockquote>'+escape(r["source_excerpt"][:1200])
            +'</blockquote><small>Quelle '+escape(r["document_id"])+' / Anker '+escape(r["anchor_id"])
            +' · Stand: '+escape(r["review_state"])+' · Verfasst: '+escape(r["created_by"])+'</small></article>'
            for r in rows)
        body='<p>Fall: '+escape(str(case.get("title","")))+' · '+str(len(rows))+' angezeigte Arbeitsbefunde. Kein KI-Faktentransfer.</p>'
        body+=form+(items or '<p>Noch keine Arbeitsbefunde vorhanden.</p>')
        return HTMLResponse(page("Quellengebundene Arbeitsbefunde",case_id,body,build),
                            headers={"Cache-Control":"no-store"})

    @app.post("/workbench/findings")
    async def add_finding(request:Request):
        if int(request.headers.get("content-length","0") or 0)>16000:
            raise HTTPException(413,"Formular zu groß.")
        form=await request.form(max_fields=8,max_files=0)
        case_id=str(form.get("case_id",""))
        user,_case=case_access(app,request,case_id,"research.run")
        verify_post(app,request,user,form.get("csrf",""))
        ref=str(form.get("anchor_ref",""))
        doc_id,separator,anchor_id=ref.partition("|")
        if not separator or not doc_id or not anchor_id:
            raise HTTPException(422,"Bitte eine Originalfundstelle auswählen.")
        title=str(form.get("title","")).strip()
        interpretation=str(form.get("interpretation","")).strip()
        if not (4<=len(title)<=180 and 10<=len(interpretation)<=2400):
            raise HTTPException(422,"Titel oder Interpretation fehlt oder ist zu lang.")
        doc,source,anchor=get_anchor(ctx,user,case_id,doc_id,anchor_id)
        excerpt=str(anchor.get("text_excerpt") or "")
        digest=str(source.get("document_sha256") or "")
        if not excerpt.strip() or len(digest)!=64:
            raise HTTPException(422,"Originaltext oder Integritätsnachweis fehlt.")
        entry=(secrets.token_hex(16),case_id,doc_id,anchor_id,title,interpretation,
               excerpt[:6000],digest,str(doc.get("source_url") or ""),str(user["username"]),
               datetime.now(timezone.utc).isoformat())
        with notes_db(app) as conn:
            conn.execute("""INSERT INTO operational_findings_478
                (finding_id,case_id,document_id,anchor_id,title,interpretation,
                 source_excerpt,document_sha256,source_url,created_by,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",entry)
        return RedirectResponse("/workbench/findings?"+urlencode({"case_id":case_id}),status_code=303)
