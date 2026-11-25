"""Build 489: read-only, case-scoped review/provenance checkpoint.

Entity judgments and source associations are independent human annotations;
this page deliberately does not imply a source proves an entity match.
"""
from __future__ import annotations
from html import escape
from urllib.parse import urlencode
from fastapi import Request
from fastapi.responses import HTMLResponse
from eagleeye.application.build488.reviews import reviews_for_case
from .operations476 import case_access, page
from .sources487 import source_links


def attach_checkpoint489(app, build):
    ctx = app.state.context

    @app.get("/workbench/checkpoint489", response_class=HTMLResponse)
    def checkpoint(request: Request, case_id: str = ""):
        user, case = case_access(app, request, case_id)
        # Both reads validate their own integrity and must fail closed on tampering.
        reviews = reviews_for_case(ctx, user, case_id)
        sources = source_links(ctx, user, case_id)
        q = escape(urlencode({"case_id": case_id}), quote=True)
        review_rows = "".join(
            "<tr><td>" + escape(r["left_entity_id"]) + " ↔ " +
            escape(r["right_entity_id"]) + "</td><td>" +
            escape(r["decision"]) + "</td><td>" +
            escape(r["rationale"]) + "</td><td>" +
            escape(r["reviewed_by"]) + "</td><td>" +
            escape(r["reviewed_at"]) + "</td></tr>"
            for r in reviews
        )
        source_rows = "".join(
            "<tr><td>" + escape(s["lead_id"]) + "</td><td>" +
            '<a href="/documents458?' + escape(urlencode({"case_id": case_id, "document_id": s["document_id"]}), quote=True) + '">' + escape(s["document_id"]) + "</a></td><td>" +
            escape(s["original_sha256"]) + "</td><td>" +
            escape(s["created_by"]) + "</td><td>" + escape(s["rationale"]) + "</td></tr>"
            for s in sources
        )
        body = (
            "<p>Fall: " + escape(str(case.get("title") or "")) + "</p>"
            "<p class='warn'>Getrennte Prüfregister: Eine Quellenzuordnung "
            "belegt keine Entitätsidentität. Keine automatische Bestätigung "
            "von Evidence oder Claims.</p>"
            "<p><a href='/workbench/entities488?" + q +
            "'>Entitätsprüfungen</a> · <a href='/workbench/sources487?" + q +
            "'>Quellen und Originale</a></p>"
            "<h2>Auditierte Entitätsentscheidungen (" + str(len(reviews)) +
            ")</h2><table><thead><tr><th>Entitäten</th><th>Entscheidung</th>"
            "<th>Begründung</th><th>Prüfer</th><th>Zeit</th></tr></thead><tbody>" +
            (review_rows or "<tr><td colspan='5'>Keine Entscheidungen</td></tr>") +
            "</tbody></table><h2>Integritätsgeprüfte Quellenzuordnungen (" +
            str(len(sources)) +
            ")</h2><table><thead><tr><th>Hinweis</th><th>Original</th>"
            "<th>Original SHA-256</th><th>Prüfer</th><th>Begründung</th></tr></thead><tbody>" +
            (source_rows or "<tr><td colspan='5'>Keine Zuordnungen</td></tr>") +
            "</tbody></table>"
        )
        return HTMLResponse(page("Prüfcheckpoint 489", case_id, body, build),
                            headers={"Cache-Control": "no-store",
                                     "Referrer-Policy": "no-referrer"})
