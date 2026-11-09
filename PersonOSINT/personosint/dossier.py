"""Word-Export: Personen-Dossier, Verbindungsgrafik und Vermissten-Suchplakat."""
from __future__ import annotations

import io
import math
import os
from datetime import datetime
from typing import Any

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont

from . import graph as g
from .service import IDENTIFIER_KINDS, MISSING_FIELDS, PERSON_FIELDS, Platform

TYPE_COLORS = {
    "person": (37, 99, 235), "organisation": (124, 58, 237), "ort": (5, 150, 105), "konto": (234, 88, 12),
    "telefon": (219, 39, 119), "email": (202, 138, 4), "fahrzeug": (71, 85, 105), "ereignis": (220, 38, 38),
    "dokument": (100, 116, 139), "sonstiges": (148, 163, 184),
}
NAVY = RGBColor(0x0F, 0x2A, 0x4A)
GREY = RGBColor(0x55, 0x60, 0x6E)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for path in (f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",
                 f"C:/Windows/Fonts/{'arialbd' if bold else 'arial'}.ttf",
                 f"/System/Library/Fonts/Supplemental/Arial{' Bold' if bold else ''}.ttf"):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def render_graph_png(graph: dict[str, Any], highlight: set[int] | None = None, width: int = 1600, height: int = 1100) -> bytes:
    nodes = graph["nodes"]
    ids = [n["id"] for n in nodes]
    adj = g.adjacency(ids, [{"source_id": e["source"], "target_id": e["target"]} for e in graph["edges"]])
    pos = g.force_layout(ids, adj, width, height, iterations=250 if len(ids) < 120 else 80)
    img = Image.new("RGB", (width, height), (255, 255, 255))
    d = ImageDraw.Draw(img)
    f_label, f_small, f_bold = _font(20), _font(15), _font(22, True)
    for e in graph["edges"]:
        if e["source"] not in pos or e["target"] not in pos:
            continue
        (x1, y1), (x2, y2) = pos[e["source"]], pos[e["target"]]
        conf = e["confidence"]
        col = (148, 163, 184) if conf >= 50 else (203, 213, 225)
        w = 2 + int(conf / 30)
        if conf < 50:  # gestrichelt = unsicher
            segs = max(1, int(math.hypot(x2 - x1, y2 - y1) / 14))
            for i in range(0, segs, 2):
                a, b = i / segs, min(1, (i + 1) / segs)
                d.line([(x1 + (x2 - x1) * a, y1 + (y2 - y1) * a), (x1 + (x2 - x1) * b, y1 + (y2 - y1) * b)], fill=col, width=w)
        else:
            d.line([(x1, y1), (x2, y2)], fill=col, width=w)
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        txt = e["relation"][:28]
        bb = d.textbbox((mx, my), txt, font=f_small, anchor="mm")
        d.rectangle([bb[0] - 3, bb[1] - 2, bb[2] + 3, bb[3] + 2], fill=(255, 255, 255))
        d.text((mx, my), txt, fill=(71, 85, 105), font=f_small, anchor="mm")
    for n in nodes:
        x, y = pos[n["id"]]
        r = 16 + min(22, n["degree"] * 3) + (10 if n["subject"] else 0)
        col = TYPE_COLORS.get(n["type"], (148, 163, 184))
        if highlight and n["id"] in highlight:
            d.ellipse([x - r - 7, y - r - 7, x + r + 7, y + r + 7], fill=(250, 204, 21))
        d.ellipse([x - r, y - r, x + r, y + r], fill=col, outline=(15, 23, 42) if n["subject"] else (255, 255, 255), width=4 if n["subject"] else 2)
        label = n["label"] if len(n["label"]) <= 34 else n["label"][:32] + "…"
        font = f_bold if n["subject"] else f_label
        bb = d.textbbox((x, y + r + 16), label, font=font, anchor="mm")
        d.rectangle([bb[0] - 4, bb[1] - 2, bb[2] + 4, bb[3] + 2], fill=(255, 255, 255))
        d.text((x, y + r + 16), label, fill=(15, 23, 42), font=font, anchor="mm")
    # Legende
    types = sorted({n["type"] for n in nodes})
    lx, ly = 20, 20
    for t in types:
        d.ellipse([lx, ly, lx + 18, ly + 18], fill=TYPE_COLORS.get(t, (148, 163, 184)))
        d.text((lx + 26, ly + 9), next(n["type_label"] for n in nodes if n["type"] == t), fill=(51, 65, 85), font=f_small, anchor="lm")
        ly += 26
    d.text((lx, ly + 6), "– – unsichere Verbindung (< 50 %)", fill=(100, 116, 139), font=f_small)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


