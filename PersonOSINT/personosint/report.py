"""Schritt 3 – Top-Dossier: Vorlagen, Management Summary, Belegdichte, Fußnoten mit Admiralty-Code und Beleg-Hash.

Aufbau: ``collect`` sammelt alle Daten eines Falls in einem Modell; jede Kapitel-Funktion kann daraus
entweder nur zählen (Vorschau der Belegdichte) oder in ein Word-Dokument schreiben.
"""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.shared import Cm, Pt, RGBColor

from . import opsec as ops
from .dossier import GREY, _base_document, _fmt_ts, _hyperlink, _kv, _table, render_graph_png, scrub_and_mark
from .service import IDENTIFIER_KINDS, MISSING_FIELDS, PERSON_FIELDS

TEMPLATES: dict[str, dict[str, Any]] = {
    "volldossier": {"label": "Volldossier", "description": "Alle Kapitel – für Akte, Redaktion oder Auftraggeber mit vollem Informationsbedarf.",
                    "sections": ["summary", "auftrag", "identitaet", "lebenslauf", "familie", "wirtschaft", "online", "netzwerk", "risiko",
                                 "widersprueche", "erkenntnisse", "offene_punkte", "quellen", "methodik", "protokoll"]},
    "kurzprofil": {"label": "Kurzprofil (2 Seiten)", "description": "Management Summary, Identität, Wirtschaft, Auffälligkeiten – für den schnellen Überblick.",
                   "sections": ["summary", "identitaet", "wirtschaft", "risiko", "quellen"]},
    "due_diligence": {"label": "Due-Diligence-Bericht", "description": "Geschäftspartner-/Hintergrundprüfung: Verflechtungen, Red Flags, Widersprüche.",
                      "sections": ["summary", "auftrag", "identitaet", "wirtschaft", "netzwerk", "risiko", "widersprueche", "offene_punkte", "quellen", "methodik"]},
    "vermisst": {"label": "Vermisstendossier", "description": "Vermisstenangaben, Gefährdung, Zeitleiste, Umfeld und Hinweise.",
                 "sections": ["summary", "auftrag", "identitaet", "vermisst", "zeitleiste", "netzwerk", "familie", "erkenntnisse", "offene_punkte",
                              "quellen", "methodik", "protokoll"]},
}

SECTION_LABELS = {
    "summary": "Management Summary", "auftrag": "Auftrag, Zweck und Rechtsgrundlage", "identitaet": "Identität",
    "lebenslauf": "Lebenslauf und Zeitachse", "familie": "Familie und Umfeld", "wirtschaft": "Beruf und wirtschaftliche Verflechtungen",
    "online": "Online-Präsenz und Technik", "netzwerk": "Verbindungen und Netzwerk", "risiko": "Auffälligkeiten (Red Flags)",
    "widersprueche": "Widersprüche und offene Identitätsfragen", "vermisst": "Vermisstenangaben", "zeitleiste": "Zeitleiste",
    "erkenntnisse": "Weitere bestätigte Erkenntnisse", "offene_punkte": "Offene Punkte und nächste Schritte", "quellen": "Quellenverzeichnis",
    "methodik": "Methodik, Bewertung und Hinweise", "protokoll": "Bearbeitungsprotokoll (Auszug)",
}
SEV_LABEL = {"hoch": "HOCH", "mittel": "mittel", "niedrig": "niedrig"}


def default_template(case: dict[str, Any]) -> str:
    return "vermisst" if case["case_type"] == "vermisst" else "volldossier"


# --------------------------------------------------------------------------- Datenmodell

