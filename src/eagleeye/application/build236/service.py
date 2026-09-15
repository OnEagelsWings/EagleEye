from __future__ import annotations

import hashlib
import html
import json
from collections import Counter
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from eagleeye_pro.core.database import dumps, new_id, now_ts


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    raw = value if isinstance(value, bytes) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _loads(value: str | None, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except Exception:
        return default


def _text(value: Any, limit: int = 20_000) -> str:
    return str(value or "").replace("\x00", "")[:limit]


def _uniq(values: Sequence[Any], *, limit: int = 100) -> list[str]:
    out: list[str] = []
    for value in values:
        item = _text(value, 200).strip()
        if item and item not in out:
            out.append(item)
        if len(out) >= limit:
            break
    return out


class Build236SourceFabric3Service:
    """Canonical source/capability fabric for Phase 9.

    Build 236 consolidates source metadata and governance while leaving Build 226
    as the canonical explainable ranker. It never performs network access. New or
    revised sources require independent governance before they can be eligible in
    ranking. Case usage maps sources into the Build-235 canonical Source/Evidence
    model. Reviewed Build-231 source outcomes may be staged as Build-228 training
    examples, but remain redaction- and human-review-gated there.
    """

    BUILD = "236.0"
    ALLOWED_OPSEC = {"low", "elevated", "high", "critical"}
    ALLOWED_HEALTH = {"healthy", "degraded", "unknown", "unavailable", "quarantined", "contract_failed"}
    ALLOWED_ACCESS = {"local", "local_import", "manual_browser", "public_api", "licensed_api", "provider_managed", "unknown"}

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        source_intelligence: Any,
        planner: Any,
        reliability: Any,
        adaptive: Any,
        kernel: Any,
        training: Any,
        actor: str = "local-analyst",
    ) -> None:
        self.db, self.audit = db, audit
        self.source_intelligence, self.planner, self.reliability = source_intelligence, planner, reliability
        self.adaptive, self.kernel, self.training = adaptive, kernel, training
        self.actor = actor
        # Seed before attaching the ranker hook to avoid Build226.catalog() -> Fabric -> Build226 recursion.
        self.seed_registry()
        self.source_intelligence._source_fabric_236 = self

    # ------------------------------------------------------------------
    # Registry and governed revisions
    # ------------------------------------------------------------------
    def seed_registry(self) -> dict[str, Any]:
        seeded = 0
        for src in self.source_intelligence.catalog():
            key = _text(src.get("source_key"), 200).strip()
            if not key or self.db.one("SELECT fabric_source_id FROM source_fabric_sources_236 WHERE source_key=?", (key,)):
                continue
            sid, now = new_id("fabric236"), now_ts()
            base_payload = {"fabric_source_id": sid, "source_key": key, "origin": "build226_inherited", "created_by": "migration-236", "created_at": now}
            self.db.execute("INSERT INTO source_fabric_sources_236 VALUES(?,?,?,?,?,?)", (sid, key, "build226_inherited", "migration-236", now, _hash(base_payload)))
            caps = self._capabilities(src.get("target_types", []), src.get("expected_outputs", []), src.get("route_class", "unknown"))
            self._insert_revision(
                sid=sid,
                revision_no=1,
                title=src.get("title") or key,
                provider=src.get("adapter_family") or "",
                source_type=src.get("source_group") or src.get("route_class") or "unknown",
                route_class=src.get("route_class") or "unknown",
                adapter_family=src.get("adapter_family") or "legacy",
                access_mode=self._access_mode(src),
                target_types=src.get("target_types", []),
                outputs=src.get("expected_outputs", []),
                countries=src.get("countries", ["global"]),
                languages=src.get("languages", ["mul"]),
                capabilities=caps,
                cost_class=src.get("cost_class") or "unknown",
                network_capable=bool(src.get("network_capable")),
                requires_auth=bool(src.get("requires_auth")),
                active=bool(src.get("active", True)),
                health_state=self._health(src.get("health_state")),
                opsec_risk=self._opsec(src.get("opsec_risk")),
                governance_state="inherited_approved",
                notes=src.get("notes") or "Inherited from the Build-226 canonical catalog during Build-236 consolidation.",
                created_by="migration-236",
            )
            seeded += 1
        if seeded:
            self._event("", "source_fabric_seeded", "source_registry", "catalog", {"seeded": seeded, "automatic_network_access": False}, "migration-236")
        return {"build": self.BUILD, "seeded": seeded, "total": self.db.one("SELECT COUNT(*) AS n FROM source_fabric_sources_236")["n"]}

    def register_source(
        self,
        *,
        source_key: str,
        title: str,
        provider: str,
        source_type: str,
        route_class: str,
        adapter_family: str,
        access_mode: str,
        target_types: Sequence[str],
        outputs: Sequence[str],
        countries: Sequence[str],
        languages: Sequence[str],
        cost_class: str,
        network_capable: bool,
        requires_auth: bool,
        opsec_risk: str,
        notes: str,
        created_by: str,
        confirmation: str,
    ) -> dict[str, Any]:
        key = _text(source_key, 200).strip()
        if confirmation != f"SOURCE FABRIC 236 {key} ANLEGEN":
            raise PermissionError("explicit approval required")
        if not key or len(key) < 3:
            raise ValueError("source_key required")
        if self.db.one("SELECT fabric_source_id FROM source_fabric_sources_236 WHERE source_key=?", (key,)):
            raise ValueError("source_key already exists; create a revision instead")
        mode = _text(access_mode, 40).strip().lower()
        if mode not in self.ALLOWED_ACCESS:
            raise ValueError("invalid access mode")
        sid, now = new_id("fabric236"), now_ts()
        base = {"fabric_source_id": sid, "source_key": key, "origin": "manual_236", "created_by": created_by, "created_at": now}
        self.db.execute("INSERT INTO source_fabric_sources_236 VALUES(?,?,?,?,?,?)", (sid, key, "manual_236", created_by, now, _hash(base)))
        rid = self._insert_revision(
            sid=sid, revision_no=1, title=title, provider=provider, source_type=source_type, route_class=route_class,
            adapter_family=adapter_family, access_mode=mode, target_types=target_types, outputs=outputs, countries=countries,
            languages=languages, capabilities=self._capabilities(target_types, outputs, route_class), cost_class=cost_class,
            network_capable=network_capable, requires_auth=requires_auth, active=True, health_state="unknown",
            opsec_risk=self._opsec(opsec_risk), governance_state="pending_review", notes=notes, created_by=created_by,
        )
        self._sync_ranker_profile(key)
        self._event("", "source_registered", "fabric_source", sid, {"source_key": key, "revision_id": rid, "governance": "pending_review", "automatic_activation": False}, created_by)
        return self.source(key)

    def revise_source(self, *, source_key: str, changes: Mapping[str, Any], created_by: str, confirmation: str) -> dict[str, Any]:
        key = _text(source_key, 200).strip()
        if confirmation != f"SOURCE FABRIC REVISION 236 {key} ANLEGEN":
            raise PermissionError("explicit approval required")
        current = self.source(key)
        allowed = {"title", "provider", "source_type", "route_class", "adapter_family", "access_mode", "target_types", "outputs", "countries", "languages", "cost_class", "network_capable", "requires_auth", "active", "health_state", "opsec_risk", "notes"}
        unknown = sorted(set(changes) - allowed)
        if unknown:
            raise ValueError("unsupported fields: " + ",".join(unknown))
        merged = {k: current[k] for k in allowed if k in current}
        merged.update(dict(changes))
        if merged.get("access_mode") not in self.ALLOWED_ACCESS:
            raise ValueError("invalid access mode")
        sid = current["fabric_source_id"]
        no = int(current["revision_no"]) + 1
        rid = self._insert_revision(
            sid=sid, revision_no=no, title=merged.get("title", key), provider=merged.get("provider", ""),
            source_type=merged.get("source_type", "unknown"), route_class=merged.get("route_class", "unknown"),
            adapter_family=merged.get("adapter_family", "manual"), access_mode=merged.get("access_mode", "unknown"),
            target_types=merged.get("target_types", []), outputs=merged.get("outputs", []), countries=merged.get("countries", ["global"]),
            languages=merged.get("languages", ["mul"]), capabilities=self._capabilities(merged.get("target_types", []), merged.get("outputs", []), merged.get("route_class", "unknown")),
            cost_class=merged.get("cost_class", "unknown"), network_capable=bool(merged.get("network_capable")), requires_auth=bool(merged.get("requires_auth")),
            active=bool(merged.get("active", True)), health_state=self._health(merged.get("health_state")), opsec_risk=self._opsec(merged.get("opsec_risk")),
            governance_state="pending_review", notes=merged.get("notes", ""), created_by=created_by,
        )
        self._sync_ranker_profile(key)
        self._event("", "source_revision_created", "fabric_source", sid, {"source_key": key, "revision_id": rid, "revision_no": no, "automatic_activation": False}, created_by)
        return self.source(key)

    def review_revision(self, *, revision_id: str, decision: str, rationale: str, reviewer: str, confirmation: str) -> dict[str, Any]:
        row = self._revision(revision_id)
        if confirmation != f"SOURCE FABRIC REVIEW 236 {revision_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        if decision not in {"approved", "rejected", "deferred"}:
            raise ValueError("invalid decision")
        if reviewer == row["created_by"]:
            raise PermissionError("independent reviewer required")
        note = _text(rationale, 5000).strip()
        if len(note) < 12:
            raise ValueError("substantive rationale required")
        if row["governance_state"] == "inherited_approved":
            raise ValueError("inherited baseline revision does not require a review")
        if self.db.one("SELECT review_id FROM source_fabric_reviews_236 WHERE revision_id=?", (revision_id,)):
            raise ValueError("revision already reviewed")
        rid, now = new_id("fabrev236"), now_ts()
        payload = {"review_id": rid, "revision_id": revision_id, "fabric_source_id": row["fabric_source_id"], "decision": decision, "rationale": note, "reviewer": reviewer, "reviewed_at": now}
        self.db.execute("INSERT INTO source_fabric_reviews_236 VALUES(?,?,?,?,?,?,?,?)", (rid, revision_id, row["fabric_source_id"], decision, note, reviewer, now, _hash(payload)))
        self._event("", "source_revision_reviewed", "fabric_revision", revision_id, {"decision": decision, "independent_review": True}, reviewer)
        return {**payload, "automatic_source_execution": False, "automatic_activation": False}

    def observe_health(self, *, source_key: str, health_state: str, latency_ms: int, error_class: str, note: str, observed_by: str, confirmation: str) -> dict[str, Any]:
        key = _text(source_key, 200).strip(); src = self.source(key)
        if confirmation != f"SOURCE HEALTH 236 {key} SPEICHERN":
            raise PermissionError("explicit approval required")
        state = self._health(health_state)
        oid, now = new_id("health236"), now_ts()
        payload = {"observation_id": oid, "fabric_source_id": src["fabric_source_id"], "source_key": key, "health_state": state,
                   "latency_ms": max(0, min(int(latency_ms or 0), 86_400_000)), "error_class": _text(error_class, 200), "note": _text(note, 4000),
                   "observed_by": observed_by, "observed_at": now}
        self.db.execute("INSERT INTO source_fabric_health_236 VALUES(?,?,?,?,?,?,?,?,?,?)", (oid, src["fabric_source_id"], key, state, payload["latency_ms"], payload["error_class"], payload["note"], observed_by, now, _hash(payload)))
        self._event("", "source_health_observed", "fabric_source", src["fabric_source_id"], {"source_key": key, "health_state": state, "network_executed_by_fabric": False}, observed_by)
        return payload

    # ------------------------------------------------------------------
    # Build-226 integration
    # ------------------------------------------------------------------
    def catalog(self, *, active_only: bool = False) -> list[dict[str, Any]]:
        rows = self.db.all("""
            SELECT s.*,r.*,rv.decision AS review_decision,rv.reviewer AS reviewer
            FROM source_fabric_sources_236 s
            JOIN source_fabric_revisions_236 r ON r.fabric_source_id=s.fabric_source_id
            JOIN (SELECT fabric_source_id,MAX(revision_no) AS n FROM source_fabric_revisions_236 GROUP BY fabric_source_id) x
              ON x.fabric_source_id=r.fabric_source_id AND x.n=r.revision_no
            LEFT JOIN source_fabric_reviews_236 rv ON rv.revision_id=r.revision_id
            ORDER BY r.route_class,r.title,s.source_key
        """)
        out: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            for field in ("target_types_json", "outputs_json", "countries_json", "languages_json", "capabilities_json"):
                item[field.removesuffix("_json")] = _loads(item.get(field), [])
            item["governance_effective"] = self._governance(item)
            health = self.db.one("SELECT * FROM source_fabric_health_236 WHERE fabric_source_id=? ORDER BY observed_at DESC,observation_id DESC LIMIT 1", (item["fabric_source_id"],))
            item["health_effective"] = (health or {}).get("health_state") or item["health_state"]
            if active_only and (not bool(item["active"]) or item["governance_effective"] not in {"approved", "inherited_approved"}):
                continue
            out.append(item)
        return out

    def source(self, source_key: str) -> dict[str, Any]:
        key = _text(source_key, 200).strip()
        row = next((x for x in self.catalog(active_only=False) if x["source_key"] == key), None)
        if not row:
            raise KeyError(key)
        return row

    def catalog_entries_for_ranker(self, base_entries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        base = {str(x.get("source_key")): dict(x) for x in base_entries}
        for src in self.catalog(active_only=False):
            old = base.get(src["source_key"], {})
            target_types = src["target_types"] or old.get("target_types", ["unknown"])
            outputs = src["outputs"] or old.get("expected_outputs", ["evidence"])
            base[src["source_key"]] = {
                **old,
                "source_key": src["source_key"], "title": src["title"], "route_class": src["route_class"], "adapter_family": src["adapter_family"],
                "target_types": target_types, "expected_outputs": outputs, "countries": src["countries"] or ["global"], "languages": src["languages"] or ["mul"],
                "network_capable": bool(src["network_capable"]), "requires_auth": bool(src["requires_auth"]), "active": bool(src["active"]),
                "health_state": src["health_effective"], "opsec_risk": src["opsec_risk"], "cost_class": src["cost_class"],
                "source_group": old.get("source_group") or src["source_type"] or src["adapter_family"], "notes": src["notes"],
                "precision_prior": float(old.get("precision_prior", .55)), "recall_prior": float(old.get("recall_prior", .55)),
                "provenance_prior": float(old.get("provenance_prior", .60)), "identity_risk": float(old.get("identity_risk", .50)),
                "fabric_governance": src["governance_effective"], "fabric_revision_id": src["revision_id"], "fabric_source_id": src["fabric_source_id"],
                "access_mode": src["access_mode"], "capabilities": src["capabilities"],
            }
        return list(base.values())

    def ranking_constraint(self, *, source_key: str) -> dict[str, Any]:
        try:
            src = self.source(source_key)
        except KeyError:
            return {"managed": False, "eligible": True, "reason": "not_managed_by_build236"}
        reasons=[]
        if src["governance_effective"] not in {"approved", "inherited_approved"}: reasons.append("source_fabric_governance_not_approved")
        if not bool(src["active"]): reasons.append("source_fabric_inactive")
        if src["health_effective"] in {"unavailable", "quarantined", "contract_failed"}: reasons.append("source_fabric_unhealthy")
        return {"managed": True, "eligible": not reasons, "reasons": reasons, "governance": src["governance_effective"],
                "health": src["health_effective"], "opsec_risk": src["opsec_risk"], "revision_id": src["revision_id"],
                "automatic_execution": False}

    # ------------------------------------------------------------------
    # Build-235 canonical mapping
    # ------------------------------------------------------------------
    def bind_source_to_case(self, *, case_id: str, source_key: str, actor: str, confirmation: str) -> dict[str, Any]:
        self._case(case_id); key = _text(source_key, 200).strip(); src = self.source(key)
        if confirmation != f"SOURCE FABRIC BIND 236 {case_id} {key}":
            raise PermissionError("explicit approval required")
        if src["governance_effective"] not in {"approved", "inherited_approved"}:
            raise PermissionError("source revision is not governance-approved")
        existing = self.db.one("SELECT * FROM source_fabric_case_bindings_236 WHERE case_id=? AND fabric_source_id=?", (case_id, src["fabric_source_id"]))
        if existing:
            return {**existing, "idempotent": True}
        source_obj = self.kernel.create_source(case_id=case_id, label=src["title"], url="", source_class=src["source_type"], actor=actor,
                                               confirmation=f"KERNEL OBJECT 235 {case_id} ANLEGEN")
        bid, now = new_id("bind236"), now_ts()
        payload = {"binding_id": bid, "case_id": case_id, "fabric_source_id": src["fabric_source_id"], "source_key": key,
                   "canonical_source_object_id": source_obj["object_id"], "bound_by": actor, "bound_at": now}
        self.db.execute("INSERT INTO source_fabric_case_bindings_236 VALUES(?,?,?,?,?,?,?,?)", (bid, case_id, src["fabric_source_id"], key, source_obj["object_id"], actor, now, _hash(payload)))
        self._event(case_id, "source_bound_to_kernel", "fabric_source", src["fabric_source_id"], {"source_key": key, "canonical_source_object_id": source_obj["object_id"]}, actor)
        return payload

    def create_case_evidence(self, *, case_id: str, source_key: str, title: str, statement: str, confidence: float, actor: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"SOURCE EVIDENCE 236 {case_id} {source_key} ANLEGEN":
            raise PermissionError("explicit approval required")
        binding = self.bind_source_to_case(case_id=case_id, source_key=source_key, actor=actor, confirmation=f"SOURCE FABRIC BIND 236 {case_id} {source_key}")
        ev = self.kernel.create_evidence(case_id=case_id, title=title, statement=statement, source_object_id=binding["canonical_source_object_id"], confidence=confidence,
                                         actor=actor, confirmation=f"KERNEL OBJECT 235 {case_id} ANLEGEN")
        self._event(case_id, "fabric_evidence_created", "canonical_evidence", ev["object_id"], {"source_key": source_key, "canonical_source_object_id": binding["canonical_source_object_id"]}, actor)
        return {"evidence": ev, "binding": binding}

    # ------------------------------------------------------------------
    # Continuous governed AI training
    # ------------------------------------------------------------------
    def stage_training_from_reviewed_outcomes(self, *, case_id: str, limit: int, actor: str, confirmation: str) -> dict[str, Any]:
        self._case(case_id)
        if confirmation != f"SOURCE TRAINING 236 {case_id} VORBEREITEN":
            raise PermissionError("explicit approval required")
        lim = max(1, min(int(limit or 10), 50))
        rows = self.db.all("""
            SELECT o.*,r.decision AS review_decision,r.review_note,r.reviewer
            FROM source_outcomes_231 o
            JOIN source_outcome_reviews_231 r ON r.outcome_id=o.outcome_id AND r.decision='accepted'
            LEFT JOIN source_fabric_training_links_236 t ON t.source_outcome_id=o.outcome_id
            WHERE o.case_id=? AND t.training_link_id IS NULL
            ORDER BY r.reviewed_at,o.outcome_id LIMIT ?
        """, (case_id, lim))
        staged=[]; blocked=[]
        for row in rows:
            source_key = row["source_key"]
            try:
                src = self.source(source_key)
                source_context = {"source_key": source_key, "source_type": src["source_type"], "route_class": src["route_class"], "access_mode": src["access_mode"],
                                  "countries": src["countries"], "languages": src["languages"], "opsec_risk": src["opsec_risk"], "governance": src["governance_effective"]}
            except KeyError:
                source_context = {"source_key": source_key, "source_type": "unknown"}
            context = {**source_context, "target_type": row.get("target_type") or "unknown", "country": row.get("country") or "", "language": row.get("language") or "und",
                       "outcome_kind": row["outcome_kind"], "precision_signal": float(row["precision_signal"]), "counterevidence_signal": float(row["counterevidence_signal"]),
                       "error_signal": float(row["error_signal"]), "opsec_incident": bool(row["opsec_incident"]), "independent_review": True}
            instruction = "Bewerte dieses bereits unabhängig geprüfte Quellen-Outcome für die zukünftige investigative Quellenwahl. Begründe Nutzen, Grenzen, Gegenbelegwert und OPSEC-Risiko ausschließlich aus dem bereitgestellten Kontext."
            response = (f"Reviewtes Outcome: {row['outcome_kind']}. Präzisionssignal {float(row['precision_signal']):.2f}; "
                        f"Gegenbelegsignal {float(row['counterevidence_signal']):.2f}; Fehlersignal {float(row['error_signal']):.2f}; "
                        f"OPSEC-Vorfall: {'ja' if bool(row['opsec_incident']) else 'nein'}. "
                        f"Analystische Begründung: {_text(row['rationale'], 3000)}. Unabhängiges Review: {_text(row['review_note'], 2000)}")
            try:
                example = self.training.add_example(case_id=case_id, instruction=instruction, response=response, context=context,
                    evidence_refs=_loads(row.get("evidence_refs_json"), []), language=row.get("language") or "de", source_type="source_fabric_236",
                    source_ref=row["outcome_id"], created_by=actor, confirmation=f"TRAINING EXAMPLE 228 {case_id} ANLEGEN")
                lid, now = new_id("trainlink236"), now_ts(); payload={"training_link_id":lid,"case_id":case_id,"source_outcome_id":row["outcome_id"],"source_key":source_key,"training_example_id":example["example_id"],"created_by":actor,"created_at":now}
                self.db.execute("INSERT INTO source_fabric_training_links_236 VALUES(?,?,?,?,?,?,?,?)", (lid,case_id,row["outcome_id"],source_key,example["example_id"],actor,now,_hash(payload)))
                staged.append({"outcome_id": row["outcome_id"], "training_example_id": example["example_id"], "redaction_status": example["redaction_status"], "review_status": example["review_status"]})
            except Exception as exc:
                blocked.append({"outcome_id": row["outcome_id"], "error": type(exc).__name__, "message": _text(exc, 500)})
        self._event(case_id, "source_training_candidates_staged", "training_batch", new_id("batch236"), {"staged": len(staged), "blocked": len(blocked), "automatic_dataset_approval": False, "automatic_model_activation": False}, actor)
        return {"build": self.BUILD, "case_id": case_id, "eligible_reviewed_outcomes": len(rows), "staged": staged, "blocked": blocked,
                "training_pipeline": "build228", "human_review_required": True, "automatic_training_execution": False, "automatic_model_activation": False}

    def training_status(self, *, case_id: str) -> dict[str, Any]:
        reviewed = self.db.one("SELECT COUNT(*) AS n FROM source_outcomes_231 o JOIN source_outcome_reviews_231 r ON r.outcome_id=o.outcome_id AND r.decision='accepted' WHERE o.case_id=?", (case_id,))["n"]
        staged = self.db.one("SELECT COUNT(*) AS n FROM source_fabric_training_links_236 WHERE case_id=?", (case_id,))["n"]
        pending = self.db.one("SELECT COUNT(*) AS n FROM training_examples_228 WHERE case_id=? AND source_type='source_fabric_236' AND review_status='pending'", (case_id,))["n"]
        approved = self.db.one("SELECT COUNT(*) AS n FROM training_examples_228 WHERE case_id=? AND source_type='source_fabric_236' AND review_status='approved'", (case_id,))["n"]
        return {"reviewed_source_outcomes": reviewed, "staged_training_examples": staged, "pending_training_review": pending, "approved_training_examples": approved,
                "unstaged_reviewed_outcomes": max(0, int(reviewed)-int(staged))}

    # ------------------------------------------------------------------
    # Dashboard/UI
    # ------------------------------------------------------------------
    def dashboard(self, *, case_id: str) -> dict[str, Any]:
        catalog=self.catalog(active_only=False); gov=Counter(x["governance_effective"] for x in catalog); health=Counter(x["health_effective"] for x in catalog)
        bindings=self.db.one("SELECT COUNT(*) AS n FROM source_fabric_case_bindings_236 WHERE case_id=?",(case_id,))["n"]
        return {"build":self.BUILD,"source_count":len(catalog),"approved_sources":sum(1 for x in catalog if x["governance_effective"] in {"approved","inherited_approved"}),
                "pending_sources":gov.get("pending_review",0),"governance":dict(gov),"health":dict(health),"case_bindings":bindings,"training":self.training_status(case_id=case_id),
                "automatic_network_access":False,"ranker":"build226","kernel":"build235","training_pipeline":"build228"}

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        d=self.dashboard(case_id=case_id); esc=lambda x: html.escape(str(x if x is not None else ""), quote=True)
        rows="".join(f"<tr><td><code>{esc(x['source_key'])}</code></td><td>{esc(x['title'])}</td><td>{esc(x['route_class'])}</td><td>{esc(x['governance_effective'])}</td><td>{esc(x['health_effective'])}</td><td>{esc(x['opsec_risk'])}</td></tr>" for x in self.catalog(active_only=False)[:30]) or "<tr><td colspan='6'>Keine Quellen.</td></tr>"
        tr=d["training"]
        return f"""
<section class='card' id='build236_source_fabric'><h2>Source Fabric 3.0 + Continuous AI Training · Build 236</h2>
<p>Zentrale, versionierte Quellen-/Capability-Registry über Build 226. Neue Quellen bleiben bis zum unabhängigen Governance-Review ranking-ineligible. Build 236 führt selbst keine Netzwerkzugriffe aus.</p>
<p><strong>Quellen:</strong> {d['source_count']} · freigegeben: {d['approved_sources']} · pending: {d['pending_sources']} · Fallbindungen an Kernel 235: {d['case_bindings']}</p>
<div class='grid two'>
<div class='card'><h3>Quelle im Fall verankern</h3><form method='post' action='/build236/bind-source'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='source_key' placeholder='source_key' required><button>Mit Kernel 235 verbinden</button></form><p class='muted'>Nur governance-freigegebene Quellen.</p></div>
<div class='card'><h3>Health-Beobachtung</h3><form method='post' action='/build236/health-observe'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='source_key' placeholder='source_key' required><select name='health_state'><option>healthy</option><option>degraded</option><option>unknown</option><option>unavailable</option><option>quarantined</option><option>contract_failed</option></select><input name='latency_ms' type='number' min='0' value='0'><input name='note' placeholder='Beobachtung / Begründung'><button>Beobachtung speichern</button></form></div>
<div class='card'><h3>KI-Training fortführen</h3><p>Reviewte Source-Outcomes: {tr['reviewed_source_outcomes']} · noch nicht gestaged: {tr['unstaged_reviewed_outcomes']} · pending Training-Review: {tr['pending_training_review']} · freigegeben: {tr['approved_training_examples']}</p><form method='post' action='/build236/training-stage'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='limit' type='number' min='1' max='50' value='10'><button>Reviewte Outcomes als Trainingskandidaten vorbereiten</button></form><p class='muted'>Danach gelten weiterhin Build-228-Redaktion, Human Review, Holdout und Qualifikationsgates. Keine automatische Modellaktivierung.</p></div>
<div class='card'><h3>Neue Quelle registrieren</h3><form method='post' action='/build236/source-register'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='source_key' placeholder='eindeutiger source_key' required><input name='title' placeholder='Titel' required><input name='route_class' value='public_web'><input name='source_type' value='open_web'><select name='access_mode'><option>manual_browser</option><option>local</option><option>local_import</option><option>public_api</option><option>licensed_api</option><option>provider_managed</option></select><input name='target_types' value='unknown'><input name='outputs' value='evidence'><input name='countries' value='global'><input name='languages' value='mul'><select name='opsec_risk'><option>low</option><option selected>elevated</option><option>high</option><option>critical</option></select><button>Als reviewpflichtige Quelle registrieren</button></form></div>
<div class='card'><h3>Quellenrevision prüfen</h3><form method='post' action='/build236/source-review'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='revision_id' placeholder='Revision-ID' required><select name='decision'><option>approved</option><option>deferred</option><option>rejected</option></select><textarea name='rationale' placeholder='Unabhängige Begründung' required></textarea><button>Governance-Review speichern</button></form></div>
</div>
<div class='table-wrap'><table><thead><tr><th>Key</th><th>Quelle</th><th>Route</th><th>Governance</th><th>Health</th><th>OPSEC</th></tr></thead><tbody>{rows}</tbody></table></div>
</section>"""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _insert_revision(self, *, sid: str, revision_no: int, title: str, provider: str, source_type: str, route_class: str, adapter_family: str,
                         access_mode: str, target_types: Sequence[str], outputs: Sequence[str], countries: Sequence[str], languages: Sequence[str], capabilities: Sequence[Mapping[str, Any]],
                         cost_class: str, network_capable: bool, requires_auth: bool, active: bool, health_state: str, opsec_risk: str, governance_state: str,
                         notes: str, created_by: str) -> str:
        rid, now = new_id("fabrev236"), now_ts(); target=_uniq(target_types) or ["unknown"]; out=_uniq(outputs) or ["evidence"]; ctr=_uniq(countries) or ["global"]; langs=_uniq(languages) or ["mul"]
        payload={"revision_id":rid,"fabric_source_id":sid,"revision_no":int(revision_no),"title":_text(title,500),"provider":_text(provider,300),"source_type":_text(source_type,120),
                 "route_class":_text(route_class,120),"adapter_family":_text(adapter_family,120),"access_mode":access_mode,"target_types":target,"outputs":out,"countries":ctr,"languages":langs,
                 "capabilities":list(capabilities),"cost_class":_text(cost_class,80),"network_capable":bool(network_capable),"requires_auth":bool(requires_auth),"active":bool(active),
                 "health_state":self._health(health_state),"opsec_risk":self._opsec(opsec_risk),"governance_state":governance_state,"notes":_text(notes,5000),"created_by":created_by,"created_at":now}
        self.db.execute("INSERT INTO source_fabric_revisions_236 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (rid,sid,int(revision_no),payload["title"],payload["provider"],payload["source_type"],payload["route_class"],payload["adapter_family"],access_mode,dumps(target),dumps(out),dumps(ctr),dumps(langs),dumps(list(capabilities)),payload["cost_class"],int(bool(network_capable)),int(bool(requires_auth)),int(bool(active)),payload["health_state"],payload["opsec_risk"],governance_state,payload["notes"],created_by,now,_hash(payload)))
        return rid

    def _revision(self, revision_id: str) -> dict[str, Any]:
        row=self.db.one("SELECT * FROM source_fabric_revisions_236 WHERE revision_id=?",(revision_id,))
        if not row: raise KeyError(revision_id)
        return row

    def _governance(self, row: Mapping[str, Any]) -> str:
        if row.get("governance_state") == "inherited_approved": return "inherited_approved"
        decision=row.get("review_decision")
        return decision if decision in {"approved","rejected","deferred"} else "pending_review"

    def _capabilities(self, target_types: Sequence[str], outputs: Sequence[str], route_class: str) -> list[dict[str, str]]:
        targets=_uniq(target_types) or ["unknown"]; outs=_uniq(outputs) or ["evidence"]
        return [{"capability_key":f"{_text(route_class,80)}:{t}:{o}","target_type":t,"output_type":o} for t in targets for o in outs][:100]

    def _access_mode(self, src: Mapping[str, Any]) -> str:
        if not bool(src.get("network_capable")): return "local"
        if bool(src.get("requires_auth")): return "provider_managed"
        if src.get("cost_class") == "public-browser": return "manual_browser"
        return "public_api"

    def _health(self, value: Any) -> str:
        state=_text(value or "unknown",50).lower()
        return state if state in self.ALLOWED_HEALTH else "unknown"

    def _opsec(self, value: Any) -> str:
        risk=_text(value or "elevated",30).lower()
        return risk if risk in self.ALLOWED_OPSEC else "critical"

    def _sync_ranker_profile(self, source_key: str) -> None:
        """Keep the Build-226 FK/catalog substrate aware of Fabric-only sources.

        Governance remains authoritative in Build 236; this profile only provides
        the stable foreign-key row and conservative scoring priors.
        """
        src=self.source(source_key); now=now_ts(); existing=self.db.one("SELECT created_at FROM source_intelligence_profiles_226 WHERE source_key=?",(source_key,))
        created=(existing or {}).get("created_at",now)
        payload={"source_key":source_key,"title":src["title"],"route_class":src["route_class"],"adapter_family":src["adapter_family"],"target_types":src["target_types"],"outputs":src["outputs"],"countries":src["countries"],"languages":src["languages"],"network_capable":bool(src["network_capable"]),"requires_auth":bool(src["requires_auth"]),"active":bool(src["active"]),"health_state":src["health_effective"],"opsec_risk":src["opsec_risk"],"cost_class":src["cost_class"],"source_group":src["source_type"],"notes":src["notes"],"updated_at":now}
        self.db.execute("""INSERT INTO source_intelligence_profiles_226(source_key,title,route_class,adapter_family,target_types_json,expected_outputs_json,countries_json,languages_json,network_capable,requires_auth,active,health_state,opsec_risk,cost_class,provenance_prior,precision_prior,recall_prior,identity_risk,source_group,notes,created_at,updated_at,payload_sha256) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(source_key) DO UPDATE SET title=excluded.title,route_class=excluded.route_class,adapter_family=excluded.adapter_family,target_types_json=excluded.target_types_json,expected_outputs_json=excluded.expected_outputs_json,countries_json=excluded.countries_json,languages_json=excluded.languages_json,network_capable=excluded.network_capable,requires_auth=excluded.requires_auth,active=excluded.active,health_state=excluded.health_state,opsec_risk=excluded.opsec_risk,cost_class=excluded.cost_class,source_group=excluded.source_group,notes=excluded.notes,updated_at=excluded.updated_at,payload_sha256=excluded.payload_sha256""",
            (source_key,src["title"],src["route_class"],src["adapter_family"],dumps(src["target_types"]),dumps(src["outputs"]),dumps(src["countries"]),dumps(src["languages"]),int(bool(src["network_capable"])),int(bool(src["requires_auth"])),int(bool(src["active"])),src["health_effective"],src["opsec_risk"],src["cost_class"],.55,.55,.55,.50,src["source_type"],src["notes"],created,now,_hash(payload)))

    def _case(self, case_id: str) -> None:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?",(case_id,)): raise KeyError(case_id)

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: Mapping[str, Any], actor: str) -> None:
        prev=self.db.one("SELECT event_hash FROM build236_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1",(case_id,)); previous=(prev or {}).get("event_hash","GENESIS")
        eid,now=new_id("evt236"),now_ts(); material={"event_id":eid,"case_id":case_id,"event_type":event_type,"object_type":object_type,"object_id":object_id,"actor":actor,"payload":dict(payload),"previous_hash":previous,"created_at":now}; event_hash=_hash(material)
        self.db.execute("INSERT INTO build236_events VALUES(?,?,?,?,?,?,?,?,?,?)",(eid,case_id,event_type,object_type,object_id,actor,dumps(dict(payload)),previous,event_hash,now))
        try: self.audit.log(event_type,object_type,object_id,case_id,dict(payload))
        except Exception: pass
