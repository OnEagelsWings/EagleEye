"""Client report (PDF) for a mandate: letterhead, file number, findings selected by recipient level.

The selection is the one of the working report (Build 492 protection classes):
``mandant`` only reviewed findings classed "offen", ``behoerde`` only findings reviewed by a
second account with unchanged sources. Omitted findings are listed on the mandate page and in
the audit log, not in the client's copy. Every finding cites its source as a numbered note;
the source list shows address, document, retrieval time and SHA-256 so the client can have
the evidence checked.
"""
from __future__ import annotations

import io
from datetime import date
from html import escape
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import Response

from eagleeye.application.buero import checklists, service as buero
from eagleeye.application.intel492 import captures, markings, stamps
from .findings478 import KINDS, REVIEW_LABELS, notes_for_case
from .intel492 import _when

LEVEL_TITLES = {"mandant": "Ermittlungsbericht", "behoerde": "Ermittlungsbericht für Behörde oder Gericht",
                "intern": "Interner Arbeitsstand"}
FONT_CANDIDATES = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
]
MAX_FINDINGS = 1000


def _fonts() -> tuple[str, str]:
    """A Unicode TrueType font when one is installed (quotes from foreign sources), else Helvetica."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    if "EEReport" in pdfmetrics.getRegisteredFontNames():
        return "EEReport", "EEReport-Bold"
    for regular, bold in FONT_CANDIDATES:
        if Path(regular).is_file() and Path(bold).is_file():
            try:
                pdfmetrics.registerFont(TTFont("EEReport", regular))
                pdfmetrics.registerFont(TTFont("EEReport-Bold", bold))
                # <b>/<i> inside paragraphs need the family mapping.
                pdfmetrics.registerFontFamily("EEReport", normal="EEReport", bold="EEReport-Bold",
                                              italic="EEReport", boldItalic="EEReport-Bold")
                return "EEReport", "EEReport-Bold"
            except Exception:  # damaged or unsupported font file: fall back
                continue
    return "Helvetica", "Helvetica-Bold"


def report_material(app, user, case_id: str, level: str) -> dict:
    """Mandate, office settings and the findings allowed for ``level`` (no export logged)."""
    ctx = app.state.context
    row = buero.mandate(ctx, user, case_id)
    if row is None:
        raise buero.BueroError("Für diesen Fall sind noch keine Auftragsdaten angelegt.")
    if level not in markings.LEVELS:
        raise buero.BueroError("Unbekannte Empfängerstufe.")
    notes = notes_for_case(app, case_id)
    if len(notes) > MAX_FINDINGS:
        raise buero.BueroError("Mehr als 1000 Befunde: bitte den Bericht aufteilen.")
    selection = getattr(app.state, "report_selection", None)
    kept, omitted = selection(user, case_id, notes, level) if selection else (notes, {})
    kept = sorted(kept, key=lambda r: (str(r.get("created_at") or ""), str(r["finding_id"])))
    documents = {d["document_id"]: d for d in ctx.document_intelligence_458.documents(identity=user, case_id=case_id)}
    marks = markings.current(ctx, case_id)
    return {"mandate": row, "office": buero.settings(ctx), "findings": kept, "omitted": omitted, "total": len(notes),
            "scope": checklists.checklist(ctx, user, case_id),
            "documents": documents, "marks": marks, "level": level}


def _sources(ctx, case_id: str, material: dict) -> tuple[list[dict], dict]:
    """Numbered source list (one entry per document) and finding_id -> number."""
    numbers: dict[str, int] = {}
    entries: list[dict] = []
    by_document: dict[str, int] = {}
    for finding in material["findings"]:
        doc_id = finding["document_id"]
        if doc_id not in by_document:
            doc = material["documents"].get(doc_id, {})
            try:
                web = captures.provenance_for_document(ctx, case_id, doc_id)
            except ValueError:
                web = None
            if web:
                web["evidence"] = stamps.client_summary(ctx, case_id, web["capture_id"])
            entries.append({"title": doc.get("title") or "Dokument", "url": finding.get("source_url") or doc.get("source_url") or "",
                            "sha256": finding.get("document_sha256") or "", "stored_at": str(doc.get("created_at") or ""),
                            "web": web})
            by_document[doc_id] = len(entries)
        numbers[finding["finding_id"]] = by_document[doc_id]
    return entries, numbers


def report_pdf(app, user, case_id: str, level: str, material: dict | None = None) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    ctx = app.state.context
    material = material or report_material(app, user, case_id, level)
    row, office = material["mandate"], material["office"]
    regular, bold = _fonts()
    base = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=base["BodyText"], fontName=regular, fontSize=10, leading=13.5)
    small = ParagraphStyle("small", parent=body, fontSize=8.5, leading=11)
    quote = ParagraphStyle("quote", parent=body, fontSize=9, leading=12, leftIndent=8 * mm, textColor=colors.HexColor("#333333"))
    h1 = ParagraphStyle("h1", parent=base["Title"], fontName=bold, fontSize=17, leading=21, alignment=0)
    h2 = ParagraphStyle("h2", parent=base["Heading2"], fontName=bold, fontSize=12.5, leading=16, spaceBefore=8)
    h3 = ParagraphStyle("h3", parent=base["Heading3"], fontName=bold, fontSize=10.5, leading=14, spaceBefore=6)
    esc = lambda value: escape(str(value or "")).replace("\n", "<br/>")
    today = date.today().strftime("%d.%m.%Y")
    marking = f'Vertraulich · Empfängerstufe: {markings.LEVELS[level]} · Aktenzeichen {row["aktenzeichen"]}'

    def decorate(canvas, doc):
        canvas.saveState()
        canvas.setFont(regular, 7.5)
        canvas.setFillColor(colors.HexColor("#555555"))
        canvas.drawString(20 * mm, 287 * mm, marking)
        footer = (office["bericht_fusszeile"] + " · " if office["bericht_fusszeile"] else "") + f"Seite {doc.page}"
        canvas.drawString(20 * mm, 10 * mm, footer[:150])
        canvas.restoreState()

    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=20 * mm, bottomMargin=18 * mm,
                            title=f'{LEVEL_TITLES[level]} {row["aktenzeichen"]}', author=office["firma"] or "EagleEye")
    story = []
    if office["firma"] or office["anschrift"]:
        story.append(Paragraph("<b>" + esc(office["firma"]) + "</b><br/>" + esc(office["anschrift"])
                               + ("<br/>" + esc(office["kontakt"]) if office["kontakt"] else ""), small))
        story.append(Spacer(1, 7 * mm))
    client = row["client"]
    recipient = row["recipient"] or "\n".join(x for x in (client["name"], client.get("contact_person"), client.get("address")) if x)
    story += [Paragraph(esc(recipient), body), Spacer(1, 8 * mm), Paragraph(esc(LEVEL_TITLES[level]), h1),
              Paragraph(f'Aktenzeichen {esc(row["aktenzeichen"])} · {esc(row["title"])}<br/>Stand {today}', body), Spacer(1, 4 * mm)]

    story.append(Paragraph("1. Auftrag", h2))
    facts = [["Auftraggeber", Paragraph(esc(client["name"]), body)],
             ["Auftragsart", Paragraph(esc(buero.MANDATE_KINDS.get(row["kind"], row["kind"])), body)],
             ["Auftrag und Zweck", Paragraph(esc(row["purpose"]), body)],
             ["Rechtsgrundlage", Paragraph(esc(row["legal_basis"]), body)],
             ["Auftrag erteilt", _when(row["received_on"])]]
    story.append(Table(facts, colWidths=[38 * mm, 132 * mm], style=TableStyle([
        ("FONTNAME", (0, 0), (0, -1), bold), ("FONTNAME", (1, 0), (1, -1), regular), ("FONTSIZE", (0, 0), (-1, -1), 9.5), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#bbbbbb"))])))

    story.append(Paragraph("2. Prüfumfang", h2))
    story.append(Paragraph("Arbeitsliste für „" + esc(buero.MANDATE_KINDS.get(row["kind"], row["kind"])) + "“ – was geprüft wurde, "
                           "was nicht und was nicht einschlägig war:", body))
    scope_rows = [[Paragraph("<b>Prüfschritt</b>", small), Paragraph("<b>Stand</b>", small)]]
    for item in material["scope"]:
        state = checklists.REPORT_STATES[item["state"]] + (": " + item["note"] if item["note"] else "")
        scope_rows.append([Paragraph(esc(item["title"]), small), Paragraph(esc(state), small)])
    story.append(Table(scope_rows, colWidths=[118 * mm, 52 * mm], repeatRows=1, style=TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), regular), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#bbbbbb"))])))

    sources, numbers = _sources(ctx, case_id, material)
    story.append(Paragraph("3. Ergebnisse", h2))
    if not material["findings"]:
        story.append(Paragraph("Für diese Empfängerstufe liegen noch keine freigegebenen Ergebnisse vor.", body))
    for index, finding in enumerate(material["findings"], 1):
        cls = markings.effective(material["marks"], finding)
        flag = " <font color='#a33'>(besonders schutzwürdige Angabe)</font>" if cls == "besonders_schutzwuerdig" else ""
        block = [Paragraph(f'3.{index} {esc(finding["title"])}<super>[{numbers[finding["finding_id"]]}]</super>{flag}', h3),
                 Paragraph(f'<i>{esc(KINDS.get(finding["kind"], "Arbeitsnotiz"))}</i>', small),
                 Paragraph(esc(finding["interpretation"]), body)]
        if finding.get("source_excerpt"):
            block.append(Paragraph("„" + esc(str(finding["source_excerpt"])[:1500]) + "“", quote))
        block.append(Paragraph("Prüfung: " + esc(REVIEW_LABELS.get(finding["review_state"], finding["review_state"]))
                               + (f' ({esc(finding["reviewed_by"])})' if finding.get("reviewed_by") else ""), small))
        block.append(Spacer(1, 2 * mm))
        story.append(KeepTogether(block))

    story.append(Paragraph("4. Methodik und Grenzen", h2))
    method = ["Ausgewertet wurden öffentlich zugängliche Quellen und vom Auftraggeber übergebene Unterlagen. "
              "Jede Aussage ist mit ihrer Fundstelle verknüpft."]
    if level == "intern":
        method.append("Dieser interne Arbeitsstand enthält auch noch nicht geprüfte Befunde und ist nicht zur Weitergabe bestimmt.")
    else:
        method.append("Jede aufgenommene Aussage wurde vor der Aufnahme in diesen Bericht mit dem Original verglichen"
                      + (" und zusätzlich von einer zweiten Person geprüft." if level == "behoerde" else "."))
    if any(source["web"] for source in sources):
        method.append("Web-Seiten wurden beim Abruf unverändert gesichert (WARC-Format).")
    if any(source["web"] and any(e.startswith("unabhängiger") for e in source["web"]["evidence"]) for source in sources):
        method.append("Wo vermerkt, bestätigt ein unabhängiger Zeitstempeldienst (RFC 3161), dass die Prüfsummen der Sicherung "
                      "zum angegebenen Zeitpunkt vorlagen; ein Prüfpaket zur eigenen Kontrolle kann angefordert werden.")
    method.append("SHA-256-Prüfsummen weisen nach, dass eine Quelle seit der Sicherung nicht verändert wurde; sie bestätigen "
                  "nicht die inhaltliche Richtigkeit. Bewertungen sind als solche gekennzeichnet. Der Bericht gibt den "
                  f"Erkenntnisstand am {today} wieder.")
    story.append(Paragraph(" ".join(method), body))

    story.append(Paragraph("5. Quellenverzeichnis", h2))
    for number, source in enumerate(sources, 1):
        web = source["web"]
        detail = [esc(source["title"])]
        if source["url"]:
            detail.append(esc(source["url"]))
        if web:
            detail.append(("Archivfassung" if web["kind"] == "archive" else "Abruf") + " am "
                          + esc(_when(web["captured_at"])) + " UTC, als WARC gesichert"
                          + ("" if web["integrity_verified"] else " – Sicherung beschädigt, nicht verwenden"))
            if web["integrity_verified"]:
                detail.extend(esc(e) for e in web["evidence"])
        elif source["stored_at"]:
            detail.append("übernommen am " + esc(_when(source["stored_at"])))
        if source["sha256"]:
            detail.append("SHA-256 " + esc(source["sha256"]))
        story.append(Paragraph(f"[{number}] " + " · ".join(detail), small))
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return out.getvalue()


def preview_html(app, user, case_id: str, level: str) -> str:
    """Short note for the mandate page: what the client copy will contain and what stays back."""
    try:
        material = report_material(app, user, case_id, level)
    except (buero.BueroError, HTTPException):
        return ""
    kept = len(material["findings"])
    why = "; ".join(f"{n} × {escape(r)}" for r, n in sorted(material["omitted"].items()))
    return (f'<p class="muted">Bericht für die Stufe „{escape(markings.LEVELS[level])}“: {kept} von {material["total"]} '
            f'Befunden enthalten' + (f'; zurückgehalten: {why}' if why else '') + '.</p>')


def attach_report_pdf(app, build: str) -> None:
    ctx = app.state.context
    app.state.buero_report_pdf = True
    app.state.buero_report_preview = lambda user, case_id, level: preview_html(app, user, case_id, level)

    @app.get("/buero/bericht.pdf")
    def client_report(request: Request, case_id: str = "", level: str = ""):
        from .buero import _user
        user = _user(app, request)
        try:
            ctx.team_governance_359.authorize(user, case_id=case_id, capability="dossier.write",
                                              object_type="buero_report", object_id=case_id)
        except PermissionError:
            raise HTTPException(403, "Den Mandantenbericht erstellen Fallleitung, Ermittler und Berichtsautoren.") from None
        try:
            row = buero.mandate(ctx, user, case_id)
            if row is None:
                raise buero.BueroError("Für diesen Fall sind noch keine Auftragsdaten angelegt.")
            level = level or row["recipient_level"]
            material = report_material(app, user, case_id, level)
            pdf = report_pdf(app, user, case_id, level, material)
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from None
        except buero.BueroError as exc:
            raise HTTPException(422, str(exc)) from None
        ctx.audit.log("buero_client_report_exported", "buero_mandate", case_id, case_id,
                      {"level": level, "kept": len(material["findings"]), "omitted": material["omitted"],
                       "actor": user["username"]})
        name = "Bericht" if level != "intern" else "Arbeitsstand_intern"
        return Response(pdf, media_type="application/pdf", headers={
            "Content-Disposition": f'attachment; filename="{name}_{row["aktenzeichen"]}.pdf"', "Cache-Control": "no-store"})