# --------------------------------------------------------------------------- docx helpers

def _shade(cell, hex_color: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tc_pr.append(shd)


def _table(doc, headers: list[str], rows: list[list[Any]], widths: list[float] | None = None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        c.text = ""
        run = c.paragraphs[0].add_run(h)
        run.bold = True
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        _shade(c, "0F2A4A")
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            run = cells[i].paragraphs[0].add_run("" if v is None else str(v))
            run.font.size = Pt(9)
            if ri % 2:
                _shade(cells[i], "F1F5F9")
    if widths:
        t.autofit = False
        for i, w in enumerate(widths):
            t.columns[i].width = Cm(w)
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    doc.add_paragraph()
    return t


def _kv(doc, pairs: list[tuple[str, Any]]) -> None:
    pairs = [(k, v) for k, v in pairs if v not in (None, "", [])]
    if not pairs:
        doc.add_paragraph("Keine Angaben erfasst.").runs[0].italic = True
        return
    t = doc.add_table(rows=0, cols=2)
    t.style = "Table Grid"
    t.autofit = False
    for k, v in pairs:
        cells = t.add_row().cells
        cells[0].text = ""
        r = cells[0].paragraphs[0].add_run(k)
        r.bold = True
        r.font.size = Pt(9)
        _shade(cells[0], "E2E8F0")
        cells[1].text = ""
        cells[1].paragraphs[0].add_run(", ".join(v) if isinstance(v, list) else str(v)).font.size = Pt(9)
        cells[0].width, cells[1].width = Cm(5), Cm(11.5)
    doc.add_paragraph()


def _hyperlink(paragraph, url: str, text: str) -> None:
    part = paragraph.part
    r_id = part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), r_id)
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "1D4ED8")
    u = OxmlElement("w:u")
    u.set(qn("w:val"), "single")
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), "17")
    rpr.extend([color, u, sz])
    run.append(rpr)
    t = OxmlElement("w:t")
    t.text = text
    t.set(qn("xml:space"), "preserve")
    run.append(t)
    link.append(run)
    paragraph._p.append(link)


def scrub_and_mark(doc: Document, p: Platform, case: dict[str, Any], export_id: str, kind: str) -> None:
    """OPSEC: Dokument-Metadaten neutralisieren und Export-Kennung als Wasserzeichen in die Fußzeile setzen."""
    from . import opsec as ops
    from .service import current_user

    lv = ops.level(case.get("opsec_level"))
    cp = doc.core_properties
    now = datetime.now()
    cp.author = cp.last_modified_by = ""
    cp.comments = cp.keywords = cp.subject = cp.category = cp.content_status = ""
    cp.title = case["codename"] if lv.codename and case.get("codename") else kind
    cp.created = cp.modified = now
    cp.revision = 1
    if not export_id:
        return
    user = current_user.get()
    for sec in doc.sections:
        fp = sec.footer.add_paragraph()
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = fp.add_run(f"Export-ID {export_id} · {user['display_name'] if user else 'System'} · {now:%d.%m.%Y %H:%M}"
                         + (f" · OPSEC-Stufe {lv.key} „{lv.name}“ – Weitergabe nur an das Fallteam" if lv.key >= 2 else ""))
        run.font.size = Pt(7)
        run.font.color.rgb = GREY


