from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json
import zipfile

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, new_id, now_ts


class CollaborationHandoverService:
    """Build 54 collaboration and handover bundles with redacted manifests."""

    def __init__(self, db: Database, audit: AuditService, out_root: str | Path):
        self.db = db
        self.audit = audit
        self.out_root = Path(out_root)
        self.out_root.mkdir(parents=True, exist_ok=True)
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS collaboration_bundles_54 (
          bundle_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          bundle_type TEXT NOT NULL,
          recipient_class TEXT NOT NULL,
          redaction_level TEXT NOT NULL,
          bundle_path TEXT NOT NULL,
          manifest_path TEXT NOT NULL,
          sha256 TEXT NOT NULL,
          file_count INTEGER DEFAULT 0,
          created_at TEXT NOT NULL,
          notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_collab54_case ON collaboration_bundles_54(case_id, created_at);
        ''')
        self.db.conn.commit()

    def create_bundle(self, case_id: str, *, bundle_type: str = "authority_handover_package", recipient_class: str = "authority_or_meldestelle", redaction_level: str = "redacted", notes: str = "") -> Dict[str, Any]:
        bundle_id = new_id("bundle54")
        outdir = self.out_root / case_id
        outdir.mkdir(parents=True, exist_ok=True)
        manifest = {"build": "54.0", "bundle_id": bundle_id, "case_id": case_id, "bundle_type": bundle_type, "recipient_class": recipient_class, "redaction_level": redaction_level, "created_at": now_ts(), "files": [], "rules": ["No forbidden claims", "Facts and indicators separated", "Private addresses/live locations excluded unless lawful authority request is documented"]}
        zip_path = outdir / f"{bundle_id}.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("README_HANDOVER.txt", self._readme(bundle_type, recipient_class, redaction_level))
            profile = self._latest_profile(case_id)
            if profile:
                zf.writestr("PROFILE.md", profile.get("markdown", ""))
                manifest["files"].append({"path": "PROFILE.md", "kind": "profile", "id": profile.get("profile_id", ""), "sha256": hashlib.sha256(profile.get("markdown", "").encode("utf-8")).hexdigest()})
            report = self._latest_report(case_id)
            if report:
                p = Path(report["report_path"])
                if p.exists():
                    zf.write(p, "REPORT.md")
                    manifest["files"].append({"path": "REPORT.md", "kind": "handover_report", "id": report.get("report_id", ""), "sha256": self._sha256_file(p)})
            chain_summary = self._chain_summary(case_id)
            zf.writestr("SEARCH_FUND_CHAIN_SUMMARY.json", json.dumps(chain_summary, ensure_ascii=False, indent=2))
            manifest["files"].append({"path": "SEARCH_FUND_CHAIN_SUMMARY.json", "kind": "chain_summary", "sha256": hashlib.sha256(json.dumps(chain_summary, sort_keys=True).encode("utf-8")).hexdigest()})
            zf.writestr("MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        sha = self._sha256_file(zip_path)
        manifest["bundle_sha256"] = sha
        manifest_path = outdir / f"{bundle_id}_manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        self.db.execute('''INSERT INTO collaboration_bundles_54(bundle_id,case_id,bundle_type,recipient_class,redaction_level,bundle_path,manifest_path,sha256,file_count,created_at,notes)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)''', [bundle_id, case_id, bundle_type, recipient_class, redaction_level, str(zip_path), str(manifest_path), sha, len(manifest["files"]), now_ts(), notes])
        self.audit.log("create", "collaboration_bundle_54", bundle_id, case_id, {"sha256": sha, "bundle_type": bundle_type, "redaction_level": redaction_level})
        return self.get_bundle(bundle_id)

    def get_bundle(self, bundle_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM collaboration_bundles_54 WHERE bundle_id=?", [bundle_id])
        if not row:
            raise KeyError(bundle_id)
        return row

    def verify_bundle(self, bundle_id: str) -> Dict[str, Any]:
        row = self.get_bundle(bundle_id)
        p = Path(row["bundle_path"])
        current = self._sha256_file(p) if p.exists() else ""
        return {"bundle_id": bundle_id, "valid": bool(current and current == row["sha256"]), "stored_sha256": row["sha256"], "current_sha256": current}

    def _latest_profile(self, case_id: str) -> Dict[str, Any] | None:
        if not self._table_exists("spearhead_profiles_50"):
            return None
        return self.db.one("SELECT * FROM spearhead_profiles_50 WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id])

    def _latest_report(self, case_id: str) -> Dict[str, Any] | None:
        if not self._table_exists("handover_reports_50"):
            return None
        return self.db.one("SELECT * FROM handover_reports_50 WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id])

    def _chain_summary(self, case_id: str) -> Dict[str, Any]:
        if not self._table_exists("search_chain_nodes_54"):
            return {"nodes": 0, "edges": 0}
        nodes = self.db.all("SELECT node_type,title,value,source_url,confidence_label FROM search_chain_nodes_54 WHERE case_id=? ORDER BY created_at", [case_id])
        edges = self.db.all("SELECT relation_type,explanation FROM search_chain_edges_54 WHERE case_id=? ORDER BY created_at", [case_id]) if self._table_exists("search_chain_edges_54") else []
        return {"nodes": len(nodes), "edges": len(edges), "items": nodes[:200], "relations": edges[:200]}

    def _readme(self, bundle_type: str, recipient_class: str, redaction_level: str) -> str:
        return f"EagleEye Build 54 Handover Bundle\nType: {bundle_type}\nRecipient: {recipient_class}\nRedaction: {redaction_level}\n\nThis package separates facts, indicators, uncertainty and counter-evidence. It is not an automated guilt/identity verdict.\n"

    def _sha256_file(self, path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def _table_exists(self, name: str) -> bool:
        return bool(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", [name]))
