from __future__ import annotations

import html
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Dict, List
from urllib.parse import urlparse

from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

AGENTS = {
    "org_links": {
        "name": "Co-Ermittler 1 – Firmen & Organisationen",
        "scope": "Öffentliche berufliche Rollen, Registerhinweise, Unternehmensseiten, Verbände, Publikationen und institutionelle Verbindungen.",
        "templates": [
            '"{name}" Unternehmen OR Firma OR Organisation',
            '"{name}" Vorstand OR Geschäftsführer OR Mitarbeiter OR Team',
            '"{name}" Verein OR Verband OR Stiftung OR NGO',
            '"{name}" site:linkedin.com/in OR site:xing.com/profile',
        ],
    },
    "visual_geo": {
        "name": "Co-Ermittler 2 – Bilder & Geokontext",
        "scope": "Öffentlich publizierte Bilder, Bildquellen, erkennbare Ortskontexte und Metadaten aus rechtmäßig vorliegenden Dateien. Keine Rekonstruktion privater Wohnadressen.",
        "templates": [
            '"{name}" Bilder OR Foto OR Galerie',
            '"{name}" Veranstaltung OR Konferenz OR Messe',
            '"{name}" Standort OR Büro OR Impressum',
            '"{name}" site:commons.wikimedia.org OR site:flickr.com',
        ],
    },
    "money_business": {
        "name": "Co-Ermittler 3 – Follow the Money",
        "scope": "Öffentliche Unternehmensbeteiligungen, Geschäftsaktivitäten, Ausschreibungen, Förderungen, Insolvenzhinweise und veröffentlichte Finanzbezüge. Keine Bankdaten oder nicht öffentliche Finanzinformationen.",
        "templates": [
            '"{name}" Beteiligung OR Gesellschafter OR Geschäftsführer',
            '"{name}" Jahresabschluss OR Unternehmensregister OR Handelsregister',
            '"{name}" Förderung OR Ausschreibung OR Auftrag',
            '"{name}" Insolvenz OR Liquidation OR Übernahme',
        ],
    },
    "social_writing": {
        "name": "Co-Ermittler 4 – Social Media & Schriftspuren",
        "scope": "Öffentliche Profile, Usernames, Kommentare, Rezensionen, Autorenprofile und öffentlich sichtbare Textbeiträge. Keine geschützten Konten oder Umgehung von Zugangssperren.",
        "templates": [
            '"{name}" Profil OR Username OR Benutzername',
            '"{name}" Kommentar OR Rezension OR Bewertung',
            '"{name}" Autor OR Beitrag OR Interview',
            '"{name}" site:github.com OR site:reddit.com OR site:medium.com',
        ],
    },
}

BLOCKED = re.compile(r"\b(password|passwort|credential|zugangsdaten|private account|privates konto|wohnadresse|home address|bankkonto|kontonummer|leak|doxx|captcha|paywall)\b", re.I)
CLASSIFICATIONS = {"public", "internal", "confidential", "highly_sensitive"}


def _esc(v: Any) -> str:
    return html.escape(str(v or ""))


def _split(v: Any) -> List[str]:
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    return [x.strip() for x in re.split(r"[,;\n|]+", str(v or "")) if x.strip()]


@dataclass(frozen=True)
class AgentOutcome:
    agent_key: str
    status: str
    query_count: int
    result_count: int
    error: str = ""