class Ctx:
    def __init__(self, p, case_id: int, opts: dict[str, Any]):
        self.p, self.opts = p, opts
        ov = p.overview(case_id)
        self.case, self.subject, self.counts = ov["case"], ov["subject"], ov["counts"]
        self.team = ov["team"]
        self.lv = ops.level(self.case.get("opsec_level"))
        asm = p.assessment(case_id)
        self.redflags, self.contradictions, self.legend = asm["redflags"], asm["contradictions"], asm["legend"]
        allowed = {"bestätigt"} | ({"neu"} if opts.get("include_unreviewed") else set())
        self.facts = [f for f in asm["facts"] if f["status"] in allowed]
        self.findings = p.list_findings(case_id)
        self.evidence = p.db.all("SELECT * FROM evidence WHERE case_id = ? ORDER BY id", (case_id,))
        self.ev_finding = defaultdict(list)
        self.ev_fact = defaultdict(list)
        self.ev_url = {}
        for e in self.evidence:
            if e["finding_id"]:
                self.ev_finding[e["finding_id"]].append(e)
            if e["fact_id"]:
                self.ev_fact[e["fact_id"]].append(e)
            self.ev_url.setdefault(e["url"], e)
        self.graph = p.graph(case_id)
        self.links = p.list_links(case_id)
        self.events = p.list_events(case_id)
        self.tasks = p.list_tasks(case_id)
        self.groups = [g for g in (p.candidates(case_id, self.subject["id"]) if self.subject else []) if g["kind"] == "kandidat"]
        self.branding = p.branding()
        self.ai = p.approved_ai_summary(case_id) if hasattr(p, "approved_ai_summary") else None
        self.cites: list[dict[str, Any]] = []
        self._cite_idx: dict[str, int] = {}
        self.stats: dict[str, tuple[int, int]] = {}

    # ---- Belege
    def evidence_for(self, f: dict[str, Any]) -> dict[str, Any] | None:
        if self.ev_fact.get(f["id"]):
            return self.ev_fact[f["id"]][0]
        if f.get("finding_id") and self.ev_finding.get(f["finding_id"]):
            return self.ev_finding[f["finding_id"]][0]
        return self.ev_url.get(f.get("source_url") or "")

    def belegt(self, f: dict[str, Any]) -> bool:
        return f["credibility_final"] <= 2 or self.evidence_for(f) is not None

    def cite(self, url: str, title: str, retrieved: str = "", reliability: str = "", ev: dict[str, Any] | None = None) -> str:
        key = url or title
        if not key:
            return ""
        if key not in self._cite_idx:
            ev = ev or self.ev_url.get(url)
            self.cites.append({"url": url, "title": title, "retrieved": retrieved, "reliability": reliability,
                               "sha": ev["sha256"] if ev else "", "archive": ev["archive_url"] if ev else "", "evidence_id": ev["id"] if ev else None})
            self._cite_idx[key] = len(self.cites)
        return f"[{self._cite_idx[key]}]"

    def cite_fact(self, f: dict[str, Any]) -> str:
        return self.cite(f.get("source_url") or "", f["source_label"], f["retrieved_at"], f["reliability"], self.evidence_for(f))

    def facts_in(self, category: str) -> list[dict[str, Any]]:
        return [f for f in self.facts if f["category"] == category]


# --------------------------------------------------------------------------- Bausteine

def _density_line(doc, total: int, ok: int) -> None:
    if not total:
        return
    pct = round(100 * ok / total)
    par = doc.add_paragraph()
    r = par.add_run(f"Belegdichte: {pct} % – {ok} von {total} Aussagen mehrfach belegt, aus zuverlässiger Quelle bestätigt oder gesichert.")
    r.italic = True
    r.font.size = Pt(8.5)
    r.font.color.rgb = RGBColor(0x06, 0x5F, 0x46) if pct >= 75 else RGBColor(0xB4, 0x53, 0x09) if pct >= 50 else RGBColor(0xB9, 0x1C, 0x1C)


def _facts_table(ctx: Ctx, doc, facts: list[dict[str, Any]], show_subject: bool = True) -> tuple[int, int]:
    total, ok = len(facts), sum(1 for f in facts if ctx.belegt(f))
    if doc is None or not facts:
        return total, ok
    rows = []
    for f in facts:
        val = f["object_label"] + (f" ({f['data']['rolle']})" if (f.get("data") or {}).get("rolle") else "")
        if f["status"] != "bestätigt":
            val += " (ungeprüft)"
        period = " – ".join(x for x in [f["valid_from"], f["valid_to"]] if x) if (f["valid_from"] or f["valid_to"]) else ""
        row = ([f["subject_label"]] if show_subject else []) + [f["predicate_label"], val, period, f["code"] + (f" · {f['corroboration']} Q." if f["corroboration"] >= 2 else ""), ctx.cite_fact(f)]
        rows.append(row)
    headers = (["Wer"] if show_subject else []) + ["Aussage", "Wert", "Zeitraum", "Bewertung", "Beleg"]
    widths = ([3.0] if show_subject else []) + [3.0, 4.9, 2.6, 2.3, 1.2]
    _table(doc, headers, rows, widths)
    return total, ok


def _bullet(doc, text: str) -> None:
    doc.add_paragraph(text, style="List Bullet")


# --------------------------------------------------------------------------- Kapitel

