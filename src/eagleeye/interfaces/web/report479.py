"""Build 479: human review and exportable, distinctly non-official research working report."""
from __future__ import annotations
from html import escape
from urllib.parse import urlencode
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from .operations476 import case_access, page
from .findings478 import notes_db, notes_for_case, verify_post, get_anchor


def source_state(app, user, case_id, row):
    try:
        _doc, snapshot, anchor = get_anchor(
            app.state.context, user, case_id, row["document_id"], row["anchor_id"])
        same_hash = str(snapshot.get("document_sha256") or "") == row["document_sha256"]
        same_text = str(anchor.get("text_excerpt") or "")[:6000] == row["source_excerpt"]
        return "snapshot_match" if same_hash and same_text else "changed"
    except (KeyError, ValueError, HTTPException, PermissionError):
        return "missing"


def report_body(app, user, case, notes):
    case_id=str(case["case_id"])
    lines=[
        "# EagleEye – Quellengebundener Arbeitsbericht",
        "",
        "**KEIN freigegebenes Ermittlungsdossier oder bestätigter Tatsachenbericht.**",
        "Nur selbst formulierte Notizen mit Herkunftssnapshots; Zitate beweisen keine Interpretation.",
        "",
        "Fall: "+str(case.get("title") or ""),
        "Auftrag/Zweck: "+str(case.get("purpose") or "im Fall dokumentiert"),
        "Rechtsgrundlage: "+str(case.get("legal_basis") or "im Fall prüfen"),
        "Anzahl angezeigter Notizen: "+str(len(notes)),
        "",
    ]
    for i,row in enumerate(notes,1):
        state=source_state(app,user,case_id,row)
        lines.extend([
            "## "+str(i)+". "+row["title"],
            "",
            "Einordnung (eigene Beobachtung/Hypothese):",
            row["interpretation"],
            "",
            "Originaltextauszug:",
            "> "+row["source_excerpt"].replace("\n","\n> "),
            "",
            "Dokument-ID: "+row["document_id"],
            "Anker-ID: "+row["anchor_id"],
            "Dokument SHA-256 bei Aufnahme: "+row["document_sha256"],
            "Herkunfts-URL (unbestätigter Metadateneintrag): "+(row["source_url"] or "nicht hinterlegt"),
            "Quellenintegrität beim Export: "+state,
            "Eigenprüfung: "+row["review_state"]+"; Vermerk: "+row["review_reason"],
            "Bearbeiter: "+row["created_by"]+"; Verfasst: "+row["created_at"],
            "",
        ])
    lines.extend(["## Ausstehende Prüfung", "",
        "- Gegenbelege, alternative Erklärungen und unabhängige Quellen noch prüfen.",
        "- Freigabe, Vier-Augen-Prüfung und offizieller Dossierexport erfolgen NICHT über diesen Arbeitsbericht.",
        "- Keine verdeckte automatische Aufwertung von KI-Entwürfen oder Hypothesen.",
        ""])
    return "\n".join(lines)


def attach_report(app,build):
    @app.get("/workbench/report",response_class=HTMLResponse)
    def report_view(request:Request,case_id:str=""):
        user,case=case_access(app,request,case_id)
        notes=notes_for_case(app,case_id)
        csrf=escape(request.cookies.get("ee_auth_csrf",""),quote=True)
        cards=[]
        for row in notes:
            state=source_state(app,user,case_id,row)
            badge="Quelle unverändert" if state=="snapshot_match" else "Quelle geändert oder fehlt – neu prüfen"
            review=""
            if row["review_state"]!="reviewed_self":
                review=('<form method="post" action="/workbench/report/review">'
                        '<input type="hidden" name="case_id" value="'+escape(case_id,quote=True)+'">'
                        '<input type="hidden" name="finding_id" value="'+escape(row["finding_id"],quote=True)+'">'
                        '<input type="hidden" name="csrf" value="'+csrf+'">'
                        '<label>Begründete Eigenprüfung (keine unabhängige Freigabe)</label>'
                        '<textarea name="reason" required minlength="10" maxlength="1200" rows="3"></textarea>'
                        '<button type="submit">Als eigengeprüft kennzeichnen</button></form>')
            cards.append('<section class="card"><h2>'+escape(row["title"])+'</h2>'
                '<p>'+escape(row["interpretation"])+'</p><p><strong>'+escape(badge)+'</strong>'
                ' · Status: '+escape(row["review_state"])+'</p><blockquote>'
                +escape(row["source_excerpt"][:1200])+'</blockquote>'+review+'</section>')
        link="/workbench/report.md?"+urlencode({"case_id":case_id})
        body=('<p>Fall '+escape(str(case.get("title") or ""))+' · '+str(len(notes))+' quellengestützte Notizen.'
              ' Jeder Eintrag wird mit seinem gespeicherten Dokument-Hash verglichen.</p>'
              '<p><a href="'+escape(link,quote=True)+'">Arbeitsbericht als Markdown herunterladen →</a></p>'
              +("".join(cards) or "<p>Bitte erst unter Arbeitsbefunde quellengebundene Beobachtungen speichern.</p>"))
        return HTMLResponse(page("Prüfen und Arbeitsbericht erstellen",case_id,body,build),
                            headers={"Cache-Control":"no-store"})

    @app.post("/workbench/report/review")
    async def self_review(request:Request):
        if int(request.headers.get("content-length","0") or 0)>6000:
            raise HTTPException(413,"Formular zu groß")
        form=await request.form(max_fields=6,max_files=0)
        case_id=str(form.get("case_id",""))
        user,_case=case_access(app,request,case_id,capability="source.review")
        verify_post(app,request,user,form.get("csrf",""))
        note_id=str(form.get("finding_id",""))
        reason=str(form.get("reason","")).strip()
        if not (10<=len(reason)<=1200):
            raise HTTPException(422,"Prüfbegründung muss 10–1200 Zeichen enthalten.")
        with notes_db(app) as conn:
            row=conn.execute("SELECT * FROM operational_findings_478 WHERE finding_id=? AND case_id=?",
                             (note_id,case_id)).fetchone()
            if not row:
                raise HTTPException(404,"Befund in diesem Fall nicht vorhanden.")
            if source_state(app,user,case_id,dict(row))!="snapshot_match":
                raise HTTPException(409,"Quellenstand verändert – erneute Quellenprüfung erforderlich.")
            conn.execute("UPDATE operational_findings_478 SET review_state='reviewed_self',review_reason=?,reviewed_by=? "
                         "WHERE finding_id=? AND case_id=?",(reason,str(user["username"]),note_id,case_id))
        return RedirectResponse("/workbench/report?"+urlencode({"case_id":case_id}),status_code=303)

    @app.get("/workbench/report.md")
    def download_report(request:Request,case_id:str=""):
        user,case=case_access(app,request,case_id,capability="case.read")
        notes=notes_for_case(app,case_id)
        md=report_body(app,user,case,notes)
        safe_id="".join(ch for ch in case_id if ch.isalnum() or ch in "-_")[:60] or "fall"
        return Response(md,media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition":'attachment; filename="EagleEye_'+safe_id+'_Arbeitsbericht.md"',
                                 "Cache-Control":"no-store","X-Content-Type-Options":"nosniff"})
