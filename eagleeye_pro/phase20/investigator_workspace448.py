from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import secrets

BUILD = "448.0"
POLICY_ID = "phase20.investigator-workspace-ui-audit.v448"

PRIMARY_VIEWS = (
    ("overview", "Übersicht"),
    ("research", "Recherche"),
    ("ai", "AI-Ermittlung"),
    ("evidence", "Evidence"),
    ("claims", "Claims & Hypothesen"),
    ("analysis", "Graph & Timeline"),
    ("dossier", "Dossier"),
    ("operations", "OPSEC & Team"),
)

REQUIRED_MUTATION_ROUTES = (
    ("POST", "/api/build439/cases/{case_id}/investigation/loops"),
    ("POST", "/api/build439/cases/{case_id}/investigation/loops/{loop_id}/authorize"),
    ("POST", "/api/build439/cases/{case_id}/investigation/loops/{loop_id}/advance"),
    ("POST", "/api/build446/loops/{loop_id}/dispatches/prepare"),
    ("POST", "/api/build446/dispatches/{dispatch_id}/execute"),
    ("POST", "/api/build447/cases/{case_id}/evidence/sync"),
    ("POST", "/api/build447/evidence/{evidence_id}/review"),
    ("POST", "/api/build447/cases/{case_id}/claims"),
    ("POST", "/api/build447/claims/{claim_id}/review"),
    ("POST", "/api/build447/cases/{case_id}/dossiers"),
    ("POST", "/api/build447/dossiers/{revision_id}/review"),
    ("POST", "/api/build447/dossiers/{revision_id}/export"),
)

REQUIRED_READ_ROUTES = (
    ("GET", "/api/build439/cases/{case_id}/investigation/loops"),
    ("GET", "/api/build446/loops/{loop_id}/dispatches"),
    ("GET", "/api/build446/loops/{loop_id}/executions"),
    ("GET", "/api/build447/cases/{case_id}/evidence"),
    ("GET", "/api/build447/cases/{case_id}/claims"),
    ("GET", "/api/build447/cases/{case_id}/dossiers"),
)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value):
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