def sec_summary(ctx: Ctx, doc) -> tuple[int, int]:
    facts = ctx.facts
    by_pred = defaultdict(list)
    for f in facts:
        by_pred[f["predicate"]].append(f)
    key: list[tuple[str, list[dict]]] = []
    name = ctx.subject["label"] if ctx.subject else ctx.case["title"]
    best = lambda pred: sorted(by_pred.get(pred, []), key=lambda f: (f["credibility_final"], -f["corroboration"]))  # noqa: E731
    ident = [x for x in (best("geburtsdatum")[:1] + best("staatsangehoerigkeit")[:1] + best("adresse")[:1])]
    if ident:
        key.append((f"{name}: " + "; ".join(f"{f['predicate_label']} {f['object_label']}" for f in ident), ident))
    roles = by_pred.get("funktion_bei", []) + by_pred.get("arbeitet_bei", [])
    if roles:
        current = [f for f in roles if not f["valid_to"]]
        orgs = {f["object_label"] for f in roles}
        txt = f"{len(roles)} belegte berufliche Funktionen in {len(orgs)} Organisationen"
        if current:
            txt += "; aktuell u. a.: " + ", ".join(sorted({f["object_label"] for f in current})[:3])
        key.append((txt, sorted(roles, key=lambda f: f["credibility_final"])[:3]))
    fam = [f for f in facts if f["category"] == "Familie & Umfeld"]
    if fam:
        key.append(("Familie/Umfeld: " + ", ".join(f"{f['predicate_label']} {f['object_label']}" for f in fam[:4]), fam[:4]))
    online = [f for f in ctx.findings if f["status"] == "bestätigt" and f["category"] == "Konto"]
    if online:
        key.append((f"{len(online)} bestätigte Online-Konten (" + ", ".join(sorted({(f['data'] or {}).get('plattform') or f['source'] for f in online})[:5]) + ")", []))
    if ctx.graph["key_nodes"]:
        key.append(("Zentrale Akteure im Netzwerk: " + ", ".join(n["label"] for n in ctx.graph["key_nodes"][:3]), []))
    if ctx.case["case_type"] == "vermisst" and ctx.subject:
        d = ctx.subject.get("data") or {}
        risk = ctx.subject.get("risk") or {}
        key.append((f"Vermisst seit {d.get('vermisst_seit', '–')}, zuletzt gesehen {d.get('zuletzt_gesehen_zeit', '')} {d.get('zuletzt_gesehen_ort', '')}. "
                    f"Gefährdung: {risk.get('level', 'n. b.')}", []))
    total = sum(len(fs) for _, fs in key)
    ok = sum(1 for _, fs in key for f in fs if ctx.belegt(f))
    all_total = len(ctx.facts)
    all_ok = sum(1 for f in ctx.facts if ctx.belegt(f))
    if doc is None:
        return total, ok
    doc.add_paragraph(f"Gegenstand: {ctx.case['purpose']}")
    if ctx.ai:
        doc.add_heading("Zusammenfassung", 2)
        par = doc.add_paragraph(_resolve_ai_citations(ctx, ctx.ai["text"]))
        note = doc.add_paragraph(f"KI-gestützter Entwurf (lokales Modell {ctx.ai['model']}), geprüft und freigegeben von {ctx.ai['approved_by']} am {_fmt_ts(ctx.ai['approved_at'])}.")
        note.runs[0].italic = True
        note.runs[0].font.size = Pt(8)
        del par
    doc.add_heading("Kernaussagen", 2)
    if key:
        for text, fs in key:
            refs = " ".join(dict.fromkeys(ctx.cite_fact(f) for f in fs if f))
            codes = ", ".join(dict.fromkeys(f["code"] for f in fs))
            _bullet(doc, text + (f" ({codes}) {refs}" if fs else ""))
    else:
        doc.add_paragraph("Es liegen noch keine bestätigten Aussagen vor.")
    doc.add_heading("Auffälligkeiten", 2)
    if ctx.redflags:
        for r in ctx.redflags[:6]:
            _bullet(doc, f"[{SEV_LABEL.get(r['severity'], r['severity'])}] {r['label']}: {r['text']}" + ("" if r["confirmed"] else " (beruht auf ungeprüften Aussagen)"))
    else:
        doc.add_paragraph("Keine Auffälligkeiten nach den aktiven Prüfregeln.")
    doc.add_heading("Unsicherheiten", 2)
    unc = []
    if ctx.contradictions:
        unc.append(f"{len(ctx.contradictions)} Widerspruch/Widersprüche in den Angaben (siehe Kapitel Widersprüche).")
    if len(ctx.groups) > 1:
        unc.append(f"{len(ctx.groups)} mögliche Personen (Kandidatengruppen) sind noch nicht zugeordnet – Verwechslungsgefahr mit Namensvettern.")
    if ctx.counts["open_findings"]:
        unc.append(f"{ctx.counts['open_findings']} Treffer sind noch ungeprüft und nicht Teil dieses Dossiers.")
    for u in unc or ["Keine offenen Unsicherheiten erfasst."]:
        _bullet(doc, u)
    pct = round(100 * all_ok / all_total) if all_total else 0
    grade = "hoch" if pct >= 75 else "mittel" if pct >= 50 else "gering"
    par = doc.add_paragraph()
    r = par.add_run(f"Belegstärke insgesamt: {grade.upper()} ({pct} % von {all_total} Aussagen mehrfach belegt, aus zuverlässiger Quelle bestätigt oder gesichert).")
    r.bold = True
    return total, ok


def _resolve_ai_citations(ctx: Ctx, text: str) -> str:
    import re

    by_id = {f["id"]: f for f in ctx.facts}

    def repl(m):
        refs = []
        for fid in re.findall(r"\d+", m.group(0)):
            f = by_id.get(int(fid))
            if f:
                refs.append(ctx.cite_fact(f))
        return " ".join(dict.fromkeys(refs)) if refs else ""
    return re.sub(r"\[F\d+(?:\s*,\s*F?\d+)*\]", repl, text)


