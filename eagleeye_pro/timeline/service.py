from __future__ import annotations
from typing import Any, Dict, List
from collections import defaultdict
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.audit.service import AuditService

class TimelineService:
    """Build 22.0 Timeline Pro: Ereignisse, Unsicherheiten, Widersprüche und Narrativ."""

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit

    def add_event(self, case_id: str, event_date: str, title: str, description: str="", source_evidence_id: str="", confidence: str="candidate", review_status: str="candidate", event_type: str="osint_finding", actor: str="", location: str="", narrative_weight: float=0.5, uncertainty_note: str="") -> Dict[str, Any]:
        eid = new_id("time")
        self.db.execute("""INSERT INTO timeline_events(event_id,case_id,event_date,title,description,source_evidence_id,confidence,review_status,event_type,actor,location,narrative_weight,uncertainty_note)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""", [eid,case_id,event_date,title,description,source_evidence_id,confidence,review_status,event_type,actor,location,float(narrative_weight),uncertainty_note])
        self.audit.log("create", "timeline_event", eid, case_id, {"date": event_date, "title": title, "type": event_type, "evidence": source_evidence_id})
        return self.db.one("SELECT * FROM timeline_events WHERE event_id=?", [eid])

    def list_events(self, case_id: str) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM timeline_events WHERE case_id=? ORDER BY event_date ASC, narrative_weight DESC, title", [case_id])

    def build_from_evidence(self, case_id: str) -> Dict[str, Any]:
        created = 0
        for ev in self.db.all("SELECT * FROM evidence_items WHERE case_id=? ORDER BY captured_at", [case_id]):
            ev_id = ev.get("evidence_id")
            if not ev_id:
                continue
            existing = self.db.one("SELECT event_id FROM timeline_events WHERE case_id=? AND source_evidence_id=? AND event_type='evidence_capture'", [case_id, ev_id])
            if existing:
                continue
            date = (ev.get("captured_at") or now_ts())[:10]
            conf = ev.get("confidence") or "candidate"
            status = "accepted" if ev.get("review_decision") == "accepted" else "candidate"
            title = f"Evidence übernommen: {ev.get('title') or ev_id}"
            desc = f"Kategorie: {ev.get('category')}; Entscheidung: {ev.get('review_decision')}; Quelle: {ev.get('source_url') or 'n/a'}; Hash: {(ev.get('content_hash') or '')[:16]}..."
            self.add_event(case_id, date, title, desc, source_evidence_id=ev_id, confidence=conf, review_status=status, event_type="evidence_capture", actor=ev.get("captured_by") or "local-analyst", narrative_weight=float(ev.get("reliability_score") or 0.55), uncertainty_note="Zeitpunkt bezieht sich auf Capture/Übernahme, nicht zwingend auf das reale Ursprungsereignis.")
            created += 1
        self.audit.log("rebuild", "timeline", case_id, case_id, {"created_from_evidence": created})
        return {"case_id": case_id, "created": created, "events": len(self.list_events(case_id))}

    def detect_conflicts(self, case_id: str) -> Dict[str, Any]:
        events = self.list_events(case_id)
        by_title = defaultdict(list)
        for e in events:
            key = (e.get("title") or "").lower().strip()
            if key:
                by_title[key].append(e)
        conflicts=[]
        for key, rows in by_title.items():
            dates = sorted({(r.get("event_date") or "")[:10] for r in rows})
            if len(dates) > 1:
                conflicts.append({"title": rows[0].get("title"), "dates": dates, "event_ids": [r.get("event_id") for r in rows], "issue": "same_title_multiple_dates"})
                for r in rows:
                    self.db.execute("UPDATE timeline_events SET review_status=?, uncertainty_note=? WHERE event_id=?", ["conflicting", "Gleiches Ereignis/gleicher Titel liegt mit mehreren Daten vor; Gegenprüfung erforderlich.", r["event_id"]])
        self.audit.log("analyze", "timeline_conflicts", case_id, case_id, {"conflicts": conflicts})
        return {"case_id": case_id, "conflict_count": len(conflicts), "conflicts": conflicts}

    def timeline_dashboard(self, case_id: str) -> Dict[str, Any]:
        total = self.db.one("SELECT COUNT(*) AS n FROM timeline_events WHERE case_id=?", [case_id]) or {"n":0}
        types = self.db.all("SELECT event_type, COUNT(*) AS n FROM timeline_events WHERE case_id=? GROUP BY event_type", [case_id])
        status = self.db.all("SELECT review_status, COUNT(*) AS n FROM timeline_events WHERE case_id=? GROUP BY review_status", [case_id])
        bounds = self.db.one("SELECT MIN(event_date) AS first_date, MAX(event_date) AS last_date, AVG(narrative_weight) AS avg_weight FROM timeline_events WHERE case_id=?", [case_id]) or {}
        return {
            "events": int(total.get("n") or 0),
            "event_types": {r["event_type"]: r["n"] for r in types},
            "statuses": {r["review_status"]: r["n"] for r in status},
            "first_date": bounds.get("first_date") or "",
            "last_date": bounds.get("last_date") or "",
            "avg_narrative_weight": round(float(bounds.get("avg_weight") or 0), 3),
        }

    def build_narrative(self, case_id: str, title: str="Timeline-Narrativ") -> Dict[str, Any]:
        events = self.list_events(case_id)
        dash = self.timeline_dashboard(case_id)
        lines = [
            "Build 22.0 Timeline Pro – Zeitachsen-Narrativ.",
            "Zeitpunkte sind OSINT-/Evidence-Zeitpunkte oder manuell gesetzte Ereignisse und müssen quellenkritisch gelesen werden.",
            f"Zeitraum: {dash.get('first_date') or 'n/a'} bis {dash.get('last_date') or 'n/a'}; Ereignisse: {dash.get('events')}",
            f"Typen: {dash.get('event_types', {})}; Review-Status: {dash.get('statuses', {})}.",
        ]
        for e in events[:40]:
            uncertainty = f" Unsicherheit: {e.get('uncertainty_note')}" if e.get("uncertainty_note") else ""
            src = f" Evidence: {e.get('source_evidence_id')}" if e.get("source_evidence_id") else ""
            lines.append(f"- {e.get('event_date')} | {e.get('event_type')} | {e.get('title')} | Status: {e.get('review_status')}.{src}{uncertainty}")
        nid = new_id("narr")
        ts = now_ts()
        body = "\n".join(lines)
        self.db.execute("""INSERT INTO analysis_narratives(narrative_id,case_id,narrative_type,title,body,confidence_summary,source_object_ids_json,created_at,updated_at,analyst)
        VALUES(?,?,?,?,?,?,?,?,?,?)""", [nid, case_id, "timeline", title, body, "candidate_with_human_review", dumps([e.get("event_id") for e in events[:40]]), ts, ts, "local-analyst"])
        self.audit.log("create", "analysis_narrative", nid, case_id, {"type": "timeline", "title": title})
        return self.db.one("SELECT * FROM analysis_narratives WHERE narrative_id=?", [nid])

    def list_narratives(self, case_id: str, narrative_type: str | None=None) -> List[Dict[str, Any]]:
        if narrative_type:
            return self.db.all("SELECT * FROM analysis_narratives WHERE case_id=? AND narrative_type=? ORDER BY created_at DESC", [case_id, narrative_type])
        return self.db.all("SELECT * FROM analysis_narratives WHERE case_id=? ORDER BY created_at DESC", [case_id])
