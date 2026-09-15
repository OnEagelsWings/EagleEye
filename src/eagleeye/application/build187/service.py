from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping

from eagleeye_pro.core.database import dumps, new_id, now_ts


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


class Build187SourceOperationsCenterService:
    """Operational control plane for sources with a beginner-safe workspace model."""

    BUILD = "187.0"
    EXPERIENCE_MODES = {"guided", "expert"}
    HEALTH_STATES = {"healthy", "degraded", "down", "not_tested", "blocked"}
    SOURCE_STATES = {
        "DOCUMENTED", "FIXTURE_VALIDATED", "LIVE_REVIEW_REQUIRED", "LIVE_VALIDATED",
        "PRODUCTION_READY", "BLOCKED", "DEGRADED", "SUSPENDED"
    }
    OPERATIONAL_REFERENCES = (
        {"source_id":"openapi_source_contracts","title":"OpenAPI Source Contracts","class":"connector_standard","endpoint":"https://spec.openapis.org/oas/latest.html"},
        {"source_id":"json_schema_source_validation","title":"JSON Schema Validation","class":"schema_standard","endpoint":"https://json-schema.org/specification"},
        {"source_id":"rfc6585_rate_limits","title":"HTTP Rate Limit Semantics","class":"protocol_standard","endpoint":"https://www.rfc-editor.org/rfc/rfc6585"},
        {"source_id":"w3c_prov_source_lineage","title":"W3C PROV Source Lineage","class":"provenance_standard","endpoint":"https://www.w3.org/TR/prov-o/"},
        {"source_id":"owasp_api_security","title":"OWASP API Security","class":"security_standard","endpoint":"https://owasp.org/www-project-api-security/"},
        {"source_id":"ietf_http_semantics","title":"HTTP Semantics","class":"protocol_standard","endpoint":"https://www.rfc-editor.org/rfc/rfc9110"},
    )

    def __init__(self, db: Any, audit: Any, *, production_sources: Any, guided_router: Any, actor: str = "system"):
        self.db, self.audit = db, audit
        self.production_sources, self.guided_router, self.actor = production_sources, guided_router, actor

    def synchronize(self, *, confirmation: str) -> dict[str, Any]:
        if confirmation != "SOURCE OPERATIONS 187 SYNCHRONISIEREN":
            raise PermissionError("explicit approval required")
        rows = self.db.all("SELECT * FROM production_source_profiles_1857 ORDER BY title")
        created = 0
        for row in rows:
            source = dict(row)
            payload = {
                "source_id": source["source_id"], "title": source["title"],
                "source_class": source["authority"], "mode": source["mode"],
                "endpoint": source["endpoint"], "status": source["status"],
                "production_active": bool(source["production_active"]),
                "terms_status": "reviewed" if source["status"] in {"LIVE_VALIDATED", "PRODUCTION_READY"} else "review_required",
                "credential_status": "not_required" if source["auth"] == "none" else "setup_required",
                "parser_status": source["parser_status"], "rate_limit_per_minute": int(source["rate_limit_per_minute"]),
            }
            self.db.execute(
                "INSERT OR REPLACE INTO source_operations_profiles_187 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (payload["source_id"], payload["title"], payload["source_class"], payload["mode"], payload["endpoint"],
                 payload["status"], int(payload["production_active"]), payload["terms_status"], payload["credential_status"],
                 payload["parser_status"], payload["rate_limit_per_minute"], None, None, 0, 0.0,
                 self._initial_quality(payload), now_ts(), _hash(payload)),
            )
            created += 1
        self._event("sources_synchronized", "*", {"count": created})
        return {"synchronized": created, "production_active": sum(1 for r in rows if r["production_active"]), "automatic_activation": False}

    def seed_operational_references(self, *, confirmation: str) -> dict[str, Any]:
        if confirmation != "SOURCE REFERENCES 187 ANLEGEN":
            raise PermissionError("explicit approval required")
        return {"created": len(self.OPERATIONAL_REFERENCES), "references": list(self.OPERATIONAL_REFERENCES), "production_active": 0}

    def record_health(self, source_id: str, *, health_status: str, http_status: int | None = None,
                      latency_ms: int | None = None, error_code: str = "", error_message: str = "",
                      records_received: int = 0, confirmation: str) -> dict[str, Any]:
        if confirmation != f"SOURCE HEALTH 187 {source_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        if health_status not in self.HEALTH_STATES:
            raise ValueError("unsupported health status")
        row = self.db.one("SELECT * FROM source_operations_profiles_187 WHERE source_id=?", (source_id,))
        if not row:
            raise KeyError(source_id)
        observed = now_ts(); event_id = new_id("health187")
        safe_error = (error_message or "")[:500]
        payload = {"event_id":event_id,"source_id":source_id,"health_status":health_status,"http_status":http_status,
                   "latency_ms":latency_ms,"error_code":error_code,"error_message":safe_error,
                   "records_received":max(0,int(records_received)),"observed_at":observed}
        self.db.execute("INSERT INTO source_health_events_187 VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (event_id,source_id,health_status,http_status,latency_ms,error_code,safe_error,payload["records_received"],observed,_hash(payload)))
        success = health_status == "healthy"
        failures = 0 if success else int(row["consecutive_failures"]) + 1
        avg = float(row["average_latency_ms"] or 0)
        if latency_ms is not None:
            avg = float(latency_ms) if avg <= 0 else round((avg * 0.7) + (float(latency_ms) * 0.3), 2)
        status = row["status"]
        if health_status == "down" and failures >= 3: status = "DEGRADED"
        quality = self._quality_score(dict(row), health_status, failures, avg)
        self.db.execute("UPDATE source_operations_profiles_187 SET status=?,last_success_at=?,last_failure_at=?,consecutive_failures=?,average_latency_ms=?,quality_score=?,updated_at=? WHERE source_id=?",
                        (status, observed if success else row["last_success_at"], observed if not success else row["last_failure_at"], failures, avg, quality, observed, source_id))
        self._event("health_recorded", source_id, payload)
        return {**payload,"consecutive_failures":failures,"quality_score":quality,"automatic_disable":False,"review_required":not success}

    def record_terms_review(self, source_id: str, *, decision: str, reviewer: str, evidence_ref: str,
                            valid_until: str | None = None, confirmation: str) -> dict[str, Any]:
        if confirmation != f"SOURCE TERMS 187 {source_id} PRUEFEN": raise PermissionError("explicit approval required")
        if decision not in {"accepted_for_sandbox","accepted_for_production","restricted","rejected"}: raise ValueError("unsupported decision")
        if not self.db.one("SELECT source_id FROM source_operations_profiles_187 WHERE source_id=?",(source_id,)): raise KeyError(source_id)
        rid=new_id("terms187"); created=now_ts(); payload={"review_id":rid,"source_id":source_id,"decision":decision,"reviewer":reviewer,"evidence_ref":evidence_ref,"valid_until":valid_until,"created_at":created}
        self.db.execute("INSERT INTO source_terms_reviews_187 VALUES(?,?,?,?,?,?,?,?)",(rid,source_id,decision,reviewer,evidence_ref,valid_until,created,_hash(payload)))
        terms_status = "reviewed_production" if decision=="accepted_for_production" else decision
        self.db.execute("UPDATE source_operations_profiles_187 SET terms_status=?,updated_at=? WHERE source_id=?",(terms_status,created,source_id))
        self._event("terms_reviewed",source_id,payload)
        return payload

    def set_experience_mode(self, principal: str, *, mode: str, show_technical_details: bool | None = None,
                            confirmation: str) -> dict[str, Any]:
        if confirmation != f"SOURCE UX 187 {principal} SPEICHERN": raise PermissionError("explicit approval required")
        if mode not in self.EXPERIENCE_MODES: raise ValueError("unsupported experience mode")
        technical = bool(show_technical_details) if show_technical_details is not None else mode == "expert"
        payload={"principal":principal,"experience_mode":mode,"show_technical_details":technical,
                 "default_source_view":"recommended" if mode=="guided" else "operations","updated_at":now_ts()}
        self.db.execute("INSERT OR REPLACE INTO source_workspace_preferences_187 VALUES(?,?,?,?,?,?)",
                        (principal,mode,int(technical),payload["default_source_view"],payload["updated_at"],_hash(payload)))
        return payload

    def dashboard(self, *, principal: str = "system") -> dict[str, Any]:
        pref=self.db.one("SELECT * FROM source_workspace_preferences_187 WHERE principal=?",(principal,))
        mode=pref["experience_mode"] if pref else "guided"
        rows=[dict(r) for r in self.db.all("SELECT * FROM source_operations_profiles_187 ORDER BY production_active DESC,quality_score DESC,title")]
        counts={"total":len(rows),"production_ready":0,"healthy":0,"degraded":0,"action_required":0}
        latest={r["source_id"]:self.db.one("SELECT health_status FROM source_health_events_187 WHERE source_id=? ORDER BY observed_at DESC LIMIT 1",(r["source_id"],)) for r in rows}
        cards=[]
        for r in rows:
            health=(latest[r["source_id"]]["health_status"] if latest[r["source_id"]] else "not_tested")
            if r["status"]=="PRODUCTION_READY": counts["production_ready"]+=1
            if health=="healthy": counts["healthy"]+=1
            if health in {"degraded","down"} or r["terms_status"] in {"review_required","rejected"}: counts["action_required"]+=1
            if health in {"degraded","down"}: counts["degraded"]+=1
            next_action=self._next_action(r,health)
            card={"source_id":r["source_id"],"title":r["title"],"status":r["status"],"health":health,
                  "quality_score":round(float(r["quality_score"] or 0),2),"next_action":next_action,
                  "production_active":bool(r["production_active"]),"terms_status":r["terms_status"],
                  "credential_status":r["credential_status"],"parser_status":r["parser_status"]}
            if mode=="expert": card.update({"endpoint":r["endpoint"],"mode":r["mode"],"rate_limit_per_minute":r["rate_limit_per_minute"],"average_latency_ms":r["average_latency_ms"]})
            cards.append(card)
        return {"build":self.BUILD,"experience_mode":mode,"counts":counts,"sources":cards,
                "beginner_message":"Wähle zuerst die Fragestellung. EagleEye zeigt dann nur passende Quellen und den nächsten Prüfschritt.",
                "expert_message":"Health, Terms, Credentials, Parser, Rate Limits und Quality sind gemeinsam steuerbar.",
                "automatic_activation":False,"human_release_required":True}

    def route_question(self, *, case_id: str, question: str, person: Mapping[str, Any], lawful_basis: str,
                       principal: str = "system", confirmation: str) -> dict[str, Any]:
        route=self.production_sources.route_with_readiness(case_id=case_id,question=question,person=person,lawful_basis=lawful_basis,confirmation=confirmation)
        dashboard=self.dashboard(principal=principal)
        states={x["source_id"]:x for x in dashboard["sources"]}
        steps=[]
        for step in route.get("steps",[]):
            item=dict(step); state=states.get(item.get("source_id"),{})
            item["operational_health"]=state.get("health","not_tested")
            item["quality_score"]=state.get("quality_score",0)
            item["next_action"]=state.get("next_action","Quelle öffnen und Treffer als Kandidat sichern")
            steps.append(item)
        steps.sort(key=lambda x:(x.get("execution_mode")!="structured_connector", -float(x.get("quality_score") or 0)))
        return {**route,"steps":steps,"experience_mode":dashboard["experience_mode"],
                "workflow_position":"2_research_sources","next_global_step":"3_verify_candidates",
                "candidate_only":True,"automatic_identity_confirmation":False}

    @staticmethod
    def _initial_quality(payload: Mapping[str, Any]) -> float:
        score=20.0
        if payload.get("parser_status")=="FIXTURE_VALIDATED": score+=25
        if payload.get("terms_status")!="review_required": score+=20
        if payload.get("credential_status") in {"not_required","ready"}: score+=15
        if payload.get("production_active"): score+=20
        return min(100.0,score)

    @staticmethod
    def _quality_score(row: Mapping[str, Any], health: str, failures: int, avg_latency: float) -> float:
        score=35.0
        if row.get("parser_status")=="FIXTURE_VALIDATED": score+=20
        if row.get("terms_status") in {"reviewed","reviewed_production"}: score+=15
        if row.get("credential_status") in {"not_required","ready"}: score+=10
        score += {"healthy":20,"degraded":5,"not_tested":0,"blocked":-15,"down":-25}[health]
        score -= min(20,failures*5)
        if avg_latency>5000: score-=10
        elif 0<avg_latency<1000: score+=5
        return round(max(0.0,min(100.0,score)),2)

    @staticmethod
    def _next_action(row: Mapping[str, Any], health: str) -> str:
        if row.get("terms_status")=="review_required": return "Nutzungsbedingungen prüfen"
        if row.get("credential_status")=="setup_required": return "Zugang lokal einrichten"
        if row.get("parser_status")!="FIXTURE_VALIDATED": return "Fixture und Parser validieren"
        if health in {"down","degraded"}: return "Fehler prüfen und Live-Probe wiederholen"
        if row.get("status")!="PRODUCTION_READY": return "Source Gate durch verantwortlichen Reviewer prüfen"
        return "Quelle ist einsatzbereit"

    def _event(self,event_type:str,source_id:str,payload:Mapping[str,Any])->None:
        prev=self.db.one("SELECT event_sha256 FROM source_operations_events_187 ORDER BY created_at DESC,event_id DESC LIMIT 1")
        prev_sha=prev["event_sha256"] if prev else "0"*64
        eid=new_id("sourceevt187"); created=now_ts(); digest=_hash({"event_id":eid,"event_type":event_type,"source_id":source_id,"payload":payload,"created_at":created,"actor":self.actor,"prev":prev_sha})
        self.db.execute("INSERT INTO source_operations_events_187 VALUES(?,?,?,?,?,?,?,?)",(eid,event_type,source_id,dumps(payload),created,self.actor,prev_sha,digest))