def sec_auftrag(ctx: Ctx, doc) -> tuple[int, int]:
    if doc is not None:
        c = ctx.case
        _kv(doc, [("Zweck der Recherche", c["purpose"]), ("Rechtsgrundlage / Auftrag", c["legal_basis"]), ("Auftraggeber / Redaktion", c["client"]),
                  ("Verantwortlich", (ctx.team["owner"] or {}).get("display_name")), ("Prüfung (Vier-Augen)", (ctx.team["reviewer"] or {}).get("display_name")),
                  ("Status", c["status"]), ("OPSEC-Stufe", f"{ctx.lv.key} – {ctx.lv.name}"), ("Löschfrist", c.get("retention_until")),
                  ("Auftragsprüfung", _mandate_text(c)), ("Hinweise", c["notes"])])
    return 0, 0


def _mandate_text(case: dict[str, Any]) -> str:
    import json

    raw = case.get("mandate_check") or ""
    if not raw:
        return "nicht dokumentiert"
    m = json.loads(raw)
    txt = f"durchgeführt von {m['checked_by']} am {_fmt_ts(m['checked_at'])}: "
    if m["warnings"]:
        return txt + f"{len(m['warnings'])} Warnsignal(e), angenommen mit Begründung: {m['override_reason']}"
    return txt + "keine Warnsignale"


def sec_identitaet(ctx: Ctx, doc) -> tuple[int, int]:
    facts = ctx.facts_in("Identität")
    if doc is not None and ctx.subject:
        data = ctx.subject.get("data") or {}
        doc.add_heading("Profil (Angaben im Fall)", 2)
        pairs = [("Name", ctx.subject["label"])]
        if (ctx.subject.get("risk") or {}).get("age") is not None:
            pairs.append(("Alter", f"{ctx.subject['risk']['age']} Jahre"))
        _kv(doc, pairs + [(label, data.get(key)) for key, label in PERSON_FIELDS if key != "notizen"])
        idents = [i for i in ctx.subject["identifiers"] if i["kind"] != "name"]
        if idents:
            _table(doc, ["Identifikator", "Wert", "Herkunft", "geprüft"],
                   [[IDENTIFIER_KINDS.get(i["kind"], i["kind"]), i["value"], i["source"], "ja" if i["verified"] else "nein"] for i in idents], [3.5, 7, 4, 2])
        if facts:
            doc.add_heading("Belegte Identitätsangaben", 2)
    return _facts_table(ctx, doc, facts)


def sec_lebenslauf(ctx: Ctx, doc) -> tuple[int, int]:
    dated = sorted([f for f in ctx.facts if f["valid_from"] or f["predicate"] == "geburtsdatum"],
                   key=lambda f: (f["valid_from"] or f["object_label"])[:10])
    total, ok = len(dated), sum(1 for f in dated if ctx.belegt(f))
    if doc is not None:
        if not dated:
            doc.add_paragraph("Keine datierten Aussagen vorhanden.")
            return 0, 0
        rows = []
        for f in dated:
            when = f["object_label"][:10] if f["predicate"] == "geburtsdatum" else f["valid_from"] + (f" – {f['valid_to']}" if f["valid_to"] else "")
            what = "Geburt" if f["predicate"] == "geburtsdatum" else f"{f['predicate_label']} {f['object_label']}" + (f" ({f['data']['rolle']})" if (f.get('data') or {}).get('rolle') else "")
            rows.append([when, f["subject_label"], what, f["code"], ctx.cite_fact(f)])
        _table(doc, ["Zeitraum", "Wer", "Ereignis", "Bewertung", "Beleg"], rows, [3.2, 3.2, 7, 1.8, 1.4])
    return total, ok


def sec_familie(ctx: Ctx, doc) -> tuple[int, int]:
    facts = ctx.facts_in("Familie & Umfeld")
    if doc is not None and not facts:
        doc.add_paragraph("Keine belegten Angaben zu Familie und Umfeld.")
    return _facts_table(ctx, doc, facts)


def sec_wirtschaft(ctx: Ctx, doc) -> tuple[int, int]:
    facts = ctx.facts_in("Beruf & Wirtschaft")
    if doc is not None:
        roles = [f for f in facts if f["predicate"] in {"funktion_bei", "arbeitet_bei"}]
        if roles:
            active = [f for f in roles if not f["valid_to"]]
            doc.add_paragraph(f"{len(roles)} Funktionen in {len({f['object_label'] for f in roles})} Organisationen, davon {len(active)} ohne bekanntes Ende.")
        if not facts:
            doc.add_paragraph("Keine belegten Angaben zu Beruf und wirtschaftlichen Verflechtungen.")
    return _facts_table(ctx, doc, facts)


def sec_online(ctx: Ctx, doc) -> tuple[int, int]:
    facts = ctx.facts_in("Online & Technik")
    accounts = [f for f in ctx.findings if f["status"] == "bestätigt" and f["category"] == "Konto"]
    if doc is not None:
        if accounts:
            doc.add_heading("Bestätigte Online-Konten", 2)
            _table(doc, ["Konto", "Quelle", "Prüfnotiz", "Beleg"],
                   [[f["title"], f["source"], f["review_note"], ctx.cite(f["url"], f["title"], f["created_at"], "", (ctx.ev_finding.get(f["id"]) or [None])[0])] for f in accounts],
                   [6.5, 3, 5, 1.5])
        if facts:
            doc.add_heading("Domains und technische Spuren", 2)
        if not facts and not accounts:
            doc.add_paragraph("Keine bestätigte Online-Präsenz.")
    t, o = _facts_table(ctx, doc, facts)
    acc_ok = sum(1 for f in accounts if ctx.ev_finding.get(f["id"]))
    return t + len(accounts), o + acc_ok