class InvestigatorWorkspace448:
    """Case-first workspace aggregator and UI audit ledger.

    Build 448 intentionally does not create another analytical truth layer. It
    composes the current case state into an operator-facing workspace and records
    repeatable UI/route audits.
    """

    def __init__(
        self,
        db,
        audit,
        *,
        cases,
        registry421,
        loop439,
        dispatcher446,
        closure447,
        fusion438,
        resolution437,
        matrix418,
        synthesis419,
        governance,
        actor="local-analyst",
    ):
        self.db = db
        self.audit = audit
        self.cases = cases
        self.registry421 = registry421
        self.loop439 = loop439
        self.dispatcher446 = dispatcher446
        self.closure447 = closure447
        self.fusion438 = fusion438
        self.resolution437 = resolution437
        self.matrix418 = matrix418
        self.synthesis419 = synthesis419
        self.governance = governance
        self.actor = actor
        self._init_schema()

    def _init_schema(self):
        self.db.conn.executescript(
            """CREATE TABLE IF NOT EXISTS ui_audit_448(
            audit_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            result TEXT NOT NULL,
            checks_json TEXT NOT NULL,
            warnings_json TEXT NOT NULL,
            route_count INTEGER NOT NULL,
            markup_sha256 TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_ui_audit448_case
            ON ui_audit_448(case_id,created_at);
            """
        )
        self.db.conn.commit()

    def _rh(self, row):
        return _sha({k: row[k] for k in row if k != "record_hash"})

    def _identity(self, identity):
        if not isinstance(identity, dict) or not identity.get("username") or not identity.get("user_id"):
            raise PermissionError("canonical active identity required")
        try:
            user = self.governance.identity.public_user(str(identity["username"]))
        except (KeyError, ValueError):
            raise PermissionError("canonical active identity required")
        if not user.get("active") or str(user.get("user_id")) != str(identity.get("user_id")):
            raise PermissionError("canonical active identity required")
        return {**user, "session_id": str(identity.get("session_id") or "workspace448")}

    def _authorize(self, identity, case_id, capability="case.read"):
        ident = self._identity(identity)
        self.governance.authorize(
            ident,
            case_id=str(case_id),
            capability=capability,
            object_type="investigator_workspace_448",
            object_id=str(case_id),
        )
        return ident

    @staticmethod
    def _count(rows, key, value):
        return sum(1 for row in rows if str(row.get(key) or "") == str(value))

    def _source_rows(self):
        try:
            return self.registry421.list_sources()
        except TypeError:
            return self.registry421.list_sources(enabled_only=False)

    def snapshot(self, *, identity, case_id):
        ident = self._authorize(identity, case_id)
        case = self.cases.get_case(str(case_id))
        loops = self.loop439.loops(str(case_id))
        latest_loop = loops[-1] if loops else None
        dispatches = self.dispatcher446.dispatches(latest_loop["loop_id"]) if latest_loop else []
        executions = self.dispatcher446.executions(latest_loop["loop_id"]) if latest_loop else []
        evidence = self.closure447.case_evidence(str(case_id))
        claims = self.closure447.case_claims(str(case_id))
        dossiers = self.closure447.case_dossiers(str(case_id))
        exports = self.closure447.exports(str(case_id))
        sources = self._source_rows()

        latest_fusion = self.db.one(
            "SELECT * FROM phase19_fusion_run_438 WHERE case_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1",
            (str(case_id),),
        )
        latest_fusion = dict(latest_fusion) if latest_fusion else {}
        entity_count = int(
            (self.db.one(
                "SELECT COUNT(*) n FROM resolution_entities_115 WHERE case_id=?",
                (str(case_id),),
            ) or {}).get("n") or 0
        )
        binding_count = int(
            (self.db.one(
                "SELECT COUNT(*) n FROM phase19_entity_binding_437 WHERE case_id=?",
                (str(case_id),),
            ) or {}).get("n") or 0
        ) if self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name='phase19_entity_binding_437'") else 0

        matrix = None
        latest_synthesis = None
        if latest_loop:
            try:
                matrix = self.matrix418.matrix(
                    session_id=latest_loop["session_id"],
                    identity=ident,
                )
            except (KeyError, PermissionError, RuntimeError, ValueError):
                matrix = None
            row = self.db.one(
                "SELECT * FROM investigation_synthesis_419 WHERE session_id=? "
                "ORDER BY created_at DESC,rowid DESC LIMIT 1",
                (latest_loop["session_id"],),
            )
            if row:
                latest_synthesis = dict(row)
                try:
                    latest_synthesis["summary"] = json.loads(
                        latest_synthesis.get("summary_json") or "{}"
                    )
                except Exception:
                    latest_synthesis["summary"] = {}

        metrics = {
            "sources": len(sources),
            "loops": len(loops),
            "active_loops": self._count(loops, "state", "active"),
            "dispatches": len(dispatches),
            "executions": len(executions),
            "evidence": len(evidence),
            "evidence_unreviewed": self._count(evidence, "review_state", "unreviewed"),
            "claims": len(claims),
            "claims_review_required": self._count(claims, "state", "candidate_review_required"),
            "claims_accepted": self._count(claims, "state", "accepted_for_dossier"),
            "dossiers": len(dossiers),
            "dossiers_review_required": self._count(dossiers, "state", "draft_for_review"),
            "exports": len(exports),
            "entities": entity_count,
            "bindings": binding_count,
            "timeline_events": int(latest_fusion.get("timeline_events") or 0),
            "relationship_edges": int(latest_fusion.get("relationship_edges") or 0),
            "unresolved_relationships": int(latest_fusion.get("unresolved_relationships") or 0),
            "hypotheses": len((matrix or {}).get("hypotheses") or []),
            "gaps": len((matrix or {}).get("gaps") or []),
            "conflicts": len((matrix or {}).get("conflicts") or []),
        }

        next_actions = []
        if not loops:
            next_actions.append({"view": "ai", "priority": "high", "label": "AI-Ermittlung anlegen"})
        elif latest_loop and latest_loop["state"] == "awaiting_human_authorization":
            next_actions.append({"view": "ai", "priority": "high", "label": "AI-Ermittlung freigeben"})
        elif latest_loop and latest_loop["state"] == "active" and not dispatches:
            next_actions.append({"view": "research", "priority": "high", "label": "Quellen-Dispatch vorbereiten"})
        if metrics["evidence_unreviewed"]:
            next_actions.append({"view": "evidence", "priority": "high", "label": f"{metrics['evidence_unreviewed']} Evidence-Items prüfen"})
        if metrics["claims_review_required"]:
            next_actions.append({"view": "claims", "priority": "high", "label": f"{metrics['claims_review_required']} Claims prüfen"})
        if metrics["gaps"] or metrics["conflicts"]:
            next_actions.append({"view": "claims", "priority": "medium", "label": f"{metrics['gaps']} Gaps / {metrics['conflicts']} Konflikte prüfen"})
        if metrics["claims_accepted"] and not dossiers:
            next_actions.append({"view": "dossier", "priority": "medium", "label": "Living Dossier erzeugen"})
        if metrics["dossiers_review_required"]:
            next_actions.append({"view": "dossier", "priority": "high", "label": f"{metrics['dossiers_review_required']} Dossier-Revision(en) prüfen"})
        if not next_actions:
            next_actions.append({"view": "overview", "priority": "normal", "label": "Keine zwingende nächste Aktion"})

        return {
            "build": BUILD,
            "case": case,
            "actor": ident["username"],
            "metrics": metrics,
            "sources": sources,
            "loops": loops,
            "latest_loop": latest_loop,
            "dispatches": dispatches,
            "executions": executions,
            "evidence": evidence,
            "claims": claims,
            "dossiers": dossiers,
            "exports": exports,
            "matrix": matrix,
            "latest_synthesis": latest_synthesis,
            "latest_fusion": latest_fusion,
            "next_actions": next_actions,
            "primary_views": [{"key": k, "label": label} for k, label in PRIMARY_VIEWS],
            "truth_determined": False,
        }

    def audit_markup(self, *, identity, case_id, markup, route_inventory):
        ident = self._authorize(identity, case_id)
        routes = {(str(m).upper(), str(p)) for m, p in route_inventory}
        checks = {
            "doctype_present": "<!doctype html>" in markup.lower(),
            "language_declared": 'lang="de"' in markup.lower(),
            "viewport_present": 'name="viewport"' in markup.lower(),
            "main_landmark": "<main" in markup.lower(),
            "nav_landmark": "<nav" in markup.lower(),
            "status_region": 'aria-live="polite"' in markup.lower(),
            "keyboard_focus_css": ":focus-visible" in markup,
            "mobile_breakpoint": "@media" in markup and "max-width" in markup,
            "legacy_phase13_brand_removed": "Phase 13 · Simplified AI Investigation Workspace" not in markup,
            "primary_view_count": all(
                f"view={key}" in markup for key, _label in PRIMARY_VIEWS
            ),
            "legacy_workspace_available": "/legacy" in markup,
            "build447_visible": "Build 447" in markup or "447" in markup,
            "truth_boundary_visible": "keine automatische wahrheitsfeststellung" in markup.lower(),
        }
        missing_routes = []
        for route in REQUIRED_READ_ROUTES + REQUIRED_MUTATION_ROUTES:
            if route not in routes:
                missing_routes.append(f"{route[0]} {route[1]}")
        checks["required_routes_registered"] = not missing_routes

        warnings = []
        if missing_routes:
            warnings.append("missing_routes: " + ", ".join(missing_routes))
        if markup.count("<table") > 8:
            warnings.append("high_table_density")
        if markup.count("<details") > 12:
            warnings.append("high_disclosure_density")
        if "onclick=" in markup.lower():
            warnings.append("inline_click_handlers_present")
        if len(markup.encode("utf-8")) > 220000:
            warnings.append("initial_markup_large_over_220kb")

        result = "PASS" if all(checks.values()) else "FAIL"
        row = {
            "audit_id": "uia448_" + secrets.token_hex(10),
            "case_id": str(case_id),
            "result": result,
            "checks_json": _canon(checks),
            "warnings_json": _canon(warnings),
            "route_count": len(routes),
            "markup_sha256": hashlib.sha256(markup.encode("utf-8")).hexdigest(),
            "created_by": str(ident["username"]),
            "created_at": _now(),
        }
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "INSERT INTO ui_audit_448 VALUES(" + ",".join("?" for _ in row) + ")",
            tuple(row.values()),
        )
        self.audit.log(
            "ui_audit_recorded_448",
            "ui_audit_448",
            row["audit_id"],
            str(case_id),
            {
                "result": result,
                "warning_count": len(warnings),
                "route_count": len(routes),
            },
        )
        return {
            **row,
            "checks": checks,
            "warnings": warnings,
            "missing_routes": missing_routes,
        }

    def audit_history(self, case_id, limit=25):
        out = []
        for row in self.db.all(
            "SELECT * FROM ui_audit_448 WHERE case_id=? ORDER BY created_at DESC LIMIT ?",
            (str(case_id), int(limit)),
        ):
            item = dict(row)
            item["checks"] = json.loads(item.pop("checks_json"))
            item["warnings"] = json.loads(item.pop("warnings_json"))
            out.append(item)
        return out

    def verify_integrity(self):
        bad = []
        for row in self.db.all("SELECT * FROM ui_audit_448"):
            item = dict(row)
            if self._rh(item) != item.get("record_hash"):
                bad.append({"audit_id": item.get("audit_id"), "reason": "record_hash_mismatch"})
        return {"build": BUILD, "valid": not bad, "violations": bad}

    def status(self):
        total = int((self.db.one("SELECT COUNT(*) n FROM ui_audit_448") or {}).get("n") or 0)
        failed = int((self.db.one("SELECT COUNT(*) n FROM ui_audit_448 WHERE result='FAIL'") or {}).get("n") or 0)
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "primary_views": [{"key": k, "label": label} for k, label in PRIMARY_VIEWS],
            "ui_audits": total,
            "failed_ui_audits": failed,
            "integrity_valid": self.verify_integrity()["valid"],
            "case_first_workspace": True,
            "responsive_workspace": True,
            "evidence_claim_dossier_flow_visible": True,
            "ai_loop_visible": True,
            "graph_timeline_summary_visible": True,
            "legacy_expert_workspace_preserved": True,
            "ui_route_contract_audited": True,
            "automatic_truth_determination": False,
            "production_release_ready": False,
            "next_build": "449.0",
            "next_hard_checkpoint": "450.0",
        }