def _base_document(title: str, reference: str) -> Document:
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(10.5)
    for name, size in (("Heading 1", 16), ("Heading 2", 13), ("Heading 3", 11)):
        doc.styles[name].font.color.rgb = NAVY
        doc.styles[name].font.size = Pt(size)
    sec = doc.sections[0]
    sec.top_margin = sec.bottom_margin = Cm(2)
    sec.left_margin = sec.right_margin = Cm(2.2)
    hp = sec.header.paragraphs[0]
    hp.text = f"VERTRAULICH · {reference} · {title}"
    hp.runs[0].font.size = Pt(8)
    hp.runs[0].font.color.rgb = GREY
    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = fp.add_run("EagleEye PersonOSINT · Seite ")
    run.font.size = Pt(8)
    for code in ("PAGE",):
        r = fp.add_run()
        r.font.size = Pt(8)
        b, instr, e = OxmlElement("w:fldChar"), OxmlElement("w:instrText"), OxmlElement("w:fldChar")
        b.set(qn("w:fldCharType"), "begin")
        instr.text = code
        e.set(qn("w:fldCharType"), "end")
        r._r.extend([b, instr, e])
    return doc


def _fmt_ts(ts: str | None) -> str:
    if not ts:
        return ""
    try:
        return datetime.fromisoformat(ts).astimezone().strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return ts


# --------------------------------------------------------------------------- Dossier