def sec_netzwerk(ctx: Ctx, doc) -> tuple[int, int]:
    if doc is None:
        return 0, 0
    g = ctx.graph
    if g["nodes"] and ctx.opts.get("include_graph", True):
        png = render_graph_png(g, highlight={ctx.subject["id"]} if ctx.subject else None)
        doc.add_picture(io.BytesIO(png), width=Cm(16.5))
        cap = doc.add_paragraph(f"Abbildung: Verbindungsnetz ({len(g['nodes'])} Einträge, {len(g['edges'])} Verbindungen). "
                                "Knotengröße = Anzahl Verbindungen; gestrichelt = Sicherheit unter 50 %.")
        cap.runs[0].italic = True
        cap.runs[0].font.size = Pt(8.5)
    if g["key_nodes"]:
        doc.add_heading("Schlüsselakteure", 2)
        _table(doc, ["Eintrag", "Verbindungen", "Vermittlerrolle"], [[n["label"], n["degree"], f"{n['betweenness']:.2f}"] for n in g["key_nodes"]], [8, 3.5, 5])
    if ctx.links:
        doc.add_heading("Verbindungen", 2)
        _table(doc, ["Von", "Beziehung", "Zu", "Sicherheit", "Beleg"],
               [[lk["source_label"], lk["relation"], lk["target_label"], f"{lk['confidence']} %", (lk["evidence"] or lk["note"])[:110]] for lk in ctx.links[:120]],
               [3.6, 3.2, 3.6, 1.8, 4.6])
    else:
        doc.add_paragraph("Noch keine Verbindungen erfasst.")
    return 0, 0


def sec_risiko(ctx: Ctx, doc) -> tuple[int, int]:
    facts = ctx.facts_in("Risiko")
    if doc is not None:
        if ctx.redflags:
            _table(doc, ["Schwere", "Regel", "Befund", "Status", "Quellen"],
                   [[SEV_LABEL.get(r["severity"], r["severity"]), r["label"], r["text"], "bestätigt" if r["confirmed"] else "ungeprüft", ", ".join(r["sources"])]
                    for r in ctx.redflags], [1.8, 3.8, 6.5, 2, 3])
            p = doc.add_paragraph("Red Flags sind regelbasierte Recherchehinweise und keine Bewertung oder Vorverurteilung der Person.")
            p.runs[0].italic = True
            p.runs[0].font.size = Pt(8.5)
        else:
            doc.add_paragraph("Keine Auffälligkeiten nach den aktiven Prüfregeln.")
        if facts:
            doc.add_heading("Zugrunde liegende Aussagen", 2)
    return _facts_table(ctx, doc, facts)


def sec_widersprueche(ctx: Ctx, doc) -> tuple[int, int]:
    if doc is None:
        return 0, 0
    if ctx.contradictions:
        for c in ctx.contradictions:
            _bullet(doc, f"{c['subject']} – {c['predicate_label']}: " + " / ".join(f"{v['value']} ({', '.join(v['sources'])})" for v in c["values"])
                    + (f"; Profil: {c['profile_value']}" if c["profile_value"] else ""))
    else:
        doc.add_paragraph("Keine widersprüchlichen Angaben in den berücksichtigten Aussagen.")
    if len(ctx.groups) > 1:
        doc.add_heading("Nicht zugeordnete Kandidaten (mögliche Namensvettern)", 2)
        _table(doc, ["Kandidat", "Treffer", "Geburt", "Organisationen", "Passung"],
               [[g["label"], g["count"], ", ".join(g["births"]), ", ".join(g["orgs"][:3]), g["score"]] for g in ctx.groups], [3, 1.6, 2.4, 7, 2])
    return 0, 0


def sec_vermisst(ctx: Ctx, doc) -> tuple[int, int]:
    if doc is None or not ctx.subject:
        return 0, 0
    data = ctx.subject.get("data") or {}
    _kv(doc, [(label, data.get(key)) for key, label in MISSING_FIELDS])
    risk = ctx.subject.get("risk") or {}
    doc.add_heading("Gefährdungseinschätzung", 2)
    doc.add_paragraph(f"Stufe: {risk.get('level', 'n. b.')} ({risk.get('points', 0)} Punkte). {risk.get('advice', '')}")
    for f in risk.get("factors", []):
        _bullet(doc, f"{f['label']} (Gewicht {f['weight']})")
    return 0, 0


def sec_zeitleiste(ctx: Ctx, doc) -> tuple[int, int]:
    if doc is None:
        return 0, 0
    if ctx.events:
        _table(doc, ["Zeitpunkt", "Art", "Ort", "Beschreibung", "Quelle / Verlässlichkeit"],
               [[e["occurred_at"].replace("T", " "), e["kind"], e["location"], e["description"], f"{e['source']} · {e['reliability']}"] for e in ctx.events],
               [2.8, 2.6, 3.2, 5.2, 3])
    else:
        doc.add_paragraph("Keine Ereignisse erfasst.")
    return 0, 0


