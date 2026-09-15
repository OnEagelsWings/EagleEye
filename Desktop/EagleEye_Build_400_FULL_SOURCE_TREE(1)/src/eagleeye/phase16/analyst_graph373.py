from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

POLICY = "phase16.analyst-graph-ux.v373"
CRAWLER_POLICY = "phase16.graph-aware-crawler.v373"
AI_POLICY = "phase16.autonomous-investigation.v373"
OPSEC_POLICY = "phase16.defensive-opsec-supervisor.v373"
MAX_GRAPH_NODES = 240
MAX_GRAPH_EDGES = 480
MAX_FOCUS_DEPTH = 2
MAX_NAV_SOURCES = 2
MAX_SOURCE_PAGES = 10
MAX_TOTAL_NAV_REQUESTS = 30


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    raw = value if isinstance(value, (bytes, bytearray)) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _j(value: Any, default: Any) -> Any:
    try:
        return json.loads(value) if isinstance(value, str) else value
    except Exception:
        return default


def _node_id(kind: str, object_id: str) -> str:
    return f"{kind}:{object_id}"


class AnalystGraphUX373:
    """Read-only analyst graph projection over canonical ledgers.

    The graph is deliberately a projection, not a new source of truth. It never
    confirms identities, writes inferred relationships, or expands the research
    scope. All candidate edges remain review artefacts.
    """

    def __init__(self, db: Any, audit: Any, *, governance: Any, entity371: Any, source_quality372: Any, actor: str = "local-analyst") -> None:
        self.db = db
        self.audit = audit
        self.governance = governance
        self.entity371 = entity371
        self.source_quality372 = source_quality372
        self.actor = actor

    def _authorize(self, identity: dict[str, Any], case_id: str, capability: str = "case.read") -> None:
        self.governance.authorize(identity, case_id=case_id, capability=capability, object_type="analyst_graph_v373", object_id=case_id)

    def _entity_nodes(self, case_id: str) -> list[dict[str, Any]]:
        rows = self.db.all(
            "SELECT resolution_entity_id,entity_type,display_name,candidate_only,created_at FROM resolution_entities_115 WHERE case_id=? ORDER BY created_at LIMIT ?",
            (case_id, MAX_GRAPH_NODES),
        )
        return [
            {
                "id": _node_id("entity", r["resolution_entity_id"]),
                "object_id": r["resolution_entity_id"],
                "kind": "entity",
                "entity_type": r["entity_type"],
                "label": r["display_name"],
                "candidate_only": bool(r["candidate_only"]),
                "review_required": bool(r["candidate_only"]),
                "sensitivity": "case_entity",
            }
            for r in rows
        ]

    def _source_nodes(self, case_id: str) -> list[dict[str, Any]]:
        rows = self.db.all(
            "SELECT DISTINCT s.source_id,s.display_name,s.source_kind,s.review_status,s.risk_class,p.source_health "
            "FROM phase15_crawl_runs r JOIN phase15_sources s ON s.source_id=r.source_id "
            "JOIN phase15_crawler_policies p ON p.source_id=s.source_id WHERE r.case_id=? ORDER BY s.source_id LIMIT ?",
            (case_id, MAX_GRAPH_NODES),
        )
        return [
            {
                "id": _node_id("source", r["source_id"]),
                "object_id": r["source_id"],
                "kind": "source",
                "label": r["display_name"],
                "source_kind": r["source_kind"],
                "review_status": r["review_status"],
                "source_health": r["source_health"],
                "risk_class": r["risk_class"],
                "review_required": False,
            }
            for r in rows
        ]

    def _comparison_edges(self, case_id: str) -> list[dict[str, Any]]:
        rows = self.db.all(
            "SELECT comparison_id,left_entity_id,right_entity_id,total_score,classification,state,reviewed_by,reviewed_at,explanation_json "
            "FROM resolution_comparisons_115 WHERE case_id=? ORDER BY created_at DESC LIMIT ?",
            (case_id, MAX_GRAPH_EDGES),
        )
        out: list[dict[str, Any]] = []
        for r in rows:
            explanation = _j(r.get("explanation_json"), {}) or {}
            v2 = dict(explanation.get("v371") or {})
            out.append(
                {
                    "id": _node_id("comparison", r["comparison_id"]),
                    "object_id": r["comparison_id"],
                    "kind": "entity_comparison",
                    "source": _node_id("entity", r["left_entity_id"]),
                    "target": _node_id("entity", r["right_entity_id"]),
                    "classification": r["classification"],
                    "state": r["state"],
                    "reviewed": bool(r.get("reviewed_at")),
                    "review_required": not bool(r.get("reviewed_at")),
                    "evidence_weight": round(float(v2.get("evidence_weight") or r.get("total_score") or 0.0), 4),
                    "score_is_probability": False,
                    "strong_identifier_conflict_veto": bool(v2.get("strong_identifier_conflict_veto")),
                    "independent_source_count": int(v2.get("independent_source_count") or 0),
                    "automatic_merge": False,
                }
            )
        return out

    def _reviewed_link_edges(self, case_id: str) -> list[dict[str, Any]]:
        rows = self.db.all(
            "SELECT link_id,canonical_entity_id,linked_entity_id,relationship,comparison_id,approved_by,approved_at,active "
            "FROM resolution_links_115 WHERE case_id=? AND active=1 ORDER BY approved_at DESC LIMIT ?",
            (case_id, MAX_GRAPH_EDGES),
        )
        return [
            {
                "id": _node_id("link", r["link_id"]),
                "object_id": r["link_id"],
                "kind": "reviewed_entity_link",
                "source": _node_id("entity", r["canonical_entity_id"]),
                "target": _node_id("entity", r["linked_entity_id"]),
                "relationship": r["relationship"],
                "comparison_id": r["comparison_id"],
                "reviewed": True,
                "review_required": False,
                "approved_at": r["approved_at"],
                "non_destructive": True,
                "automatic_merge": False,
            }
            for r in rows
        ]

    def _crawler_lead_edges(self, case_id: str) -> list[dict[str, Any]]:
        rows = self.db.all(
            "SELECT job_id,status,payload_json,result_json,created_at FROM phase15_jobs WHERE job_type='entity_link_lead_v371' AND case_id=? ORDER BY created_at DESC LIMIT ?",
            (case_id, MAX_GRAPH_EDGES),
        )
        out: list[dict[str, Any]] = []
        for r in rows:
            p = _j(r.get("payload_json"), {}) or {}
            result = _j(r.get("result_json"), {}) or {}
            sid = str(p.get("source_id") or "")
            if not sid:
                try:
                    q = self.source_quality372.lead_quality_packet(job_id=r["job_id"])
                    sid = str(q.get("source_id") or "")
                except Exception:
                    sid = ""
            quality: dict[str, Any] = {}
            try:
                quality = dict((self.source_quality372.lead_quality_packet(job_id=r["job_id"]).get("quality") or {}).get("quality") or {})
            except Exception:
                quality = {}
            for role, entity_id in (("target", p.get("target_entity_id")), ("candidate", p.get("candidate_entity_id"))):
                if not sid or not entity_id:
                    continue
                out.append(
                    {
                        "id": f"lead:{r['job_id']}:{role}",
                        "object_id": r["job_id"],
                        "kind": "crawler_entity_lead",
                        "source": _node_id("source", sid),
                        "target": _node_id("entity", str(entity_id)),
                        "entity_role": role,
                        "job_status": r["status"],
                        "classification": result.get("classification") or "pending",
                        "provenance_hash": str(p.get("provenance_hash") or ""),
                        "source_record_hash": str(p.get("source_record_hash") or ""),
                        "quality_band": quality.get("quality_band") or "unknown",
                        "quality_score": int(quality.get("quality_score") or 0),
                        "source_quality_is_identity_probability": False,
                        "review_required": True,
                        "automatic_merge": False,
                    }
                )
        return out

    def snapshot(self, *, case_id: str, identity: dict[str, Any], max_nodes: int = 180, max_edges: int = 360) -> dict[str, Any]:
        self._authorize(identity, case_id)
        nlimit = max(10, min(int(max_nodes), MAX_GRAPH_NODES))
        elimit = max(10, min(int(max_edges), MAX_GRAPH_EDGES))
        nodes = self._entity_nodes(case_id) + self._source_nodes(case_id)
        node_map = {n["id"]: n for n in nodes}
        edges = self._comparison_edges(case_id) + self._reviewed_link_edges(case_id) + self._crawler_lead_edges(case_id)
        # Only keep edges whose endpoint nodes are part of this case projection.
        edges = [e for e in edges if e.get("source") in node_map and e.get("target") in node_map][:elimit]
        connected: set[str] = set()
        for e in edges:
            connected.add(str(e["source"])); connected.add(str(e["target"]))
        prioritized = sorted(nodes, key=lambda n: (0 if n["id"] in connected else 1, n["kind"], n["id"]))[:nlimit]
        keep = {n["id"] for n in prioritized}
        edges = [e for e in edges if e["source"] in keep and e["target"] in keep][:elimit]
        metrics = {
            "nodes": len(prioritized),
            "edges": len(edges),
            "entity_nodes": sum(1 for n in prioritized if n["kind"] == "entity"),
            "source_nodes": sum(1 for n in prioritized if n["kind"] == "source"),
            "review_candidate_edges": sum(1 for e in edges if e.get("review_required")),
            "reviewed_entity_links": sum(1 for e in edges if e["kind"] == "reviewed_entity_link"),
            "crawler_entity_leads": sum(1 for e in edges if e["kind"] == "crawler_entity_lead"),
            "strong_conflict_veto_edges": sum(1 for e in edges if e.get("strong_identifier_conflict_veto")),
        }
        graph_hash = _sha({"case_id": case_id, "nodes": prioritized, "edges": edges})
        return {
            "policy": POLICY,
            "case_id": case_id,
            "graph_hash": graph_hash,
            "nodes": prioritized,
            "edges": edges,
            "metrics": metrics,
            "projection_only": True,
            "source_of_truth": "canonical ledgers",
            "automatic_scope_expansion": False,
            "automatic_identity_confirmation": False,
            "automatic_merge": False,
        }

    def focus(self, *, case_id: str, node_id: str, identity: dict[str, Any], depth: int = 1, max_nodes: int = 60) -> dict[str, Any]:
        graph = self.snapshot(case_id=case_id, identity=identity, max_nodes=MAX_GRAPH_NODES, max_edges=MAX_GRAPH_EDGES)
        if node_id not in {n["id"] for n in graph["nodes"]}:
            raise KeyError(node_id)
        max_depth = max(0, min(int(depth), MAX_FOCUS_DEPTH))
        keep = {node_id}
        frontier = {node_id}
        for _ in range(max_depth):
            nxt: set[str] = set()
            for e in graph["edges"]:
                if e["source"] in frontier:
                    nxt.add(e["target"])
                if e["target"] in frontier:
                    nxt.add(e["source"])
            nxt -= keep
            keep |= nxt
            frontier = nxt
        limit = max(5, min(int(max_nodes), 100))
        ordered = [n for n in graph["nodes"] if n["id"] in keep][:limit]
        ids = {n["id"] for n in ordered}
        edges = [e for e in graph["edges"] if e["source"] in ids and e["target"] in ids]
        return {"policy": POLICY, "case_id": case_id, "focus_node": node_id, "depth": max_depth, "nodes": ordered, "edges": edges, "network_execution": False, "scope_expansion": False}

    def status(self) -> dict[str, Any]:
        return {
            "policy": POLICY,
            "ledger_projection": True,
            "entity_resolution_v2_edges": True,
            "crawler_provenance_edges": True,
            "review_state_visible": True,
            "source_quality_visible": True,
            "offline_focus_navigation": True,
            "score_is_probability": False,
            "automatic_identity_confirmation": False,
            "automatic_merge": False,
            "automatic_scope_expansion": False,
            "new_per_build_data_tables": 0,
        }


