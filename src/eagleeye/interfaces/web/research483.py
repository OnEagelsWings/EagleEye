"""Build 483 – case-scoped handoff from public Dork/search links to manually verified sources.

A proposed URL is ONLY a lead. No network access, hidden harvesting,
automatic evidence, or identity inference takes place here.
"""
from __future__ import annotations
import hashlib
import ipaddress
import idna
import re
import json
import secrets
from datetime import datetime, timezone
from html import escape
from urllib.parse import urlsplit, urlencode

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .app364 import CSRF_COOKIE
from .findings478 import bounded_form, verify_post
from .operations476 import case_access, page

MAX_LEADS = 250

def validate_public_lead_url(value):
    raw = str(value or "").strip()
    if not 12 <= len(raw) <= 1800 or any(ord(c) < 32 or ord(c) == 127 for c in raw):
        raise HTTPException(422, "Gültige öffentliche HTTPS-Adresse angeben (max. 1800 Zeichen).")
    try:
        url = urlsplit(raw)
        # Canonicalize IDNA before stripping the terminal dot: Unicode dot
        # equivalents (U+3002, U+FF0E, U+FF61) normalize to ASCII dots.
        host = idna.encode(url.hostname or "", uts46=True, transitional=False).decode("ascii").rstrip(".").lower()
        port = url.port
    except (ValueError, idna.IDNAError, UnicodeError):
        raise HTTPException(422, "Ungültige URL.") from None
    if url.scheme != "https" or not host or url.username or url.password or port not in (None, 443):
        raise HTTPException(422, "Nur öffentliche HTTPS-Adressen ohne Zugangsdaten/Portangaben.")
    if (not "." in host or host.endswith((".local", ".localhost", ".internal", ".test", ".invalid", ".onion"))
        or host in ("localhost", "metadata.google.internal")
        or any(x in host for x in ("\\", "%", " ", "\t", "\n"))
        or host.startswith("-") or ".." in host):
        raise HTTPException(422, "Lokale oder ungültige Zieladresse.")
    # WHATWG browser URL parsing resolves numeric IPv4 variants such as
    # 127.1, 0177.0.0.1 and 0x7f.0.0.1 to the loopback address.
    # Reject numeric host labels, including bare 0x (WHATWG treats it as zero),\n    # rather than trusting Python ipaddress alone.
    labels=host.split(".")
    if labels and all(re.fullmatch(r"(?:0[xX][0-9A-Fa-f]*|[0-9]+)",part)
                      for part in labels):
        raise HTTPException(422,"IP-ähnliche numerische Hosts sind nicht erlaubt.")
    try:
        ipaddress.ip_address(host.strip("[]"))
        raise HTTPException(422, "IP-Adressen und interne Ziele sind hier nicht zulässig.")
    except ValueError:
        pass
    # No network request and thus no DNS resolution: the later crawler must
    # independently validate resolved IPs, redirects and actual connected peer.
    return raw

def _init(ctx):
    ctx.db.conn.execute("""CREATE TABLE IF NOT EXISTS research_leads_483(
        lead_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,
        url TEXT NOT NULL,title TEXT NOT NULL,analyst_note TEXT NOT NULL,
        review_state TEXT NOT NULL,created_by TEXT NOT NULL,
        created_at TEXT NOT NULL,record_hash TEXT NOT NULL,
        UNIQUE(case_id,url)
    )""")
    ctx.db.conn.execute(
        "CREATE INDEX IF NOT EXISTS research_leads483_case ON research_leads_483(case_id,created_at)"
    )
    ctx.db.conn.commit()

def _digest(row):
    return hashlib.sha256(json.dumps(
        {k: v for k,v in row.items() if k != "record_hash"},
        sort_keys=True,ensure_ascii=False,separators=(",",":")
    ).encode("utf-8")).hexdigest()

def listed(ctx,case_id):
    records=ctx.db.all(
        "SELECT * FROM research_leads_483 WHERE case_id=? ORDER BY created_at DESC LIMIT ?",
        (case_id,MAX_LEADS)
    )
    for x in records:
        if x["record_hash"]!=_digest(x):
            raise HTTPException(409,"Quellen-Fundliste wurde verändert.")
    return records