def sec_erkenntnisse(ctx: Ctx, doc) -> tuple[int, int]:
    with_facts = {f["finding_id"] for f in ctx.p.list_facts(ctx.case["id"]) if f["finding_id"]}
    items = [f for f in ctx.findings if f["status"] == "bestätigt" and f["id"] not in with_facts and f["category"] != "Konto"]
    if ctx.opts.get("include_unreviewed"):
        items += [f for f in ctx.findings if f["status"] == "neu" and f["id"] not in with_facts]
    total = len(items)
    ok = sum(1 for f in items if ctx.ev_finding.get(f["id"]))
    if doc is not None:
        if items:
            _table(doc, ["Erkenntnis", "Quelle", "Bewertung", "Prüfnotiz", "Beleg"],
                   [[f["title"] + (f"\n{f['snippet'][:160]}" if f["snippet"] else "") + ("" if f["status"] == "bestätigt" else "\n(UNGEPRÜFT)"),
                     f["source"], f"{f['score']} ({f['confidence']})", f["review_note"],
                     ctx.cite(f["url"], f["title"], f["created_at"], "", (ctx.ev_finding.get(f["id"]) or [None])[0])] for f in items],
                   [6.2, 2.8, 2.2, 3.6, 1.6])
        else:
            doc.add_paragraph("Keine weiteren Erkenntnisse.")
    return total, ok


def sec_offene_punkte(ctx: Ctx, doc) -> tuple[int, int]:
    if doc is None:
        return 0, 0
    items = []
    if ctx.counts["open_findings"]:
        items.append(f"{ctx.counts['open_findings']} Treffer sind noch ungeprüft.")
    if len(ctx.groups) > 1:
        items.append(f"{len(ctx.groups)} Kandidatengruppen sind noch nicht eindeutig zugeordnet.")
    unbelegt = [f for f in ctx.facts if not ctx.belegt(f)]
    if unbelegt:
        items.append(f"{len(unbelegt)} Aussagen stützen sich auf nur eine Quelle ohne Sicherung – Beleg sichern oder Zweitquelle suchen.")
    items += [t["title"] + (" (hohe Priorität)" if t["priority"] == "hoch" else "") for t in ctx.tasks if not t["done"]]
    for s in ctx.p.suggestions(ctx.case["id"])[:8]:
        items.append(f"Verbindungshinweis prüfen: {s['source_label']} ↔ {s['target_label']} – {s['reason']}")
    for it in items or ["Keine offenen Punkte."]:
        _bullet(doc, it)
    return 0, 0


def sec_quellen(ctx: Ctx, doc) -> tuple[int, int]:
    if doc is None:
        return 0, 0
    if not ctx.cites:
        doc.add_paragraph("Keine verlinkten Quellen.")
        return 0, 0
    for i, c in enumerate(ctx.cites, 1):
        par = doc.add_paragraph()
        r = par.add_run(f"[{i}] {c['title'][:110]}" + (f" · Verlässlichkeit {c['reliability']}" if c["reliability"] else "")
                        + (f" · abgerufen {_fmt_ts(c['retrieved'])}" if c["retrieved"] else "") + " – ")
        r.font.size = Pt(8.5)
        if c["url"]:
            _hyperlink(par, c["url"], c["url"][:100])
        if c["sha"]:
            r2 = par.add_run(f"  · gesichert als Beleg B{c['evidence_id']:04d}, SHA-256 {c['sha'][:16]}…")
            r2.font.size = Pt(8)
            r2.font.color.rgb = GREY
        if c["archive"]:
            r3 = par.add_run(" · Archivkopie: ")
            r3.font.size = Pt(8)
            _hyperlink(par, c["archive"], c["archive"][:80])
    return 0, 0


def sec_methodik(ctx: Ctx, doc) -> tuple[int, int]:
    if doc is None:
        return 0, 0
    egress = ctx.p.opsec_status(ctx.case["id"])
    for txt in (
        "Es wurden ausschließlich öffentlich zugängliche oder rechtmäßig lizenzierte Quellen genutzt; Zugangsschranken wurden nicht umgangen.",
        "Automatisch gefundene Treffer sind Kandidaten. In dieses Dossier gehen nur von Menschen geprüfte Aussagen ein"
        + (" sowie ausdrücklich als ungeprüft markierte Hinweise." if ctx.opts.get("include_unreviewed") else "."),
        "Gleiche Namen beweisen keine Identität. Namensvettern wurden über Kandidatengruppen (Geburtsdatum, Organisationen, Orte) getrennt.",
        f"Netzausgang: {egress['profile']['name']}; {egress['totals']['requests']} automatische Außenabfragen bei {egress['totals']['hosts']} Stellen (OPSEC-Stufe {ctx.lv.key}).",
        f"Gesicherte Belege: {len(ctx.evidence)} Fundstellen mit Zeitstempel und SHA-256 (Beweispaket separat exportierbar).",
    ):
        _bullet(doc, txt)
    doc.add_heading("Bewertungsschlüssel (Admiralty-Code)", 2)
    _table(doc, ["Code", "Verlässlichkeit der Quelle", "Code", "Glaubwürdigkeit der Information"],
           [[k, v, str(n), c] for (k, v), (n, c) in zip(ctx.legend["reliability"].items(), ctx.legend["credibility"].items())], [1.2, 6.5, 1.2, 7.5])
    if ctx.branding.get("disclaimer"):
        doc.add_heading("Hinweis", 2)
        doc.add_paragraph(ctx.branding["disclaimer"])
    return 0, 0