class GraphAwareCrawler373:
    """Human-directed, bounded graph pivot into already-approved crawler sources.

    A graph pivot is not an autonomous discovery operation. A source must already
    have appeared in this case's crawl→entity provenance, must remain approved and
    healthy, and the analyst must explicitly select it and type NAVIGATE.
    """

    def __init__(self, db: Any, audit: Any, *, governance: Any, graph373: AnalystGraphUX373, entity371: Any, crawler352: Any, crawler369: Any, jobs: Any, actor: str = "local-analyst") -> None:
        self.db = db
        self.audit = audit
        self.governance = governance
        self.graph373 = graph373
        self.entity371 = entity371
        self.crawler352 = crawler352
        self.crawler369 = crawler369
        self.jobs = jobs
        self.actor = actor

    def _authorize(self, identity: dict[str, Any], case_id: str) -> None:
        self.governance.authorize(identity, case_id=case_id, capability="crawler.run", object_type="graph_navigation_v373", object_id=case_id)

    def _entity_case(self, entity_id: str) -> str:
        row = self.db.one("SELECT case_id FROM resolution_entities_115 WHERE resolution_entity_id=?", (str(entity_id),))
        if not row:
            raise KeyError(entity_id)
        return str(row["case_id"])

    def observed_sources(self, *, case_id: str, root_entity_id: str) -> list[str]:
        if self._entity_case(root_entity_id) != case_id:
            raise PermissionError("cross-case graph navigation prohibited")
        rows = self.db.all("SELECT payload_json FROM phase15_jobs WHERE job_type='entity_link_lead_v371' AND case_id=?", (case_id,))
        out: set[str] = set()
        for r in rows:
            p = _j(r.get("payload_json"), {}) or {}
            if root_entity_id in {str(p.get("target_entity_id") or ""), str(p.get("candidate_entity_id") or "")} and p.get("source_id"):
                out.add(str(p["source_id"]))
            elif root_entity_id in {str(p.get("target_entity_id") or ""), str(p.get("candidate_entity_id") or "")}:
                cr = str(p.get("crawl_run_id") or "")
                if cr:
                    row = self.db.one("SELECT source_id FROM phase15_crawl_runs WHERE crawl_run_id=? AND case_id=?", (cr, case_id))
                    if row:
                        out.add(str(row["source_id"]))
        return sorted(out)

    def _source_packet(self, *, case_id: str, source_id: str) -> dict[str, Any]:
        row = self.db.one(
            "SELECT s.*,p.* FROM phase15_sources s JOIN phase15_crawler_policies p ON p.source_id=s.source_id WHERE s.source_id=?",
            (str(source_id),),
        )
        if not row:
            raise KeyError(source_id)
        allowed = True
        reasons: list[str] = []
        if row.get("review_status") != "approved_read_only" or int(row.get("enabled") or 0) != 1:
            allowed = False; reasons.append("source_not_approved")
        if str(row.get("auth_type") or "") != "none":
            allowed = False; reasons.append("authenticated_source")
        if str(row.get("source_kind") or "") == "darknet_onion":
            allowed = False; reasons.append("tor_gateway_separate")
        if self.crawler369._is_connector_source(source_id):
            allowed = False; reasons.append("provider_live_gate_separate")
        max_pages = int(row.get("max_pages") or 0)
        if max_pages > MAX_SOURCE_PAGES:
            allowed = False; reasons.append("source_page_budget_too_large")
        sitemap = _j(row.get("sitemap_urls_json"), []) or []
        archive = _j(row.get("archive_seed_urls_json"), []) or []
        if sitemap or archive:
            allowed = False; reasons.append("discovery_expansion_not_allowed_for_graph_navigation")
        health = self.crawler369.source_health(source_id=source_id)
        if health.get("circuit_open"):
            allowed = False; reasons.append("source_health_circuit_open")
        est_requests = max_pages + 4
        return {
            "source_id": source_id,
            "display_name": row.get("display_name"),
            "source_kind": row.get("source_kind"),
            "max_pages": max_pages,
            "estimated_max_requests": est_requests,
            "source_health": health.get("source_health"),
            "circuit_open": bool(health.get("circuit_open")),
            "allowed": allowed,
            "reasons": reasons,
            "analyst_selected_only": True,
        }

    def plan(self, *, case_id: str, root_entity_id: str, source_ids: Sequence[str], identity: dict[str, Any]) -> dict[str, Any]:
        self._authorize(identity, case_id)
        if self._entity_case(root_entity_id) != case_id:
            raise PermissionError("cross-case graph navigation prohibited")
        selected = list(dict.fromkeys(str(x) for x in source_ids if str(x)))
        if not selected:
            raise ValueError("at least one analyst-selected source required")
        if len(selected) > MAX_NAV_SOURCES:
            raise ValueError(f"at most {MAX_NAV_SOURCES} sources per graph navigation")
        observed = set(self.observed_sources(case_id=case_id, root_entity_id=root_entity_id))
        if not set(selected).issubset(observed):
            raise PermissionError("graph navigation may only use sources already evidenced for this entity in the case")
        packets = [self._source_packet(case_id=case_id, source_id=s) for s in selected]
        total = sum(int(p["estimated_max_requests"]) for p in packets)
        pressure = self.crawler369.backpressure(case_id=case_id)
        allowed = all(bool(p["allowed"]) for p in packets) and total <= MAX_TOTAL_NAV_REQUESTS and bool(pressure.get("accept_new_scheduled_work"))
        reasons = [reason for p in packets for reason in p["reasons"]]
        if total > MAX_TOTAL_NAV_REQUESTS:
            reasons.append("total_request_budget_exceeded")
        if not pressure.get("accept_new_scheduled_work"):
            reasons.append("crawler_backpressure")
        plan = {
            "policy": CRAWLER_POLICY,
            "case_id": case_id,
            "root_entity_id": root_entity_id,
            "source_packets": packets,
            "selected_source_ids": selected,
            "estimated_max_requests": total,
            "max_sources_per_navigation": MAX_NAV_SOURCES,
            "max_source_pages": MAX_SOURCE_PAGES,
            "max_total_requests": MAX_TOTAL_NAV_REQUESTS,
            "backpressure": pressure,
            "allowed": allowed,
            "reasons": sorted(set(reasons)),
            "required_confirmation": "NAVIGATE",
            "network_execution": False,
            "automatic_scope_expansion": False,
            "automatic_source_discovery": False,
        }
        plan["plan_hash"] = _sha(plan)
        return plan

    def navigate(self, *, case_id: str, root_entity_id: str, source_ids: Sequence[str], identity: dict[str, Any], confirmation: str) -> dict[str, Any]:
        plan = self.plan(case_id=case_id, root_entity_id=root_entity_id, source_ids=source_ids, identity=identity)
        if str(confirmation or "").strip().upper() != "NAVIGATE":
            raise PermissionError("explicit confirmation NAVIGATE required")
        if not plan["allowed"]:
            raise PermissionError("graph navigation plan is blocked: " + ",".join(plan["reasons"]))
        actor = str(identity.get("username") or self.actor)
        queued: list[dict[str, Any]] = []
        for sid in plan["selected_source_ids"]:
            # Re-check source just before enqueue to avoid stale graph plans.
            packet = self._source_packet(case_id=case_id, source_id=sid)
            if not packet["allowed"]:
                raise PermissionError("source became ineligible before enqueue")
            pressure = self.crawler369.backpressure(case_id=case_id)
            if not pressure.get("accept_new_scheduled_work"):
                raise PermissionError("crawler backpressure opened before enqueue")
            out = self.crawler352.enqueue_crawl(case_id=case_id, source_id=sid)
            job_id = out["job"]["job_id"]
            # Tag graph-originated work while preserving the job-record integrity hash.
            row = self.jobs.get(job_id)
            payload = _j(row.get("payload_json"), {}) or {}
            payload.update({
                "phase16_graph_navigation_v373": True,
                "graph_navigation_policy": CRAWLER_POLICY,
                "graph_root_entity_id": root_entity_id,
                "graph_plan_hash": plan["plan_hash"],
                "graph_analyst": actor[:160],
                "automatic_scope_expansion": False,
            })
            row_for_hash = {k: row[k] for k in row if k not in {"record_hash", "deduplicated"}}
            tagged_at = _now()
            row_for_hash["payload_json"] = _canon(payload)
            row_for_hash["updated_at"] = tagged_at
            new_hash = _sha(row_for_hash)
            self.db.execute("UPDATE phase15_jobs SET payload_json=?,record_hash=?,updated_at=? WHERE job_id=?", (_canon(payload), new_hash, tagged_at, job_id))
            queued.append({"source_id": sid, "crawl_run_id": out["crawl_run_id"], "search_run_id": out["search_run_id"], "job_id": job_id})
            self.audit.log("GRAPH373_NAVIGATION_ENQUEUED", "crawl_run", out["crawl_run_id"], case_id=case_id, details={"root_entity_id": root_entity_id, "source_id": sid, "job_id": job_id, "plan_hash": plan["plan_hash"], "automatic_scope_expansion": False, "policy": CRAWLER_POLICY})
        return {"policy": CRAWLER_POLICY, "case_id": case_id, "root_entity_id": root_entity_id, "plan_hash": plan["plan_hash"], "queued": queued, "network_execution": "delegated_to_existing_governed_crawler_worker", "automatic_scope_expansion": False, "automatic_source_discovery": False}

    def invalid_navigation_jobs(self, *, case_id: str) -> list[str]:
        invalid: list[str] = []
        rows = self.db.all("SELECT job_id,payload_json,rate_budget_json,status FROM phase15_jobs WHERE job_type='governed_crawl_v1' AND case_id=? AND status IN ('queued','running')", (case_id,))
        for row in rows:
            p = _j(row.get("payload_json"), {}) or {}
            if p.get("phase16_graph_navigation_v373") is not True:
                continue
            try:
                entity_id = str(p.get("graph_root_entity_id") or "")
                source_id = str(p.get("source_id") or "")
                observed = set(self.observed_sources(case_id=case_id, root_entity_id=entity_id))
                source = self._source_packet(case_id=case_id, source_id=source_id)
                budget = _j(row.get("rate_budget_json"), {}) or {}
                bad = (
                    p.get("graph_navigation_policy") != CRAWLER_POLICY
                    or p.get("automatic_scope_expansion") is not False
                    or source_id not in observed
                    or not source["allowed"]
                    or int(budget.get("max_requests") or 0) > MAX_TOTAL_NAV_REQUESTS
                )
            except Exception:
                bad = True
            if bad:
                invalid.append(row["job_id"])
        return invalid

    def case_status(self, *, case_id: str) -> dict[str, Any]:
        rows = self.db.all("SELECT job_id,status,payload_json,rate_budget_json,created_at FROM phase15_jobs WHERE job_type='governed_crawl_v1' AND case_id=? ORDER BY created_at DESC LIMIT 200", (case_id,))
        nav = []
        for r in rows:
            p = _j(r.get("payload_json"), {}) or {}
            if p.get("phase16_graph_navigation_v373") is True:
                nav.append({"job_id": r["job_id"], "status": r["status"], "root_entity_id": p.get("graph_root_entity_id"), "source_id": p.get("source_id"), "plan_hash": p.get("graph_plan_hash"), "rate_budget": _j(r.get("rate_budget_json"), {}), "created_at": r["created_at"]})
        return {"policy": CRAWLER_POLICY, "case_id": case_id, "navigation_jobs": nav, "active": sum(1 for r in nav if r["status"] in {"queued", "running"}), "automatic_scope_expansion": False}

    def status(self) -> dict[str, Any]:
        return {
            "policy": CRAWLER_POLICY,
            "graph_aware_crawler_navigation": True,
            "analyst_selected_sources_only": True,
            "explicit_navigation_confirmation": "NAVIGATE",
            "already_evidenced_sources_only": True,
            "max_sources_per_navigation": MAX_NAV_SOURCES,
            "max_source_pages": MAX_SOURCE_PAGES,
            "max_total_requests": MAX_TOTAL_NAV_REQUESTS,
            "source_health_gate": True,
            "backpressure_gate": True,
            "darknet_navigation_separate": True,
            "provider_live_gate_separate": True,
            "automatic_source_discovery": False,
            "automatic_scope_expansion": False,
            "new_per_build_data_tables": 0,
        }


