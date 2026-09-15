from __future__ import annotations
import html
import re
from pathlib import Path
from typing import Any, Dict, List
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.case.service import CaseService, TargetService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

class AnalystWorkspaceUI71Service:
    """Build 71.0 real analyst workspace UI foundation.

    This is a local, static workspace renderer for the top-tier PersonOSINT
    platform direction. It turns cockpit, graph, capture, case and quality data
    into a review-first analyst surface without live collection, bypassing, or
    unsupported external calls.
    """
    def __init__(self, db: Database, audit: AuditService, workspace_dir: str | Path, *, cases: CaseService | None = None, targets: TargetService | None = None, cockpit=None, graph=None, capture_vault=None, quality_control=None):
        self.db = db
        self.audit = audit
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.cases = cases
        self.targets = targets
        self.cockpit = cockpit
        self.graph = graph
        self.capture_vault = capture_vault
        self.quality_control = quality_control
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS analyst_workspace_ui_snapshots_71 (
          workspace_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, entity_id TEXT DEFAULT '',
          label TEXT NOT NULL, readiness_score INTEGER NOT NULL, html_path TEXT DEFAULT '', markdown_path TEXT DEFAULT '',
          panels_json TEXT NOT NULL, actions_json TEXT NOT NULL, warnings_json TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_workspace71_case ON analyst_workspace_ui_snapshots_71(case_id, created_at);
        """)
        self.db.conn.commit()

    def build_workspace(self, case_id: str, entity_id: str = "", persist: bool = True, export_files: bool = True) -> Dict[str, Any]:
        case = self._case(case_id)
        targets = self.targets.list_targets(case_id) if self.targets else []
        cockpit = self.cockpit.build_dashboard(case_id, entity_id=entity_id, persist=False) if self.cockpit else {"readiness_score": 0, "label": "unknown", "panels": {}, "next_actions": []}
        graph = self.graph.build_graph(case_id) if self.graph else {"nodes": [], "edges": [], "metrics": {}}
        captures = self.capture_vault.list_case_artifacts(case_id) if self.capture_vault else []
        quality = self.quality_control.latest(case_id, entity_id) if self.quality_control else None
        panels = {
            "case_header": self._case_header(case, targets),
            "mission_control": self._mission_control(cockpit),
            "entity_board": self._entity_board(targets, graph),
            "capture_timeline": self._capture_timeline(captures),
            "graph_map": self._graph_map(graph),
            "review_board": self._review_board(graph, captures, quality),
            "export_gate": self._export_gate(cockpit, quality, captures),
        }
        warnings = self._warnings(panels, cockpit, quality)
        actions = self._actions(panels, cockpit, warnings)
        readiness = self._score(cockpit, panels, warnings)
        label = self._label(readiness)
        workspace_id = new_id("ui71")
        markdown = self.render_markdown(case_id, panels, actions, warnings, readiness, label)
        html_doc = self.render_html(case_id, panels, actions, warnings, readiness, label)
        html_path = markdown_path = ""
        if export_files:
            out_dir = self.workspace_dir / self._safe_name(case.get("title") or case_id)
            out_dir.mkdir(parents=True, exist_ok=True)
            html_file = out_dir / f"{workspace_id}.html"
            md_file = out_dir / f"{workspace_id}.md"
            html_file.write_text(html_doc, encoding="utf-8")
            md_file.write_text(markdown, encoding="utf-8")
            html_path, markdown_path = str(html_file), str(md_file)
        result = {
            "workspace_id": workspace_id, "case_id": case_id, "entity_id": entity_id,
            "build_version": "71.0", "label": label, "readiness_score": readiness,
            "panels": panels, "actions": actions, "warnings": warnings,
            "html_path": html_path, "markdown_path": markdown_path, "created_at": now_ts(),
        }
        if persist:
            self.db.execute("""INSERT INTO analyst_workspace_ui_snapshots_71(workspace_id,case_id,entity_id,label,readiness_score,html_path,markdown_path,panels_json,actions_json,warnings_json,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""", [workspace_id, case_id, entity_id, label, readiness, html_path, markdown_path, dumps(panels), dumps(actions), dumps(warnings), result["created_at"]])
            self.audit.log("build", "analyst_workspace_ui_71", workspace_id, case_id, {"label": label, "readiness_score": readiness})
        return result

    def latest(self, case_id: str) -> Dict[str, Any] | None:
        row = self.db.one("SELECT * FROM analyst_workspace_ui_snapshots_71 WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id])
        if not row:
            return None
        row["panels"] = loads(row.pop("panels_json", "{}"), {})
        row["actions"] = loads(row.pop("actions_json", "[]"), [])
        row["warnings"] = loads(row.pop("warnings_json", "[]"), [])
        return row

    def render_markdown(self, case_id: str, panels: Dict[str, Any], actions: List[str], warnings: List[str], readiness: int, label: str) -> str:
        lines: List[str] = []
        head = panels.get("case_header", {})
        lines.append(f"# EagleEye Analyst Workspace 71.0 – {head.get('title', case_id)}")
        lines.append("")
        lines.append(f"**Status:** {label}  ")
        lines.append(f"**Readiness:** {readiness}/100  ")
        lines.append(f"**Zweckbindung:** {head.get('purpose', '')}  ")
        lines.append(f"**Rechtsgrundlage:** {head.get('legal_basis', '')}  ")
        lines.append("")
        lines.append("## Warnungen")
        for w in warnings or ["keine kritischen UI-Warnungen"]:
            lines.append(f"- {w}")
        lines.append("")
        lines.append("## Nächste Arbeitsschritte")
        for a in actions:
            lines.append(f"- {a}")
        lines.append("")
        lines.append("## Capture Timeline")
        for item in panels.get("capture_timeline", {}).get("items", []):
            lines.append(f"- {item.get('created_at','')} – {item.get('title','')} – {item.get('normalized_url','')} – {item.get('custody_status','')}")
        lines.append("")
        lines.append("## Graph Map")
        gm = panels.get("graph_map", {})
        lines.append(f"Nodes: {gm.get('node_count',0)} | Edges: {gm.get('edge_count',0)} | Reviewed: {gm.get('reviewed_edge_count',0)}")
        for n in gm.get("top_nodes", []):
            lines.append(f"- {n.get('node_type')}: {n.get('label')} ({n.get('confidence',0)}%)")
        lines.append("")
        lines.append("## Export Gate")
        eg = panels.get("export_gate", {})
        lines.append(f"Decision: {eg.get('decision','review_required')}")
        for r in eg.get("reasons", []):
            lines.append(f"- {r}")
        return "\n".join(lines) + "\n"

    def render_html(self, case_id: str, panels: Dict[str, Any], actions: List[str], warnings: List[str], readiness: int, label: str) -> str:
        head = panels.get("case_header", {})
        def esc(v: Any) -> str: return html.escape(str(v or ""))
        capture_items = "".join(f"<li><b>{esc(i.get('title'))}</b><br><span>{esc(i.get('normalized_url'))}</span><br><small>{esc(i.get('created_at'))} · {esc(i.get('custody_status'))}</small></li>" for i in panels.get("capture_timeline", {}).get("items", [])) or "<li>Noch keine Capture-Artefakte.</li>"
        graph_nodes = "".join(f"<li>{esc(n.get('node_type'))}: <b>{esc(n.get('label'))}</b> <small>{esc(n.get('confidence'))}%</small></li>" for n in panels.get("graph_map", {}).get("top_nodes", [])) or "<li>Noch keine Graph-Knoten.</li>"
        warning_items = "".join(f"<li>{esc(w)}</li>" for w in warnings) or "<li>Keine kritischen UI-Warnungen.</li>"
        action_items = "".join(f"<li>{esc(a)}</li>" for a in actions) or "<li>Keine offenen Pflichtaktionen.</li>"
        export_gate = panels.get("export_gate", {})
        export_reasons = "".join(f"<li>{esc(r)}</li>" for r in export_gate.get("reasons", [])) or "<li>Keine zusätzlichen Hinweise.</li>"
        return f"""<!doctype html>
<html lang=\"de\"><head><meta charset=\"utf-8\"><title>EagleEye Workspace 71 – {esc(head.get('title', case_id))}</title>
<style>
body{{font-family:Arial,Helvetica,sans-serif;margin:0;background:#f6f7f9;color:#1f2937}}header{{background:#111827;color:white;padding:24px}}main{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:16px}}section{{background:white;border:1px solid #e5e7eb;border-radius:12px;padding:16px;box-shadow:0 1px 2px rgba(0,0,0,.04)}}.wide{{grid-column:1/-1}}.score{{font-size:40px;font-weight:700}}.pill{{display:inline-block;padding:4px 8px;border-radius:999px;background:#e5e7eb;margin-right:6px}}ul{{padding-left:20px}}small,span{{color:#6b7280}}@media(max-width:900px){{main{{grid-template-columns:1fr}}}}
</style></head><body>
<header><h1>EagleEye Analyst Workspace 71.0</h1><p>{esc(head.get('title'))} · {esc(head.get('jurisdiction'))} · {esc(head.get('status'))}</p></header>
<main>
<section><h2>Readiness</h2><div class=\"score\">{readiness}/100</div><p><span class=\"pill\">{esc(label)}</span><span class=\"pill\">review-first</span><span class=\"pill\">public-only</span></p></section>
<section><h2>Zweckbindung</h2><p><b>Zweck:</b> {esc(head.get('purpose'))}</p><p><b>Rechtsgrundlage:</b> {esc(head.get('legal_basis'))}</p><p><b>Targets:</b> {esc(head.get('target_count'))}</p></section>
<section><h2>Warnungen</h2><ul>{warning_items}</ul></section>
<section><h2>Nächste Schritte</h2><ul>{action_items}</ul></section>
<section><h2>Capture Timeline</h2><ul>{capture_items}</ul></section>
<section><h2>Graph Map</h2><p>{esc(panels.get('graph_map',{}).get('node_count',0))} Nodes · {esc(panels.get('graph_map',{}).get('edge_count',0))} Edges · {esc(panels.get('graph_map',{}).get('reviewed_edge_count',0))} reviewed</p><ul>{graph_nodes}</ul></section>
<section class=\"wide\"><h2>Export Gate</h2><p><b>Decision:</b> {esc(export_gate.get('decision'))}</p><ul>{export_reasons}</ul></section>
</main></body></html>"""

    def _case(self, case_id: str) -> Dict[str, Any]:
        if self.cases:
            return self.cases.get_case(case_id)
        return self.db.one("SELECT * FROM cases WHERE case_id=?", [case_id]) or {"case_id": case_id, "title": case_id, "purpose": "", "legal_basis": "", "status": "unknown", "jurisdiction": ""}

    def _case_header(self, case: Dict[str, Any], targets: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {"case_id": case.get("case_id"), "title": case.get("title"), "client": case.get("client"), "purpose": case.get("purpose"), "legal_basis": case.get("legal_basis"), "jurisdiction": case.get("jurisdiction"), "risk_level": case.get("risk_level"), "status": case.get("status"), "target_count": len(targets), "targets": [t.get("name") for t in targets[:8]]}

    def _mission_control(self, cockpit: Dict[str, Any]) -> Dict[str, Any]:
        return {"label": cockpit.get("label"), "readiness_score": cockpit.get("readiness_score", 0), "next_actions": cockpit.get("next_actions", []), "panels": cockpit.get("panels", {})}

    def _entity_board(self, targets: List[Dict[str, Any]], graph: Dict[str, Any]) -> Dict[str, Any]:
        person_nodes = [n for n in graph.get("nodes", []) if n.get("node_type") == "person"]
        return {"target_count": len(targets), "targets": targets[:10], "person_node_count": len(person_nodes), "person_nodes": person_nodes[:10]}

    def _capture_timeline(self, captures: List[Dict[str, Any]]) -> Dict[str, Any]:
        items = [{k: c.get(k, "") for k in ["artifact_id", "title", "normalized_url", "capture_mode", "custody_status", "created_at", "text_hash", "file_hash"]} for c in captures[:25]]
        return {"artifact_count": len(captures), "items": items}

    def _graph_map(self, graph: Dict[str, Any]) -> Dict[str, Any]:
        metrics = graph.get("metrics", {})
        nodes = sorted(graph.get("nodes", []), key=lambda n: int(n.get("confidence", 0)), reverse=True)
        return {"node_count": metrics.get("node_count", len(nodes)), "edge_count": metrics.get("edge_count", len(graph.get("edges", []))), "reviewed_edge_count": metrics.get("reviewed_edge_count", 0), "node_types": metrics.get("node_types", []), "top_nodes": nodes[:12]}

    def _review_board(self, graph: Dict[str, Any], captures: List[Dict[str, Any]], quality: Dict[str, Any] | None) -> Dict[str, Any]:
        candidate_edges = [e for e in graph.get("edges", []) if e.get("review_status") == "candidate"]
        unverified_caps = [c for c in captures if c.get("custody_status") != "verified"]
        return {"candidate_edge_count": len(candidate_edges), "unverified_capture_count": len(unverified_caps), "quality_label": (quality or {}).get("label", "not_evaluated"), "quality_score": (quality or {}).get("score", 0)}

    def _export_gate(self, cockpit: Dict[str, Any], quality: Dict[str, Any] | None, captures: List[Dict[str, Any]]) -> Dict[str, Any]:
        reasons: List[str] = []
        score = int(cockpit.get("readiness_score", 0) or 0)
        qscore = int((quality or {}).get("score", 0) or 0)
        if not captures:
            reasons.append("no_capture_artifacts_linked_to_case")
        if qscore < 50:
            reasons.append("quality_control_below_export_threshold_or_missing")
        if score < 70:
            reasons.append("cockpit_readiness_below_professional_beta")
        decision = "export_ready_for_redacted_review" if score >= 70 and qscore >= 50 and captures else "review_required_before_export"
        return {"decision": decision, "reasons": reasons}

    def _warnings(self, panels: Dict[str, Any], cockpit: Dict[str, Any], quality: Dict[str, Any] | None) -> List[str]:
        warnings: List[str] = []
        if panels["capture_timeline"].get("artifact_count", 0) == 0:
            warnings.append("No verified source capture exists yet; claims must not be finalized.")
        if panels["graph_map"].get("node_count", 0) < 3:
            warnings.append("Investigation graph is still too thin for robust person attribution.")
        if not quality:
            warnings.append("Quality Control 65 has not been run for this workspace.")
        if cockpit.get("readiness_score", 0) < 70:
            warnings.append("Cockpit readiness is below professional beta threshold.")
        return warnings

    def _actions(self, panels: Dict[str, Any], cockpit: Dict[str, Any], warnings: List[str]) -> List[str]:
        actions = list(cockpit.get("next_actions") or [])
        if panels["entity_board"].get("target_count", 0) == 0 and panels["entity_board"].get("person_node_count", 0) == 0:
            actions.append("create_or_import_primary_person_entity")
        if panels["capture_timeline"].get("artifact_count", 0) == 0:
            actions.append("capture_first_public_source_snapshot")
        if panels["review_board"].get("candidate_edge_count", 0) > 0:
            actions.append("review_candidate_graph_edges")
        if warnings:
            actions.append("resolve_workspace_warnings_before_report_export")
        return list(dict.fromkeys(actions))[:10]

    def _score(self, cockpit: Dict[str, Any], panels: Dict[str, Any], warnings: List[str]) -> int:
        base = int(cockpit.get("readiness_score", 0) or 0)
        capture_bonus = min(15, panels["capture_timeline"].get("artifact_count", 0) * 5)
        graph_bonus = min(15, panels["graph_map"].get("node_count", 0) * 2 + panels["graph_map"].get("reviewed_edge_count", 0) * 3)
        warning_penalty = min(25, len(warnings) * 5)
        return max(0, min(100, base + capture_bonus + graph_bonus - warning_penalty))

    def _label(self, score: int) -> str:
        if score >= 85:
            return "operator_ready_workspace"
        if score >= 70:
            return "professional_beta_workspace"
        if score >= 50:
            return "structured_analyst_workspace"
        return "workspace_foundation"

    def _safe_name(self, text: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", text or "case").strip("._")[:80] or "case"