def sec_protokoll(ctx: Ctx, doc) -> tuple[int, int]:
    if doc is None or not ctx.opts.get("include_audit", True):
        return 0, 0
    _table(doc, ["Zeit", "Person", "Aktion", "Details"], [[_fmt_ts(a["ts"]), a.get("username", ""), a["action"], a["detail"][:150]] for a in ctx.p.audit(ctx.case["id"])[:60]],
           [2.8, 2.2, 3.6, 8])
    return 0, 0


SECTIONS: dict[str, Callable[[Ctx, Any], tuple[int, int]]] = {
    "summary": sec_summary, "auftrag": sec_auftrag, "identitaet": sec_identitaet, "lebenslauf": sec_lebenslauf, "familie": sec_familie,
    "wirtschaft": sec_wirtschaft, "online": sec_online, "netzwerk": sec_netzwerk, "risiko": sec_risiko, "widersprueche": sec_widersprueche,
    "vermisst": sec_vermisst, "zeitleiste": sec_zeitleiste, "erkenntnisse": sec_erkenntnisse, "offene_punkte": sec_offene_punkte,
    "quellen": sec_quellen, "methodik": sec_methodik, "protokoll": sec_protokoll,
}


# --------------------------------------------------------------------------- Vorschau & Erzeugung

def preview(p, case_id: int, template: str, opts: dict[str, Any]) -> dict[str, Any]:
    ctx = Ctx(p, case_id, opts)
    tpl = TEMPLATES.get(template) or TEMPLATES[default_template(ctx.case)]
    secs = []
    for key in tpl["sections"]:
        t, o = SECTIONS[key](ctx, None)
        secs.append({"key": key, "label": SECTION_LABELS[key], "statements": t, "belegt": o, "density": round(100 * o / t) if t else None})
    all_t = len(ctx.facts)
    all_o = sum(1 for f in ctx.facts if ctx.belegt(f))
    warnings = []
    if ctx.counts["open_findings"]:
        warnings.append(f"{ctx.counts['open_findings']} Treffer sind ungeprüft und erscheinen nicht im Dossier.")
    if len(ctx.groups) > 1:
        warnings.append(f"{len(ctx.groups)} Kandidatengruppen offen – Verwechslungsgefahr.")
    if ctx.contradictions:
        warnings.append(f"{len(ctx.contradictions)} Widerspruch/Widersprüche ungeklärt.")
    unbelegt = all_t - all_o
    if unbelegt:
        warnings.append(f"{unbelegt} Aussagen nur einfach belegt und nicht gesichert.")
    if ctx.case["status"] not in {"freigegeben", "abgeschlossen", "archiviert"}:
        warnings.append("Fall ist nicht freigegeben – das Dossier trägt den Vermerk ENTWURF.")
    return {"template": template if template in TEMPLATES else default_template(ctx.case), "sections": secs,
            "overall": {"statements": all_t, "belegt": all_o, "density": round(100 * all_o / all_t) if all_t else None},
            "redflags": len(ctx.redflags), "evidence": len(ctx.evidence), "warnings": warnings, "ai": bool(ctx.ai)}


