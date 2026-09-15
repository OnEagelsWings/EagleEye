from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts


FINDING_STATUSES = {"candidate", "included", "needs_review", "counter_evidence", "discarded", "report_ready"}
FINDING_TYPES = {"web", "pdf", "image", "registry", "court", "finance", "network", "note", "other"}
NARRATIVE_STATUSES = {"draft", "review", "approved", "blocked"}


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, tuple):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value).replace(";", ",").split(",") if v.strip()]


class PersonDetailPageService:
    """Build 55.4 clickable person page.

    Provides a person/entity-centric workspace for documenting findings and
    writing a free-flow narrative result report. It intentionally does not make
    documented findings automatically true; all findings keep status, source,
    category and provenance links.
    """

    def __init__(self, db: Database, audit: AuditService, reports_root: str | Path):
        self.db = db
        self.audit = audit
        self.reports_root = Path(reports_root)
        self.reports_root.mkdir(parents=True, exist_ok=True)
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript(
            '''
            CREATE TABLE IF NOT EXISTS person_finding_notes_55_4 (
              finding_note_id TEXT PRIMARY KEY,
              case_id TEXT NOT NULL,
              entity_id TEXT NOT NULL,
              title TEXT NOT NULL,
              finding_type TEXT NOT NULL,
              source_url TEXT DEFAULT '',
              document_date TEXT DEFAULT '',
              category TEXT DEFAULT '',
              status TEXT NOT NULL,
              summary TEXT NOT NULL,
              analyst_note TEXT DEFAULT '',
              chain_node_id TEXT DEFAULT '',
              evidence_level TEXT DEFAULT 'candidate',
              redaction_required INTEGER NOT NULL DEFAULT 1,
              metadata_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_person_finding_notes_554_entity ON person_finding_notes_55_4(case_id, entity_id, updated_at);

            CREATE TABLE IF NOT EXISTS person_narrative_reports_55_4 (
              narrative_id TEXT PRIMARY KEY,
              case_id TEXT NOT NULL,
              entity_id TEXT NOT NULL,
              title TEXT NOT NULL,
              body TEXT NOT NULL,
              status TEXT NOT NULL,
              body_sha256 TEXT NOT NULL,
              finding_count INTEGER NOT NULL DEFAULT 0,
              source_metrics_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_person_narrative_reports_554_entity ON person_narrative_reports_55_4(case_id, entity_id, updated_at);
            '''
        )
        self.db.conn.commit()

    def build_person_page(self, case_id: str, entity_id: str) -> Dict[str, Any]:
        entity = self._entity(entity_id)
        if entity.get("case_id") != case_id:
            raise ValueError("Entity does not belong to selected case.")
        findings = self.list_findings(case_id, entity_id)
        narratives = self.list_narratives(case_id, entity_id)
        chain_nodes = self._chain_nodes(case_id, entity_id)
        status_counts: Dict[str, int] = {}
        type_counts: Dict[str, int] = {}
        for f in findings:
            status_counts[f.get("status", "candidate")] = status_counts.get(f.get("status", "candidate"), 0) + 1
            type_counts[f.get("finding_type", "other")] = type_counts.get(f.get("finding_type", "other"), 0) + 1
        return {
            "case_id": case_id,
            "entity_id": entity_id,
            "entity": entity,
            "findings": findings,
            "narratives": narratives,
            "chain_nodes": chain_nodes,
            "metrics": {
                "finding_count": len(findings),
                "narrative_count": len(narratives),
                "chain_node_count": len(chain_nodes),
                "status_counts": status_counts,
                "type_counts": type_counts,
            },
            "page_title": f"Personenakte – {entity.get('display_name', entity_id)}",
        }

    def add_finding_note(
        self,
        case_id: str,
        entity_id: str,
        *,
        title: str,
        summary: str,
        finding_type: str = "web",
        source_url: str = "",
        document_date: str = "",
        category: str = "",
        status: str = "candidate",
        analyst_note: str = "",
        chain_node_id: str = "",
        evidence_level: str = "candidate",
        redaction_required: bool = True,
        metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        self._ensure_entity_case(case_id, entity_id)
        if not title.strip():
            raise ValueError("Finding title is required.")
        if not summary.strip():
            raise ValueError("Finding summary is required.")
        finding_type = finding_type if finding_type in FINDING_TYPES else "other"
        status = status if status in FINDING_STATUSES else "candidate"
        finding_note_id = new_id("pfind554")
        now = now_ts()
        self.db.execute(
            '''INSERT INTO person_finding_notes_55_4(finding_note_id,case_id,entity_id,title,finding_type,source_url,document_date,category,status,summary,analyst_note,chain_node_id,evidence_level,redaction_required,metadata_json,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            [finding_note_id, case_id, entity_id, title.strip(), finding_type, source_url.strip(), document_date.strip(), category.strip(), status, summary.strip(), analyst_note.strip(), chain_node_id.strip(), evidence_level.strip() or "candidate", 1 if redaction_required else 0, dumps(metadata or {}), now, now],
        )
        self.audit.log("create", "person_finding_note_55_4", finding_note_id, case_id, {"entity_id": entity_id, "status": status, "type": finding_type})
        return self.get_finding(finding_note_id)

    def update_finding_status(self, finding_note_id: str, status: str, *, analyst_note: str = "") -> Dict[str, Any]:
        if status not in FINDING_STATUSES:
            raise ValueError("unsupported finding status")
        finding = self.get_finding(finding_note_id)
        note = analyst_note if analyst_note else finding.get("analyst_note", "")
        self.db.execute("UPDATE person_finding_notes_55_4 SET status=?, analyst_note=?, updated_at=? WHERE finding_note_id=?", [status, note, now_ts(), finding_note_id])
        self.audit.log("update", "person_finding_note_status_55_4", finding_note_id, finding["case_id"], {"status": status})
        return self.get_finding(finding_note_id)

    def list_findings(self, case_id: str, entity_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        rows = self.db.all(
            "SELECT * FROM person_finding_notes_55_4 WHERE case_id=? AND entity_id=? ORDER BY updated_at DESC LIMIT ?",
            [case_id, entity_id, int(limit)],
        )
        for r in rows:
            r["metadata"] = loads(r.pop("metadata_json", "{}"), {})
            r["redaction_required"] = bool(r.get("redaction_required"))
        return rows

    def get_finding(self, finding_note_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM person_finding_notes_55_4 WHERE finding_note_id=?", [finding_note_id])
        if not row:
            raise KeyError(finding_note_id)
        row["metadata"] = loads(row.pop("metadata_json", "{}"), {})
        row["redaction_required"] = bool(row.get("redaction_required"))
        return row

    def save_narrative(self, case_id: str, entity_id: str, *, title: str, body: str, status: str = "draft") -> Dict[str, Any]:
        self._ensure_entity_case(case_id, entity_id)
        if status not in NARRATIVE_STATUSES:
            raise ValueError("unsupported narrative status")
        if not body.strip():
            raise ValueError("Narrative body is required.")
        narrative_id = new_id("pnarr554")
        now = now_ts()
        findings = self.list_findings(case_id, entity_id)
        metrics = self._source_metrics(findings)
        body_sha = _sha_text(body)
        self.db.execute(
            '''INSERT INTO person_narrative_reports_55_4(narrative_id,case_id,entity_id,title,body,status,body_sha256,finding_count,source_metrics_json,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
            [narrative_id, case_id, entity_id, (title or "Ergebnisbericht").strip(), body.strip(), status, body_sha, len(findings), dumps(metrics), now, now],
        )
        self.audit.log("create", "person_narrative_report_55_4", narrative_id, case_id, {"entity_id": entity_id, "status": status, "sha256": body_sha})
        return self.get_narrative(narrative_id)

    def update_narrative(self, narrative_id: str, *, title: str | None = None, body: str | None = None, status: str | None = None) -> Dict[str, Any]:
        current = self.get_narrative(narrative_id)
        new_title = title if title is not None else current.get("title", "")
        new_body = body if body is not None else current.get("body", "")
        new_status = status if status is not None else current.get("status", "draft")
        if new_status not in NARRATIVE_STATUSES:
            raise ValueError("unsupported narrative status")
        self.db.execute(
            "UPDATE person_narrative_reports_55_4 SET title=?, body=?, status=?, body_sha256=?, updated_at=? WHERE narrative_id=?",
            [new_title, new_body, new_status, _sha_text(new_body), now_ts(), narrative_id],
        )
        self.audit.log("update", "person_narrative_report_55_4", narrative_id, current["case_id"], {"status": new_status})
        return self.get_narrative(narrative_id)

    def list_narratives(self, case_id: str, entity_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        rows = self.db.all(
            "SELECT * FROM person_narrative_reports_55_4 WHERE case_id=? AND entity_id=? ORDER BY updated_at DESC LIMIT ?",
            [case_id, entity_id, int(limit)],
        )
        for r in rows:
            r["source_metrics"] = loads(r.pop("source_metrics_json", "{}"), {})
        return rows

    def get_narrative(self, narrative_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM person_narrative_reports_55_4 WHERE narrative_id=?", [narrative_id])
        if not row:
            raise KeyError(narrative_id)
        row["source_metrics"] = loads(row.pop("source_metrics_json", "{}"), {})
        return row

    def build_default_narrative(self, case_id: str, entity_id: str) -> Dict[str, str]:
        page = self.build_person_page(case_id, entity_id)
        ent = page["entity"]
        findings = page["findings"]
        lines = [
            f"# Ergebnisbericht zur Person/Organisation: {ent.get('display_name', entity_id)}",
            "",
            "## Kurzfazit",
            "Dieser Bericht ist ein redaktioneller Arbeitsentwurf. Er trennt dokumentierte Funde, analystische Einschätzung, Unsicherheiten und offene Prüfpunkte.",
            "",
            "## Grundinformationen",
            f"- Typ: {ent.get('entity_type', '')}",
            f"- Name: {ent.get('display_name', '')}",
            f"- bekannte Namen: {', '.join(ent.get('known_names') or [])}",
            f"- Aliasse: {', '.join(ent.get('aliases') or [])}",
            f"- Orte: {', '.join(ent.get('places') or [])}",
            f"- Organisationen: {', '.join(ent.get('organizations') or [])}",
            f"- Rollen: {', '.join(ent.get('roles') or [])}",
            "",
            "## Dokumentierte Funde",
        ]
        if findings:
            for f in findings:
                lines.append(f"- {f.get('title')} [{f.get('status')}/{f.get('evidence_level')}] – {f.get('summary')}")
                if f.get("source_url"):
                    lines.append(f"  Quelle: {f.get('source_url')}")
        else:
            lines.append("- Noch keine Funde dokumentiert.")
        lines += [
            "",
            "## Ergebnis im Fließtext",
            "Bitte hier den zusammenhängenden Ergebnisbericht zur Person/Organisation formulieren.",
            "",
            "## Unsicherheiten / Gegenbelege",
            "- Namensgleichheiten, OCR-Fehler, unklare Datierungen und nicht unabhängige Quellen gesondert prüfen.",
            "",
            "## Offene Prüffragen",
            "- Welche Aussagen benötigen eine zweite unabhängige Quelle?",
            "- Welche Angaben sind sensibel und vor Export zu redigieren?",
        ]
        return {"title": f"Ergebnisbericht – {ent.get('display_name', entity_id)}", "body": "\n".join(lines)}

    def export_person_page_markdown(self, case_id: str, entity_id: str, *, narrative_id: str = "") -> Dict[str, Any]:
        page = self.build_person_page(case_id, entity_id)
        ent = page["entity"]
        if narrative_id:
            narrative = self.get_narrative(narrative_id)
            body = narrative.get("body", "")
            title = narrative.get("title", "Personenbericht")
        else:
            default = self.build_default_narrative(case_id, entity_id)
            body = default["body"]
            title = default["title"]
        outdir = self.reports_root / case_id / "person_pages"
        outdir.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in ent.get("display_name", entity_id))[:80]
        path = outdir / f"{safe_name}_{new_id('personpage')}.md"
        export_text = body + "\n\n---\n\n## Funddokumentation\n"
        for f in page["findings"]:
            export_text += f"\n### {f.get('title')}\n- Status: {f.get('status')}\n- Beleggrad: {f.get('evidence_level')}\n- Kategorie: {f.get('category')}\n- Quelle: {f.get('source_url')}\n\n{f.get('summary')}\n"
            if f.get("analyst_note"):
                export_text += f"\nAnalystische Notiz: {f.get('analyst_note')}\n"
        path.write_text(export_text, encoding="utf-8")
        sha = _sha_text(export_text)
        self.audit.log("export", "person_detail_page_55_4", entity_id, case_id, {"path": str(path), "sha256": sha, "title": title})
        return {"path": str(path), "sha256": sha, "title": title, "entity_id": entity_id, "case_id": case_id}

    def _source_metrics(self, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        by_status: Dict[str, int] = {}
        by_type: Dict[str, int] = {}
        by_category: Dict[str, int] = {}
        for f in findings:
            by_status[f.get("status", "candidate")] = by_status.get(f.get("status", "candidate"), 0) + 1
            by_type[f.get("finding_type", "other")] = by_type.get(f.get("finding_type", "other"), 0) + 1
            if f.get("category"):
                by_category[f.get("category")] = by_category.get(f.get("category"), 0) + 1
        return {"by_status": by_status, "by_type": by_type, "by_category": by_category}

    def _entity(self, entity_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM investigation_entities_54 WHERE entity_id=?", [entity_id])
        if not row:
            raise KeyError(entity_id)
        for col, logical in [
            ("known_names_json", "known_names"), ("aliases_json", "aliases"), ("dates_json", "dates"),
            ("places_json", "places"), ("organizations_json", "organizations"), ("roles_json", "roles"),
            ("identifiers_json", "identifiers"), ("public_links_json", "public_links"),
        ]:
            row[logical] = loads(row.pop(col, "[]"), [])
        return row

    def _ensure_entity_case(self, case_id: str, entity_id: str) -> None:
        ent = self._entity(entity_id)
        if ent.get("case_id") != case_id:
            raise ValueError("Entity does not belong to selected case.")

    def _chain_nodes(self, case_id: str, entity_id: str) -> List[Dict[str, Any]]:
        rows = self.db.all(
            "SELECT node_id,node_type,title,value,source_url,status,confidence_label,created_at FROM search_chain_nodes_54 WHERE case_id=? AND entity_id=? ORDER BY created_at DESC LIMIT 200",
            [case_id, entity_id],
        )
        return rows
