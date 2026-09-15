from __future__ import annotations

import hashlib
import html as html_lib
import json
import mimetypes
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.security.url_policy import URLPolicy


class PlatformConsolidation1031Service:
    """Build 103.1: consolidated single-case workspace and canonical intake pipeline.

    A public finding is physically stored once as one canonical capture group and one
    primary Evidence Vault item. Analysis, graph and compatibility records reference
    that canonical object instead of recapturing the same material.
    """

    BUILD = "103.1"
    MAX_TEXT_BYTES = 8 * 1024 * 1024
    MAX_HTML_BYTES = 16 * 1024 * 1024
    MAX_SCREENSHOT_BYTES = 20 * 1024 * 1024
    SCREENSHOT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

    def __init__(
        self,
        db: Database,
        audit: AuditService,
        artifact_dir: str | Path,
        *,
        cases: Any,
        graph: Any,
        graph_workspace: Any,
        evidence_vault: Any,
        document_intel: Any,
        security: Any,
        local_ai: Any,
        source_reliability: Any,
        review_board: Any,
        claims: Any,
        casefile: Any,
    ):
        self.db = db
        self.audit = audit
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.cases = cases
        self.graph = graph
        self.graph_workspace = graph_workspace
        self.evidence = evidence_vault
        self.documents = document_intel
        self.security = security
        self.local_ai = local_ai
        self.reliability = source_reliability
        self.review_board = review_board
        self.claims = claims
        self.casefile = casefile
        self.ensure_schema()
        self.apply_migrations()

    def ensure_schema(self) -> None:
        self.db.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations_103_1(
              migration_id TEXT PRIMARY KEY, version TEXT NOT NULL, description TEXT NOT NULL,
              checksum TEXT NOT NULL, applied_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS app_state_103_1(
              state_key TEXT PRIMARY KEY, state_value TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS canonical_captures_103_1(
              capture_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, input_kind TEXT NOT NULL,
              original_url TEXT DEFAULT '', canonical_url TEXT DEFAULT '', host TEXT DEFAULT '',
              title TEXT NOT NULL, content_sha256 TEXT NOT NULL, text_sha256 TEXT DEFAULT '',
              html_sha256 TEXT DEFAULT '', screenshot_sha256 TEXT DEFAULT '', artifact_dir TEXT NOT NULL,
              text_path TEXT DEFAULT '', html_path TEXT DEFAULT '', screenshot_path TEXT DEFAULT '',
              manifest_path TEXT NOT NULL, evidence_id TEXT DEFAULT '', document_id TEXT DEFAULT '',
              paste_id TEXT DEFAULT '', browser_capture_id TEXT DEFAULT '', source_rating_id TEXT DEFAULT '',
              security_decision TEXT DEFAULT '', ai_run_id TEXT DEFAULT '', status TEXT NOT NULL,
              warnings_json TEXT NOT NULL, metadata_json TEXT NOT NULL, created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(case_id, canonical_url, content_sha256),
              FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_canonical_capture_case_103_1
              ON canonical_captures_103_1(case_id, created_at);
            CREATE TABLE IF NOT EXISTS canonical_findings_103_1(
              finding_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, capture_id TEXT NOT NULL UNIQUE,
              status TEXT NOT NULL, review_status TEXT NOT NULL, title TEXT NOT NULL,
              excerpt TEXT DEFAULT '', source_ref TEXT DEFAULT '', evidence_id TEXT DEFAULT '',
              document_id TEXT DEFAULT '', metadata_json TEXT NOT NULL, created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
              FOREIGN KEY(capture_id) REFERENCES canonical_captures_103_1(capture_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_canonical_finding_case_103_1
              ON canonical_findings_103_1(case_id, created_at);
            """
        )
        self.db.conn.commit()

    def apply_migrations(self) -> Dict[str, Any]:
        migration_id = "103.1-platform-consolidation-v1"
        row = self.db.one("SELECT migration_id FROM schema_migrations_103_1 WHERE migration_id=?", [migration_id])
        if row:
            return {"version": self.BUILD, "status": "already_applied", "migration_id": migration_id}
        checksum = hashlib.sha256(migration_id.encode("utf-8")).hexdigest()
        with self.db.conn:
            self.db.conn.execute(
                "INSERT INTO schema_migrations_103_1 VALUES(?,?,?,?,?)",
                [migration_id, self.BUILD, "Unified workspace, active case state and canonical intake", checksum, now_ts()],
            )
            # The historical migration is tracked in schema_migrations_103_1;
            # it must not overwrite current global runtime metadata.
        self.audit.log("migrate", "schema", migration_id, None, {"version": self.BUILD, "checksum": checksum})
        return {"version": self.BUILD, "status": "applied", "migration_id": migration_id}

    # ---------- case context ----------
    def list_cases(self) -> List[Dict[str, Any]]:
        return self.cases.list_cases()

    def create_case(self, title: str, purpose: str, legal_basis: str, *, client: str = "Local Analyst") -> Dict[str, Any]:
        case = self.cases.create_case(title, client, purpose, legal_basis)
        self.select_case(case["case_id"])
        return case

    def select_case(self, case_id: str) -> Dict[str, Any]:
        case = self.cases.get_case(case_id)
        self.db.execute(
            "INSERT OR REPLACE INTO app_state_103_1(state_key,state_value,updated_at) VALUES('active_case_id',?,?)",
            [case_id, now_ts()],
        )
        self.audit.log("select", "active_case_103_1", case_id, case_id, {"title": case.get("title", "")})
        return case

    def active_case(self, create_if_missing: bool = True) -> Dict[str, Any]:
        row = self.db.one("SELECT state_value FROM app_state_103_1 WHERE state_key='active_case_id'")
        if row:
            try:
                return self.cases.get_case(row["state_value"])
            except KeyError:
                pass
        cases = self.list_cases()
        if cases:
            self.select_case(cases[0]["case_id"])
            return cases[0]
        if not create_if_missing:
            return {}
        return self.create_case(
            "EagleEye Working Case",
            "Public-only, review-first PersonenOSINT working case",
            "Legitimate interest / manual legal review required before operational use",
        )

    def resolve_case_id(self, case_id: str = "") -> str:
        if case_id:
            self.select_case(case_id)
            return case_id
        return self.active_case()["case_id"]

    # ---------- canonical intake ----------
    def include_finding(
        self,
        *,
        case_id: str = "",
        url: str = "",
        text: str = "",
        html_snapshot: str = "",
        title: str = "",
        source_label: str = "manual_public_intake",
        notes: str = "",
        screenshot_path: str = "",
        input_kind: str = "paste",
        run_security: bool = True,
        run_ai_triage: bool = True,
        metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        case_id = self.resolve_case_id(case_id)
        original_url = (url or "").strip()
        canonical_url = ""
        host = ""
        if original_url:
            decision = URLPolicy.normalize_public_url(original_url)
            if not decision.get("ok"):
                raise ValueError(decision.get("blocked_reason") or "URL blocked by URLPolicy")
            canonical_url = decision.get("canonical_url") or decision.get("normalized_url") or original_url
            host = urlparse(canonical_url).hostname or ""
        html_snapshot = html_snapshot or ""
        visible_text = (text or self._html_to_text(html_snapshot)).strip()
        if not canonical_url and not visible_text and not html_snapshot:
            raise ValueError("URL, sichtbarer Text oder HTML ist erforderlich.")
        self._enforce_size(visible_text, self.MAX_TEXT_BYTES, "text")
        self._enforce_size(html_snapshot, self.MAX_HTML_BYTES, "html")
        title = (title or self._extract_title(html_snapshot) or canonical_url or "Public finding").strip()[:240]
        normalized_kind = input_kind
        if input_kind == "paste":
            normalized_kind = "url" if canonical_url else "text"
        storage_status = "stored_candidate_not_claim" if normalized_kind in {"browser", "browser_capture"} else "candidate_not_claim"
        content_seed = "\0".join([canonical_url, visible_text, html_snapshot])
        content_sha = hashlib.sha256(content_seed.encode("utf-8")).hexdigest()
        existing = self.db.one(
            "SELECT capture_id FROM canonical_captures_103_1 WHERE case_id=? AND canonical_url=? AND content_sha256=?",
            [case_id, canonical_url, content_sha],
        )
        if existing:
            out = self.get_capture(existing["capture_id"])
            if input_kind in {"browser", "browser_capture"} and not out.get("browser_capture_id"):
                browser_id = new_id("bc102")
                manifest_sha = self._sha_file(Path(out["manifest_path"])) if Path(out["manifest_path"]).exists() else ""
                self.db.execute(
                    """INSERT INTO browser_captures_102(bridge_capture_id,case_id,url,canonical_url,title,capture_mode,status,html_path,text_path,screenshot_path,manifest_path,html_sha256,text_sha256,screenshot_sha256,manifest_sha256,real_capture_id,evidence_id,paste_id,warnings_json,metadata_json,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    [browser_id, case_id, original_url, canonical_url, out["title"], "canonical_deduplicated_browser_capture_103_1", "stored_candidate_not_claim", out.get("html_path", ""), out.get("text_path", ""), out.get("screenshot_path", ""), out["manifest_path"], out.get("html_sha256", ""), out.get("text_sha256", ""), out.get("screenshot_sha256", ""), manifest_sha, out["capture_id"], out.get("evidence_id", ""), out.get("paste_id", ""), dumps(out.get("warnings", [])), dumps({"build": self.BUILD, "deduplicated": True}), now_ts()],
                )
                self.db.execute("UPDATE canonical_captures_103_1 SET browser_capture_id=?,updated_at=? WHERE capture_id=?", [browser_id, now_ts(), out["capture_id"]])
                out = self.get_capture(out["capture_id"])
                out["status"] = "stored_candidate_not_claim"
            out["deduplicated"] = True
            return out

        capture_id = new_id("cap1031")
        finding_id = new_id("find1031")
        paste_id = new_id("paste91")
        browser_id = new_id("bc102") if input_kind in {"browser", "browser_capture"} else ""
        cdir = self.artifact_dir / case_id / capture_id
        cdir.mkdir(parents=True, exist_ok=False)
        text_path = html_path = stored_screenshot = ""
        text_sha = html_sha = screenshot_sha = ""
        warnings: List[Dict[str, str]] = []
        if visible_text:
            tp = cdir / "visible_text.txt"
            tp.write_text(visible_text, encoding="utf-8")
            text_path, text_sha = str(tp), self._sha_file(tp)
        if html_snapshot:
            hp = cdir / "snapshot.html"
            hp.write_text(html_snapshot, encoding="utf-8")
            html_path, html_sha = str(hp), self._sha_file(hp)
        if screenshot_path:
            sp = self._validated_screenshot(Path(screenshot_path))
            dest = cdir / ("screenshot" + sp.suffix.lower())
            shutil.copy2(sp, dest)
            stored_screenshot, screenshot_sha = str(dest), self._sha_file(dest)
        elif input_kind in {"browser", "browser_capture"}:
            warnings.append({"level": "low", "code": "screenshot_not_supplied", "message": "Kein Screenshot mitgeliefert."})
        if not canonical_url:
            warnings.append({"level": "medium", "code": "missing_url", "message": "Quell-URL fehlt; Export braucht manuelles Quellenreview."})
        if canonical_url and not visible_text and not html_snapshot:
            warnings.append({"level": "medium", "code": "url_only", "message": "Nur URL gespeichert; Inhalt wurde nicht gesichert."})

        evidence_id = ""
        evidence_source = text_path or html_path
        if evidence_source:
            evidence_id = new_id("ev75")
        document_id = ""
        if visible_text or html_snapshot:
            document_id = new_id("doc85")
        excerpt = (visible_text or self._html_to_text(html_snapshot) or notes or canonical_url)[:2000]
        created = now_ts()
        manifest_path = cdir / "manifest.json"
        manifest = {
            "schema": "eagleeye_canonical_capture_v1",
            "build": self.BUILD,
            "capture_id": capture_id,
            "case_id": case_id,
            "input_kind": normalized_kind,
            "canonical_url": canonical_url,
            "title": title,
            "hashes": {"content": content_sha, "text": text_sha, "html": html_sha, "screenshot": screenshot_sha},
            "status": "candidate_not_claim",
            "created_at": created,
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        try:
            with self.db.conn:
                if evidence_id:
                    p = Path(evidence_source)
                    self.db.conn.execute(
                        """INSERT INTO local_evidence_items_75(evidence_id,case_id,title,original_path,stored_path,artifact_type,sha256,size_bytes,source_ref,linked_object_type,linked_object_id,custody_status,metadata_json,created_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        [evidence_id, case_id, title, "", str(p), "canonical_public_finding_103_1", self._sha_file(p), p.stat().st_size, canonical_url, "canonical_capture_103_1", capture_id, "stored_to_review", dumps({"build": self.BUILD, "source_label": source_label}), created],
                    )
                if document_id:
                    body = visible_text or self._html_to_text(html_snapshot)
                    entities = self.documents._entities(body) if self.documents and hasattr(self.documents, "_entities") else {"emails": [], "urls": [], "dates": [], "organizations": []}
                    counts = {k: len(v) for k, v in entities.items()}
                    self.db.conn.execute(
                        "INSERT INTO public_documents_85 VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        [document_id, case_id, title, canonical_url, "canonical_capture_103_1", hashlib.sha256(body.encode()).hexdigest(), dumps(counts), dumps(entities), evidence_id, created, dumps({"build": self.BUILD, "capture_id": capture_id})],
                    )
                self.db.conn.execute(
                    """INSERT INTO canonical_captures_103_1(capture_id,case_id,input_kind,original_url,canonical_url,host,title,content_sha256,text_sha256,html_sha256,screenshot_sha256,artifact_dir,text_path,html_path,screenshot_path,manifest_path,evidence_id,document_id,paste_id,browser_capture_id,status,warnings_json,metadata_json,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    [capture_id, case_id, normalized_kind, original_url, canonical_url, host, title, content_sha, text_sha, html_sha, screenshot_sha, str(cdir), text_path, html_path, stored_screenshot, str(manifest_path), evidence_id, document_id, paste_id, browser_id, storage_status, dumps(warnings), dumps({"source_label": source_label, "notes": notes, **(metadata or {})}), created, created],
                )
                self.db.conn.execute(
                    """INSERT INTO canonical_findings_103_1(finding_id,case_id,capture_id,status,review_status,title,excerpt,source_ref,evidence_id,document_id,metadata_json,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    [finding_id, case_id, capture_id, "candidate_not_claim", "candidate", title, excerpt, canonical_url, evidence_id, document_id, dumps({"build": self.BUILD}), created, created],
                )
                self.db.conn.execute(
                    """INSERT INTO pasted_findings_91(paste_id,case_id,title,input_kind,url,canonical_url,host,pasted_text_hash,pasted_html_hash,status,classification,capture_id,evidence_id,search_result_id,document_id,warnings_json,created_at,metadata_json,content_excerpt,source_label)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    [paste_id, case_id, title, "url" if canonical_url else "text", original_url, canonical_url, host, text_sha, html_sha, "candidate_not_claim", "public_web_candidate" if canonical_url else "public_text_candidate", capture_id, evidence_id, "", document_id, dumps(warnings), created, dumps({"build": self.BUILD, "canonical": True}), excerpt, source_label],
                )
                if browser_id:
                    self.db.conn.execute(
                        """INSERT INTO browser_captures_102(bridge_capture_id,case_id,url,canonical_url,title,capture_mode,status,html_path,text_path,screenshot_path,manifest_path,html_sha256,text_sha256,screenshot_sha256,manifest_sha256,real_capture_id,evidence_id,paste_id,warnings_json,metadata_json,created_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        [browser_id, case_id, original_url, canonical_url, title, "canonical_manual_browser_capture_103_1", "stored_candidate_not_claim", html_path, text_path, stored_screenshot, str(manifest_path), html_sha, text_sha, screenshot_sha, self._sha_file(manifest_path), capture_id, evidence_id, paste_id, dumps(warnings), dumps({"build": self.BUILD, "canonical": True}), created],
                    )
        except Exception:
            shutil.rmtree(cdir, ignore_errors=True)
            raise

        graph_refs = self._upsert_graph(case_id, capture_id, finding_id, title, canonical_url, evidence_id, document_id, excerpt)
        source_rating_id = ai_run_id = ""
        security_decision = "not_run"
        if self.reliability and canonical_url:
            try:
                rating = self.reliability.rate(case_id, canonical_url, source_type=str((metadata or {}).get("source_type") or "public_web_capture"), factors={"timestamped": True, "hash_verified": bool(text_sha or html_sha), "browser_capture_102": input_kind.startswith("browser"), "adapter_execution_104": bool((metadata or {}).get("adapter_execution_id"))})
                source_rating_id = rating.get("rating_id", "") or rating.get("source_rating_id", "")
            except Exception as exc:
                warnings.append({"level": "low", "code": "source_rating_failed", "message": str(exc)})
        if run_security and self.security:
            try:
                sec = self.security.assess_case_security(case_id, scope="canonical_intake_103_1")
                security_decision = sec.get("decision") or sec.get("status") or "review_required"
            except Exception as exc:
                security_decision = "review_required"
                warnings.append({"level": "medium", "code": "security_check_failed", "message": str(exc)})
        if run_ai_triage and self.local_ai:
            try:
                ai = self.local_ai.triage_pasted_finding(case_id, paste_id)
                ai_run_id = ai.get("run_id", "")
            except Exception as exc:
                warnings.append({"level": "low", "code": "ai_triage_failed", "message": str(exc)})
        self.db.execute(
            "UPDATE canonical_captures_103_1 SET source_rating_id=?,security_decision=?,ai_run_id=?,warnings_json=?,metadata_json=?,updated_at=? WHERE capture_id=?",
            [source_rating_id, security_decision, ai_run_id, dumps(warnings), dumps({"source_label": source_label, "notes": notes, "graph_refs": graph_refs, **(metadata or {})}), now_ts(), capture_id],
        )
        self.audit.log("canonical_intake", "canonical_capture_103_1", capture_id, case_id, {"finding_id": finding_id, "evidence_id": evidence_id, "status": "candidate_not_claim"})
        out = self.get_capture(capture_id)
        out["finding_id"] = finding_id
        out["deduplicated"] = False
        return out

    def review_finding(self, finding_id: str, decision: str, reason: str = "", actor: str = "local-analyst") -> Dict[str, Any]:
        allowed = {"accepted", "rejected", "disputed", "needs_review"}
        if decision not in allowed:
            raise ValueError(f"decision must be one of {sorted(allowed)}")
        row = self.db.one("SELECT * FROM canonical_findings_103_1 WHERE finding_id=?", [finding_id])
        if not row:
            raise KeyError(finding_id)
        self.db.execute("UPDATE canonical_findings_103_1 SET review_status=?,updated_at=? WHERE finding_id=?", [decision, now_ts(), finding_id])
        if self.review_board:
            self.review_board.decide(row["case_id"], "canonical_finding_103_1", finding_id, decision, reason=reason, actor=actor, metadata={"capture_id": row["capture_id"]})
        self.audit.log("review", "canonical_finding_103_1", finding_id, row["case_id"], {"decision": decision, "reason": reason})
        return self.get_finding(finding_id)

    # ---------- views / export ----------
    def dashboard(self, case_id: str = "") -> Dict[str, Any]:
        case_id = self.resolve_case_id(case_id)
        case = self.cases.get_case(case_id)
        counts = {
            "captures": self._count("canonical_captures_103_1", case_id),
            "evidence": self._count("local_evidence_items_75", case_id),
            "findings": self._count("canonical_findings_103_1", case_id),
            "graph_nodes": self._count("investigation_graph_nodes_68", case_id),
            "graph_edges": self._count("investigation_graph_edges_68", case_id),
            "claims": self._count("claims_v3_80", case_id),
            "reviews": self._count("review_decisions_88", case_id),
            "adapter_executions": self._count("source_adapter_executions_104", case_id),
        }
        security = {}
        try:
            security = self.security.assess_case_security(case_id, scope="platform_dashboard_103_1") if self.security else {}
        except Exception as exc:
            security = {"decision": "review_required", "error": str(exc)}
        return {
            "build": self.BUILD,
            "case": case,
            "counts": counts,
            "security": security,
            "recent_captures": self.list_captures(case_id, 10),
            "recent_findings": self.list_findings(case_id, 20),
            "ai": self.local_ai.build_case_context(case_id) if self.local_ai else {},
        }

    def export_casefile(self, case_id: str = "", export_mode: str = "authority_redacted") -> Dict[str, Any]:
        case_id = self.resolve_case_id(case_id)
        result = self.casefile.build(case_id, export_mode=export_mode, include_evidence_files=False)
        self.audit.log("export", "casefile_103_1", result.get("package_id", ""), case_id, {"export_mode": export_mode})
        return result

    def list_captures(self, case_id: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        case_id = self.resolve_case_id(case_id)
        rows = self.db.all("SELECT capture_id FROM canonical_captures_103_1 WHERE case_id=? ORDER BY created_at DESC LIMIT ?", [case_id, int(limit)])
        return [self.get_capture(r["capture_id"]) for r in rows]

    def list_findings(self, case_id: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        case_id = self.resolve_case_id(case_id)
        rows = self.db.all("SELECT finding_id FROM canonical_findings_103_1 WHERE case_id=? ORDER BY created_at DESC LIMIT ?", [case_id, int(limit)])
        return [self.get_finding(r["finding_id"]) for r in rows]

    def get_capture(self, capture_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM canonical_captures_103_1 WHERE capture_id=?", [capture_id])
        if not row:
            raise KeyError(capture_id)
        row["warnings"] = loads(row.pop("warnings_json", "[]"), [])
        row["metadata"] = loads(row.pop("metadata_json", "{}"), {})
        row["bridge_capture_id"] = row.get("browser_capture_id", "")
        row["real_capture_id"] = row.get("capture_id", "")
        finding = self.db.one("SELECT excerpt FROM canonical_findings_103_1 WHERE capture_id=?", [capture_id])
        row["content_excerpt"] = (finding or {}).get("excerpt", "")
        row["source_label"] = row.get("metadata", {}).get("source_label", "")
        manifest_path = row.get("manifest_path", "")
        row["manifest_sha256"] = self._sha_file(Path(manifest_path)) if manifest_path and Path(manifest_path).exists() else ""
        return row

    def get_finding(self, finding_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM canonical_findings_103_1 WHERE finding_id=?", [finding_id])
        if not row:
            raise KeyError(finding_id)
        row["metadata"] = loads(row.pop("metadata_json", "{}"), {})
        return row

    def verify_capture(self, capture_id: str) -> Dict[str, Any]:
        cap = self.get_capture(capture_id)
        problems: List[str] = []
        for path_key, hash_key in (("text_path", "text_sha256"), ("html_path", "html_sha256"), ("screenshot_path", "screenshot_sha256")):
            p = cap.get(path_key)
            expected = cap.get(hash_key)
            if p:
                fp = Path(p)
                if not fp.exists():
                    problems.append(path_key + "_missing")
                elif expected and self._sha_file(fp) != expected:
                    problems.append(path_key + "_hash_mismatch")
        return {"capture_id": capture_id, "valid": not problems, "problems": problems}

    # ---------- helpers ----------
    def _upsert_graph(self, case_id: str, capture_id: str, finding_id: str, title: str, canonical_url: str, evidence_id: str, document_id: str, excerpt: str) -> Dict[str, str]:
        refs: Dict[str, str] = {}
        source = self._graph_node(case_id, "url" if canonical_url else "source", canonical_url or "Manual public source", canonical_url, 45, canonical_url, {"build": self.BUILD})
        capture = self._graph_node(case_id, "capture", title, capture_id, 60, evidence_id or canonical_url, {"build": self.BUILD})
        finding = self._graph_node(case_id, "finding", title, excerpt[:500], 40, evidence_id or canonical_url, {"build": self.BUILD, "finding_id": finding_id})
        refs.update(source_node_id=source, capture_node_id=capture, finding_node_id=finding)
        self._graph_edge(case_id, source, capture, "captured_from", 60, "candidate", evidence_id)
        self._graph_edge(case_id, capture, finding, "derived_from", 50, "candidate", evidence_id)
        if evidence_id:
            ev = self._graph_node(case_id, "document", "Evidence artifact", evidence_id, 60, evidence_id, {"build": self.BUILD})
            refs["evidence_node_id"] = ev
            self._graph_edge(case_id, ev, finding, "supports", 45, "candidate", evidence_id)
        if document_id:
            doc = self._graph_node(case_id, "document", title, document_id, 50, canonical_url, {"build": self.BUILD})
            refs["document_node_id"] = doc
            self._graph_edge(case_id, capture, doc, "derived_from", 50, "candidate", evidence_id)
        return refs

    def _graph_node(self, case_id: str, node_type: str, label: str, value: str, confidence: int, source_ref: str, metadata: Dict[str, Any]) -> str:
        row = self.db.one("SELECT node_id FROM investigation_graph_nodes_68 WHERE case_id=? AND node_type=? AND value=? LIMIT 1", [case_id, node_type, value]) if value else None
        if not row:
            row = self.db.one("SELECT node_id FROM investigation_graph_nodes_68 WHERE case_id=? AND node_type=? AND label=? LIMIT 1", [case_id, node_type, label])
        if row:
            return row["node_id"]
        return self.graph.add_node(case_id, node_type, label, value=value, confidence=confidence, source_ref=source_ref, metadata=metadata)["node_id"]

    def _graph_edge(self, case_id: str, source: str, target: str, edge_type: str, confidence: int, review_status: str, evidence_ref: str) -> str:
        row = self.db.one("SELECT edge_id FROM investigation_graph_edges_68 WHERE case_id=? AND source_node_id=? AND target_node_id=? AND edge_type=? LIMIT 1", [case_id, source, target, edge_type])
        if row:
            return row["edge_id"]
        return self.graph.add_edge(case_id, source, target, edge_type, confidence=confidence, review_status=review_status, evidence_ref=evidence_ref, metadata={"build": self.BUILD})["edge_id"]

    def _count(self, table: str, case_id: str) -> int:
        try:
            row = self.db.one(f"SELECT COUNT(*) n FROM {table} WHERE case_id=?", [case_id])
            return int(row["n"] if row else 0)
        except Exception:
            return 0

    def _enforce_size(self, value: str, limit: int, label: str) -> None:
        if len((value or "").encode("utf-8")) > limit:
            raise ValueError(f"{label} exceeds size limit")

    def _validated_screenshot(self, path: Path) -> Path:
        path = path.resolve()
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(str(path))
        if path.suffix.lower() not in self.SCREENSHOT_EXTENSIONS:
            raise ValueError("Unsupported screenshot file type")
        if path.stat().st_size > self.MAX_SCREENSHOT_BYTES:
            raise ValueError("Screenshot exceeds size limit")
        mime = mimetypes.guess_type(str(path))[0] or ""
        if not mime.startswith("image/"):
            raise ValueError("Screenshot MIME type is not an image")
        head = path.read_bytes()[:16]
        valid_magic = (
            (path.suffix.lower() == ".png" and head.startswith(b"\x89PNG\r\n\x1a\n")) or
            (path.suffix.lower() in {".jpg", ".jpeg"} and head.startswith(b"\xff\xd8\xff")) or
            (path.suffix.lower() == ".webp" and head.startswith(b"RIFF") and head[8:12] == b"WEBP")
        )
        if not valid_magic:
            raise ValueError("Screenshot file signature does not match its extension")
        return path

    def _extract_title(self, html: str) -> str:
        m = re.search(r"<title[^>]*>(.*?)</title>", html or "", re.I | re.S)
        return re.sub(r"\s+", " ", html_lib.unescape(m.group(1))).strip() if m else ""

    def _html_to_text(self, html: str) -> str:
        no_script = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html or "", flags=re.I | re.S)
        return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", no_script))).strip()

    def _sha_file(self, path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