def propose(ctx,user,case_id,url,title,note):
    url=validate_public_lead_url(url)
    title=" ".join(str(title or "").split())
    note=" ".join(str(note or "").split())
    if not (4<=len(title)<=240 and 15<=len(note)<=1600):
        raise HTTPException(422,"Titel (4–240 Zeichen) und Herkunftsbegründung (15–1600 Zeichen) erforderlich.")
    with ctx.audit.actor_scope(user["username"]),ctx.db.transaction(immediate=True):
        existing=ctx.db.one("SELECT * FROM research_leads_483 WHERE case_id=? AND url=?", (case_id,url))
        if existing:
            if existing["record_hash"]!=_digest(existing):
                raise HTTPException(409,"Bestehender Fundlisten-Eintrag ist beschädigt.")
            return existing
        count=ctx.db.one("SELECT count(*) n FROM research_leads_483 WHERE case_id=?",(case_id,))["n"]
        if count>=MAX_LEADS:raise HTTPException(409,"Maximal 250 offene Suchhinweise je Fall.")
        row={
            "lead_id":"lead483_"+secrets.token_hex(12),
            "case_id":case_id,"url":url,"title":title,"analyst_note":note,
            "review_state":"unverified_lead","created_by":user["username"],
            "created_at":datetime.now(timezone.utc).isoformat()
        }
        row["record_hash"]=_digest(row)
        cols=list(row)
        ctx.db.execute(
            "INSERT INTO research_leads_483("+",".join(cols)+") VALUES("+",".join("?" for _ in cols)+")",
            [row[k] for k in cols]
        )
        # Intentionally do not create acquisition events or Evidence.
        ctx.audit.log("public_search_lead_proposed_483","research_leads_483",row["lead_id"],
                      case_id,{"url_sha256":hashlib.sha256(url.encode()).hexdigest(),
                               "verified":False,"network_fetch":False})
        return row

def attach_research483(app,build):
    ctx=app.state.context
    _init(ctx)

    @app.get("/workbench/leads483",response_class=HTMLResponse)
    def get_leads(request:Request,case_id:str=""):
        user,case=case_access(app,request,case_id)
        rows=listed(ctx,case_id)
        lead_actions=getattr(app.state,'lead_actions',None)  # later builds: capture as web evidence
        actions=lead_actions(request,user,case_id,rows) if lead_actions else {}
        form=(
            '<section class="card"><h2>1. Öffentlichen Treffer als Suchhinweis aufnehmen</h2>'
            '<p>Recherchelink zuerst im Browser öffnen und Herkunft beurteilen. '
            'Dieser Schritt sichert <strong>noch keinen Originalbeleg</strong>.</p>'
            '<form action="/workbench/leads483" method="post">'
            '<input type="hidden" name="case_id" value="'+escape(case_id,quote=True)+'">'
            '<input type="hidden" name="csrf" value="'+escape(request.cookies.get(CSRF_COOKIE,""),quote=True)+'">'
            '<label for="lead483-url">Öffentliche HTTPS-URL</label><input id="lead483-url" required type="url" name="url" maxlength="1800">'
            '<label for="lead483-title">Seitentitel oder Befundthema</label><input id="lead483-title" required name="title" maxlength="240">'
            '<label for="lead483-note">Woher stammt der Link? Warum ist er relevant?</label>'
            '<textarea id="lead483-note" required name="note" maxlength="1600" rows="3"></textarea>'
            '<button type="submit">Als ungeprüften Suchhinweis speichern</button></form></section>'
        )
        entries="".join(
            '<section class="card"><h3>'+escape(x["title"])+'</h3>'
            '<p><strong>Ungeprüfter Suchhinweis – keine Evidence</strong></p>'
            '<p><a target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer" href="'+
            escape(x["url"],quote=True)+'">Originaladresse im Browser prüfen</a></p>'
            '<p>'+escape(x["analyst_note"])+'</p>'
            '<p>Erfasst von '+escape(x["created_by"])+' am '+escape(x["created_at"])+'</p>'+
            actions.get(x["lead_id"],"")+'</section>'
            for x in rows
        )
        body=('<p>Fall: <strong>'+escape(str(case.get("title") or ""))+'</strong> · '+
              str(len(rows))+' Suchhinweise.</p>'
              '<p class="warn">Die URL ist ein Recherchehinweis. Eine belastbare Quelle entsteht '
              'erst durch rechtmäßigen Abruf, gesicherte Originalbytes, Hash und Prüfung. '
              'Externe Seiten dürfen den Zugriff protokollieren.</p>'+form+
              '<h2>2. Ungeprüfte Recherchefunde</h2>'+(entries or
              '<p>Noch keine Treffer aufgenommen.</p>')+
              '<p><a href="/workbench/dorks482?'+escape(urlencode({"case_id":case_id}),quote=True)+
              '">Dork-Suchstrategie öffnen</a> · <a href="/documents458?'+
              escape(urlencode({"case_id":case_id}),quote=True)+
              '">Geprüften Originalbeleg importieren</a></p>')
        return HTMLResponse(page("Recherchefunde – fallbezogene Suchhinweise",case_id,body,build),
                            headers={"Cache-Control":"no-store","Referrer-Policy":"no-referrer"})

    @app.post("/workbench/leads483")
    async def add_lead(request:Request):
        form=await bounded_form(request,max_bytes=6500)
        cid=str(form.get("case_id") or "")
        user,_case=case_access(app,request,cid,capability="research.run")
        verify_post(app,request,user,form.get("csrf",""))
        propose(ctx,user,cid,form.get("url"),form.get("title"),form.get("note"))
        return RedirectResponse("/workbench/leads483?"+urlencode({"case_id":cid}),status_code=303)
