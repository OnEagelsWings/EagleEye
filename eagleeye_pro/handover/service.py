from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import hashlib
import json

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts


class AuthorityHandoverReportService:
    """Build 50 redacted handover package writer."""

    def __init__(self, db: Database, audit: AuditService, reports_root: str | Path):
        self.db = db
        self.audit = audit
        self.reports_root = Path(reports_root)
        self.reports_root.mkdir(parents=True, exist_ok=True)
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS handover_reports_50 (
          report_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          profile_id TEXT DEFAULT '',
          report_type TEXT NOT NULL,
          recipient_class TEXT NOT NULL,
          report_path TEXT NOT NULL,
          manifest_json TEXT NOT NULL,
          content_hash TEXT NOT NULL,
          status TEXT DEFAULT 'created',
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_handover50_case ON handover_reports_50(case_id, created_at);
        ''')
        self.db.conn.commit()

    def create_report(self, case_id: str, *, profile_id: str = "", report_type: str = "authority_handover", recipient_class: str = "authority_or_meldestelle", markdown: str = "", profile: Dict[str, Any] | None = None) -> Dict[str, Any]:
        if not markdown and profile_id:
            row = self.db.one("SELECT markdown, profile_json FROM spearhead_profiles_50 WHERE profile_id=?", [profile_id])
            if row:
                markdown = row.get("markdown", "")
                profile = loads(row.get("profile_json"), {})
        if not markdown:
            raise ValueError("Markdown or profile_id is required for handover report.")
        report_id = new_id("hrep50")
        case_dir = self.reports_root / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        path = case_dir / f"{report_id}_{report_type}.md"
        header = f"<!-- EagleEye Build 50 Handover Report | recipient={recipient_class} | created={now_ts()} -->\n"
        content = header + markdown
        path.write_text(content, encoding="utf-8")
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        manifest = {
            "report_id": report_id,
            "case_id": case_id,
            "profile_id": profile_id,
            "report_type": report_type,
            "recipient_class": recipient_class,
            "content_hash": content_hash,
            "created_at": now_ts(),
            "guardrails": ["redacted_handover", "no_forbidden_claims", "source_and_uncertainty_required"],
        }
        self.db.execute('''INSERT INTO handover_reports_50(report_id,case_id,profile_id,report_type,recipient_class,report_path,manifest_json,content_hash,status,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)''', [report_id, case_id, profile_id, report_type, recipient_class, str(path), dumps(manifest), content_hash, "created", manifest["created_at"]])
        self.audit.log("create", "handover_report_50", report_id, case_id, {"report_type": report_type, "content_hash": content_hash})
        return self.get(report_id)

    def get(self, report_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM handover_reports_50 WHERE report_id=?", [report_id])
        if not row:
            raise KeyError(report_id)
        row["manifest"] = loads(row.pop("manifest_json", "{}"), {})
        return row