def build(p, case_id: int, template: str = "", opts: dict[str, Any] | None = None, export_id: str = "") -> bytes:
    opts = {"include_unreviewed": False, "include_audit": True, "include_graph": True, **(opts or {})}
    ctx = Ctx(p, case_id, opts)
    template = template if template in TEMPLATES else default_template(ctx.case)
    tpl = TEMPLATES[template]
    case, subj, lv, br = ctx.case, ctx.subject, ctx.lv, ctx.branding
    name = subj["label"] if subj else case["title"]
    accent = _hex(br.get("color")) or RGBColor(0x0F, 0x2A, 0x4A)
    doc = _base_document(case["codename"] if lv.codename and case.get("codename") else name, case["reference"])
    for st in ("Heading 1", "Heading 2", "Heading 3"):
        doc.styles[st].font.color.rgb = accent
    hp = doc.sections[0].header.paragraphs[0]
    if br.get("org_name"):
        hp.runs[0].text = f"{br['org_name']} · " + hp.runs[0].text
    if br.get("footer"):
        fp = doc.sections[0].footer.add_paragraph(br["footer"])
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        fp.runs[0].font.size = Pt(7)
        fp.runs[0].font.color.rgb = GREY

    # ---- Deckblatt
    logo = p.branding_logo()
    if logo:
        doc.add_picture(str(logo), height=Cm(1.8))
    for _ in range(2):
        doc.add_paragraph()
    r = doc.add_paragraph().add_run("VERTRAULICH – NUR FÜR DEN DIENSTGEBRAUCH" + (f" · OPSEC-STUFE {lv.key} ({lv.name.upper()})" if lv.key >= 2 else ""))
    r.bold, r.font.size, r.font.color.rgb = True, Pt(10), RGBColor(0xB9, 0x1C, 0x1C)
    if case["status"] not in {"freigegeben", "abgeschlossen", "archiviert"}:
        rd = doc.add_paragraph().add_run("ENTWURF – noch nicht im Vier-Augen-Verfahren freigegeben")
        rd.bold, rd.font.size, rd.font.color.rgb = True, Pt(11), RGBColor(0xB4, 0x53, 0x09)
    kind = tpl["label"] if template != "volldossier" else ("Recherchedossier" if case["case_type"] == "investigativ" else "Personendossier")
    r = doc.add_paragraph().add_run(kind)
    r.font.size, r.font.color.rgb = Pt(14), GREY
    r = doc.add_paragraph().add_run(name)
    r.bold, r.font.size, r.font.color.rgb = True, Pt(30), accent
    if subj and subj.get("photo"):
        photo = p.photo_bytes(case["id"], subj["id"])
        if photo:
            doc.add_picture(io.BytesIO(photo[0]), width=Cm(5.5))
    doc.add_paragraph()
    _kv(doc, [("Aktenzeichen (intern)", case["reference"]), ("Deckname", case.get("codename")), ("Export-ID", export_id),
              ("Fall", case["title"]), ("Fallart", case["case_type_label"]), ("Vorlage", tpl["label"]), ("Status", case["status"]),
              ("Bearbeitung", (ctx.team["owner"] or {}).get("display_name") or case["analyst"]),
              ("Prüfung (Vier-Augen)", (ctx.team["reviewer"] or {}).get("display_name")), ("Erstellt am", datetime.now().strftime("%d.%m.%Y %H:%M")),
              ("Inhalt", "Nur geprüfte Aussagen" if not opts["include_unreviewed"] else "Geprüfte und ungeprüfte Aussagen (gekennzeichnet)")])
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # ---- Kapitel (Quellenverzeichnis zuletzt befüllen, damit alle Fußnoten erfasst sind)
    order = tpl["sections"]
    deferred = [k for k in order if k in {"quellen"}]
    for i, key in enumerate(order, 1):
        doc.add_heading(f"{i}  {SECTION_LABELS[key]}", 1)
        if key in deferred:
            anchor = doc.add_paragraph()
            ctx.stats[key] = (0, 0)
            ctx._deferred_anchor = anchor  # type: ignore[attr-defined]
            continue
        heading_par = doc.paragraphs[-1]
        t, o = SECTIONS[key](ctx, doc)
        ctx.stats[key] = (t, o)
        if t:
            # Belegdichte direkt unter die Überschrift setzen
            _density_line(doc, t, o)
            heading_par._p.addnext(doc.paragraphs[-1]._p)
    if deferred:
        # Quellenverzeichnis ans Ende des Kapitels „Quellen“ verschieben
        anchor = ctx._deferred_anchor  # type: ignore[attr-defined]
        before = len(doc.paragraphs)
        sec_quellen(ctx, doc)
        node = anchor._p
        for par in doc.paragraphs[before:]:
            node.addnext(par._p)
            node = par._p
    scrub_and_mark(doc, p, case, export_id, tpl["label"])
    p.log(case_id, "Dossier exportiert", f"{tpl['label']} ({'inkl.' if opts['include_unreviewed'] else 'ohne'} ungeprüfte Aussagen)"
          + (f" · {export_id}" if export_id else ""))
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _hex(value: str | None) -> RGBColor | None:
    v = (value or "").lstrip("#")
    if len(v) == 6:
        try:
            return RGBColor(int(v[:2], 16), int(v[2:4], 16), int(v[4:], 16))
        except ValueError:
            return None
    return None


# --------------------------------------------------------------------------- PDF/A

def pdf_available() -> bool:
    return bool(shutil.which("soffice") or shutil.which("libreoffice"))


def to_pdf(docx: bytes) -> bytes:
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe:
        raise RuntimeError("PDF-Export benötigt LibreOffice auf dem Server.")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "dossier.docx"
        src.write_bytes(docx)
        env = {**os.environ, "HOME": tmp}
        filt = 'pdf:writer_pdf_Export:{"SelectPdfVersion":{"type":"long","value":"2"}}'
        subprocess.run([exe, "--headless", "--norestore", f"-env:UserInstallation=file://{tmp}/profile", "--convert-to", filt, "--outdir", tmp, str(src)],
                       check=True, capture_output=True, timeout=180, env=env)
        out = Path(tmp) / "dossier.pdf"
        if not out.exists():
            raise RuntimeError("PDF-Konvertierung fehlgeschlagen.")
        return out.read_bytes()


__all__ = ["TEMPLATES", "SECTION_LABELS", "build", "preview", "default_template", "pdf_available", "to_pdf"]
