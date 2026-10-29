"""Build 481: deliberate, provenance-preserving handoff of reviewed files into Build-447 Evidence.

This is an explicit human action, not an automated claim, truth judgment, or
network crawler. The original Build-458 document bytes stay in their vault.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from html import escape
from urllib.parse import urlencode, urlsplit

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .app364 import CSRF_COOKIE
from .findings478 import bounded_form, verify_post
from .operations476 import case_access, page


def _init_bridge(ctx):
    ctx.db.conn.execute("""CREATE TABLE IF NOT EXISTS document_evidence_bridge_481(
        document_id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL,
        observation_id TEXT NOT NULL UNIQUE,
        evidence_id TEXT NOT NULL UNIQUE,
        content_sha256 TEXT NOT NULL,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        record_hash TEXT NOT NULL
    )""")
    ctx.db.conn.execute(
        "CREATE INDEX IF NOT EXISTS bridge481_case_idx ON document_evidence_bridge_481(case_id)"
    )
    ctx.db.conn.commit()


def _record_hash(row):
    return hashlib.sha256(json.dumps(
        {k: v for k, v in row.items() if k != "record_hash"},
        sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def _records(ctx, case_id):
    rows = [dict(x) for x in ctx.db.all(
        "SELECT * FROM document_evidence_bridge_481 WHERE case_id=? ORDER BY created_at",
        (str(case_id),)
    )]
    for row in rows:
        if _record_hash(row) != row["record_hash"]:
            raise HTTPException(409, "Verknüpfungsregister verändert; Integrität nicht bestanden.")
    return rows


def _reviewed_bytes(ctx, user, case_id, document_id):
    service = ctx.document_intelligence_458
    try:
        doc = service._document(document_id)
    except KeyError:
        raise HTTPException(404, "Dokument nicht vorhanden.") from None
    if doc["case_id"] != case_id:
        raise HTTPException(403, "Dokument gehört nicht zu diesem Fall.")
    service._identity(user, case_id, "case.read", document_id)
    if doc["record_hash"] != service._rh(doc):
        raise HTTPException(409, "Dokument-Metadaten wurden verändert.")
    if doc["state"] != "extraction_approved":
        raise HTTPException(409, "Zuerst die Textextraktion des Dokuments menschlich freigeben.")
    if doc["ocr_required"]:
        raise HTTPException(409, "OCR-Bedarf: erst eine überprüfbare Textfassung bereitstellen.")
    if not service._payload_current(doc):
        raise HTTPException(409, "Datei fehlt oder stimmt nicht mehr mit dem Originalhash überein.")
    extracted = service.anchors(identity=user, document_id=document_id)
    anchors = extracted["anchors"]
    if not anchors or any(
        a["document_sha256"] != doc["document_sha256"] or
        a["record_hash"] != service._rh(service._anchor(a["anchor_id"]))
        for a in anchors
    ):
        raise HTTPException(409, "Unvollständige oder veränderte Originalfundstellen.")
    raw = (service.root / doc["stored_relpath"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != doc["document_sha256"]:
        raise HTTPException(409, "SHA-256 des Originaldokuments stimmt nicht.")
    return doc, raw, anchors


def promote_reviewed_document(ctx, user, case_id, document_id, rationale):
    """Creates unreviewed Evidence. Does NOT approve it or create a Claim."""
    rationale = " ".join(str(rationale or "").split())
    if not (15 <= len(rationale) <= 1200):
        raise HTTPException(422, "Bitte Prüfzweck und rechtmäßige Herkunft begründen (15–1200 Zeichen).")
    ctx.team_governance_359.authorize(
        user, case_id=case_id, capability="research.run",
        object_type="operational_case", object_id=case_id,
    )
    ctx.team_governance_359.authorize(
        user, case_id=case_id, capability="dossier.write",
        object_type="operational_case", object_id=case_id,
    )
    existing = ctx.db.one(
        "SELECT * FROM document_evidence_bridge_481 WHERE document_id=?",
        (document_id,)
    )
    if existing:
        row = dict(existing)
        if row["case_id"] != case_id or _record_hash(row) != row["record_hash"]:
            raise HTTPException(409, "Widersprüchliche bestehende Evidence-Verknüpfung.")
        return {"observation_id": row["observation_id"],
                "evidence_id": row["evidence_id"], "already_linked": True}
    doc, raw, anchors = _reviewed_bytes(ctx, user, case_id, document_id)
    # No remote access: the optional source URL remains user-supplied metadata.
    url = str(doc.get("source_url") or "")
    source = ctx.acquisition_source_registry_421.register(
        identity=user,
        name=("Manuell geprüft: " + str(doc.get("title") or document_id))[:180],
        source_type="website" if url else "dataset",
        access_mode="public" if url else "local_dataset",
        base_url=(urlsplit(url).scheme + "://" + urlsplit(url).netloc + "/") if url else "",
        capabilities=["manual_import"],
        coverage={"origin": "document_intelligence_458",
                  "document_id": document_id, "human_reviewed_extraction": True},
        license_note="Analyst documents lawful acquisition; source URL is unverified metadata.",
    )
    event = ctx.acquisition_events_422.record(
        identity=user, case_id=case_id, source_id=source["source_id"],
        target=url or ("urn:eagleeye:document:458:" + document_id),
        method="manual_import", status="retrieved",
        content_sha256=doc["document_sha256"], media_type=doc["media_type"],
        bytes_count=len(raw),
        provenance={
            "document_id": document_id,
            "document_record_hash": doc["record_hash"],
            "document_sha256": doc["document_sha256"],
            "anchor_ids": [a["anchor_id"] for a in anchors[:3200]],
            "human_rationale": rationale,
            "source_url_user_supplied_unverified": bool(url),
            "network_fetch_performed": False,
            "document_extraction_reviewed_by": doc.get("review_by", ""),
            "promoted_from": "build458_reviewed_document",
        },
        usage={"public_or_lawfully_held": True, "truth_determined": False,
               "review_required": True},
    )
    observation = ctx.content_store_423.ingest(
        identity=user, event_id=event["event_id"], content=raw,
        media_type=doc["media_type"],
        metadata={"document_id": document_id,
                  "document_sha256": doc["document_sha256"],
                  "source_url_unverified": bool(url)},
    )
    ctx.evidence_claims_dossier_447.sync_case_evidence(
        identity=user, case_id=case_id
    )
    evidence = next((
        x for x in ctx.evidence_claims_dossier_447.case_evidence(case_id)
        if x["observation_id"] == observation["observation_id"]
    ), None)
    if not evidence or evidence["content_sha256"] != doc["document_sha256"]:
        raise HTTPException(409, "Evidence-Registrierung konnte nicht nachgewiesen werden.")
    if evidence["review_state"] != "unreviewed":
        raise HTTPException(409, "Neue Evidence muss ungeprüft beginnen.")
    row = {
        "document_id": document_id, "case_id": case_id,
        "observation_id": observation["observation_id"],
        "evidence_id": evidence["evidence_id"],
        "content_sha256": doc["document_sha256"],
        "created_by": user["username"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    row["record_hash"] = _record_hash(row)
    columns = list(row)
    ctx.db.execute(
        "INSERT INTO document_evidence_bridge_481 (" + ",".join(columns) +
        ") VALUES (" + ",".join("?" for _ in columns) + ")",
        tuple(row.values()),
    )
    ctx.audit.log(
        "document_promoted_to_unreviewed_evidence_481",
        "document_evidence_bridge_481", document_id, case_id,
        {"document_sha256": doc["document_sha256"],
         "evidence_id": evidence["evidence_id"],
         "truth_determined": False},
    )
    return {"observation_id": observation["observation_id"],
            "evidence_id": evidence["evidence_id"], "already_linked": False}


def attach_bridge(app, build):
    ctx = app.state.context
    _init_bridge(ctx)

    @app.get("/workbench/bridge481", response_class=HTMLResponse)
    def bridge_page(request: Request, case_id: str = "", document_id: str = ""):
        user, case = case_access(app, request, case_id)
        docs = ctx.document_intelligence_458.documents(identity=user, case_id=case_id)
        links = {row["document_id"]: row for row in _records(ctx, case_id)}
        items = []
        for doc in docs[:200]:
            doc_id = str(doc["document_id"])
            linked = links.get(doc_id)
            eligible = (doc["state"] == "extraction_approved"
                        and not doc["ocr_required"] and not linked)
            status = ("Bereits als ungeprüfte Evidence registriert" if linked else
                      "Bereit zur Übernahme" if eligible else
                      "Erst Extraktion prüfen / OCR abschließen")
            href = "/workbench/bridge481?" + urlencode({
                "case_id": case_id, "document_id": doc_id
            })
            items.append(
                '<tr><td><a href="' + escape(href, quote=True) + '">' +
                escape(str(doc["title"])[:130]) + '</a></td><td>' +
                escape(status) + '</td><td>' +
                escape(str(doc["document_sha256"])[:14]) + '…</td></tr>'
            )
        current = next((x for x in docs if x["document_id"] == document_id), None)
        if document_id and current is None:
            raise HTTPException(403, "Kein fallzugehöriges Dokument.")
        form = ""
        if current and current["document_id"] not in links:
            form = (
                '<section class="card"><h2>Geprüftes Dokument bewusst in Evidence aufnehmen</h2>'
                '<p>Prüfe zunächst im Dokumentenarchiv den Originaltext und bestätige '
                'die Extraktion. Mit der Übernahme entsteht ausschließlich <strong>ungeprüfte</strong> '
                'Evidence. Kein Claim, keine Wahrheitsfeststellung und keine Exportfreigabe.</p>'
                '<form method="post" action="/workbench/bridge481">'
                '<input type="hidden" name="case_id" value="' + escape(case_id, quote=True) + '">'
                '<input type="hidden" name="document_id" value="' + escape(document_id, quote=True) + '">'
                '<input type="hidden" name="csrf" value="' +
                escape(request.cookies.get(CSRF_COOKIE, ""), quote=True) + '">'
                '<label>Herkunft, rechtmäßiger Zugriff und Zweck der Übernahme</label>'
                '<textarea name="rationale" required minlength="15" maxlength="1200" rows="4"></textarea>'
                '<label><input type="checkbox" name="confirm" value="yes" required>'
                ' Ich habe Original und Herkunft geprüft. Eine inhaltliche'
                ' Evidence-Freigabe erfolgt gesondert.</label>'
                '<button type="submit">Als ungeprüfte Evidence aufnehmen</button></form></section>'
            )
        body = (
            '<p>Fall: <strong>' + escape(str(case.get("title") or "")) +
            '</strong> · ' + str(len(docs)) + ' Originaldokumente · ' +
            str(len(links)) + ' übernommene Dokumente.</p>'
            '<p>1. Quelle importieren → 2. Textextraktion überprüfen → '
            '3. Übernahme begründen → 4. Evidence unabhängig prüfen → '
            '5. Claim und Gegenbelege bearbeiten → 6. Dossier erstellen.</p>'
            '<p><a href="/documents458?' +
            escape(urlencode({"case_id": case_id}), quote=True) +
            '">Dokumente und Extraktionsprüfung öffnen →</a></p>' +
            '<table><thead><tr><th>Originaldokument</th><th>Prüfstand</th>'
            '<th>SHA-256</th></tr></thead><tbody>' +
            ("".join(items) or '<tr><td colspan="3">Noch keine Dokumente.</td></tr>') +
            '</tbody></table>' + form +
            '<p><a href="/workbench/closure?' +
            escape(urlencode({"case_id": case_id}), quote=True) +
            '">Original-Evidence-/Dossierstatus öffnen →</a></p>'
        )
        return HTMLResponse(page(
            "Quellenübergabe: Originaldokument → Evidence", case_id, body, build
        ), headers={"Cache-Control": "no-store", "Referrer-Policy": "same-origin"})

    @app.post("/workbench/bridge481")
    async def bridge_post(request: Request):
        form = await bounded_form(request, max_bytes=8000)
        cid = str(form.get("case_id") or "")
        user, _case = case_access(app, request, cid, capability="research.run")
        verify_post(app, request, user, form.get("csrf", ""))
        if str(form.get("confirm")) != "yes":
            raise HTTPException(422, "Die ausdrückliche Prüfbestätigung fehlt.")
        document_id = str(form.get("document_id") or "")
        try:
            promote_reviewed_document(
                ctx, user, cid, document_id, form.get("rationale", "")
            )
        except PermissionError as exc:
            raise HTTPException(403, "Recht zur Quellenregistrierung oder Dossierbearbeitung fehlt.") from exc
        return RedirectResponse(
            "/workbench/bridge481?" + urlencode({
                "case_id": cid, "document_id": document_id
            }), status_code=303
        )