class AutonomousInvestigation373:
    def __init__(self, *, base372: Any, graph373: AnalystGraphUX373, navigation373: GraphAwareCrawler373) -> None:
        self.base372 = base372
        self.graph373 = graph373
        self.navigation373 = navigation373

    def status(self) -> dict[str, Any]:
        base = dict(self.base372.status())
        base.update({
            "policy_version": AI_POLICY,
            "analyst_graph_awareness": True,
            "graph_review_state_awareness": True,
            "crawler_graph_navigation_awareness": True,
            "direct_graph_navigation_authority": False,
            "automatic_scope_expansion": False,
            "automatic_entity_merge": False,
        })
        return base

    def run_cycle(self, *, case_id: str, max_ticks: int = 8) -> dict[str, Any]:
        out = self.base372.run_cycle(case_id=case_id, max_ticks=max_ticks)
        dossier = out.get("dossier")
        if isinstance(dossier, dict):
            # AI receives only aggregate graph/navigation state here. It does not get
            # authority to execute a graph pivot.
            entity_count = int((self.graph373.db.one("SELECT COUNT(*) c FROM resolution_entities_115 WHERE case_id=?", (case_id,)) or {}).get("c") or 0)
            comparison_count = int((self.graph373.db.one("SELECT COUNT(*) c FROM resolution_comparisons_115 WHERE case_id=?", (case_id,)) or {}).get("c") or 0)
            nav = self.navigation373.case_status(case_id=case_id)
            dossier["phase16_analyst_graph_v373"] = {
                "entity_nodes": entity_count,
                "entity_comparisons": comparison_count,
                "graph_navigation_jobs": len(nav["navigation_jobs"]),
                "graph_is_projection": True,
                "direct_graph_navigation_authority": False,
                "automatic_scope_expansion": False,
                "automatic_entity_merge": False,
            }
        return out


