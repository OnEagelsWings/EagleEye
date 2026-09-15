from __future__ import annotations

from typing import Any, Dict, List

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts


class ClaimNarrativeReport62Service:
    """Build 62.0: stronger report drafting from findings, claims and dashboard state."""

    def __init__(self, db: Database, audit: AuditService, *, person_detail=None, dashboard=None, osint_core=None, privacy_finish=None):
        self.db = db
        self.audit = audit
        self.person_detail = person_detail
        self.dashboard = dashboard
        self.osint_core = osint_core
        self.privacy_finish = privacy_finish
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS claim_narrative_reports_62 (
          report_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          narrative_id TEXT DEFAULT '',
          title TEXT NOT NULL,
          body TEXT NOT NULL,
          metrics_json TEXT NOT NULL,
          export_readiness TEXT DEFAULT 'draft',
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_claimrep62_entity ON claim_narrative_reports_62(case_id, entity_id, created_at DESC);
        ''')
        self.db.conn.commit()

    def build_report(self, case_id: str, entity_id: str, *, session_id: str = "", save_to_person_file: bool = True) -> Dict[str, Any]:
        page = self.person_detail.build_person_page(case_id, entity_id) if self.person_detail else {"entity": {}, "findings": [], "narratives": []}
        dash = self.dashboard.dashboard(case_id, entity_id) if self.dashboard else {}
        core = self.osint_core.dashboard(session_id) if (session_id and self.osint_core) else (dash.get("latest_core") or {})
        ent = page.get("entity", {})
        findings = page.get("findings", [])
        claims = (core.get("claims") or dash.get("claims") or [])
        report_ready = [f for f in findings if f.get("status") in {"report_ready", "included"}]
        counter = [f for f in findings if f.get("status") == "counter_evidence"]
        needs_review = [f for f in findings if f.get("status") in {"needs_review", "candidate"}]
        metrics = {
            "finding_count": len(findings), "report_ready_count": len(report_ready), "claim_count": len(claims),
            "counter_evidence_count": len(counter), "needs_review_count": len(needs_review),
            "dashboard_status": dash.get("status_ampel", {}),
        }
        title = f"Ergebnisbericht – {ent.get('display_name', entity_id)}"
        body = self._body(ent, findings, claims, dash, metrics)
        readiness = "review_required"
        if metrics["report_ready_count"] >= 2 and metrics["claim_count"] >= 1 and metrics["counter_evidence_count"] == 0:
            readiness = "authority_draft"
        elif metrics["finding_count"] == 0:
            readiness = "insufficient_data"
        narrative_id = ""
        if save_to_person_file and self.person_detail:
            narrative = self.person_detail.save_narrative(case_id, entity_id, title=title, body=body, status="review")
            narrative_id = narrative.get("narrative_id", "")
        report_id = new_id("crep62")
        self.db.execute('''INSERT INTO claim_narrative_reports_62(report_id,case_id,entity_id,narrative_id,title,body,metrics_json,export_readiness,created_at)
        VALUES(?,?,?,?,?,?,?,?,?)''', [report_id, case_id, entity_id, narrative_id, title, body, dumps(metrics), readiness, now_ts()])
        self.audit.log("create", "claim_narrative_report_62", report_id, case_id, {"entity_id": entity_id, "readiness": readiness, "narrative_id": narrative_id})
        return {"report_id": report_id, "narrative_id": narrative_id, "case_id": case_id, "entity_id": entity_id, "title": title, "body": body, "metrics": metrics, "export_readiness": readiness}

    def latest(self, case_id: str, entity_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM claim_narrative_reports_62 WHERE case_id=? AND entity_id=? ORDER BY created_at DESC LIMIT ?", [case_id, entity_id, int(limit)])
        for r in rows:
            r["metrics"] = loads(r.pop("metrics_json", "{}"), {})
        return rows

    def _body(self, ent: Dict[str, Any], findings: List[Dict[str, Any]], claims: List[Dict[str, Any]], dash: Dict[str, Any], metrics: Dict[str, Any]) -> str:
        name = ent.get("display_name") or ent.get("entity_id") or "Zielperson/Zielorganisation"
        lines: List[str] = [
            f"# Ergebnisbericht zu {name}",
            "",
            "## 1. Kurzfazit",
            f"Zu {name} liegen aktuell {metrics['finding_count']} dokumentierte Funde und {metrics['claim_count']} Claim-/Aussagekandidaten vor. Dieser Bericht ist ein prüfpflichtiger Arbeitsentwurf; er trennt belastbare öffentliche Hinweise, offene Prüffragen und Gegenbelege.",
            "",
            "## 2. Identitätsanker und Kontext",
            f"- Typ: {ent.get('entity_type','')}",
            f"- bekannte Namen: {', '.join(ent.get('known_names') or [])}",
            f"- Aliasse: {', '.join(ent.get('aliases') or [])}",
            f"- Orte: {', '.join(ent.get('places') or [])}",
            f"- Organisationen: {', '.join(ent.get('organizations') or [])}",
            f"- Rollen: {', '.join(ent.get('roles') or [])}",
            "",
            "## 3. Belastbare öffentliche Hinweise / reportfähige Funde",
        ]
        ready = [f for f in findings if f.get("status") in {"report_ready", "included"}]
        if ready:
            for f in ready[:15]:
                lines.append(f"- **{f.get('title')}** [{f.get('status')}/{f.get('evidence_level')}]: {f.get('summary')}")
                if f.get("source_url"): lines.append(f"  Quelle: {f.get('source_url')}")
        else:
            lines.append("- Noch keine Funde als reportfähig markiert. Top-Funde müssen geprüft und freigegeben werden.")
        lines += ["", "## 4. Claim-/Aussagekandidaten"]
        if claims:
            for c in claims[:12]:
                title = c.get("claim") or c.get("title") or c.get("claim_text") or "Claim-Kandidat"
                lines.append(f"- {title} | Beleggrad: {c.get('confidence') or c.get('claim_strength') or c.get('score','prüfen')}")
        else:
            lines.append("- Noch keine automatisch gebildeten Claims vorhanden oder Dashboard nicht mit OSINT-Core-Session verknüpft.")
        lines += ["", "## 5. Unsicherheiten, Namensdoppler und Gegenbelege"]
        counter = [f for f in findings if f.get("status") == "counter_evidence"]
        if counter:
            for f in counter[:10]: lines.append(f"- Gegenbeleg/Prüfpunkt: {f.get('title')} – {f.get('summary')}")
        else:
            lines.append("- Keine Gegenbelege dokumentiert. Namensdoppler und Gegenqueries bleiben gesondert zu prüfen.")
        lines += ["", "## 6. Offene Prüffragen und nächste Schritte"]
        for a in (dash.get("next_actions") or [])[:10]:
            lines.append(f"- {a.get('title')}: {a.get('query','')} {a.get('rationale','')}")
        if not (dash.get("next_actions") or []):
            lines.append("- Weitere Top-Treffer importieren, Entity-Fit prüfen, reportfähige Claims bilden.")
        lines += ["", "## 7. Export-/Datenschutzhinweis", "Sensible Angaben, Minderjährigen-/Opfer-/Zeugendaten, private Adressen, ungesicherte Vorwürfe und Gesundheits-/Religionsdaten sind vor externer Weitergabe zu redigieren und rechtlich zu prüfen."]
        return "\n".join(lines)
