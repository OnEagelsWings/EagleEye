from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Iterable
import hashlib
import html
import json
import re
import zipfile

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.reporting.docx_writer import write_docx
from eagleeye_pro.reporting.pdf_writer import write_pdf

_EMAIL_RE = re.compile(r"(?i)([A-Z0-9._%+-]{1,64})@([A-Z0-9.-]+\.[A-Z]{2,})")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s()./-]{6,}\d)(?!\d)")

ALLOWED_OUTPUT_TYPES = {
    "profile",
    "report",
    "casefile",
    "authority_handover",
    "missing_child_brief",
    "organization_profile",
    "antisemitism_incident_profile",
}

DRAFT_STATUSES = {"draft", "review", "approved", "redaction_required", "blocked"}
REDACTION_STATUSES = {"redacted", "internal", "minimal_public", "authority_sensitive", "needs_redaction"}


def _redact(text: str) -> str:
    text = text or ""
    text = _EMAIL_RE.sub(lambda m: m.group(1)[:2] + "***@" + m.group(2), text)
    text = _PHONE_RE.sub("[REDACTED_PHONE]", text)
    return text


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value or "output").strip("_")[:80] or "output"


class OnePageOutputService:
    """Build 55.3 output/editor/export layer for the consolidated case workflow.

    Phase 3 adds a real profile/report editor: generated outputs can become
    editable drafts with status, redaction status and export approval.

    Phase 4 adds professional export packages: Markdown, HTML, PDF, DOCX,
    Search/Fund-Chain JSON, evidence matrix, source manifest and hash manifest.
    """

    def __init__(self, db: Database, audit: AuditService, reports_root: str | Path):
        self.db = db
        self.audit = audit
        self.reports_root = Path(reports_root)
        self.privacy_gate_55 = None
        self.reports_root.mkdir(parents=True, exist_ok=True)
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS one_page_outputs_54 (
          output_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT DEFAULT '',
          output_type TEXT NOT NULL,
          recipient_class TEXT NOT NULL,
          redaction_level TEXT NOT NULL,
          output_path TEXT NOT NULL,
          sha256 TEXT NOT NULL,
          manifest_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_onepage54_case ON one_page_outputs_54(case_id, created_at);

        CREATE TABLE IF NOT EXISTS profile_report_drafts_54 (
          draft_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT DEFAULT '',
          output_type TEXT NOT NULL,
          title TEXT NOT NULL,
          body TEXT NOT NULL,
          status TEXT NOT NULL,
          redaction_status TEXT NOT NULL,
          export_approved INTEGER NOT NULL DEFAULT 0,
          source_metrics_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_profile_report_drafts54_case ON profile_report_drafts_54(case_id, updated_at);
        """)
        self.db.conn.commit()


    def attach_privacy_gate(self, privacy_gate: Any) -> None:
        """Attach Build 55 privacy/export gate without making older tests or imports depend on it."""
        self.privacy_gate_55 = privacy_gate

    # ------------------------------------------------------------------
    # Phase 3: profile/report editor
    # ------------------------------------------------------------------
    def create_editor_draft(
        self,
        case_id: str,
        *,
        entity_id: str = "",
        output_type: str = "casefile",
        title: str = "",
        recipient_class: str = "authority_or_meldestelle",
        redaction_level: str = "redacted",
    ) -> Dict[str, Any]:
        if output_type not in ALLOWED_OUTPUT_TYPES:
            raise ValueError("unsupported output_type")
        draft_id = new_id("draft54")
        body = self.build_markdown(case_id, entity_id=entity_id, output_type=output_type, recipient_class=recipient_class, redaction_level=redaction_level)
        case = self._case(case_id)
        draft_title = title or f"{self._output_title(output_type)} – {case.get('title', case_id)}"
        chain = self._chain(case_id, entity_id)
        created = now_ts()
        self.db.execute(
            """INSERT INTO profile_report_drafts_54(draft_id,case_id,entity_id,output_type,title,body,status,redaction_status,export_approved,source_metrics_json,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            [draft_id, case_id, entity_id, output_type, draft_title, body, "draft", redaction_level, 0, dumps(chain.get("metrics", {})), created, created],
        )
        self.audit.log("create", "profile_report_draft_55_0", draft_id, case_id, {"output_type": output_type, "redaction_status": redaction_level})
        row = self.get_editor_draft(draft_id)
        row["body"] = body
        return row

    def update_editor_draft(
        self,
        draft_id: str,
        *,
        body: str | None = None,
        status: str | None = None,
        redaction_status: str | None = None,
        export_approved: bool | None = None,
        title: str | None = None,
    ) -> Dict[str, Any]:
        current = self.get_editor_draft(draft_id)
        new_status = status or current.get("status", "draft")
        new_redaction = redaction_status or current.get("redaction_status", "redacted")
        if new_status not in DRAFT_STATUSES:
            raise ValueError("unsupported draft status")
        if new_redaction not in REDACTION_STATUSES:
            raise ValueError("unsupported redaction status")
        approved = int(bool(export_approved)) if export_approved is not None else int(current.get("export_approved", 0))
        new_body = body if body is not None else current.get("body", "")
        new_title = title if title is not None else current.get("title", "")
        self.db.execute(
            """UPDATE profile_report_drafts_54
               SET body=?, status=?, redaction_status=?, export_approved=?, title=?, updated_at=?
               WHERE draft_id=?""",
            [new_body, new_status, new_redaction, approved, new_title, now_ts(), draft_id],
        )
        self.audit.log("update", "profile_report_draft_55_0", draft_id, current["case_id"], {"status": new_status, "redaction_status": new_redaction, "export_approved": approved})
        return self.get_editor_draft(draft_id)

    def list_editor_drafts(self, case_id: str, limit: int = 30) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM profile_report_drafts_54 WHERE case_id=? ORDER BY updated_at DESC LIMIT ?", [case_id, int(limit)])
        for r in rows:
            r["source_metrics"] = loads(r.pop("source_metrics_json", "{}"), {})
        return rows

    def get_editor_draft(self, draft_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM profile_report_drafts_54 WHERE draft_id=?", [draft_id])
        if not row:
            raise KeyError(draft_id)
        row["source_metrics"] = loads(row.pop("source_metrics_json", "{}"), {})
        return row

    def classify_profile_points(self, case_id: str, *, entity_id: str = "") -> Dict[str, Any]:
        """Return editor-ready profile points grouped by exportability and review state."""
        chain = self._chain(case_id, entity_id)
        included = [n for n in chain.get("nodes", []) if n.get("node_type") == "included_fact"]
        groups: Dict[str, List[Dict[str, Any]]] = {
            "facts_or_strong_indicators": [],
            "needs_review": [],
            "counter_evidence": [],
            "not_exportable": [],
        }
        for item in included:
            status = item.get("status") or "included"
            entry = {
                "node_id": item.get("node_id"),
                "statement": item.get("value"),
                "category": item.get("title"),
                "status": status,
                "status_label": item.get("status_label"),
                "confidence": item.get("confidence_label"),
                "source_url": item.get("source_url"),
                "path_text": item.get("path_text"),
                "export_recommendation": "review_before_export",
            }
            if status == "counter_evidence":
                entry["export_recommendation"] = "include_as_counter_evidence"
                groups["counter_evidence"].append(entry)
            elif status in {"discarded"}:
                entry["export_recommendation"] = "do_not_export"
                groups["not_exportable"].append(entry)
            elif status in {"report_released", "profile_candidate", "included"}:
                entry["export_recommendation"] = "exportable_with_source_and_uncertainty"
                groups["facts_or_strong_indicators"].append(entry)
            else:
                groups["needs_review"].append(entry)
        return {"case_id": case_id, "entity_id": entity_id, "groups": groups, "metrics": chain.get("metrics", {})}

    # ------------------------------------------------------------------
    # Legacy/regular one-page output API kept stable
    # ------------------------------------------------------------------
    def create_markdown_output(self, case_id: str, *, entity_id: str = "", output_type: str = "casefile", recipient_class: str = "authority_or_meldestelle", redaction_level: str = "redacted") -> Dict[str, Any]:
        if output_type not in ALLOWED_OUTPUT_TYPES:
            raise ValueError("unsupported output_type")
        output_id = new_id("out54")
        markdown = self.build_markdown(case_id, entity_id=entity_id, output_type=output_type, recipient_class=recipient_class, redaction_level=redaction_level)
        outdir = self.reports_root / case_id
        outdir.mkdir(parents=True, exist_ok=True)
        path = outdir / f"{output_id}_{output_type}.md"
        path.write_text(markdown, encoding="utf-8")
        sha = _sha_text(markdown)
        manifest = self._base_manifest(output_id, case_id, entity_id, output_type, recipient_class, redaction_level, sha)
        self.db.execute(
            """INSERT INTO one_page_outputs_54(output_id,case_id,entity_id,output_type,recipient_class,redaction_level,output_path,sha256,manifest_json,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            [output_id, case_id, entity_id, output_type, recipient_class, redaction_level, str(path), sha, dumps(manifest), manifest["created_at"]],
        )
        self.audit.log("create", "one_page_output_54", output_id, case_id, {"output_type": output_type, "sha256": sha})
        row = self.get_output(output_id)
        row["markdown"] = markdown
        return row

    def create_casefile_bundle(self, case_id: str, *, entity_id: str = "", recipient_class: str = "authority_or_meldestelle", redaction_level: str = "redacted") -> Dict[str, Any]:
        output = self.create_markdown_output(case_id, entity_id=entity_id, output_type="casefile", recipient_class=recipient_class, redaction_level=redaction_level)
        chain = self._chain(case_id, entity_id)
        output_id = output["output_id"]
        outdir = self.reports_root / case_id
        zip_path = outdir / f"{output_id}_casefile_bundle.zip"
        manifest = dict(output["manifest"])
        manifest.update({"bundle_type": "one_page_casefile_bundle", "files": []})
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            md = output["markdown"]
            zf.writestr("CASEFILE.md", md)
            manifest["files"].append({"path": "CASEFILE.md", "kind": "markdown_casefile", "sha256": _sha_text(md)})
            chain_json = json.dumps(chain, ensure_ascii=False, indent=2, default=str)
            zf.writestr("SEARCH_FUND_CHAIN.json", chain_json)
            manifest["files"].append({"path": "SEARCH_FUND_CHAIN.json", "kind": "chain_export", "sha256": _sha_text(chain_json)})
            zf.writestr("MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        bundle_sha = _sha_file(zip_path)
        manifest["bundle_sha256"] = bundle_sha
        self.audit.log("create", "one_page_casefile_bundle_54", output_id, case_id, {"bundle_sha256": bundle_sha})
        return {"output_id": output_id, "bundle_path": str(zip_path), "sha256": bundle_sha, "manifest": manifest, "markdown_path": output["output_path"]}

    # ------------------------------------------------------------------
    # Phase 4: professional export
    # ------------------------------------------------------------------
    def create_professional_export_bundle(
        self,
        case_id: str,
        *,
        entity_id: str = "",
        draft_id: str = "",
        recipient_class: str = "authority_or_meldestelle",
        redaction_level: str = "redacted",
    ) -> Dict[str, Any]:
        if draft_id:
            draft = self.get_editor_draft(draft_id)
            if draft["case_id"] != case_id:
                raise ValueError("draft does not belong to case")
            markdown = draft["body"]
            output_type = draft.get("output_type", "casefile")
            title = draft.get("title") or self._output_title(output_type)
            editor_status = draft.get("status", "draft")
            export_approved = bool(draft.get("export_approved"))
            if editor_status not in {"approved", "review"} and recipient_class not in {"internal_analyst"}:
                # Do not block internal work, but force visible status in manifest.
                pass
        else:
            output_type = "casefile"
            title = self._output_title(output_type)
            markdown = self.build_markdown(case_id, entity_id=entity_id, output_type=output_type, recipient_class=recipient_class, redaction_level=redaction_level)
            editor_status = "generated_without_editor_draft"
            export_approved = False
        privacy_review = None
        redaction_result = None
        if self.privacy_gate_55 is not None:
            # Build 55.3: apply redaction before writing external bundles, then
            # run the privacy/security export gate over the exact text to be exported.
            if redaction_level in {"redacted", "minimal_public", "authority_sensitive"}:
                redaction_result = self.privacy_gate_55.redact_text(markdown, level=redaction_level)
                markdown = redaction_result.get("text", markdown)
            privacy_review = self.privacy_gate_55.assess_export(
                case_id,
                entity_id=entity_id,
                draft_id=draft_id,
                recipient_class=recipient_class,
                redaction_level=redaction_level,
                text=markdown,
            )
            if privacy_review.get("decision") == "block" and recipient_class not in {"internal", "internal_analyst", "internal_casefile"}:
                reasons = "; ".join(str(b.get("code") or b.get("action") or b) for b in privacy_review.get("blockers", [])[:5])
                raise ValueError("PrivacyGate blockiert externen Export: " + reasons)

        export_id = new_id("proexp55")
        outdir = self.reports_root / case_id / export_id
        outdir.mkdir(parents=True, exist_ok=True)
        chain = self._chain(case_id, entity_id)
        evidence_md = self._build_evidence_matrix_markdown(chain)
        source_json = json.dumps(self._build_source_manifest(chain), ensure_ascii=False, indent=2, default=str)
        chain_json = json.dumps(chain, ensure_ascii=False, indent=2, default=str)
        audit_summary = self._build_audit_summary(case_id, export_id, draft_id, recipient_class, redaction_level, editor_status)
        html_doc = self._markdown_to_simple_html(markdown, title)

        files: List[Dict[str, Any]] = []
        def write_text_file(rel: str, content: str, kind: str) -> Path:
            p = outdir / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            files.append({"path": rel, "kind": kind, "sha256": _sha_text(content)})
            return p

        md_path = write_text_file("01_CASEFILE.md", markdown, "markdown_casefile")
        html_path = write_text_file("01_CASEFILE.html", html_doc, "html_casefile")
        write_text_file("03_SEARCH_FUND_CHAIN.json", chain_json, "search_fund_chain_json")
        write_text_file("04_EVIDENCE_MATRIX.md", evidence_md, "evidence_matrix")
        write_text_file("05_SOURCES.json", source_json, "source_manifest")
        write_text_file("07_AUDIT_SUMMARY.md", audit_summary, "audit_summary")

        pdf_path = outdir / "01_CASEFILE.pdf"
        docx_path = outdir / "01_CASEFILE.docx"
        pdf_lines = [line for line in markdown.splitlines() if line.strip()]
        write_pdf(pdf_path, title, pdf_lines)
        write_docx(docx_path, title, [("Fallakte", markdown.splitlines()), ("Belegmatrix", evidence_md.splitlines()), ("Audit", audit_summary.splitlines())])
        files.append({"path": "01_CASEFILE.pdf", "kind": "pdf_casefile", "sha256": _sha_file(pdf_path)})
        files.append({"path": "01_CASEFILE.docx", "kind": "docx_casefile", "sha256": _sha_file(docx_path)})

        manifest = self._base_manifest(export_id, case_id, entity_id, "professional_export_bundle", recipient_class, redaction_level, _sha_text(markdown))
        manifest.update({
            "build": "55.3",
            "bundle_type": "professional_casefile_export",
            "draft_id": draft_id,
            "editor_status": editor_status,
            "export_approved": export_approved,
            "files": files,
            "chain_metrics": chain.get("metrics", {}),
            "privacy_review": privacy_review or {},
            "redaction_result": redaction_result or {},
            "quality_rules": [
                "Profil-/Berichtsentwurf ist redaktionell bearbeitbar.",
                "Jeder Profilpunkt muss auf die Search/Fund-Chain zurückführbar sein.",
                "Professioneller Export enthält Markdown, HTML, PDF, DOCX, Chain-JSON, Belegmatrix, Quellenmanifest und Audit Summary.",
                "Sensible Daten werden nach Redaktionsstufe behandelt; öffentliche Auffindbarkeit ersetzt keine Verwertungsprüfung.",
                "Build 55.3: Externe Profi-Exporte laufen durch PrivacyGate und Redaction-Finish.",
            ],
        })
        manifest["bundle_sha256"] = "computed_after_zip_creation"
        manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2, default=str)
        write_text_file("06_MANIFEST.json", manifest_text, "manifest")

        zip_path = self.reports_root / case_id / f"{export_id}_PROFESSIONAL_CASEFILE.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                rel = f["path"]
                zf.write(outdir / rel, rel)
        bundle_sha = _sha_file(zip_path)
        manifest["bundle_sha256"] = bundle_sha
        output_id = export_id
        self.db.execute(
            """INSERT INTO one_page_outputs_54(output_id,case_id,entity_id,output_type,recipient_class,redaction_level,output_path,sha256,manifest_json,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            [output_id, case_id, entity_id, "professional_export_bundle", recipient_class, redaction_level, str(zip_path), bundle_sha, dumps(manifest), manifest["created_at"]],
        )
        self.audit.log("create", "professional_casefile_export_55_0", output_id, case_id, {"bundle_sha256": bundle_sha, "draft_id": draft_id, "privacy_decision": (privacy_review or {}).get("decision")})
        return {"output_id": output_id, "bundle_path": str(zip_path), "bundle_dir": str(outdir), "sha256": bundle_sha, "manifest": manifest, "markdown_path": str(md_path), "pdf_path": str(pdf_path), "docx_path": str(docx_path), "html_path": str(html_path)}

    def build_markdown(self, case_id: str, *, entity_id: str = "", output_type: str = "casefile", recipient_class: str = "authority_or_meldestelle", redaction_level: str = "redacted") -> str:
        case = self._case(case_id)
        entities = self._entities(case_id, entity_id)
        chain = self._chain(case_id, entity_id)
        nodes = chain.get("nodes", [])
        metrics = chain.get("metrics", {})
        queries = [n for n in nodes if n.get("node_type") in {"search_query", "derived_query"}]
        findings = [n for n in nodes if n.get("node_type") == "source_hit"]
        included = [n for n in nodes if n.get("node_type") == "included_fact"]
        point_groups = self.classify_profile_points(case_id, entity_id=entity_id)["groups"]

        title = _redact(case.get("title", "Unbenannter Fall"))
        lines: List[str] = [
            f"# EagleEye Build 55.3 – {self._output_title(output_type)}",
            "",
            f"**Fall:** {title}",
            f"**Fall-ID:** `{case_id}`",
            f"**Empfängerklasse:** {recipient_class}",
            f"**Redaktion:** {redaction_level}",
            f"**Erstellt:** {now_ts()}",
            "",
            "## 1. Fallbasis",
            f"- Zweck: {_redact(case.get('purpose', ''))}",
            f"- Rechtsgrundlage: {_redact(case.get('legal_basis', ''))}",
            f"- Jurisdiktion: {_redact(case.get('jurisdiction', ''))}",
            f"- Risiko: {_redact(case.get('risk_level', ''))}",
            "",
            "## 2. Personen / Organisationen / Ereignisse",
        ]
        if not entities:
            lines.append("- Keine Entity erfasst.")
        for e in entities:
            lines.append(f"- **{e.get('entity_type')}**: {_redact(e.get('display_name',''))}")
            for label, key in [("Namen", "known_names"), ("Aliasse", "aliases"), ("Zeiträume/Daten", "dates"), ("Orte", "places"), ("Organisationen", "organizations"), ("Rollen", "roles"), ("Kennungen", "identifiers"), ("öffentliche Links", "public_links")]:
                vals = e.get(key) or []
                if vals:
                    lines.append(f"  - {label}: " + "; ".join(_redact(str(v)) for v in vals[:15]))
        lines += [
            "",
            "## 3. Redaktionelle Profilpunkte",
            "### 3.1 Fakten / starke öffentliche Hinweise",
        ]
        for p in point_groups["facts_or_strong_indicators"][:80]:
            lines.append(f"- **{_redact(p.get('category','Information'))}:** {_redact(p.get('statement',''))}")
            lines.append(f"  - Status: {p.get('status_label')} | Beleggrad: {p.get('confidence')} | Export: {p.get('export_recommendation')}")
            lines.append(f"  - Chain: {_redact(p.get('path_text',''))}")
        if not point_groups["facts_or_strong_indicators"]:
            lines.append("- Noch keine profilfähigen Informationen.")
        lines += ["", "### 3.2 Review erforderlich"]
        for p in point_groups["needs_review"][:50]:
            lines.append(f"- {_redact(p.get('statement',''))} | Status: {p.get('status_label')} | Chain: {_redact(p.get('path_text',''))}")
        if not point_groups["needs_review"]:
            lines.append("- Keine Review-Punkte aus der Chain markiert.")
        lines += ["", "### 3.3 Gegenbelege"]
        for p in point_groups["counter_evidence"][:50]:
            lines.append(f"- Gegenbeleg: {_redact(p.get('statement',''))} | Chain: {_redact(p.get('path_text',''))}")
        if not point_groups["counter_evidence"]:
            lines.append("- Keine Gegenbelege markiert.")
        lines += [
            "",
            "## 4. Search/Fund-Chain – Lagebild",
            f"- Nodes: {metrics.get('nodes', 0)}",
            f"- Suchanfragen: {metrics.get('queries', 0)}",
            f"- Funde: {metrics.get('findings', 0)}",
            f"- inkludierte Informationen: {metrics.get('included_facts', 0)}",
            f"- Profilkandidaten: {metrics.get('profile_candidates', 0)}",
            f"- für Bericht freigegeben: {metrics.get('report_ready', 0)}",
            f"- Statusverteilung: {metrics.get('status_counts', {})}",
            "",
            "## 4a. Rückverfolgbare Chain-Pfade",
        ]
        for fact in included[:40]:
            lines.append(f"- `{fact.get('node_id')}` {_redact(fact.get('value',''))}: {_redact(fact.get('path_text',''))}")
        if not included:
            lines.append("- Noch keine inkludierten Informationen mit Chain-Pfad.")
        lines += ["", "## 5. Abgeleitete Suchanfragen"]
        for q in queries[:60]:
            meta = q.get("metadata") or {}
            lines.append(f"- `{q.get('node_id')}` {meta.get('engine','')}: {_redact(q.get('value',''))} | Status: {q.get('status_label','')} | Tiefe: {q.get('depth',0)}")
        if not queries:
            lines.append("- Noch keine Suchanfragen erzeugt.")
        lines += ["", "## 6. Funde / Kandidaten"]
        for f in findings[:80]:
            url = f.get("source_url", "")
            lines.append(f"- `{f.get('node_id')}` {_redact(f.get('title',''))} | {url} | Relevanz {f.get('relevance_score','')} | Status: {f.get('status_label','')}")
            if f.get("value"):
                lines.append(f"  - Auszug: {_redact(f.get('value',''))[:500]}")
        if not findings:
            lines.append("- Noch keine Funde erfasst.")
        lines += ["", "## 7. Inkludierte Informationen / Profilkandidaten"]
        for fact in included[:120]:
            lines.append(f"- **{_redact(fact.get('title','Information'))}:** {_redact(fact.get('value',''))}")
            lines.append(f"  - Chain: Quelle/Fund `{fact.get('parent_node_id','')}` | Beleggrad: {fact.get('confidence_label','included_candidate')} | Status: {fact.get('status_label','')} | Pfad: {_redact(fact.get('path_text',''))}")
        if not included:
            lines.append("- Noch keine inkludierten Informationen erfasst.")
        lines += [
            "",
            "## 8. Unsicherheiten / offene Prüffragen",
            "- Namensgleichheit ist keine Identität; Doppler-Risiko bleibt zu prüfen.",
            "- Presse-/PDF-/Registertreffer sind Kandidaten, bis Quelle, Datum, Ort und Kontext geprüft sind.",
            "- Jede starke Aussage benötigt unabhängige Zweitquelle oder klare behördliche Prüfung.",
            "",
            "## 9. Nicht zulässige automatische Schlussfolgerungen",
            "- keine automatische Schuldbehauptung",
            "- keine automatische Gefährlichkeitsbehauptung",
            "- keine automatische bestätigte Identität",
            "- keine private Adresse / Privatnummer / Live-Location im Export ohne dokumentierte rechtliche Grundlage",
            "",
            "## 10. Nächste sinnvolle Schritte",
        ]
        if queries and not findings:
            lines.append("- Sichtbare Suchanfragen öffnen, Treffer prüfen und relevante Funde zur markierten Query hinzufügen.")
        elif findings and not included:
            lines.append("- Relevante Funde manuell prüfen und konkrete Informationen inkludieren, damit neue Suchparameter abgeleitet werden.")
        else:
            lines.append("- Inkludierte Informationen gegenprüfen, Gegenbelege suchen, Beleggrad festlegen und Behörden-/Fallaktenexport erzeugen.")
        return "\n".join(lines) + "\n"

    def latest_outputs(self, case_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM one_page_outputs_54 WHERE case_id=? ORDER BY created_at DESC LIMIT ?", [case_id, int(limit)])
        for r in rows:
            r["manifest"] = loads(r.pop("manifest_json", "{}"), {})
        return rows

    def get_output(self, output_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM one_page_outputs_54 WHERE output_id=?", [output_id])
        if not row:
            raise KeyError(output_id)
        row["manifest"] = loads(row.pop("manifest_json", "{}"), {})
        return row

    # ------------------------------------------------------------------
    # Data/format helpers
    # ------------------------------------------------------------------
    def _case(self, case_id: str) -> Dict[str, Any]:
        return self.db.one("SELECT * FROM cases WHERE case_id=?", [case_id]) or {}

    def _entities(self, case_id: str, entity_id: str = "") -> List[Dict[str, Any]]:
        if entity_id:
            rows = self.db.all("SELECT * FROM investigation_entities_54 WHERE case_id=? AND entity_id=? ORDER BY created_at", [case_id, entity_id])
        else:
            rows = self.db.all("SELECT * FROM investigation_entities_54 WHERE case_id=? ORDER BY created_at", [case_id])
        out = []
        for r in rows:
            for col, key in [("known_names_json", "known_names"), ("aliases_json", "aliases"), ("dates_json", "dates"), ("places_json", "places"), ("organizations_json", "organizations"), ("roles_json", "roles"), ("identifiers_json", "identifiers"), ("public_links_json", "public_links")]:
                r[key] = loads(r.pop(col, "[]"), [])
            out.append(r)
        return out

    def _chain(self, case_id: str, entity_id: str = "") -> Dict[str, Any]:
        if entity_id:
            nodes = self.db.all("SELECT * FROM search_chain_nodes_54 WHERE case_id=? AND entity_id=? ORDER BY created_at", [case_id, entity_id])
            edges = self.db.all("SELECT * FROM search_chain_edges_54 WHERE case_id=? AND (from_node_id IN (SELECT node_id FROM search_chain_nodes_54 WHERE entity_id=?) OR to_node_id IN (SELECT node_id FROM search_chain_nodes_54 WHERE entity_id=?)) ORDER BY created_at", [case_id, entity_id, entity_id])
        else:
            nodes = self.db.all("SELECT * FROM search_chain_nodes_54 WHERE case_id=? ORDER BY created_at", [case_id])
            edges = self.db.all("SELECT * FROM search_chain_edges_54 WHERE case_id=? ORDER BY created_at", [case_id])
        status_labels = {"active":"aktiv", "planned":"geplant", "opened":"gesucht/geöffnet", "found":"Fund vorhanden", "included":"inkludiert", "discarded":"verworfen", "counter_evidence":"Gegenbeleg", "profile_candidate":"Profilkandidat", "report_released":"für Bericht freigegeben", "needs_review":"Review erforderlich"}
        by_id: Dict[str, Dict[str, Any]] = {}
        for n in nodes:
            n["metadata"] = loads(n.pop("metadata_json", "{}"), {})
            by_id[n["node_id"]] = n
        def trace_for(node: Dict[str, Any]) -> List[Dict[str, Any]]:
            out: List[Dict[str, Any]] = []
            cur = node
            safety = 0
            while cur and safety < 100:
                out.append(cur)
                cur = by_id.get(cur.get("parent_node_id", ""))
                safety += 1
            return list(reversed(out))
        for n in nodes:
            tr = trace_for(n)
            n["depth"] = max(0, len(tr) - 1)
            n["status_label"] = status_labels.get(n.get("status") or "active", n.get("status") or "active")
            n["beleggrad"] = n.get("confidence_label", "candidate")
            n["path_text"] = " → ".join(f"{x.get('node_type')}:{x.get('title')}" for x in tr)
            n["trace_node_ids"] = [x.get("node_id") for x in tr]
            n["profile_eligible"] = n.get("node_type") == "included_fact" and n.get("status") not in {"discarded", "counter_evidence"}
            n["report_ready"] = n.get("status") == "report_released"
        metrics = {"nodes": len(nodes), "edges": len(edges), "queries": 0, "findings": 0, "included_facts": 0, "seed_info": 0, "status_counts": {}, "profile_candidates": 0, "report_ready": 0}
        for n in nodes:
            if n.get("node_type") in {"search_query", "derived_query"}: metrics["queries"] += 1
            if n.get("node_type") == "source_hit": metrics["findings"] += 1
            if n.get("node_type") == "included_fact": metrics["included_facts"] += 1
            if n.get("node_type") == "seed_info": metrics["seed_info"] += 1
            metrics["status_counts"][n.get("status", "active")] = metrics["status_counts"].get(n.get("status", "active"), 0) + 1
            if n.get("profile_eligible"): metrics["profile_candidates"] += 1
            if n.get("report_ready"): metrics["report_ready"] += 1
        return {"case_id": case_id, "entity_id": entity_id, "nodes": nodes, "edges": edges, "metrics": metrics, "build": "55.3", "quality_rule": "Kein Profilpunkt ohne Rückverfolgung: Grundinfo → Query → Fund → inkludierte Information."}

    def _output_title(self, output_type: str) -> str:
        return {
            "profile": "Profil aus Fallaufnahme und Search/Fund-Chain",
            "report": "Berichtsentwurf aus Fallaufnahme und Search/Fund-Chain",
            "casefile": "Fallakte aus Fallaufnahme und Search/Fund-Chain",
            "authority_handover": "Behördenübergabe aus Fallaufnahme und Search/Fund-Chain",
            "missing_child_brief": "Vermisstenfall-Sofortlage aus Fallaufnahme und Chain",
            "organization_profile": "Organisationsprofil aus Registern, Quellen und Chain",
            "antisemitism_incident_profile": "Antisemitismus-Vorfallprofil aus Chain und Quellen",
        }.get(output_type, "Fallakte")

    def _base_manifest(self, output_id: str, case_id: str, entity_id: str, output_type: str, recipient_class: str, redaction_level: str, sha: str) -> Dict[str, Any]:
        return {
            "build": "55.3",
            "output_id": output_id,
            "case_id": case_id,
            "entity_id": entity_id,
            "output_type": output_type,
            "recipient_class": recipient_class,
            "redaction_level": redaction_level,
            "sha256": sha,
            "created_at": now_ts(),
            "rules": [
                "Output comes from one-page intake and Search/Fund-Chain.",
                "Facts, indicators, uncertainties and open questions are separated.",
                "No automatic guilt, danger, confirmed identity, private address, biometric or live-location claim.",
            ],
        }

    def _build_evidence_matrix_markdown(self, chain: Dict[str, Any]) -> str:
        lines = ["# Evidence Matrix", "", "| ID | Kategorie | Aussage | Status | Beleggrad | Quelle | Chain |", "|---|---|---|---|---|---|---|"]
        included = [n for n in chain.get("nodes", []) if n.get("node_type") == "included_fact"]
        for n in included:
            lines.append("| {id} | {cat} | {val} | {status} | {conf} | {src} | {path} |".format(
                id=str(n.get("node_id", ""))[:18],
                cat=_redact(str(n.get("title", ""))).replace("|", "/"),
                val=_redact(str(n.get("value", ""))).replace("|", "/"),
                status=str(n.get("status_label", n.get("status", ""))).replace("|", "/"),
                conf=str(n.get("confidence_label", "")).replace("|", "/"),
                src=str(n.get("source_url", "")).replace("|", "/"),
                path=_redact(str(n.get("path_text", ""))).replace("|", "/"),
            ))
        if not included:
            lines.append("| - | - | Noch keine inkludierten Informationen | - | - | - | - |")
        return "\n".join(lines) + "\n"

    def _build_source_manifest(self, chain: Dict[str, Any]) -> Dict[str, Any]:
        findings = [n for n in chain.get("nodes", []) if n.get("node_type") == "source_hit"]
        return {"source_count": len(findings), "sources": [{"node_id": n.get("node_id"), "title": n.get("title"), "url": n.get("source_url"), "status": n.get("status"), "path": n.get("path_text")} for n in findings]}

    def _build_audit_summary(self, case_id: str, export_id: str, draft_id: str, recipient_class: str, redaction_level: str, editor_status: str) -> str:
        return "\n".join([
            "# Audit Summary",
            "",
            f"- Export-ID: `{export_id}`",
            f"- Fall-ID: `{case_id}`",
            f"- Draft-ID: `{draft_id or 'ohne'}`",
            f"- Empfängerklasse: {recipient_class}",
            f"- Redaktionsstufe: {redaction_level}",
            f"- Editorstatus: {editor_status}",
            f"- Erstellt: {now_ts()}",
            "- Exportregel: kein Profilpunkt ohne Chain, kein Export ohne Beleggrad.",
        ]) + "\n"

    def _markdown_to_simple_html(self, markdown: str, title: str) -> str:
        body = []
        for line in markdown.splitlines():
            esc = html.escape(line)
            if line.startswith("# "):
                body.append(f"<h1>{html.escape(line[2:])}</h1>")
            elif line.startswith("## "):
                body.append(f"<h2>{html.escape(line[3:])}</h2>")
            elif line.startswith("### "):
                body.append(f"<h3>{html.escape(line[4:])}</h3>")
            elif line.startswith("- "):
                body.append(f"<p>• {esc[2:]}</p>")
            elif not line.strip():
                body.append("<br>")
            else:
                body.append(f"<p>{esc}</p>")
        return f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title></head><body>{''.join(body)}</body></html>"