class DefensiveOpsecSupervisor373:
    def __init__(self, db: Any, audit: Any, *, base372: Any, navigation373: GraphAwareCrawler373, jobs: Any) -> None:
        self.db = db
        self.audit = audit
        self.base372 = base372
        self.navigation373 = navigation373
        self.jobs = jobs

    def status(self) -> dict[str, Any]:
        base = dict(self.base372.status())
        base.update({
            "policy_version": OPSEC_POLICY,
            "graph_navigation_integrity_monitor": True,
            "graph_scope_expansion_block": True,
            "graph_source_revalidation": True,
            "automatic_graph_navigation_authority": False,
            "automatic_scope_expansion": False,
            "system_mutations": False,
        })
        return base

    def protect_remote_session(self, **kw: Any) -> dict[str, Any]:
        return self.base372.protect_remote_session(**kw)

    def protect_case(self, *, case_id: str) -> dict[str, Any]:
        base = self.base372.protect_case(case_id=case_id)
        invalid = self.navigation373.invalid_navigation_jobs(case_id=case_id)
        for jid in invalid:
            self.jobs.cancel(jid, actor="opsec373")
        if invalid:
            self.audit.log("OPSEC373_GRAPH_NAVIGATION_CANCEL", "case", case_id, case_id=case_id, details={"cancelled_jobs": invalid, "policy": OPSEC_POLICY})
        return {**base, "cancelled_invalid_graph_navigation_jobs": invalid, "graph_navigation_status": self.navigation373.case_status(case_id=case_id), "policy_version": OPSEC_POLICY, "automatic_scope_expansion": False, "system_mutations": False}
