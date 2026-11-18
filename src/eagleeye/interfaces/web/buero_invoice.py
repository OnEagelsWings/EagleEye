"""Invoice and cancellation invoice as PDF (layout after DIN 5008, content after § 14 UStG)."""
from __future__ import annotations

import io
from html import escape

from eagleeye.application.buero import service as buero
from .buero_report import _fonts
from .intel492 import _when


def invoice_pdf(inv: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    regular, bold = _fonts()
    base = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=base["BodyText"], fontName=regular, fontSize=10, leading=13.5)
    small = ParagraphStyle("s", parent=body, fontSize=8.5, leading=11)
    tiny = ParagraphStyle("t", parent=body, fontSize=7.5, leading=9.5, textColor=colors.HexColor("#444444"))
    title = ParagraphStyle("h", parent=body, fontName=bold, fontSize=15, leading=19, spaceBefore=6, spaceAfter=6)
    esc = lambda value: escape(str(value or "")).replace("\n", "<br/>")
    seller, buyer = inv["seller"], inv["buyer"]
    storno = inv["kind"] == "storno"

    def iban(value: str) -> str:
        value = str(value or "").replace(" ", "")
        return " ".join(value[i:i + 4] for i in range(0, len(value), 4))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(regular, 7.2)
        canvas.setFillColor(colors.HexColor("#555555"))
        first = " · ".join(p for p in (seller["firma"], " ".join(seller["anschrift"].split()), seller.get("kontakt", "")) if p)
        second = " · ".join(p for p in (("St.-Nr. " + seller["steuernummer"]) if seller["steuernummer"] else "",
                                         ("USt-IdNr. " + seller["ust_idnr"]) if seller["ust_idnr"] else "",
                                         ("IBAN " + iban(seller["iban"])) if seller["iban"] else "",
                                         ("BIC " + seller["bic"]) if seller["bic"] else "") if p)
        right = f"{inv['number']} · Seite {doc.page}"
        room = 170 * mm - canvas.stringWidth(right, regular, 7.2) - 6 * mm
        for text, y in ((first, 13 * mm), (second, 9.5 * mm)):
            while text and canvas.stringWidth(text, regular, 7.2) > (room if y < 10 * mm else 170 * mm):
                text = text[:-2]
            canvas.drawString(20 * mm, y, text)
        canvas.drawRightString(190 * mm, 9.5 * mm, right)
        canvas.restoreState()

    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=24 * mm,
                            title=("Stornorechnung " if storno else "Rechnung ") + inv["number"], author=seller["firma"])
    story = [Paragraph("<b>" + esc(seller["firma"]) + "</b><br/>" + esc(seller["anschrift"])
                       + ("<br/>" + esc(seller["kontakt"]) if seller.get("kontakt") else ""), small), Spacer(1, 8 * mm),
             Paragraph(esc(seller["firma"] + " · " + " ".join(seller["anschrift"].split())), tiny)]
    recipient = Paragraph(esc(buyer["name"]) + ("<br/>" + esc(buyer["contact_person"]) if buyer.get("contact_person") else "")
                          + "<br/>" + esc(buyer["address"]), body)
    info_rows = [["Rechnungsnummer", inv["number"]], ["Rechnungsdatum", _when(inv["issued_on"])],
                 ["Leistungszeitraum", _when(inv["period_from"]) + (" – " + _when(inv["period_to"])
                                                                  if inv["period_to"] != inv["period_from"] else "")],
                 ["Aktenzeichen", inv.get("aktenzeichen", "")]]
    if seller["steuernummer"]:
        info_rows.append(["Steuernummer", seller["steuernummer"]])
    if seller["ust_idnr"]:
        info_rows.append(["USt-IdNr.", seller["ust_idnr"]])
    info = Table([[Paragraph(esc(a), small), Paragraph(esc(b), small)] for a, b in info_rows], colWidths=[34 * mm, 38 * mm],
                 style=TableStyle([("FONTNAME", (0, 0), (-1, -1), regular), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 1), ("TOPPADDING", (0, 0), (-1, -1), 1)]))
    story.append(Table([[recipient, info]], colWidths=[93 * mm, 72 * mm],
                       style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)])))
    story.append(Spacer(1, 10 * mm))
    if storno:
        story.append(Paragraph(f"Stornorechnung zu Rechnung {esc(inv['refers_to'])}", title))
        story.append(Paragraph(f"Die Rechnung {esc(inv['refers_to'])} wird vollständig storniert. Grund: {esc(inv['reason'])}", body))
    else:
        story.append(Paragraph("Rechnung", title))
        story.append(Paragraph(f"Für unsere Leistungen im Auftrag „{esc(inv.get('mandate_title', ''))}“ berechnen wir:", body))
    story.append(Spacer(1, 4 * mm))
    rows = [["Pos.", "Leistung", "Menge", "Einzelpreis", "Betrag"]]
    for number, item in enumerate(inv["positions"], 1):
        rows.append([str(number), Paragraph(esc(item["text"]), small), item["quantity"],
                     buero.euro(item["unit_cents"]) if item.get("unit_cents") else "", buero.euro(item["amount_cents"])])
    style = TableStyle([("FONTNAME", (0, 0), (-1, -1), regular), ("FONTNAME", (0, 0), (-1, 0), bold),
                        ("FONTSIZE", (0, 0), (-1, -1), 9), ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black),
                        ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#bbbbbb")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("ALIGN", (2, 0), (-1, -1), "RIGHT")])
    story.append(Table(rows, colWidths=[12 * mm, 82 * mm, 23 * mm, 24 * mm, 24 * mm], style=style, repeatRows=1))
    totals = [["Summe netto", buero.euro(inv["net_cents"])]]
    if inv["vat_rate"]:
        totals.append([f"Umsatzsteuer {inv['vat_rate']} %", buero.euro(inv["vat_cents"])])
    totals.append(["Rechnungsbetrag" if inv["vat_rate"] else "Rechnungsbetrag (ohne Umsatzsteuer)", buero.euro(inv["gross_cents"])])
    story.append(Spacer(1, 3 * mm))
    story.append(Table(totals, colWidths=[141 * mm, 24 * mm], style=TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), regular), ("FONTNAME", (0, -1), (-1, -1), bold), ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"), ("LINEABOVE", (0, -1), (-1, -1), 0.6, colors.black)])))
    story.append(Spacer(1, 6 * mm))
    if inv["vat_note"]:
        story.append(Paragraph(esc(inv["vat_note"]), body))
    if not storno:
        pay = f"Bitte überweisen Sie den Rechnungsbetrag bis zum {_when(inv['due_on'])} ohne Abzug"
        if seller["iban"]:
            pay += f" auf das Konto IBAN {esc(iban(seller['iban']))}" + (f", BIC {esc(seller['bic'])}" if seller["bic"] else "") \
                   + (f" ({esc(seller['bank'])})" if seller["bank"] else "")
        story.append(Paragraph(pay + f". Verwendungszweck: {esc(inv['number'])}.", body))
        if inv["times"] or inv["expenses"]:
            story.append(Spacer(1, 3 * mm))
            story.append(Paragraph("Die Einzelaufstellung der Leistungen finden Sie in der Anlage.", body))
    # Annex: statement of the billed entries.
    if not storno and (inv["times"] or inv["expenses"]):
        story += [PageBreak(), Paragraph(f"Anlage zu Rechnung {esc(inv['number'])}: Leistungsnachweis", title)]
        grid = TableStyle([("FONTNAME", (0, 0), (-1, -1), regular), ("FONTNAME", (0, 0), (-1, 0), bold),
                           ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#bbbbbb")),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef3")), ("VALIGN", (0, 0), (-1, -1), "TOP")])
        if inv["times"]:
            data = [["Datum", "Tätigkeit", "Beschreibung", "Dauer"]]
            data += [[_when(e["work_date"]), Paragraph(esc(buero.ACTIVITIES.get(e["activity"], e["activity"])), small),
                      Paragraph(esc(e["note"]), small), buero.hours(e["minutes"])] for e in inv["times"]]
            story += [Paragraph("Zeitaufwand", body), Table(data, colWidths=[22 * mm, 40 * mm, 81 * mm, 22 * mm], style=grid,
                                                            repeatRows=1), Spacer(1, 4 * mm)]
        if inv["expenses"]:
            data = [["Datum", "Art", "Beschreibung", "Betrag"]]
            data += [[_when(e["spent_on"]), Paragraph(esc(buero.EXPENSE_KINDS.get(e["kind"], e["kind"])
                                                          + (f' ({e["km"]} km)' if e["km"] else "")), small),
                      Paragraph(esc(e["note"]), small), buero.euro(e["amount_cents"])] for e in inv["expenses"]]
            story += [Paragraph("Auslagen", body), Table(data, colWidths=[22 * mm, 40 * mm, 81 * mm, 22 * mm], style=grid,
                                                         repeatRows=1)]
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return out.getvalue()
