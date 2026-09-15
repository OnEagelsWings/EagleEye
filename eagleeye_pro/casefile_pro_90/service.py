from __future__ import annotations
import hashlib, zipfile
from pathlib import Path
from typing import Any, Dict
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

class CasefilePro90Service:
    """Build 90.0 Casefile Pro: manifest v3, report, graph/timeline/review/evidence indexes and ZIP hash."""
    def __init__(self, db: Database, audit: AuditService, out_dir: str | Path, dashboard=None, timeline=None, review_board=None, report_builder=None, graph=None, evidence_vault=None):
        self.db = db; self.audit = audit; self.out_dir = Path(out_dir); self.out_dir.mkdir(parents=True, exist_ok=True); self.dashboard = dashboard; self.timeline = timeline; self.review_board = review_board; self.report_builder = report_builder; self.graph = graph; self.evidence_vault = evidence_vault; self.ensure_schema()
    def ensure_schema(self) -> None:
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS casefiles_pro_90(
          package_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, export_mode TEXT NOT NULL, zip_path TEXT NOT NULL,
          zip_sha256 TEXT NOT NULL, manifest_sha256 TEXT NOT NULL, manifest_json TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_casefile90_case ON casefiles_pro_90(case_id,created_at);
        """); self.db.conn.commit()
    def build(self, case_id: str, export_mode: str = "authority_redacted", include_evidence_files: bool = False) -> Dict[str, Any]:
        package_id = new_id("cf90"); case_dir = self.out_dir / case_id / package_id; case_dir.mkdir(parents=True, exist_ok=True)
        dashboard = self.dashboard.build(case_id, persist=True) if self.dashboard else {}
        timeline = self.timeline.build(case_id) if self.timeline else {"events": []}
        review = self.review_board.board(case_id) if self.review_board else {}
        report = self.report_builder.build(case_id, report_type="casefile_report", export_mode=export_mode) if self.report_builder else {}
        graph = self.graph.build_graph(case_id) if self.graph else {}
        evidence = self.evidence_vault.list_case_items(case_id) if self.evidence_vault else []
        files = {
            "01_DASHBOARD.json": dashboard,
            "02_TIMELINE.json": timeline,
            "03_REVIEW_BOARD.json": review,
            "04_GRAPH.json": graph,
            "05_EVIDENCE_INDEX.json": {"case_id": case_id, "items": evidence},
            "06_REPORT_POINTER.json": report,
            "07_AUDIT_LOG.json": {"events": self.db.all("SELECT * FROM audit_events WHERE case_id=? ORDER BY timestamp", [case_id])},
        }
        file_hashes = []
        for name, payload in files.items():
            p = case_dir / name; p.write_text(dumps(payload), encoding="utf-8"); file_hashes.append({"path": name, "sha256": self._sha(p), "size_bytes": p.stat().st_size})
        if report.get("markdown_path") and Path(report["markdown_path"]).exists():
            md_src = Path(report["markdown_path"]); md_dest = case_dir / "00_REPORT.md"; md_dest.write_text(md_src.read_text(encoding="utf-8"), encoding="utf-8"); file_hashes.append({"path": "00_REPORT.md", "sha256": self._sha(md_dest), "size_bytes": md_dest.stat().st_size})
        if include_evidence_files:
            ev_dir = case_dir / "evidence_files"; ev_dir.mkdir(exist_ok=True)
            for item in evidence:
                src = Path(item.get("stored_path", ""))
                if src.exists():
                    dest = ev_dir / (item["evidence_id"] + src.suffix); dest.write_bytes(src.read_bytes()); file_hashes.append({"path": str(dest.relative_to(case_dir)), "sha256": self._sha(dest), "size_bytes": dest.stat().st_size})
        manifest = {"schema_version": "casefile_manifest_v3", "package_id": package_id, "case_id": case_id, "build": "90.0", "created_at": now_ts(), "export_mode": export_mode, "public_only": True, "review_first": True, "claim_count": dashboard.get("metrics", {}).get("claims", 0), "evidence_count": len(evidence), "timeline_event_count": len(timeline.get("events", [])), "warnings": dashboard.get("warnings", []), "files": file_hashes}
        manifest_path = case_dir / "MANIFEST_V3.json"; manifest_path.write_text(dumps(manifest), encoding="utf-8"); manifest_sha = self._sha(manifest_path); manifest["manifest_sha256"] = manifest_sha; manifest_path.write_text(dumps(manifest), encoding="utf-8")
        zip_path = self.out_dir / case_id / f"{package_id}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(case_dir.rglob("*")):
                if p.is_file(): z.write(p, p.relative_to(case_dir))
        zip_sha = self._sha(zip_path)
        self.db.execute("INSERT INTO casefiles_pro_90(package_id,case_id,export_mode,zip_path,zip_sha256,manifest_sha256,manifest_json,created_at) VALUES(?,?,?,?,?,?,?,?)", [package_id, case_id, export_mode, str(zip_path), zip_sha, manifest_sha, dumps(manifest), now_ts()])
        self.audit.log("build", "casefile_pro_90", package_id, case_id, {"zip_sha256": zip_sha, "export_mode": export_mode})
        return {"package_id": package_id, "case_id": case_id, "zip_path": str(zip_path), "zip_sha256": zip_sha, "manifest_sha256": manifest_sha, "manifest": manifest, "valid": True}
    def verify(self, package_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM casefiles_pro_90 WHERE package_id=?", [package_id])
        if not row: raise KeyError(package_id)
        problems = []; zp = Path(row["zip_path"])
        if not zp.exists(): problems.append("zip_missing")
        elif self._sha(zp) != row["zip_sha256"]: problems.append("zip_sha256_mismatch")
        return {"package_id": package_id, "valid": not problems, "problems": problems, "zip_sha256": row["zip_sha256"]}
    def latest(self, case_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM casefiles_pro_90 WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id])
        if not row: raise KeyError(case_id)
        row["manifest"] = loads(row.pop("manifest_json", "{}"), {})
        return row
    def _sha(self, p: Path) -> str:
        h = hashlib.sha256()
        with p.open("rb") as f:
            for c in iter(lambda: f.read(1024 * 1024), b""): h.update(c)
        return h.hexdigest()