def build_dossier(p: Platform, case_id: int, options: dict[str, Any] | None = None, export_id: str = "") -> bytes:
    opts = {"include_unreviewed": False, "include_audit": True, "include_graph": True, "include_links": False, **(options or {})}
    ov = p.overview(case_id)
    case, subj = ov["case"], ov["subject"]
    persons = [e for e in p.list_entities(case_id) if e["type"] == "person"]
    findings = p.list_findings(case_id)
    confirmed = [f for f in findings if f["status"] == "bestätigt"]
    unreviewed = [f for f in findings if f["status"] == "neu"]
    rejected = [f for f in findings if f["status"] == "verworfen"]
    links = p.list_links(case_id)
    graph = p.graph(case_id)
    events = p.list_events(case_id)
    tasks = p.list_tasks(case_id)
    missing = case["case_type"] == "vermisst"
    name = subj["label"] if subj else case["title"]

    from . import opsec as ops

    lv = ops.level(case.get("opsec_level"))
    doc = _base_document(case["codename"] if lv.codename and case.get("codename") else name, case["reference"])
    # ---- Deckblatt
    for _ in range(3):
        doc.add_paragraph()
    p0 = doc.add_paragraph()
    r = p0.add_run("VERTRAULICH – NUR FÜR DEN DIENSTGEBRAUCH" + (f" · OPSEC-STUFE {lv.key} ({lv.name.upper()})" if lv.key >= 2 else ""))
    r.bold, r.font.size, r.font.color.rgb = True, Pt(10), RGBColor(0xB9, 0x1C, 0x1C)
    p1 = doc.add_paragraph()
    r = p1.add_run("Vermisstendossier" if missing else "Recherchedossier" if case["case_type"] == "investigativ" else "Personendossier")
    r.font.size, r.font.color.rgb = Pt(14), GREY
    p2 = doc.add_paragraph()
    r = p2.add_run(name)
    r.bold, r.font.size, r.font.color.rgb = True, Pt(30), NAVY
    if case["status"] not in {"freigegeben", "abgeschlossen", "archiviert"}:
        pd = doc.add_paragraph()
        rd = pd.add_run("ENTWURF – noch nicht im Vier-Augen-Verfahren freigegeben")
        rd.bold, rd.font.size, rd.font.color.rgb = True, Pt(11), RGBColor(0xB4, 0x53, 0x09)
    if subj and subj["photo"]:
        photo = p.photo_bytes(case_id, subj["id"])
        if photo:
            doc.add_picture(io.BytesIO(photo[0]), width=Cm(5.5))
    doc.add_paragraph()
    team = p.case_team(case)
    _kv(doc, [("Aktenzeichen (intern)", case["reference"]), ("Deckname", case.get("codename")), ("Export-ID", export_id),
              ("Fall", case["title"]), ("Fallart", case["case_type_label"]),
              ("Status", case["status"]), ("Auftraggeber", case["client"]),
              ("Bearbeitung", (team["owner"] or {}).get("display_name") or case["analyst"]),
              ("Prüfung (Vier-Augen)", (team["reviewer"] or {}).get("display_name")),
              ("Erstellt am", datetime.now().strftime("%d.%m.%Y %H:%M")),
              ("Inhalt", "Nur geprüfte Erkenntnisse" if not opts["include_unreviewed"] else "Geprüfte und ungeprüfte Erkenntnisse (gekennzeichnet)")])
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # ---- 1 Zusammenfassung
    doc.add_heading("1  Zusammenfassung", 1)
    c = ov["counts"]
    summary = (f"Dieses Dossier fasst die Recherche zu {name} zusammen. Es wurden {c['searches']} Quellensuchen durchgeführt; "
               f"{c['confirmed']} Erkenntnisse wurden bestätigt, {c['rejected']} verworfen und {c['open_findings']} sind noch ungeprüft. "
               f"Das Verbindungsnetz umfasst {len(graph['nodes'])} Einträge und {len(graph['edges'])} Verbindungen.")
    doc.add_paragraph(summary)
    if subj and missing:
        risk = subj.get("risk") or {}
        par = doc.add_paragraph()
        rr = par.add_run(f"Gefährdungseinschätzung: {risk.get('level', 'n. b.').upper()}  ")
        rr.bold = True
        rr.font.color.rgb = RGBColor(0xB9, 0x1C, 0x1C) if risk.get("level") == "hoch" else RGBColor(0xB4, 0x53, 0x09) if risk.get("level") == "erhöht" else NAVY
        par.add_run(risk.get("advice", ""))
    kf = []
    if subj:
        acc = [l for l in links if l["source_id"] == subj["id"] and l["relation"] == "besitzt Konto"]
        kf.append(f"{len(acc)} bestätigte Online-Konten")
        orgs = [l["target_label"] for l in links if l["source_id"] == subj["id"] and l["target_type"] == "organisation"]
        if orgs:
            kf.append("Organisationen: " + ", ".join(sorted(set(orgs))[:5]))
    if graph["key_nodes"]:
        kf.append("Zentrale Akteure im Netzwerk: " + ", ".join(n["label"] for n in graph["key_nodes"][:3]))
    if events:
        last = events[-1]
        kf.append(f"Letzter Eintrag der Zeitleiste: {last['occurred_at']} – {last['kind']} {('in ' + last['location']) if last['location'] else ''}")
    for k in kf:
        doc.add_paragraph(k, style="List Bullet")

    # ---- 2 Auftrag
    doc.add_heading("2  Auftrag, Zweck und Rechtsgrundlage", 1)
    _kv(doc, [("Zweck der Recherche", case["purpose"]), ("Rechtsgrundlage / Auftrag", case["legal_basis"]), ("Hinweise", case["notes"])])

    # ---- 3 Profil
    doc.add_heading("3  Personenprofil", 1)
    if subj:
        data = subj["data"] or {}
        pairs = [("Name", subj["label"])]
        if subj.get("risk", {}).get("age") is not None:
            pairs.append(("Alter", f"{subj['risk']['age']} Jahre"))
        pairs += [(label, data.get(key)) for key, label in PERSON_FIELDS]
        _kv(doc, pairs)
        doc.add_heading("Identifikatoren", 2)
        _table(doc, ["Art", "Wert", "Herkunft", "Geprüft"],
               [[IDENTIFIER_KINDS.get(i["kind"], i["kind"]), i["value"], i["source"], "ja" if i["verified"] else "nein"] for i in subj["identifiers"]],
               [3.5, 7, 4, 2])
    else:
        doc.add_paragraph("Keine Zielperson erfasst.")

    sec = 4
    if missing and subj:
        doc.add_heading(f"{sec}  Vermisstenangaben", 1)
        data = subj["data"] or {}
        _kv(doc, [(label, data.get(key)) for key, label in MISSING_FIELDS])
        risk = subj.get("risk") or {}
        doc.add_heading("Gefährdungseinschätzung", 2)
        doc.add_paragraph(f"Stufe: {risk.get('level', 'n. b.')} ({risk.get('points', 0)} Punkte). {risk.get('advice', '')}")
        for f in risk.get("factors", []):
            doc.add_paragraph(f"{f['label']} (Gewicht {f['weight']})", style="List Bullet")
        sec += 1

    # ---- Zeitleiste
    doc.add_heading(f"{sec}  Zeitleiste", 1)
    if events:
        _table(doc, ["Zeitpunkt", "Art", "Ort", "Beschreibung", "Quelle / Verlässlichkeit"],
               [[e["occurred_at"].replace("T", " "), e["kind"], e["location"], e["description"], f"{e['source']} · {e['reliability']}"] for e in events],
               [2.8, 2.6, 3.2, 5.2, 3])
    else:
        doc.add_paragraph("Keine Ereignisse erfasst.")
    sec += 1

    # ---- Verbindungen
    doc.add_heading(f"{sec}  Verbindungen und Netzwerk", 1)
    if graph["nodes"] and opts["include_graph"]:
        png = render_graph_png(graph, highlight={subj["id"]} if subj else None)
        doc.add_picture(io.BytesIO(png), width=Cm(16.5))
        cap = doc.add_paragraph(f"Abbildung 1: Verbindungsnetz ({len(graph['nodes'])} Einträge, {len(graph['edges'])} Verbindungen). "
                                "Knotengröße = Anzahl Verbindungen; gestrichelt = Sicherheit unter 50 %.")
        cap.runs[0].italic = True
        cap.runs[0].font.size = Pt(8.5)
    if graph["key_nodes"]:
        doc.add_heading("Schlüsselakteure", 2)
        _table(doc, ["Eintrag", "Verbindungen", "Vermittlerrolle (Betweenness)"],
               [[n["label"], n["degree"], f"{n['betweenness']:.2f}"] for n in graph["key_nodes"]], [8, 3.5, 5])
    if links:
        doc.add_heading("Alle Verbindungen", 2)
        _table(doc, ["Von", "Beziehung", "Zu", "Sicherheit", "Beleg"],
               [[l["source_label"], l["relation"], l["target_label"], f"{l['confidence']} %", (l["evidence"] or l["note"])[:120]] for l in links],
               [3.6, 3, 3.6, 1.8, 4.8])
    else:
        doc.add_paragraph("Noch keine Verbindungen erfasst.")
    others = [x for x in persons if not subj or x["id"] != subj["id"]]
    if others:
        doc.add_heading("Weitere Personen im Fall", 2)
        _table(doc, ["Name", "Identifikatoren", "Notizen"],
               [[o["label"], ", ".join(i["value"] for i in o["identifiers"] if i["kind"] != "name")[:150], (o["data"] or {}).get("notizen", "")] for o in others],
               [4.5, 7, 5])
    sec += 1

    # ---- Erkenntnisse
    doc.add_heading(f"{sec}  Bestätigte Erkenntnisse", 1)
    sources: list[tuple[str, str]] = []

    def cite(url: str, title: str) -> str:
        if not url:
            return ""
        for i, (u, _) in enumerate(sources):
            if u == url:
                return f"[{i + 1}]"
        sources.append((url, title))
        return f"[{len(sources)}]"

    if confirmed:
        by_cat: dict[str, list] = {}
        for f in confirmed:
            by_cat.setdefault(f["category"] or "Sonstiges", []).append(f)
        for cat, items in sorted(by_cat.items()):
            doc.add_heading(cat, 2)
            _table(doc, ["Erkenntnis", "Quelle", "Bewertung", "Prüfnotiz", "Beleg"],
                   [[f["title"] + (f"\n{f['snippet'][:180]}" if f["snippet"] else ""), f["source"], f"{f['score']} ({f['confidence']})",
                     f["review_note"], cite(f["url"], f["title"])] for f in items], [6.2, 2.8, 2.2, 3.6, 1.6])
    else:
        doc.add_paragraph("Es liegen noch keine bestätigten Erkenntnisse vor.")
    sec += 1
    if opts["include_unreviewed"] and unreviewed:
        doc.add_heading(f"{sec}  Ungeprüfte Hinweise (nicht verifiziert!)", 1)
        doc.add_paragraph("Die folgenden Treffer wurden automatisch gefunden, aber noch nicht geprüft. Sie dürfen nicht als Tatsachen verwendet werden.")
        _table(doc, ["Treffer", "Quelle", "Score", "Begründung", "Beleg"],
               [[f["title"], f["source"], f["score"], "; ".join(f["reasons"] or [])[:160], cite(f["url"], f["title"])] for f in unreviewed[:80]],
               [5.5, 2.8, 1.4, 5, 1.6])
        sec += 1

    # ---- Offene Punkte
    doc.add_heading(f"{sec}  Offene Punkte und nächste Schritte", 1)
    open_tasks = [t for t in tasks if not t["done"]]
    if unreviewed:
        doc.add_paragraph(f"{len(unreviewed)} Treffer sind noch ungeprüft.", style="List Bullet")
    for t in open_tasks:
        doc.add_paragraph(f"{t['title']}" + (" (hohe Priorität)" if t["priority"] == "hoch" else ""), style="List Bullet")
    sug = p.suggestions(case_id)[:10]
    if sug:
        doc.add_heading("Ungeprüfte Verbindungshinweise", 2)
        for s in sug:
            doc.add_paragraph(f"{s['source_label']} ↔ {s['target_label']}: {s['reason']}", style="List Bullet")
    if not (unreviewed or open_tasks or sug):
        doc.add_paragraph("Keine offenen Punkte.")
    sec += 1

    # ---- Quellen
    doc.add_heading(f"{sec}  Quellenverzeichnis", 1)
    if sources:
        for i, (url, title) in enumerate(sources, 1):
            par = doc.add_paragraph(f"[{i}] {title[:120]} – ")
            par.runs[0].font.size = Pt(8.5)
            _hyperlink(par, url, url[:110])
    else:
        doc.add_paragraph("Keine verlinkten Quellen.")
    sec += 1

    # ---- Methodik
    doc.add_heading(f"{sec}  Methodik, Qualität und Hinweise", 1)
    for txt in (
        "Es wurden ausschließlich öffentlich zugängliche Quellen ohne Umgehung von Zugangsbeschränkungen abgefragt.",
        "Automatisch gefundene Treffer sind Kandidaten. Nur durch einen Menschen bestätigte Erkenntnisse gelten als belegt.",
        "Gleiche Namen oder Benutzernamen beweisen keine Identität. Die Bewertung (Score) gibt nur Hinweise auf Übereinstimmungen.",
        "Personenbezogene Daten sind nach DSGVO zu behandeln: Zweckbindung, Datenminimierung, Löschung nach Abschluss.",
        f"Bewertung der Erkenntnisse: {len(confirmed)} bestätigt, {len(rejected)} verworfen, {len(unreviewed)} ungeprüft.",
    ):
        doc.add_paragraph(txt, style="List Bullet")
    if opts["include_audit"]:
        doc.add_heading("Bearbeitungsprotokoll (Auszug)", 2)
        _table(doc, ["Zeit", "Aktion", "Details"], [[_fmt_ts(a["ts"]), a["action"], a["detail"][:160]] for a in p.audit(case_id)[:60]], [3, 4, 9.5])
    scrub_and_mark(doc, p, case, export_id, "Dossier")
    p.log(case_id, "Dossier exportiert", f"Word-Dossier ({'inkl.' if opts['include_unreviewed'] else 'ohne'} ungeprüfte Treffer)"
          + (f" · {export_id}" if export_id else ""))
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def build_poster(p: Platform, case_id: int, export_id: str = "") -> bytes:
    """Einseitiges Vermissten-Suchplakat (Word, DIN A4)."""
    case = p.get_case(case_id)
    subj = p.subject(case_id)
    if not subj:
        raise ValueError("Keine Zielperson erfasst.")
    data = subj["data"] or {}
    doc = Document()
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.PORTRAIT
    sec.top_margin = sec.bottom_margin = Cm(1.5)
    sec.left_margin = sec.right_margin = Cm(1.8)
    doc.styles["Normal"].font.name = "Calibri"
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = t.add_run("VERMISST")
    r.bold, r.font.size, r.font.color.rgb = True, Pt(60), RGBColor(0xB9, 0x1C, 0x1C)
    n = doc.add_paragraph()
    n.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = n.add_run(subj["label"])
    r.bold, r.font.size = True, Pt(30)
    age = subj.get("risk", {}).get("age")
    if age is not None:
        a = doc.add_paragraph()
        a.alignment = WD_ALIGN_PARAGRAPH.CENTER
        a.add_run(f"{age} Jahre").font.size = Pt(16)
    photo = p.photo_bytes(case_id, subj["id"])
    if photo:
        doc.add_picture(io.BytesIO(photo[0]), height=Cm(9))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    else:
        ph = doc.add_paragraph("[ Foto einfügen ]")
        ph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    seen = doc.add_paragraph()
    seen.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rr = seen.add_run("Zuletzt gesehen: " + " · ".join(x for x in [data.get("zuletzt_gesehen_zeit") or data.get("vermisst_seit"), data.get("zuletzt_gesehen_ort")] if x))
    rr.bold, rr.font.size = True, Pt(15)
    pairs = [("Größe", data.get("groesse")), ("Statur", data.get("statur")), ("Haare", data.get("haare")), ("Augen", data.get("augen")),
             ("Besondere Merkmale", data.get("merkmale")), ("Kleidung", data.get("kleidung")), ("Mitgeführt", data.get("mitgefuehrt"))]
    pairs = [(k, v) for k, v in pairs if v]
    if pairs:
        tbl = doc.add_table(rows=0, cols=2)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        for k, v in pairs:
            c = tbl.add_row().cells
            c[0].text, c[1].text = "", ""
            k_run = c[0].paragraphs[0].add_run(k)
            k_run.bold, k_run.font.size = True, Pt(12)
            c[1].paragraphs[0].add_run(str(v)).font.size = Pt(12)
            c[0].width, c[1].width = Cm(4.5), Cm(12)
    doc.add_paragraph()
    box = doc.add_paragraph()
    box.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = box.add_run("Hinweise bitte an die Polizei – Notruf 110 – oder jede Polizeidienststelle")
    r.bold, r.font.size = True, Pt(15)
    extra = " · ".join(x for x in [data.get("polizei_dienststelle"), data.get("aktenzeichen") and f"Az. {data['aktenzeichen']}", data.get("kontakt_hinweise")] if x)
    if extra:
        e = doc.add_paragraph(extra)
        e.alignment = WD_ALIGN_PARAGRAPH.CENTER
    foot = doc.add_paragraph(f"Stand: {datetime.now():%d.%m.%Y} · Bitte nur in Abstimmung mit Angehörigen und Polizei verbreiten.")
    foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
    foot.runs[0].font.size = Pt(8)
    scrub_and_mark(doc, p, case, "", "Suchplakat")  # Plakat ist zur Veröffentlichung gedacht: keine personenbezogene Export-Kennung
    p.log(case_id, "Suchplakat exportiert", subj["label"] + (f" · {export_id}" if export_id else ""))
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def safe_filename(text: str) -> str:
    keep = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in text)
    return keep.strip("_")[:60] or "dossier"

