from __future__ import annotations
import re
from pathlib import Path
from typing import Any, Dict
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

class ReportBuilderPro89Service:
    """Build 89.0 report builder pro with export modes and redaction preview."""
    MODES = {"internal_full", "internal_redacted", "authority_redacted", "external_minimal"}
    def __init__(self, db: Database, audit: AuditService, out_dir: str | Path, dashboard=None, timeline=None, review_board=None):
        self.db = db; self.audit = audit; self.out_dir = Path(out_dir); self.out_dir.mkdir(parents=True, exist_ok=True); self.dashboard = dashboard; self.timeline = timeline; self.review_board = review_board; self.ensure_schema()
    def ensure_schema(self) -> None:
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS reports_pro_89(
          report_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, report_type TEXT NOT NULL, export_mode TEXT NOT NULL,
          title TEXT NOT NULL, markdown_path TEXT NOT NULL, json_path TEXT NOT NULL, redaction_log_json TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_reports89_case ON reports_pro_89(case_id,created_at);
        """); self.db.conn.commit()
    def build(self, case_id: str, report_type: str = "long_report", export_mode: str = "internal_redacted", title: str = "", persist: bool = True) -> Dict[str, Any]:
        if export_mode not in self.MODES: raise ValueError("unsupported export_mode")
        case = self.db.one("SELECT * FROM cases WHERE case_id=?", [case_id]) or {"title": case_id, "purpose": ""}
        dashboard = self.dashboard.build(case_id, persist=False) if self.dashboard else {}
        timeline = self.timeline.build(case_id) if self.timeline else {"events": []}
        review = self.review_board.board(case_id) if self.review_board else {"queues": {}, "metrics": {}}
        claims = self.db.all("SELECT * FROM claims_v3_80 WHERE case_id=? ORDER BY created_at DESC", [case_id]) if self._table("claims_v3_80") else []
        evidence = self.db.all("SELECT evidence_id,title,artifact_type,sha256,custody_status,source_ref FROM local_evidence_items_75 WHERE case_id=? ORDER BY created_at DESC", [case_id]) if self._table("local_evidence_items_75") else []
        report_id = new_id("rep89"); heading = title or f"EagleEye Report Pro – {case.get('title', case_id)}"
        lines = [f"# {heading}", "", f"**Case ID:** {case_id}", f"**Export mode:** {export_mode}", f"**Report type:** {report_type}", "", "## Executive Summary", f"Readiness: {dashboard.get('readiness_score','n/a')} / 100. Status: {dashboard.get('status','unknown')}.", "", "## Warnings"]
        for w in dashboard.get("warnings", []): lines.append(f"- {w.get('level','info').upper()}: {w.get('message','')}")
        lines += ["", "## Claims"]
        if not claims: lines.append("- No reviewed claims available yet.")
        for c in claims:
            stmt, _ = self._redact(c.get("statement", ""), export_mode)
            lines.append(f"- **{c.get('grade','candidate')} / {c.get('review_status','pending')}**: {stmt}")
        lines += ["", "## Evidence Index"]
        for e in evidence: lines.append(f"- {e['evidence_id']} – {e['title']} – sha256 `{e['sha256']}` – {e['custody_status']}")
        lines += ["", "## Timeline"]
        for ev in timeline.get("events", [])[:50]:
            desc, _ = self._redact(ev.get("description", ""), export_mode)
            lines.append(f"- {ev.get('event_time','')} [{ev.get('time_type','')}] {ev.get('title','')} — {desc}")
        lines += ["", "## Review Board Snapshot", f"Open claim reviews: {len(review.get('queues',{}).get('claims_needing_review',[]))}", f"Candidate edges: {len(review.get('queues',{}).get('candidate_edges',[]))}", "", "## Method Note", "All findings remain public-source candidates unless reviewed claims and evidence references support them."]
        md = "\n".join(lines) + "\n"
        redaction_log = {"mode": export_mode, "applied": export_mode != "internal_full"}
        if export_mode != "internal_full": md, applied = self._redact(md, export_mode); redaction_log["rules"] = applied
        case_dir = self.out_dir / case_id; case_dir.mkdir(parents=True, exist_ok=True)
        md_path = case_dir / f"{report_id}.md"; json_path = case_dir / f"{report_id}.json"
        md_path.write_text(md, encoding="utf-8")
        payload = {"report_id": report_id, "case_id": case_id, "report_type": report_type, "export_mode": export_mode, "dashboard": dashboard, "timeline_event_count": len(timeline.get("events", [])), "review_metrics": review.get("metrics", {}), "evidence_count": len(evidence), "created_at": now_ts()}
        json_path.write_text(dumps(payload), encoding="utf-8")
        if persist:
            self.db.execute("INSERT INTO reports_pro_89(report_id,case_id,report_type,export_mode,title,markdown_path,json_path,redaction_log_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)", [report_id, case_id, report_type, export_mode, heading, str(md_path), str(json_path), dumps(redaction_log), now_ts()])
            self.audit.log("build", "report_pro_89", report_id, case_id, {"export_mode": export_mode, "report_type": report_type})
        payload.update({"markdown_path": str(md_path), "json_path": str(json_path), "redaction_log": redaction_log})
        return payload
    def latest(self, case_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM reports_pro_89 WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id])
        if not row: raise KeyError(case_id)
        row["redaction_log"] = loads(row.pop("redaction_log_json", "{}"), {})
        return row
    def _redact(self, text: str, mode: str):
        if mode == "internal_full": return text, []
        applied = []
        new = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[E-MAIL REDACTED]", text)
        new = re.sub(r"(\+?\d[\d\s()/.-]{7,}\d)", "[PHONE REDACTED]", new)
        if new != text: applied.append("basic_contact_redaction")
        if mode == "external_minimal":
            newer = re.sub(r"\b[A-ZÄÖÜ][a-zäöüß]+\s+[A-ZÄÖÜ][a-zäöüß]+\b", "[PERSON]", new)
            if newer != new: applied.append("person_name_mask_external_minimal")
            new = newer
        return new, applied
    def _table(self, name: str) -> bool:
        return self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", [name]) is not None
