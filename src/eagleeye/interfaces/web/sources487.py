"""Human-attributed case links between unverified web leads and verified local originals.

Never asserts URL origin, performs a fetch, or creates/accepts Evidence or Claims.
"""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from html import escape
from urllib.parse import urlencode
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from .app364 import CSRF_COOKIE
from .bridge481 import _reviewed_bytes
from .findings478 import bounded_form, verify_post
from .operations476 import case_access, page
from .research483 import listed


def _hash(row):
    return hashlib.sha256(json.dumps(
        {k: v for k, v in row.items() if k != "record_hash"},
        sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def _init(ctx):
    ctx.db.conn.execute("""CREATE TABLE IF NOT EXISTS lead_original_links_487(
        case_id TEXT NOT NULL, lead_id TEXT NOT NULL, document_id TEXT NOT NULL,
        lead_record_hash TEXT NOT NULL, document_record_hash TEXT NOT NULL,
        original_sha256 TEXT NOT NULL, url_sha256 TEXT NOT NULL,
        rationale TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
        record_hash TEXT NOT NULL, PRIMARY KEY(case_id,lead_id,document_id)
    )""")
    ctx.db.conn.execute("CREATE INDEX IF NOT EXISTS source487_case ON lead_original_links_487(case_id)")
    ctx.db.conn.commit()


def source_links(ctx, user, case_id):
    leads = {x["lead_id"]: x for x in listed(ctx, case_id)}
    rows = [dict(x) for x in ctx.db.all(
        "SELECT * FROM lead_original_links_487 WHERE case_id=? ORDER BY created_at", (case_id,)
    )]
    for row in rows:
        lead = leads.get(row["lead_id"])
        if row["record_hash"] != _hash(row) or not lead or lead["record_hash"] != row["lead_record_hash"]:
            raise HTTPException(409, "Quellenzuordnung oder Suchhinweis verändert.")
        doc, _raw, _anchors = _reviewed_bytes(ctx, user, case_id, row["document_id"])
        if (doc["record_hash"] != row["document_record_hash"]
                or doc["document_sha256"] != row["original_sha256"]
                or hashlib.sha256(lead["url"].encode("utf-8")).hexdigest() != row["url_sha256"]):
            raise HTTPException(409, "Original oder Herkunftszuordnung verändert.")
    return rows


def associate(ctx, user, case_id, lead_id, document_id, rationale):
    rationale = " ".join(str(rationale or "").split())
    if not 20 <= len(rationale) <= 1200:
        raise HTTPException(422, "Begründung der Quellenzuordnung (20–1200 Zeichen) erforderlich.")
    ctx.team_governance_359.authorize(
        user, case_id=case_id, capability="research.run",
        object_type="operational_case", object_id=case_id
    )
    with ctx.audit.actor_scope(user["username"]), ctx.db.transaction(immediate=True):
        lead = next((x for x in listed(ctx, case_id) if x["lead_id"] == lead_id), None)
        if not lead:
            raise HTTPException(404, "Kein fallzugehöriger Suchhinweis.")
        doc, _raw, _anchors = _reviewed_bytes(ctx, user, case_id, document_id)
        existing = ctx.db.one(
            "SELECT * FROM lead_original_links_487 WHERE case_id=? AND lead_id=? AND document_id=?",
            (case_id, lead_id, document_id)
        )
        if existing:
            row = dict(existing)
            if (row["record_hash"] != _hash(row) or row["lead_record_hash"] != lead["record_hash"]
                    or row["document_record_hash"] != doc["record_hash"]
                    or row["original_sha256"] != doc["document_sha256"]):
                raise HTTPException(409, "Bestehende Quellenzuordnung ist nicht integer.")
            return row
        row = {
            "case_id": case_id, "lead_id": lead_id, "document_id": document_id,
            "lead_record_hash": lead["record_hash"], "document_record_hash": doc["record_hash"],
            "original_sha256": doc["document_sha256"],
            "url_sha256": hashlib.sha256(lead["url"].encode("utf-8")).hexdigest(),
            "rationale": rationale, "created_by": user["username"],
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        row["record_hash"] = _hash(row)
        cols = list(row)
        ctx.db.execute(
            "INSERT INTO lead_original_links_487 (" + ",".join(cols) + ") VALUES (" +
            ",".join("?" for _ in cols) + ")", tuple(row[k] for k in cols)
        )
        ctx.audit.log("lead_linked_to_reviewed_original_487", "lead_original_links_487",
                      lead_id, case_id, {"lead_id": lead_id, "document_id": document_id,
                      "original_sha256": doc["document_sha256"], "url_sha256": row["url_sha256"],
                      "manual_association": True, "url_origin_proven": False,
                      "network_fetch": False, "truth_determined": False})
        return row


def attach_sources487(app, build):
    ctx = app.state.context
    _init(ctx)

    @app.get("/workbench/sources487", response_class=HTMLResponse)
    def source_page(request: Request, case_id: str = ""):
        user, case = case_access(app, request, case_id)
        leads = listed(ctx, case_id)
        links = source_links(ctx, user, case_id)
        docs = ctx.document_intelligence_458.documents(identity=user, case_id=case_id)
        eligible = [d for d in docs if d["state"] == "extraction_approved" and not d["ocr_required"]]
        form = ""
        if leads and eligible:
            lead_options = "".join('<option value="' + escape(x["lead_id"], quote=True) + '">' +
                                   escape(x["title"][:140]) + "</option>" for x in leads)
            doc_options = "".join('<option value="' + escape(x["document_id"], quote=True) + '">' +
                                  escape(x["title"][:140]) + "</option>" for x in eligible)
            form = (
                '<section class="card"><h2>Manuelle Quellenzuordnung</h2>'
                '<form method="post" action="/workbench/sources487">'
                '<input type="hidden" name="case_id" value="' + escape(case_id, quote=True) + '">'
                '<input type="hidden" name="csrf" value="' +
                escape(request.cookies.get(CSRF_COOKIE, ""), quote=True) + '">'
                '<label>Recherchehinweis</label><select name="lead_id">' + lead_options + '</select>'
                '<label>Geprüftes Original</label><select name="document_id">' + doc_options + '</select>'
                '<label>Warum ordnest du Hinweis und Original einander zu?</label>'
                '<textarea name="rationale" required minlength="20" maxlength="1200" rows="4"></textarea>'
                '<label><input type="checkbox" name="confirm" value="yes" required>'
                ' Nur manuelle Zuordnung, keine bewiesene Herkunft oder Wahrheit.</label>'
                '<button type="submit">Original mit Suchhinweis verknüpfen</button></form></section>'
            )
        entries = "".join(
            '<tr><td>' + escape(x["lead_id"]) + '</td><td><a href="/documents458?' +
            escape(urlencode({"case_id": case_id, "document_id": x["document_id"]}), quote=True) +
            '">' + escape(x["document_id"]) + '</a></td><td>' +
            escape(x["original_sha256"][:16]) + '…</td><td>' + escape(x["rationale"]) + '</td></tr>'
            for x in links
        )
        body = (
            '<p>Fall: <strong>' + escape(str(case.get("title") or "")) + '</strong>.</p>'
            '<p class="warn">Die Zuordnung ist eine menschliche Hypothese zwischen einem '
            'ungeprüften Recherchehinweis und einem lokal gesicherten Original. '
            'Die tatsächliche Herkunft aus der URL ist nicht bewiesen. '
            'Keine automatische Evidence, kein Claim und kein Netzwerkabruf.</p>'
            '<p><a href="/workbench/leads483?' + escape(urlencode({"case_id": case_id}), quote=True) +
            '">Recherchehinweis anlegen</a> · <a href="/documents458?' +
            escape(urlencode({"case_id": case_id}), quote=True) +
            '">Original importieren und prüfen</a> · <a href="/workbench/bridge481?' +
            escape(urlencode({"case_id": case_id}), quote=True) +
            '">Evidence separat prüfen</a></p>' + form +
            '<h2>Integritätsgeprüfte Zuordnungen (' + str(len(links)) + ')</h2>'
            '<div style="overflow-x:auto"><table><thead><tr><th>Hinweis</th><th>Original</th>'
            '<th>SHA-256</th><th>Begründung</th></tr></thead><tbody>' +
            (entries or '<tr><td colspan="4">Noch keine Zuordnung.</td></tr>') +
            '</tbody></table></div>'
        )
        return HTMLResponse(page("Quellenzuordnung und Provenienz 487", case_id, body, build),
                            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})

    @app.post("/workbench/sources487")
    async def source_post(request: Request):
        # 1200 astral Unicode code points can expand to 14,400 bytes when URL-encoded.
        # Keep a finite transport cap while validating the decoded 20–1200 characters below.
        form = await bounded_form(request, max_bytes=24576)
        cid = str(form.get("case_id") or "")
        user, _case = case_access(app, request, cid, capability="research.run")
        verify_post(app, request, user, form.get("csrf", ""))
        if form.get("confirm") != "yes":
            raise HTTPException(422, "Menschliche Zuordnung bestätigen.")
        associate(ctx, user, cid, str(form.get("lead_id") or ""),
                  str(form.get("document_id") or ""), form.get("rationale"))
        return RedirectResponse("/workbench/sources487?" + urlencode({"case_id": cid}), status_code=303)
