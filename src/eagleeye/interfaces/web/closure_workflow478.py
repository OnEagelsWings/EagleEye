"""Operator-facing, read-only bridge to the ORIGINAL Evidence→Claim→Dossier workflow.

Counts refer to persisted, case-scoped canonical Build-447 artifacts, not to
document-import previews, AI drafts or the separate Build-478 note ledger.
No new approval or export route is created here.
"""
from __future__ import annotations

from html import escape
from urllib.parse import urlencode

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse

from .operations476 import case_access, page


def _link(case_id: str, view: str) -> str:
    return escape("/?" + urlencode({"case_id": case_id, "view": view}), quote=True)


def _stage(num: int, heading: str, count: str, explanation: str,
           case_id: str, view: str, action: str) -> str:
    return (
        '<section class="card"><h2>' + str(num) + '. ' + escape(heading) +
        '</h2><p><strong>' + escape(count) + '</strong></p><p>' +
        escape(explanation) + '</p><a href="' + _link(case_id, view) + '">' +
        escape(action) + ' →</a></section>'
    )


def case_closure_counts(ctx, identity, case_id):
    """Read the existing guarded stores. Never infer facts from raw documents."""
    # Checking the upstream chain and record hashes prevents compromised older
    # artifacts from being displayed as a healthy or export-ready case.
    integrity = ctx.evidence_claims_dossier_447.verify_integrity()
    if not integrity.get("valid", False):
        raise HTTPException(
            409,
            "Evidence-/Claim-Integrität nicht bestanden. Keine Fortschrittsanzeige.",
        )
    docs = ctx.document_intelligence_458.documents(
        identity=identity, case_id=case_id
    )
    closure = ctx.evidence_claims_dossier_447
    evidence = closure.case_evidence(case_id)
    claims = closure.case_claims(case_id)
    dossiers = closure.case_dossiers(case_id)
    exports = closure.exports(case_id)
    return {
        "documents": len(docs),
        "evidence": len(evidence),
        "reviewed_evidence": sum(
            row.get("review_state") == "accepted" for row in evidence
        ),
        "claims": len(claims),
        "accepted_claims": sum(
            row.get("state") == "accepted_for_dossier" for row in claims
        ),
        "dossiers": len(dossiers),
        "approved_dossiers": sum(
            row.get("state") == "approved_for_export" for row in dossiers
        ),
        "exports": len(exports),
        "integrity_valid": True,
    }


def attach_canonical_closure(app, build):
    ctx = app.state.context

    @app.get("/workbench/closure", response_class=HTMLResponse)
    def closure_status(request: Request, case_id: str = ""):
        identity, case = case_access(app, request, case_id)
        counts = case_closure_counts(ctx, identity, case_id)

        # Build-458 documents and Build-447 evidence are separate stores.
        # Not conflating them is a critical honesty/usability requirement.
        gap = (
            '<p class="warn"><strong>Wichtige Integrationslücke:</strong> '
            'Ein PDF/TXT im Dokumentenarchiv ist noch kein prüfbares '
            'Build-447-Evidence-Objekt. Die ursprüngliche Evidence-Kette '
            'nimmt nur registrierte, provenienzgebundene Beschaffungsbeobachtungen '
            'auf. Eine automatische Umwandlung ist hier ausdrücklich nicht implementiert.</p>'
            if counts["documents"] and not counts["evidence"] else ""
        )
        steps = [
            _stage(
                1, "Originalquellen aufbewahren", str(counts["documents"]) + " Dokumente",
                "Importierte Quellen mit Originaltextankern und SHA-256 sind separat gespeichert.",
                case_id, "research", "Recherchequellen öffnen",
            ),
            _stage(
                2, "Kanonische Evidence prüfen",
                f'{counts["reviewed_evidence"]}/{counts["evidence"]} akzeptiert',
                "Build-447-Evidence kommt aus der vorher geprüften Beschaffungskette; nicht aus jedem hochgeladenen Dokument.",
                case_id, "evidence", "Evidence und Review öffnen",
            ),
            _stage(
                3, "Claims und Gegenbelege bewerten",
                f'{counts["accepted_claims"]}/{counts["claims"]} für Dossier akzeptiert',
                "Ein Claim erfordert akzeptierte Evidence und menschliche Prüfung. Widersprüche dokumentieren.",
                case_id, "claims", "Claims und Hypothesen öffnen",
            ),
            _stage(
                4, "Living-Dossier-Revision prüfen",
                f'{counts["approved_dossiers"]}/{counts["dossiers"]} zur Ausfuhr freigegeben',
                "Eine Dossier-Revision erfordert akzeptierte Claims und die vorhandenen Freigabegates.",
                case_id, "dossier", "Dossier und Revisionen öffnen",
            ),
            _stage(
                5, "Vier-Augen-Export nachvollziehen",
                str(counts["exports"]) + " Exportdatensätze",
                "Der Build-449-Prozess erfordert getrennte Konten und einen gültigen Freigabevermerk; ein Exportzähler ist keine Wahrheitsbestätigung.",
                case_id, "operations", "Team- und Reviewprüfung öffnen",
            ),
        ]
        warning = (
            '<p class="warn"><strong>Keine Freigabeautomatik:</strong> Dieser '
            'Arbeitsstand bietet nur lesende Navigation und prüft die Integrität '
            'der bestehenden Register. Technische Review-Zustände sind keine '
            'unabhängigen Tatsachennachweise und ersetzen keine reale '
            'inhaltliche Gegenprüfung.</p>'
        )
        body = (
            "<p>Aktueller regulärer Fall: <strong>" +
            escape(str(case.get("title") or "")) +
            "</strong>. Hier siehst du, welche Ergebnisse in der "
            "ursprünglichen Evidence → Claims → Dossier-Kette tatsächlich "
            "gespeichert sind. Die Angaben stammen nicht aus Testentwürfen.</p>" +
            gap +
            '<div class="grid">' + "".join(steps) + "</div>" +
            '<p><a href="' +
            escape("/workbench/sources?" + urlencode({"case_id": case_id}), quote=True) +
            '">Quelleninventar mit Fundstellen ansehen →</a> · <a href="' +
            escape("/workbench/expert?" + urlencode({"case_id": case_id}), quote=True) +
            '">Alle Expertenwerkzeuge öffnen →</a></p>' + warning
        )
        return HTMLResponse(
            page("Evidence → Claims → Dossier: Original-Workflow", case_id, body, build),
            headers={"Cache-Control": "no-store", "Referrer-Policy": "same-origin"},
        )