class OPSECMultiAgent108Service:
    """OPSEC framework and approval-gated, target-bound multi-agent orchestration.

    Agents produce candidates and hypotheses only. They cannot confirm identity, guilt,
    private residence, protected-account content, or non-public financial information.
    """

    def __init__(self, db: Database, audit: Any, *, targets: Any, ai107: Any, graph: Any = None):
        self.db, self.audit, self.targets, self.ai107, self.graph = db, audit, targets, ai107, graph
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS opsec_case_profiles_108(
          case_id TEXT PRIMARY KEY, classification TEXT NOT NULL DEFAULT 'internal',
          threat_level TEXT NOT NULL DEFAULT 'low', cloud_policy TEXT NOT NULL DEFAULT 'local_only',
          active_content_warning INTEGER NOT NULL DEFAULT 1, external_link_warning INTEGER NOT NULL DEFAULT 1,
          notes TEXT DEFAULT '', updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS investigator_safety_checks_108(
          check_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, investigator TEXT NOT NULL,
          device_isolated INTEGER NOT NULL, vpn_reviewed INTEGER NOT NULL, personal_accounts_closed INTEGER NOT NULL,
          notifications_disabled INTEGER NOT NULL, legal_scope_confirmed INTEGER NOT NULL,
          emergency_contact_ready INTEGER NOT NULL, notes TEXT DEFAULT '', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS agent_missions_108(
          mission_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
          title TEXT NOT NULL, instructions TEXT NOT NULL, approved_by TEXT NOT NULL,
          status TEXT NOT NULL, max_queries_per_agent INTEGER NOT NULL,
          max_results_per_query INTEGER NOT NULL, created_at TEXT NOT NULL,
          started_at TEXT DEFAULT '', completed_at TEXT DEFAULT '', error TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS agent_tasks_108(
          task_id TEXT PRIMARY KEY, mission_id TEXT NOT NULL, agent_key TEXT NOT NULL,
          status TEXT NOT NULL, query_plan_json TEXT NOT NULL DEFAULT '[]', result_ids_json TEXT NOT NULL DEFAULT '[]',
          summary TEXT DEFAULT '', created_at TEXT NOT NULL, completed_at TEXT DEFAULT '', error TEXT DEFAULT '',
          UNIQUE(mission_id, agent_key)
        );
        CREATE TABLE IF NOT EXISTS hypothesis_dossiers_108(
          dossier_id TEXT PRIMARY KEY, mission_id TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'draft_for_lead_review', body_json TEXT NOT NULL,
          created_at TEXT NOT NULL, reviewed_by TEXT DEFAULT '', reviewed_at TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS opsec_incidents_108(
          incident_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, investigator TEXT NOT NULL,
          severity TEXT NOT NULL, category TEXT NOT NULL, description TEXT NOT NULL,
          containment TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_mission_case_108 ON agent_missions_108(case_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_tasks_mission_108 ON agent_tasks_108(mission_id, agent_key);
        ''')
        self.db.conn.commit()

    def save_case_profile(self, case_id: str, classification: str, threat_level: str, cloud_policy: str,
                          notes: str = "") -> Dict[str, Any]:
        classification = classification if classification in CLASSIFICATIONS else "internal"
        if threat_level not in {"low", "medium", "high", "critical"}:
            raise ValueError("Ungültige Gefährdungsstufe")
        if cloud_policy not in {"local_only", "cloud_explicit", "cloud_blocked"}:
            raise ValueError("Ungültige Cloud-Richtlinie")
        self.db.execute('''INSERT INTO opsec_case_profiles_108(case_id,classification,threat_level,cloud_policy,notes,updated_at)
          VALUES(?,?,?,?,?,?) ON CONFLICT(case_id) DO UPDATE SET classification=excluded.classification,
          threat_level=excluded.threat_level,cloud_policy=excluded.cloud_policy,notes=excluded.notes,updated_at=excluded.updated_at''',
          [case_id, classification, threat_level, cloud_policy, notes[:4000], now_ts()])
        self.db.conn.commit()
        self.audit.log("configure", "opsec_case_profile_108", case_id, None, {"classification": classification, "threat_level": threat_level, "cloud_policy": cloud_policy})
        return self.case_profile(case_id)

    def case_profile(self, case_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM opsec_case_profiles_108 WHERE case_id=?", [case_id])
        return row or {"case_id": case_id, "classification": "internal", "threat_level": "low", "cloud_policy": "local_only", "notes": ""}

    def record_safety_check(self, case_id: str, investigator: str, **checks: Any) -> Dict[str, Any]:
        if len(investigator.strip()) < 2:
            raise ValueError("Ermittlername erforderlich")
        keys = ["device_isolated", "vpn_reviewed", "personal_accounts_closed", "notifications_disabled", "legal_scope_confirmed", "emergency_contact_ready"]
        vals = [1 if checks.get(k) else 0 for k in keys]
        cid = new_id("safe")
        self.db.execute(f"INSERT INTO investigator_safety_checks_108(check_id,case_id,investigator,{','.join(keys)},notes,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        [cid, case_id, investigator.strip(), *vals, str(checks.get("notes", ""))[:4000], now_ts()])
        self.db.conn.commit()
        self.audit.log("create", "investigator_safety_check_108", cid, case_id, {"score": sum(vals), "investigator": investigator.strip()})
        return {"check_id": cid, "score": sum(vals), "max_score": len(keys), "ready": sum(vals) == len(keys)}

    def create_mission(self, *, case_id: str, target_id: str, title: str, instructions: str,
                       approved_by: str, confirmation: str, max_queries_per_agent: int = 4,
                       max_results_per_query: int = 8) -> Dict[str, Any]:
        if confirmation.strip().upper() != "AGENTENAUFTRAG FREIGEBEN":
            raise ValueError("Freigabephrase fehlt")
        target = self.targets.get_target(target_id)
        if not target or target.get("case_id") != case_id:
            raise ValueError("Zielperson gehört nicht zum ausgewählten Fall")
        if len(approved_by.strip()) < 2 or len(title.strip()) < 4 or len(instructions.strip()) < 10:
            raise ValueError("Titel, Auftrag und Freigabe durch Hauptermittler sind erforderlich")
        if BLOCKED.search(instructions):
            raise ValueError("Der Auftrag enthält einen gesperrten Recherchebereich")
        profile = self.case_profile(case_id)
        if profile.get("threat_level") in {"high", "critical"}:
            last = self.db.one("SELECT * FROM investigator_safety_checks_108 WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id])
            if not last or sum(int(last.get(k, 0)) for k in ["device_isolated","vpn_reviewed","personal_accounts_closed","notifications_disabled","legal_scope_confirmed","emergency_contact_ready"]) < 6:
                raise ValueError("Bei hoher oder kritischer Gefährdung ist vor dem Agentenlauf eine vollständige Ermittlersicherheitsprüfung erforderlich")
        qlim = max(1, min(int(max_queries_per_agent), 8)); rlim = max(1, min(int(max_results_per_query), 12))
        mid = new_id("mission")
        self.db.execute("INSERT INTO agent_missions_108(mission_id,case_id,target_id,title,instructions,approved_by,status,max_queries_per_agent,max_results_per_query,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                        [mid, case_id, target_id, title.strip()[:240], instructions.strip()[:8000], approved_by.strip()[:160], "approved_once", qlim, rlim, now_ts()])
        for key in AGENTS:
            self.db.execute("INSERT INTO agent_tasks_108(task_id,mission_id,agent_key,status,created_at) VALUES(?,?,?,?,?)", [new_id("task"), mid, key, "queued", now_ts()])
        self.db.conn.commit()
        self.audit.log("approve", "agent_mission_108", mid, case_id, {"target_id": target_id, "agents": list(AGENTS), "limits": [qlim, rlim]})
        return self.get_mission(mid)

    def _anchors(self, target: Dict[str, Any]) -> List[str]:
        out = [str(target.get("name") or "").strip()]
        for key in ("aliases", "usernames", "emails", "domains"):
            out.extend(_split(target.get(key)))
        return [x for x in dict.fromkeys(out) if len(x) >= 3]

    def _queries(self, agent_key: str, target: Dict[str, Any], instructions: str, limit: int) -> List[Dict[str, str]]:
        name = str(target.get("name") or "").strip()
        anchors = self._anchors(target)
        if not name or not anchors:
            raise ValueError("Zielperson besitzt keine ausreichenden Identitätsanker")
        queries = []
        for template in AGENTS[agent_key]["templates"]:
            q = template.format(name=name)
            if not BLOCKED.search(q):
                queries.append({"query": q, "category": agent_key, "reason": AGENTS[agent_key]["scope"]})
        # Add confirmed usernames/companies only while retaining the person's name anchor.
        for username in _split(target.get("usernames"))[:2]:
            queries.append({"query": f'"{name}" "{username}"', "category": agent_key, "reason": "Bestätigten Username mit Zielperson abgleichen"})
        for company in _split(target.get("companies"))[:2]:
            queries.append({"query": f'"{name}" "{company}"', "category": agent_key, "reason": "Bestätigten Organisationsanker prüfen"})
        valid = self.ai107._validate_queries(target, queries, limit)
        return valid[:limit]

    def _collect_agent(self, mission: Dict[str, Any], agent_key: str, target: Dict[str, Any], search_fn: Any, provider: str) -> Dict[str, Any]:
        """Network-bound collection only; no shared SQLite access from worker threads."""
        try:
            queries = self._queries(agent_key, target, mission["instructions"], mission["max_queries_per_agent"])
            collected=[]
            for q in queries:
                for result in search_fn(q["query"], mission["max_results_per_query"]):
                    url = str(result.get("url") or "").strip(); parsed=urlparse(url)
                    if parsed.scheme not in {"http","https"} or not parsed.hostname:
                        continue
                    score, rationale = self.ai107._rank(target, result)
                    collected.append({"query": q["query"], "provider": provider, "title": str(result.get("title") or "")[:1000],
                                      "url": url[:4000], "snippet": str(result.get("snippet") or result.get("content") or "")[:8000],
                                      "published_at": str(result.get("published_at") or "")[:120], "relevance": score, "rationale": rationale})
            return {"agent_key": agent_key, "status": "completed", "queries": queries, "results": collected, "error": ""}
        except Exception as exc:
            return {"agent_key": agent_key, "status": "failed", "queries": [], "results": [], "error": str(exc)}

    def execute_mission(self, mission_id: str) -> Dict[str, Any]:
        mission = self.get_mission(mission_id)
        if not mission or mission["status"] != "approved_once":
            raise ValueError("Mission ist nicht ausführbar oder wurde bereits verbraucht")
        changed = self.db.execute("UPDATE agent_missions_108 SET status='running',started_at=? WHERE mission_id=? AND status='approved_once'", [now_ts(), mission_id]).rowcount
        if changed != 1:
            raise ValueError("Mission wurde bereits gestartet")
        target = self.targets.get_target(mission["target_id"])
        cfg=self.ai107.get_config()
        search_fn={"searxng": self.ai107._search_searxng, "brave": self.ai107._search_brave, "ollama_web": self.ai107._search_ollama_web}[cfg.search_provider]
        payloads=[]
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="eagleeye-agent") as pool:
            futures={pool.submit(self._collect_agent, mission, key, target, search_fn, cfg.search_provider): key for key in AGENTS}
            for fut in as_completed(futures): payloads.append(fut.result())
        outcomes=[]
        for payload in payloads:
            key=payload["agent_key"]
            task=self.db.one("SELECT * FROM agent_tasks_108 WHERE mission_id=? AND agent_key=?", [mission_id,key])
            result_ids=[]
            if payload["status"] == "completed":
                seen=set()
                for result in payload["results"]:
                    if result["url"] in seen: continue
                    seen.add(result["url"]); rid=new_id("agentres")
                    try:
                        self.db.execute("""INSERT INTO ai_search_results_107(result_id,run_id,case_id,target_id,query,provider,title,url,snippet,source_engine,published_at,relevance,rationale,review_status,created_at)
                          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", [rid, mission_id, mission["case_id"], mission["target_id"], result["query"], result["provider"], result["title"], result["url"], result["snippet"], key, result["published_at"], result["relevance"], result["rationale"], "candidate", now_ts()])
                        result_ids.append(rid)
                    except Exception:
                        continue
                summary=f"{AGENTS[key]['name']}: {len(payload['queries'])} Abfragen, {len(result_ids)} ungeprüfte Kandidaten."
                self.db.execute("UPDATE agent_tasks_108 SET status='completed',query_plan_json=?,result_ids_json=?,summary=?,completed_at=? WHERE task_id=?", [dumps(payload["queries"]),dumps(result_ids),summary,now_ts(),task["task_id"]])
                outcomes.append(AgentOutcome(key,"completed",len(payload["queries"]),len(result_ids)))
            else:
                self.db.execute("UPDATE agent_tasks_108 SET status='failed',error=?,completed_at=? WHERE task_id=?", [payload["error"][:2000],now_ts(),task["task_id"]])
                outcomes.append(AgentOutcome(key,"failed",0,0,payload["error"]))
        failures=[o for o in outcomes if o.status != "completed"]
        dossier=self._create_dossier(mission, target, outcomes)
        status="completed_with_warnings" if failures else "completed"
        self.db.execute("UPDATE agent_missions_108 SET status=?,completed_at=?,error=? WHERE mission_id=?", [status, now_ts(), "; ".join(o.error for o in failures)[:4000], mission_id])
        self.audit.log("execute", "agent_mission_108", mission_id, mission["case_id"], {"status": status, "outcomes": [o.__dict__ for o in outcomes], "dossier_id": dossier["dossier_id"]})
        return {"mission_id": mission_id, "status": status, "outcomes": [o.__dict__ for o in outcomes], "dossier": dossier}

    def _create_dossier(self, mission: Dict[str, Any], target: Dict[str, Any], outcomes: List[AgentOutcome]) -> Dict[str, Any]:
        tasks=self.db.all("SELECT * FROM agent_tasks_108 WHERE mission_id=? ORDER BY agent_key", [mission["mission_id"]])
        results=self.db.all("SELECT * FROM ai_search_results_107 WHERE run_id=? ORDER BY relevance DESC,title LIMIT 300", [mission["mission_id"]])
        by_agent={k:[] for k in AGENTS}
        for r in results: by_agent.setdefault(r.get("source_engine") or "unknown", []).append(r)
        top=[]
        for k, vals in by_agent.items():
            for r in vals[:5]: top.append({"agent": k, "title": r["title"], "url": r["url"], "relevance": r["relevance"], "status": "unverified_candidate"})
        body={
            "title": f"Hypothesen-Dossier: {target.get('name','Zielperson')}",
            "mission": mission["title"], "lead_instructions": mission["instructions"],
            "epistemic_status": "Entwurf für Hauptermittler-Review; keine Feststellungen",
            "agent_reports": [{"agent": AGENTS.get(t["agent_key"],{}).get("name",t["agent_key"]), "status": t["status"], "summary": t.get("summary",""), "error": t.get("error","")} for t in tasks],
            "priority_candidates": top,
            "hypotheses": [
                {"statement": "Mögliche institutionelle oder geschäftliche Verbindung", "support": "Nur aus manuell bestätigten Firmen-/Organisationskandidaten ableitbar", "alternatives": ["Namensgleichheit", "veraltete Rollenangabe", "Fehlzuordnung"], "confidence": "not_assessed"},
                {"statement": "Mögliche Überschneidung zwischen öffentlicher Aktivität und Geschäftsbezug", "support": "Erfordert mindestens zwei unabhängige, manuell geprüfte Quellen", "alternatives": ["gemeinsamer Username ohne Identitätsgleichheit", "repost/automatischer Eintrag"], "confidence": "not_assessed"},
            ],
            "mandatory_checks": ["Identität je Treffer manuell prüfen", "Primärquelle sichern", "Zeitbezug prüfen", "Gegenhypothese dokumentieren", "Private Wohnadresse nicht ableiten", "Graph-Kanten erst nach Review anlegen"],
            "gaps": ["Unbestätigte Kandidaten", "Keine automatische Identitätsauflösung", "Keine Aussage zu Schuld, Absicht oder privatem Aufenthaltsort"],
            "counts": {"agents": len(outcomes), "candidates": len(results)},
        }
        did=new_id("dossier")
        self.db.execute("INSERT INTO hypothesis_dossiers_108(dossier_id,mission_id,case_id,target_id,body_json,created_at) VALUES(?,?,?,?,?,?)", [did, mission["mission_id"], mission["case_id"], mission["target_id"], dumps(body), now_ts()]); self.db.conn.commit()
        return {"dossier_id": did, **body}

    def review_dossier(self, dossier_id: str, reviewed_by: str) -> Dict[str, Any]:
        if len(reviewed_by.strip()) < 2: raise ValueError("Reviewer erforderlich")
        self.db.execute("UPDATE hypothesis_dossiers_108 SET status='lead_reviewed',reviewed_by=?,reviewed_at=? WHERE dossier_id=?", [reviewed_by.strip(), now_ts(), dossier_id]); self.db.conn.commit()
        self.audit.log("review", "hypothesis_dossier_108", dossier_id, None, {"reviewed_by": reviewed_by.strip()})
        return self.get_dossier(dossier_id)

    def record_incident(self, case_id: str, investigator: str, severity: str, category: str, description: str, containment: str = "") -> Dict[str, Any]:
        if severity not in {"low","medium","high","critical"}: raise ValueError("Ungültige Schwere")
        iid=new_id("incident")
        self.db.execute("INSERT INTO opsec_incidents_108(incident_id,case_id,investigator,severity,category,description,containment,created_at) VALUES(?,?,?,?,?,?,?,?)", [iid,case_id,investigator[:160],severity,category[:160],description[:8000],containment[:8000],now_ts()]); self.db.conn.commit()
        self.audit.log("create", "opsec_incident_108", iid, case_id, {"severity": severity, "category": category})
        return {"incident_id": iid, "status": "open"}

    def emergency_stop(self, case_id: str, investigator: str, reason: str) -> Dict[str, Any]:
        self.db.execute("UPDATE agent_missions_108 SET status='halted',error=? WHERE case_id=? AND status IN ('approved_once','running')", [f"Emergency stop by {investigator}: {reason}"[:4000], case_id]); self.db.conn.commit()
        self.audit.log("emergency_stop", "case_108", case_id, case_id, {"investigator": investigator, "reason": reason[:1000]})
        return {"case_id": case_id, "halted": True}

    def get_mission(self, mission_id: str) -> Dict[str, Any]:
        return self.db.one("SELECT * FROM agent_missions_108 WHERE mission_id=?", [mission_id]) or {}
    def list_missions(self, case_id: str) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM agent_missions_108 WHERE case_id=? ORDER BY created_at DESC LIMIT 30", [case_id])
    def get_dossier(self, dossier_id: str) -> Dict[str, Any]:
        row=self.db.one("SELECT * FROM hypothesis_dossiers_108 WHERE dossier_id=?", [dossier_id]) or {}
        if row: row["body"]=loads(row.get("body_json"), {})
        return row
    def list_dossiers(self, case_id: str) -> List[Dict[str, Any]]:
        rows=self.db.all("SELECT * FROM hypothesis_dossiers_108 WHERE case_id=? ORDER BY created_at DESC LIMIT 20", [case_id])
        for r in rows: r["body"]=loads(r.get("body_json"), {})
        return rows


def render_opsec_multiagent_108(ctx: Any, case_id: str, csrf: str, token: str) -> str:
    svc: OPSECMultiAgent108Service = ctx.opsec_multiagent_108
    targets=ctx.targets.list_targets(case_id); profile=svc.case_profile(case_id); missions=svc.list_missions(case_id); dossiers=svc.list_dossiers(case_id)
    target_opts=''.join(f'<option value="{_esc(t.get("target_id"))}">{_esc(t.get("name"))}</option>' for t in targets)
    mission_rows=''.join(f'<tr><td>{_esc(m["created_at"])}</td><td>{_esc(m["title"])}</td><td>{_esc(m["status"])}</td><td><form class="inline" method="post" action="/ai108/run?token={_esc(token)}"><input type="hidden" name="csrf" value="{csrf}"><input type="hidden" name="mission_id" value="{_esc(m["mission_id"])}"><button>Ausführen</button></form></td></tr>' for m in missions)
    dossier_blocks=''.join(f'<details><summary>{_esc(d.get("created_at"))} · {_esc(d.get("body",{}).get("title"))} · {_esc(d.get("status"))}</summary><pre>{_esc(json.dumps(d.get("body",{}),ensure_ascii=False,indent=2))}</pre></details>' for d in dossiers)
    agent_cards=''.join(f'<div class="metric"><b>{_esc(v["name"])}</b><small>{_esc(v["scope"])}</small></div>' for v in AGENTS.values())
    return f'''
<h2>OPSEC & Multi-Agent Operations – Build 108</h2>
<div class="notice"><b>Grundsatz:</b> Öffentlich, rechtmäßig, zielpersonengebunden. Keine privaten Wohnadressen, geschützten Konten, Bankdaten oder automatischen Tatsachenbehauptungen.</div>
<h3>Fallklassifizierung und Ermittlerschutz</h3>
<form method="post" action="/ai108/profile?token={_esc(token)}"><input type="hidden" name="csrf" value="{csrf}"><input type="hidden" name="case_id" value="{_esc(case_id)}">
<label>Klassifizierung<select name="classification"><option value="public">Öffentlich</option><option value="internal">Intern</option><option value="confidential">Vertraulich</option><option value="highly_sensitive">Hochsensibel</option></select></label>
<label>Gefährdungsstufe<select name="threat_level"><option>low</option><option>medium</option><option>high</option><option>critical</option></select></label>
<label>Cloud-Richtlinie<select name="cloud_policy"><option>local_only</option><option>cloud_explicit</option><option>cloud_blocked</option></select></label>
<label>OPSEC-Notizen<textarea name="notes" rows="3">{_esc(profile.get("notes"))}</textarea></label><button>Profil speichern</button></form>
<form method="post" action="/ai108/safety-check?token={_esc(token)}"><input type="hidden" name="csrf" value="{csrf}"><input type="hidden" name="case_id" value="{_esc(case_id)}"><h4>Pre-Flight-Sicherheitscheck</h4>
<label>Ermittler<input name="investigator" required></label><label><input type="checkbox" name="device_isolated"> Rechercheumgebung getrennt</label><label><input type="checkbox" name="vpn_reviewed"> Netzwerk-/VPN-Konzept geprüft</label><label><input type="checkbox" name="personal_accounts_closed"> Private Konten geschlossen</label><label><input type="checkbox" name="notifications_disabled"> Benachrichtigungen deaktiviert</label><label><input type="checkbox" name="legal_scope_confirmed"> Rechtsgrundlage und Zweckbindung bestätigt</label><label><input type="checkbox" name="emergency_contact_ready"> Notfallkontakt/-plan verfügbar</label><label>Notizen<textarea name="notes" rows="2"></textarea></label><button>Sicherheitscheck protokollieren</button></form>
<h3>Fachagenten</h3><div class="metrics">{agent_cards}</div>
<h3>Agentenauftrag durch Hauptermittler</h3>
<form method="post" action="/ai108/create?token={_esc(token)}"><input type="hidden" name="csrf" value="{csrf}"><input type="hidden" name="case_id" value="{_esc(case_id)}">
<label>Zielperson<select name="target_id" required>{target_opts}</select></label><label>Auftragstitel<input name="title" required></label><label>Gesamtauftrag<textarea name="instructions" rows="5" required placeholder="Konkrete Fragestellung, Zeitrahmen, bekannte Anker und Ausschlüsse"></textarea></label><label>Freigegeben durch<input name="approved_by" required></label><label>Queries je Agent<input type="number" name="max_queries_per_agent" value="4" min="1" max="8"></label><label>Treffer je Query<input type="number" name="max_results_per_query" value="8" min="1" max="12"></label><label>Freigabephrase<input name="confirmation" placeholder="AGENTENAUFTRAG FREIGEBEN" required></label><button>Mission anlegen</button></form>
<h3>Missionen</h3><table><tr><th>Zeit</th><th>Auftrag</th><th>Status</th><th>Aktion</th></tr>{mission_rows or '<tr><td colspan="4">Keine Missionen.</td></tr>'}</table>
<h3>Hypothesen-Dossiers</h3>{dossier_blocks or '<p>Noch keine Dossiers.</p>'}
<h3>Not-Aus</h3><form method="post" action="/ai108/stop?token={_esc(token)}"><input type="hidden" name="csrf" value="{csrf}"><input type="hidden" name="case_id" value="{_esc(case_id)}"><label>Ermittler<input name="investigator" required></label><label>Grund<input name="reason" required></label><button>Alle laufenden Agenten stoppen</button></form>
'''
