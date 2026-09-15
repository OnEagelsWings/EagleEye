from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping, Sequence

BUILD = "393.0"
POLICY_ID = "phase17.investigator-dialogue-challenge.v393"
CONFIRM_PROPOSAL_REVIEW = "REVIEW CHALLENGE PROPOSAL"
CONFIRM_KERNEL_ADMISSION = "ADMIT CHALLENGE TO KERNEL"

_ALLOWED_MODES = {
    "weakest_assumption",
    "counter_argument",
    "falsification_test",
    "blind_spot",
    "alternative_explanation",
    "source_independence_attack",
    "plan_red_team",
    "general_challenge",
}
_ALLOWED_PROPOSAL_DISPOSITIONS = {
    "approve_for_manual_revision",
    "revise_requested",
    "rejected",
    "deferred",
}
_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    raw = value if isinstance(value, (bytes, bytearray)) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _j(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value or ""))
    except Exception:
        return default


def _stable_id(prefix: str, value: Any, n: int = 24) -> str:
    return f"{prefix}_{_sha(value)[:n]}"


class InvestigatorDialogueChallenge393:
    """Review-first dialogue/challenge layer over the Build-392 reasoning workspace.

    This is deliberately not an autonomous truth engine. It exposes a deterministic,
    provenance-bound challenge surface for an investigator chat/workspace. It may
    identify weak assumptions, counterarguments, falsification needs, blind spots,
    alternative-explanation prompts, source-independence concerns and plan risks.

    It never mutates Build-391 claims/hypotheses or Build-392 plans automatically,
    never grants GO/LIVE authority, never promotes evidence and never performs network
    activity. Revision proposals require analyst review and remain manual-change tasks.
    """

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        reasoning392: Any,
        kernel112: Any,
        governance: Any,
        actor: str = "local-analyst",
    ) -> None:
        self.db = db
        self.audit = audit
        self.reasoning392 = reasoning392
        self.kernel112 = kernel112
        self.governance = governance
        self.actor = actor
        self._init_schema()

    def _init_schema(self) -> None:
        self.db.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS investigator_dialogue_session_393 (
              session_id TEXT PRIMARY KEY,
              case_id TEXT NOT NULL,
              workspace_id TEXT NOT NULL,
              source_workspace_hash TEXT NOT NULL,
              state TEXT NOT NULL,
              turn_count INTEGER NOT NULL,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              UNIQUE(case_id,workspace_id,source_workspace_hash)
            );
            CREATE INDEX IF NOT EXISTS idx_investigator_dialogue_session_393_case
              ON investigator_dialogue_session_393(case_id,updated_at);

            CREATE TABLE IF NOT EXISTS investigator_dialogue_turn_393 (
              turn_id TEXT PRIMARY KEY,
              session_id TEXT NOT NULL,
              case_id TEXT NOT NULL,
              ordinal INTEGER NOT NULL,
              challenge_mode TEXT NOT NULL,
              prompt_text TEXT NOT NULL,
              target_type TEXT NOT NULL,
              target_id TEXT NOT NULL,
              response_json TEXT NOT NULL,
              source_refs_json TEXT NOT NULL,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              UNIQUE(session_id,ordinal),
              FOREIGN KEY(session_id) REFERENCES investigator_dialogue_session_393(session_id)
            );
            CREATE INDEX IF NOT EXISTS idx_investigator_dialogue_turn_393_session
              ON investigator_dialogue_turn_393(session_id,ordinal);

            CREATE TABLE IF NOT EXISTS challenge_revision_proposal_393 (
              proposal_id TEXT PRIMARY KEY,
              turn_id TEXT NOT NULL,
              session_id TEXT NOT NULL,
              case_id TEXT NOT NULL,
              proposal_type TEXT NOT NULL,
              target_type TEXT NOT NULL,
              target_id TEXT NOT NULL,
              title TEXT NOT NULL,
              proposed_change_json TEXT NOT NULL,
              rationale TEXT NOT NULL,
              status TEXT NOT NULL,
              requires_human_review INTEGER NOT NULL,
              execution_authority INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              UNIQUE(turn_id,proposal_id),
              FOREIGN KEY(turn_id) REFERENCES investigator_dialogue_turn_393(turn_id)
            );
            CREATE INDEX IF NOT EXISTS idx_challenge_revision_proposal_393_case
              ON challenge_revision_proposal_393(case_id,status,proposal_type);

            CREATE TABLE IF NOT EXISTS challenge_revision_review_393 (
              review_id TEXT PRIMARY KEY,
              proposal_id TEXT NOT NULL UNIQUE,
              case_id TEXT NOT NULL,
              disposition TEXT NOT NULL,
              rationale TEXT NOT NULL,
              reviewed_by TEXT NOT NULL,
              reviewed_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              FOREIGN KEY(proposal_id) REFERENCES challenge_revision_proposal_393(proposal_id)
            );

            CREATE TABLE IF NOT EXISTS dialogue_kernel_bridge_393 (
              bridge_id TEXT PRIMARY KEY,
              turn_id TEXT NOT NULL UNIQUE,
              case_id TEXT NOT NULL,
              kernel_entry_id TEXT NOT NULL,
              source_turn_hash TEXT NOT NULL,
              bridge_state TEXT NOT NULL,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              FOREIGN KEY(turn_id) REFERENCES investigator_dialogue_turn_393(turn_id)
            );
            """
        )
        self.db.conn.commit()

    def _authorize(self, identity: Mapping[str, Any], case_id: str, capability: str, object_id: str) -> None:
        self.governance.authorize(
            dict(identity),
            case_id=case_id,
            capability=capability,
            object_type="phase17_investigator_dialogue_v393",
            object_id=object_id,
        )

    @staticmethod
    def _workspace_hash(workspace: Mapping[str, Any]) -> str:
        return _sha({
            "workspace_id": workspace.get("workspace_id"),
            "record_hash": workspace.get("record_hash"),
            "source_snapshot_hash": workspace.get("source_snapshot_hash"),
            "coverage_snapshot_hash": workspace.get("coverage_snapshot_hash"),
            "reasoning_state": workspace.get("reasoning_state"),
            "issues": [str(x.get("record_hash") or "") for x in workspace.get("issues") or []],
            "arguments": [str(x.get("record_hash") or "") for x in workspace.get("arguments") or []],
            "plan_id": workspace.get("plan_id"),
        })

    def _session_row(self, case_id: str, session_id: str) -> dict[str, Any]:
        row = self.db.one(
            "SELECT * FROM investigator_dialogue_session_393 WHERE case_id=? AND session_id=?",
            (case_id, session_id),
        )
        if not row:
            raise KeyError(session_id)
        return dict(row)

    def _turn_row(self, case_id: str, turn_id: str) -> dict[str, Any]:
        row = self.db.one(
            "SELECT * FROM investigator_dialogue_turn_393 WHERE case_id=? AND turn_id=?",
            (case_id, turn_id),
        )
        if not row:
            raise KeyError(turn_id)
        return dict(row)

    def _proposal_row(self, case_id: str, proposal_id: str) -> dict[str, Any]:
        row = self.db.one(
            "SELECT * FROM challenge_revision_proposal_393 WHERE case_id=? AND proposal_id=?",
            (case_id, proposal_id),
        )
        if not row:
            raise KeyError(proposal_id)
        return dict(row)

    def create_session(self, *, case_id: str, workspace_id: str, identity: Mapping[str, Any]) -> dict[str, Any]:
        self._authorize(identity, case_id, "dossier.write", workspace_id)
        verify = self.reasoning392.verify_workspace(case_id=case_id, workspace_id=workspace_id)
        if not bool(verify.get("valid")):
            raise ValueError("reasoning workspace integrity verification failed")
        if bool(verify.get("stale")):
            raise ValueError("reasoning workspace is stale; create a fresh Build-392 workspace before challenge dialogue")
        workspace = self.reasoning392.workspace(case_id=case_id, workspace_id=workspace_id)
        whash = self._workspace_hash(workspace)
        existing = self.db.one(
            "SELECT session_id FROM investigator_dialogue_session_393 WHERE case_id=? AND workspace_id=? AND source_workspace_hash=?",
            (case_id, workspace_id, whash),
        )
        if existing:
            return self.session(case_id=case_id, session_id=str(existing["session_id"]), identity=identity)
        actor = str(identity.get("username") or self.actor)[:120]
        now = _now()
        row = {
            "session_id": _stable_id("dialog393", {"case_id": case_id, "workspace_id": workspace_id, "workspace_hash": whash}),
            "case_id": case_id,
            "workspace_id": workspace_id,
            "source_workspace_hash": whash,
            "state": "active_review_dialogue",
            "turn_count": 0,
            "created_by": actor,
            "created_at": now,
            "updated_at": now,
        }
        self.db.execute(
            "INSERT INTO investigator_dialogue_session_393(session_id,case_id,workspace_id,source_workspace_hash,state,turn_count,created_by,created_at,updated_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (*row.values(), _sha(row)),
        )
        self.audit.log("dialogue_session", "investigator_dialogue_session_393", row["session_id"], case_id, {
            "workspace_id": workspace_id,
            "truth_determined": False,
            "execution_authority": False,
        })
        return self.session(case_id=case_id, session_id=row["session_id"], identity=identity)

    def session(self, *, case_id: str, session_id: str, identity: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if identity is not None:
            self._authorize(identity, case_id, "case.read", session_id)
        row = self._session_row(case_id, session_id)
        turns = []
        for item in self.db.all(
            "SELECT * FROM investigator_dialogue_turn_393 WHERE session_id=? ORDER BY ordinal",
            (session_id,),
        ):
            t = dict(item)
            turns.append({
                **t,
                "response": dict(_j(t.get("response_json"), {}) or {}),
                "source_refs": list(_j(t.get("source_refs_json"), []) or []),
                "proposals": self._turn_proposals(str(t["turn_id"])),
            })
        return {
            **row,
            "turns": turns,
            "truth_determined": False,
            "probability_assigned": False,
            "automatic_upstream_mutation": False,
            "execution_authority": False,
        }

    def _turn_proposals(self, turn_id: str) -> list[dict[str, Any]]:
        out = []
        for item in self.db.all(
            "SELECT * FROM challenge_revision_proposal_393 WHERE turn_id=? ORDER BY created_at,proposal_id",
            (turn_id,),
        ):
            p = dict(item)
            review = self.db.one("SELECT * FROM challenge_revision_review_393 WHERE proposal_id=?", (p["proposal_id"],))
            out.append({
                **p,
                "proposed_change": dict(_j(p.get("proposed_change_json"), {}) or {}),
                "requires_human_review": bool(p.get("requires_human_review")),
                "execution_authority": bool(p.get("execution_authority")),
                "review": dict(review) if review else None,
            })
        return out

    @staticmethod
    def _auto_mode(prompt: str) -> str:
        p = prompt.casefold()
        if any(x in p for x in ("schwäch", "weakest", "weak assumption", "annahme")):
            return "weakest_assumption"
        if any(x in p for x in ("falsif", "widerleg", "disconfirm", "refute")):
            return "falsification_test"
        if any(x in p for x in ("alternative", "andere erklär", "competing explanation")):
            return "alternative_explanation"
        if any(x in p for x in ("überseh", "blind spot", "missed", "übersehen")):
            return "blind_spot"
        if any(x in p for x in ("quelle", "source", "independ", "mirror", "spiegel")):
            return "source_independence_attack"
        if any(x in p for x in ("plan", "next step", "nächste schritt", "red team")):
            return "plan_red_team"
        if any(x in p for x in ("gegen", "argue against", "counter", "kritisi", "challenge")):
            return "counter_argument"
        return "general_challenge"

    @staticmethod
    def _claim_map(workspace: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
        return {str(x.get("claim_id") or ""): dict(x) for x in (workspace.get("source_snapshot") or {}).get("claims") or []}

    @staticmethod
    def _hyp_map(workspace: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
        return {str(x.get("hypothesis_id") or ""): dict(x) for x in (workspace.get("source_snapshot") or {}).get("hypotheses") or []}

    @staticmethod
    def _plan_map(plan: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
        if not plan:
            return {}
        return {str(x.get("action_id") or ""): dict(x) for x in plan.get("actions") or []}

    def _resolve_target(
        self,
        workspace: Mapping[str, Any],
        *,
        target_type: str,
        target_id: str,
    ) -> tuple[str, str, Mapping[str, Any] | None]:
        ttype = str(target_type or "").strip().casefold()
        tid = str(target_id or "").strip()
        claims = self._claim_map(workspace)
        hyps = self._hyp_map(workspace)
        plan = self.reasoning392.plan(case_id=str(workspace["case_id"]), plan_id=str(workspace.get("plan_id") or "")) if workspace.get("plan_id") else None
        actions = self._plan_map(plan)
        if not ttype and not tid:
            return "workspace", str(workspace["workspace_id"]), workspace
        if ttype == "claim" and tid in claims:
            return ttype, tid, claims[tid]
        if ttype == "hypothesis" and tid in hyps:
            return ttype, tid, hyps[tid]
        if ttype == "reasoning_plan" and plan and tid == str(plan.get("plan_id") or ""):
            return ttype, tid, plan
        if ttype == "plan_action" and tid in actions:
            return ttype, tid, actions[tid]
        raise ValueError("challenge target is not part of the source Build-392 workspace")

    @staticmethod
    def _issue_refs(issue: Mapping[str, Any]) -> list[dict[str, Any]]:
        return [dict(x) for x in issue.get("object_refs") or []]

    @staticmethod
    def _challenge_point(title: str, rationale: str, refs: Sequence[Mapping[str, Any]], category: str) -> dict[str, Any]:
        return {
            "category": category,
            "statement": str(title)[:600],
            "rationale": str(rationale)[:4000],
            "object_refs": [dict(x) for x in refs],
        }

    def _derive_response(
        self,
        workspace: Mapping[str, Any],
        *,
        mode: str,
        prompt: str,
        target_type: str,
        target_id: str,
        target: Mapping[str, Any] | None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        issues = [dict(x) for x in workspace.get("issues") or []]
        issues.sort(key=lambda x: (_SEVERITY_RANK.get(str(x.get("severity") or "low"), 9), str(x.get("issue_type") or ""), str(x.get("issue_id") or "")))
        claims = self._claim_map(workspace)
        hyps = self._hyp_map(workspace)
        plan = self.reasoning392.plan(case_id=str(workspace["case_id"]), plan_id=str(workspace.get("plan_id") or "")) if workspace.get("plan_id") else None

        points: list[dict[str, Any]] = []
        questions: list[str] = []
        proposals: list[dict[str, Any]] = []
        source_refs: list[dict[str, Any]] = []

        def add_issue(issue: Mapping[str, Any], category: str = "recorded_issue") -> None:
            refs = self._issue_refs(issue)
            points.append(self._challenge_point(str(issue.get("title") or issue.get("issue_type") or "Issue"), str(issue.get("rationale") or ""), refs, category))
            source_refs.extend(refs)

        if mode == "weakest_assumption":
            if issues:
                add_issue(issues[0], "weakest_recorded_assumption")
                questions.append("Welche Beobachtung oder unabhängige Quelle würde diese Schwachstelle am stärksten entkräften?")
            else:
                points.append(self._challenge_point("Keine dokumentierte Schwachstelle im aktuellen Workspace", "Das Fehlen eines Issues ist keine Bestätigung der Schlussfolgerung. Eine externe Red-Team-Prüfung kann weiterhin sinnvoll sein.", [{"object_type": "workspace", "object_id": workspace["workspace_id"]}], "absence_of_recorded_issue"))
                questions.append("Welche stillschweigende Annahme ist für die aktuelle Interpretation notwendig, aber noch nicht als Claim oder Hypothese dokumentiert?")
            proposals.append({
                "proposal_type": "reasoning_revision",
                "target_type": target_type,
                "target_id": target_id,
                "title": "Schwächste Annahme explizit dokumentieren",
                "proposed_change": {"action": "document_assumption_and_test", "mode": mode},
                "rationale": "Eine kritische Annahme sollte als überprüfbarer Punkt im Ermittlungsarbeitsstand sichtbar sein, nicht implizit bleiben.",
            })

        elif mode == "counter_argument":
            if target_type == "hypothesis" and target:
                hid = target_id
                linked_claims = [str(x.get("claim_id") or "") for x in target.get("claim_links") or []]
                related = [i for i in issues if any(str(r.get("object_id") or "") in linked_claims + [hid] for r in self._issue_refs(i))]
                for issue in related[:6]:
                    add_issue(issue, "counter_argument_basis")
                if not related:
                    points.append(self._challenge_point("Kein explizites Gegenargument im Workspace dokumentiert", "Das ist eine Erkenntnislücke, keine Unterstützung der Hypothese. Es sollte gezielt nach disconfirming evidence gesucht werden.", [{"object_type": "hypothesis", "object_id": hid}], "counterevidence_gap"))
                questions.append("Welche alternative Ursache könnte dieselben verknüpften Claims erklären, ohne diese Hypothese vorauszusetzen?")
                questions.append("Welche vorhandene Beobachtung wäre mit der Hypothese am schwersten vereinbar?")
            elif target_type == "claim" and target:
                related = [i for i in issues if any(str(r.get("object_id") or "") == target_id for r in self._issue_refs(i))]
                for issue in related[:6]:
                    add_issue(issue, "counter_argument_basis")
                questions.append("Welche unabhängige Quelle könnte den Claim direkt widersprechen oder seinen Geltungsbereich einschränken?")
            else:
                for issue in [i for i in issues if i.get("issue_type") in {"counterevidence_conflict", "contested_claim", "source_independence_gap", "independent_support_gap"}][:6]:
                    add_issue(issue, "counter_argument_basis")
                questions.append("Welche Schlussfolgerung im aktuellen Workspace würde bei Wegfall der stärksten Support-Gruppe zuerst zusammenbrechen?")
            proposals.append({
                "proposal_type": "challenge_followup",
                "target_type": target_type,
                "target_id": target_id,
                "title": "Gegenargument als expliziten Testpunkt aufnehmen",
                "proposed_change": {"action": "add_counterargument_test", "mode": mode},
                "rationale": "Gegenargumente sollen nicht nur diskutiert, sondern als überprüfbare analytische Verpflichtung erhalten bleiben.",
            })

        elif mode == "falsification_test":
            if target_type == "hypothesis" and target:
                test_plan = str(target.get("test_plan") or "").strip()
                points.append(self._challenge_point("Vorhandener Hypothesentestplan", test_plan or "Für diese Hypothese ist kein konkreter Testplan im Workspace dokumentiert.", [{"object_type": "hypothesis", "object_id": target_id}], "existing_test_plan"))
                questions.extend([
                    "Welches beobachtbare Ergebnis würde die Hypothese klar schwächen oder unhaltbar machen?",
                    "Welche Datenquelle kann dieses Ergebnis unabhängig vom bisherigen Support prüfen?",
                    "Welche Zeit-/Scope-Bedingung muss vor dem Test festgelegt werden, damit ein negatives Ergebnis interpretierbar bleibt?",
                ])
                proposals.append({
                    "proposal_type": "hypothesis_test_revision",
                    "target_type": "hypothesis",
                    "target_id": target_id,
                    "title": "Falsifikationskriterium ergänzen",
                    "proposed_change": {"action": "add_explicit_disconfirming_criterion", "existing_test_plan": test_plan},
                    "rationale": "Ein Hypothesentest sollte vor Durchführung festhalten, welches beobachtbare Ergebnis gegen die Hypothese spricht.",
                })
            else:
                points.append(self._challenge_point("Falsifikationsziel benötigt eine konkrete Hypothese", "Der Workspace kann allgemein herausgefordert werden, aber ein belastbares Falsifikationskriterium sollte an eine konkrete Hypothese gebunden sein.", [{"object_type": target_type, "object_id": target_id}], "target_scope"))
                questions.append("Welche Hypothese soll mit einem vorab definierten disconfirming criterion geprüft werden?")

        elif mode == "blind_spot":
            blind_types = {"open_question", "research_gap", "source_independence_gap", "independent_support_gap", "evidence_gap", "hypothesis_test_gap"}
            selected = [i for i in issues if str(i.get("issue_type") or "") in blind_types]
            for issue in selected[:8]:
                add_issue(issue, "blind_spot_signal")
            if not selected:
                points.append(self._challenge_point("Keine expliziten Blind-Spot-Signale im Workspace", "Der aktuelle Reasoning Workspace enthält keine offenen Gap-Issues. Das bedeutet nicht, dass keine unbekannten Lücken existieren.", [{"object_type": "workspace", "object_id": workspace["workspace_id"]}], "blind_spot_absence"))
            questions.extend([
                "Welche relevante Quelle oder Jurisdiktion ist im aktuellen Coverage-Snapshot nicht vertreten?",
                "Welche Gegenhypothese würde mit denselben Beobachtungen ebenfalls vereinbar sein?",
                "Welche zeitliche oder semantische Annahme wurde bisher nicht explizit getestet?",
            ])
            proposals.append({
                "proposal_type": "research_gap_revision",
                "target_type": "workspace",
                "target_id": str(workspace["workspace_id"]),
                "title": "Blind-Spot-Review als eigenen Research Gap führen",
                "proposed_change": {"action": "record_blind_spot_review", "source_issue_ids": [str(x.get("issue_id") or "") for x in selected[:20]]},
                "rationale": "Übersehene Bereiche sollten als sichtbare Research Gaps geführt werden, nicht nur als implizite Unsicherheit.",
            })

        elif mode == "alternative_explanation":
            refs = [{"object_type": target_type, "object_id": target_id}]
            if target_type == "hypothesis" and target:
                linked = [str(x.get("claim_id") or "") for x in target.get("claim_links") or []]
                points.append(self._challenge_point("Alternative Erklärung erforderlich", "Eine konkurrierende Erklärung sollte dieselben verknüpften Claims erklären können, ohne die aktuelle Hypothese vorauszusetzen.", refs + [{"object_type": "claim", "object_id": x} for x in linked], "alternative_model_requirement"))
                questions.append("Kann ein zeitlicher, definitorischer oder Source-Scope-Unterschied dieselben Beobachtungen erklären?")
                proposals.append({
                    "proposal_type": "alternative_hypothesis_prompt",
                    "target_type": "hypothesis",
                    "target_id": target_id,
                    "title": "Konkurrierende Hypothese formulieren",
                    "proposed_change": {"action": "draft_competing_hypothesis", "linked_claim_ids": linked, "must_explain_same_observations": True},
                    "rationale": "Die Engine erfindet keine konkurrierende Erklärung; sie erzeugt einen reviewpflichtigen Auftrag, eine solche Hypothese explizit zu formulieren und gegenzutesten.",
                })
            elif target_type == "claim" and target:
                points.append(self._challenge_point("Geltungsbereich des Claims prüfen", "Eine alternative Erklärung kann darin bestehen, dass die Beobachtung nur für einen anderen Zeitraum, Scope oder definitorischen Kontext gilt.", refs, "scope_alternative"))
                questions.append("Welche Scope-/Zeitbedingung könnte erklären, warum unterstützende und widersprechende Beobachtungen gleichzeitig bestehen?")
            else:
                points.append(self._challenge_point("Alternative-Erklärungs-Review auf Workspace-Ebene", "Wähle eine konkrete Hypothese oder einen Claim, damit eine konkurrierende Erklärung an denselben Beobachtungen geprüft werden kann.", refs, "target_scope"))

        elif mode == "source_independence_attack":
            selected = [i for i in issues if str(i.get("issue_type") or "") in {"source_independence_gap", "independent_support_gap"}]
            for issue in selected[:8]:
                add_issue(issue, "source_independence_risk")
            for claim in claims.values():
                unresolved = int(claim.get("unresolved_observations") or 0)
                if unresolved:
                    points.append(self._challenge_point(
                        f"Unresolved source independence for claim {claim.get('claim_id')}",
                        f"{unresolved} observation(s) are not assigned to a countable independent source group.",
                        [{"object_type": "claim", "object_id": claim.get("claim_id")}],
                        "source_independence_risk",
                    ))
            questions.extend([
                "Welche Support-Treffer stammen tatsächlich aus derselben ursprünglichen Quelle oder einem Mirror/Archiv?",
                "Welche unabhängige Primärquelle könnte eine derzeit unresolved observation ersetzen oder bestätigen?",
            ])
            proposals.append({
                "proposal_type": "source_independence_review",
                "target_type": "workspace",
                "target_id": str(workspace["workspace_id"]),
                "title": "Source-Independence-Lücken priorisiert reviewen",
                "proposed_change": {"action": "review_unresolved_source_families", "affected_claim_ids": [c["claim_id"] for c in claims.values() if int(c.get("unresolved_observations") or 0) > 0]},
                "rationale": "Nicht geklärte Herkunft darf die Zahl unabhängiger Bestätigungen nicht erhöhen.",
            })

        elif mode == "plan_red_team":
            if plan:
                for action in plan.get("actions") or []:
                    refs = list(action.get("object_refs") or [])
                    category = "external_authority_boundary" if bool(action.get("requires_external_execution")) else "analysis_plan_dependency"
                    points.append(self._challenge_point(str(action.get("title") or action.get("action_type") or "Plan action"), str(action.get("rationale") or ""), refs, category))
                    source_refs.extend(refs)
                questions.extend([
                    "Welche Planaktion hängt von einer noch ungeklärten Annahme oder Source-Independence-Lücke ab?",
                    "Welche externe Aktion sollte erst nach einem zusätzlichen Review-Gate stattfinden?",
                    "Welche Planaktion kann lokal/analytisch erledigt werden, bevor neue externe Autorität beantragt wird?",
                ])
                proposals.append({
                    "proposal_type": "plan_revision",
                    "target_type": "reasoning_plan",
                    "target_id": str(plan.get("plan_id") or ""),
                    "title": "Reasoning Plan nach Red-Team-Prüfung revidieren",
                    "proposed_change": {"action": "manual_plan_revision_required", "preserve_go_boundaries": True},
                    "rationale": "Eine Red-Team-Prüfung darf Prioritäten oder Reihenfolge in Frage stellen, aber keine externe Autorität selbst erzeugen.",
                })
            else:
                points.append(self._challenge_point("Kein Build-392-Plan vorhanden", "Für diesen Workspace wurde noch kein Next-Investigation-Plan erzeugt. Plan-Red-Teaming ist daher noch nicht möglich.", [{"object_type": "workspace", "object_id": workspace["workspace_id"]}], "missing_plan"))
                questions.append("Soll zuerst ein reviewpflichtiger Build-392-Ermittlungsplan erzeugt werden?")

        else:  # general_challenge
            for issue in issues[:8]:
                add_issue(issue, "general_challenge_basis")
            if not issues:
                points.append(self._challenge_point("Keine offenen Issues dokumentiert", "Der Workspace ist formal ohne offene Issues, bleibt aber ein analytischer Arbeitsstand und keine Wahrheitsfeststellung.", [{"object_type": "workspace", "object_id": workspace["workspace_id"]}], "general_review"))
            questions.extend([
                "Welche Schlussfolgerung hängt am stärksten von einer einzelnen Quelle oder Annahme ab?",
                "Welche Beobachtung würde die aktuelle Arbeitshypothese am stärksten verändern?",
                "Welche relevante Alternative ist noch nicht als Hypothese oder Research Gap dokumentiert?",
            ])
            proposals.append({
                "proposal_type": "reasoning_revision",
                "target_type": "workspace",
                "target_id": str(workspace["workspace_id"]),
                "title": "Allgemeine Challenge-Ergebnisse manuell in den Reasoning Workspace überführen",
                "proposed_change": {"action": "manual_reasoning_revision", "mode": mode},
                "rationale": "Challenge-Ergebnisse bleiben Vorschläge und müssen vor jeder Änderung upstream überprüft werden.",
            })

        # Preserve deterministic ref ordering and remove exact duplicates.
        dedup_refs: list[dict[str, Any]] = []
        seen: set[str] = set()
        for ref in source_refs + [{"object_type": target_type, "object_id": target_id}]:
            if not str(ref.get("object_id") or ""):
                continue
            key = _sha(ref)
            if key not in seen:
                seen.add(key)
                dedup_refs.append(dict(ref))

        response = {
            "mode": mode,
            "target_type": target_type,
            "target_id": target_id,
            "prompt": prompt,
            "challenge_points": points[:20],
            "questions": questions[:20],
            "source_refs": dedup_refs[:200],
            "epistemic_contract": {
                "challenge": "review aid, not a factual finding",
                "claim": "candidate/reviewed analytical proposition, not automatically fact",
                "hypothesis": "hypothesis_not_fact",
                "absence_of_counterevidence": "not confirmation",
                "revision_proposal": "manual-change proposal only",
            },
            "truth_determined": False,
            "probability_assigned": False,
            "automatic_upstream_mutation": False,
            "automatic_go_issuance": False,
            "automatic_live_confirmation": False,
            "execution_authority": False,
            "network_requests_created": 0,
        }
        return response, proposals, dedup_refs

    def challenge(
        self,
        *,
        case_id: str,
        session_id: str,
        prompt: str,
        identity: Mapping[str, Any],
        mode: str = "",
        target_type: str = "",
        target_id: str = "",
    ) -> dict[str, Any]:
        self._authorize(identity, case_id, "dossier.write", session_id)
        text = str(prompt or "").strip()
        if len(text) < 3:
            raise ValueError("challenge prompt must contain at least three characters")
        if len(text) > 4000:
            raise ValueError("challenge prompt exceeds 4000 characters")
        session = self._session_row(case_id, session_id)
        verify = self.reasoning392.verify_workspace(case_id=case_id, workspace_id=str(session["workspace_id"]))
        if not bool(verify.get("valid")):
            raise ValueError("source reasoning workspace integrity verification failed")
        if bool(verify.get("stale")):
            raise ValueError("source reasoning workspace is stale; refresh before continuing dialogue")
        workspace = self.reasoning392.workspace(case_id=case_id, workspace_id=str(session["workspace_id"]))
        if self._workspace_hash(workspace) != str(session.get("source_workspace_hash") or ""):
            raise ValueError("dialogue session workspace binding mismatch")
        chosen = str(mode or "").strip().casefold() or self._auto_mode(text)
        if chosen not in _ALLOWED_MODES:
            raise ValueError(f"unsupported challenge mode: {chosen}")
        ttype, tid, target = self._resolve_target(workspace, target_type=target_type, target_id=target_id)
        response, proposals, source_refs = self._derive_response(workspace, mode=chosen, prompt=text, target_type=ttype, target_id=tid, target=target)
        actor = str(identity.get("username") or self.actor)[:120]
        now = _now()
        ordinal = int(session.get("turn_count") or 0) + 1
        turn = {
            "turn_id": _stable_id("turn393", {"session_id": session_id, "ordinal": ordinal, "prompt": text, "mode": chosen, "target_type": ttype, "target_id": tid}),
            "session_id": session_id,
            "case_id": case_id,
            "ordinal": ordinal,
            "challenge_mode": chosen,
            "prompt_text": text,
            "target_type": ttype,
            "target_id": tid,
            "response_json": _canon(response),
            "source_refs_json": _canon(source_refs),
            "created_by": actor,
            "created_at": now,
        }
        with self.db.transaction(immediate=True):
            self.db.execute(
                "INSERT INTO investigator_dialogue_turn_393(turn_id,session_id,case_id,ordinal,challenge_mode,prompt_text,target_type,target_id,response_json,source_refs_json,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (*turn.values(), _sha(turn)),
            )
            for proposal in proposals:
                pbody = {
                    "proposal_id": _stable_id("proposal393", {"turn_id": turn["turn_id"], **proposal}),
                    "turn_id": turn["turn_id"],
                    "session_id": session_id,
                    "case_id": case_id,
                    "proposal_type": str(proposal["proposal_type"]),
                    "target_type": str(proposal["target_type"]),
                    "target_id": str(proposal["target_id"]),
                    "title": str(proposal["title"])[:500],
                    "proposed_change_json": _canon(dict(proposal["proposed_change"])),
                    "rationale": str(proposal["rationale"])[:4000],
                    "status": "proposal_needs_review",
                    "requires_human_review": 1,
                    "execution_authority": 0,
                    "created_at": now,
                }
                self.db.execute(
                    "INSERT INTO challenge_revision_proposal_393(proposal_id,turn_id,session_id,case_id,proposal_type,target_type,target_id,title,proposed_change_json,rationale,status,requires_human_review,execution_authority,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (*pbody.values(), _sha(pbody)),
                )
            updated = {k: session[k] for k in session if k != "record_hash"}
            updated.update({"turn_count": ordinal, "updated_at": now})
            self.db.execute(
                "UPDATE investigator_dialogue_session_393 SET turn_count=?,updated_at=?,record_hash=? WHERE session_id=?",
                (ordinal, now, _sha(updated), session_id),
            )
        self.audit.log("challenge_turn", "investigator_dialogue_turn_393", turn["turn_id"], case_id, {
            "mode": chosen,
            "target_type": ttype,
            "target_id": tid,
            "revision_proposals": len(proposals),
            "truth_determined": False,
            "execution_authority": False,
        })
        return self.turn(case_id=case_id, turn_id=turn["turn_id"], identity=identity)

    def turn(self, *, case_id: str, turn_id: str, identity: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if identity is not None:
            self._authorize(identity, case_id, "case.read", turn_id)
        row = self._turn_row(case_id, turn_id)
        return {
            **row,
            "response": dict(_j(row.get("response_json"), {}) or {}),
            "source_refs": list(_j(row.get("source_refs_json"), []) or []),
            "proposals": self._turn_proposals(turn_id),
            "truth_determined": False,
            "probability_assigned": False,
            "automatic_upstream_mutation": False,
            "execution_authority": False,
        }

    def review_proposal(
        self,
        *,
        case_id: str,
        proposal_id: str,
        identity: Mapping[str, Any],
        disposition: str,
        rationale: str,
        confirmation: str,
    ) -> dict[str, Any]:
        if str(confirmation or "").strip().upper() != CONFIRM_PROPOSAL_REVIEW:
            raise PermissionError(f"explicit confirmation {CONFIRM_PROPOSAL_REVIEW} required")
        self._authorize(identity, case_id, "dossier.write", proposal_id)
        disp = str(disposition or "").strip().casefold()
        if disp not in _ALLOWED_PROPOSAL_DISPOSITIONS:
            raise ValueError("unsupported challenge proposal disposition")
        reason = str(rationale or "").strip()
        if len(reason) < 12:
            raise ValueError("substantive challenge-proposal review rationale required")
        row = self._proposal_row(case_id, proposal_id)
        if str(row.get("status") or "") != "proposal_needs_review":
            raise PermissionError("challenge proposal already reviewed or not reviewable")
        actor = str(identity.get("username") or self.actor)[:120]
        now = _now()
        review = {
            "review_id": _stable_id("proprev393", {"proposal_id": proposal_id, "disposition": disp, "reviewer": actor}),
            "proposal_id": proposal_id,
            "case_id": case_id,
            "disposition": disp,
            "rationale": reason[:4000],
            "reviewed_by": actor,
            "reviewed_at": now,
        }
        status = "reviewed_for_manual_revision" if disp == "approve_for_manual_revision" else disp
        updated = {k: row[k] for k in row if k != "record_hash"}
        updated["status"] = status
        with self.db.transaction(immediate=True):
            self.db.execute(
                "INSERT INTO challenge_revision_review_393(review_id,proposal_id,case_id,disposition,rationale,reviewed_by,reviewed_at,record_hash) VALUES(?,?,?,?,?,?,?,?)",
                (*review.values(), _sha(review)),
            )
            self.db.execute(
                "UPDATE challenge_revision_proposal_393 SET status=?,record_hash=? WHERE proposal_id=?",
                (status, _sha(updated), proposal_id),
            )
        self.audit.log("challenge_proposal_reviewed", "challenge_revision_proposal_393", proposal_id, case_id, {
            "disposition": disp,
            "automatic_upstream_mutation": False,
            "execution_authority": False,
        })
        return self.proposal(case_id=case_id, proposal_id=proposal_id, identity=identity)

    def proposal(self, *, case_id: str, proposal_id: str, identity: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if identity is not None:
            self._authorize(identity, case_id, "case.read", proposal_id)
        row = self._proposal_row(case_id, proposal_id)
        review = self.db.one("SELECT * FROM challenge_revision_review_393 WHERE proposal_id=?", (proposal_id,))
        return {
            **row,
            "proposed_change": dict(_j(row.get("proposed_change_json"), {}) or {}),
            "requires_human_review": bool(row.get("requires_human_review")),
            "execution_authority": bool(row.get("execution_authority")),
            "review": dict(review) if review else None,
            "automatic_upstream_mutation": False,
        }

    def admit_turn_to_kernel(
        self,
        *,
        case_id: str,
        turn_id: str,
        identity: Mapping[str, Any],
        confirmation: str,
    ) -> dict[str, Any]:
        if str(confirmation or "").strip().upper() != CONFIRM_KERNEL_ADMISSION:
            raise PermissionError(f"explicit confirmation {CONFIRM_KERNEL_ADMISSION} required")
        self._authorize(identity, case_id, "dossier.write", turn_id)
        verify = self.verify_turn(case_id=case_id, turn_id=turn_id)
        if not bool(verify.get("valid")):
            raise PermissionError("challenge turn integrity verification failed")
        existing = self.db.one("SELECT * FROM dialogue_kernel_bridge_393 WHERE turn_id=?", (turn_id,))
        if existing:
            return dict(existing) | {"execution_authority": False, "automatic_go_issuance": False}
        turn = self.turn(case_id=case_id, turn_id=turn_id)
        actor = str(identity.get("username") or self.actor)[:120]
        body = _canon({
            "epistemic_status": "challenge_review_not_factual_finding",
            "turn_id": turn_id,
            "challenge_mode": turn["challenge_mode"],
            "target_type": turn["target_type"],
            "target_id": turn["target_id"],
            "challenge_points": (turn.get("response") or {}).get("challenge_points") or [],
            "questions": (turn.get("response") or {}).get("questions") or [],
            "proposal_ids": [str(x.get("proposal_id") or "") for x in turn.get("proposals") or []],
            "truth_determined": False,
            "probability_assigned": False,
            "execution_authority": False,
        })
        related = [str(x.get("object_id") or "") for x in turn.get("source_refs") or [] if str(x.get("object_id") or "")]
        kernel_entry_id = self.kernel112.note(case_id, actor, "phase17_challenge_dialogue", "Reviewed Phase-17 challenge turn", body, list(dict.fromkeys(related))[:200])
        now = _now()
        bridge = {
            "bridge_id": _stable_id("kbridge393", {"case_id": case_id, "turn_id": turn_id, "kernel_entry_id": kernel_entry_id}),
            "turn_id": turn_id,
            "case_id": case_id,
            "kernel_entry_id": kernel_entry_id,
            "source_turn_hash": str(turn.get("record_hash") or ""),
            "bridge_state": "kernel_notebook_challenge_review",
            "created_by": actor,
            "created_at": now,
        }
        self.db.execute(
            "INSERT INTO dialogue_kernel_bridge_393(bridge_id,turn_id,case_id,kernel_entry_id,source_turn_hash,bridge_state,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?)",
            (*bridge.values(), _sha(bridge)),
        )
        self.audit.log("bridge", "dialogue_kernel_bridge_393", bridge["bridge_id"], case_id, {
            "turn_id": turn_id,
            "execution_authority": False,
            "automatic_go_issuance": False,
        })
        return {**bridge, "record_hash": _sha(bridge), "execution_authority": False, "automatic_go_issuance": False}

    def ai_dialogue_feed(self, *, case_id: str, identity: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if identity is not None:
            self._authorize(identity, case_id, "case.read", case_id)
        row = self.db.one(
            "SELECT session_id FROM investigator_dialogue_session_393 WHERE case_id=? ORDER BY updated_at DESC,session_id DESC LIMIT 1",
            (case_id,),
        )
        session = self.session(case_id=case_id, session_id=str(row["session_id"])) if row else None
        return {
            "case_id": case_id,
            "build": BUILD,
            "latest_dialogue": session,
            "supported_challenge_modes": sorted(_ALLOWED_MODES),
            "dialogue_is_review_aid": True,
            "counterevidence_preserved": True,
            "epistemic_layers_preserved": True,
            "truth_determined": False,
            "probability_assigned": False,
            "automatic_upstream_mutation": False,
            "automatic_go_issuance": False,
            "automatic_live_confirmation": False,
            "execution_authority": False,
            "network_requests_created": 0,
        }

    def verify_session(self, *, case_id: str, session_id: str) -> dict[str, Any]:
        row = self._session_row(case_id, session_id)
        body = {k: row[k] for k in row if k != "record_hash"}
        row_valid = str(row.get("record_hash") or "") == _sha(body)
        workspace_verify = self.reasoning392.verify_workspace(case_id=case_id, workspace_id=str(row["workspace_id"]))
        workspace = self.reasoning392.workspace(case_id=case_id, workspace_id=str(row["workspace_id"]))
        binding_valid = self._workspace_hash(workspace) == str(row.get("source_workspace_hash") or "")
        return {
            "session_id": session_id,
            "row_hash_valid": row_valid,
            "workspace_valid": bool(workspace_verify.get("valid")),
            "workspace_stale": bool(workspace_verify.get("stale")),
            "workspace_binding_valid": binding_valid,
            "valid": row_valid and bool(workspace_verify.get("valid")) and not bool(workspace_verify.get("stale")) and binding_valid,
        }

    def verify_turn(self, *, case_id: str, turn_id: str) -> dict[str, Any]:
        row = self._turn_row(case_id, turn_id)
        body = {k: row[k] for k in row if k != "record_hash"}
        row_valid = str(row.get("record_hash") or "") == _sha(body)
        proposal_valid = True
        for proposal in self.db.all("SELECT * FROM challenge_revision_proposal_393 WHERE turn_id=?", (turn_id,)):
            pbody = {k: proposal[k] for k in proposal if k != "record_hash"}
            proposal_valid = proposal_valid and str(proposal.get("record_hash") or "") == _sha(pbody)
        session_valid = self.verify_session(case_id=case_id, session_id=str(row["session_id"]))
        return {
            "turn_id": turn_id,
            "row_hash_valid": row_valid,
            "proposal_hashes_valid": proposal_valid,
            "session_valid": bool(session_valid.get("valid")),
            "valid": row_valid and proposal_valid and bool(session_valid.get("valid")),
        }

    def verify_proposal(self, *, case_id: str, proposal_id: str) -> dict[str, Any]:
        row = self._proposal_row(case_id, proposal_id)
        body = {k: row[k] for k in row if k != "record_hash"}
        row_valid = str(row.get("record_hash") or "") == _sha(body)
        review = self.db.one("SELECT * FROM challenge_revision_review_393 WHERE proposal_id=?", (proposal_id,))
        review_valid = True
        if review:
            rbody = {k: review[k] for k in review if k != "record_hash"}
            review_valid = str(review.get("record_hash") or "") == _sha(rbody)
        return {"proposal_id": proposal_id, "row_hash_valid": row_valid, "review_hash_valid": review_valid, "valid": row_valid and review_valid}

    def status(self) -> dict[str, Any]:
        s = self.db.one("SELECT COUNT(*) total FROM investigator_dialogue_session_393") or {}
        t = self.db.one("SELECT COUNT(*) total FROM investigator_dialogue_turn_393") or {}
        p = self.db.one("SELECT COUNT(*) total,SUM(CASE WHEN status='reviewed_for_manual_revision' THEN 1 ELSE 0 END) reviewed FROM challenge_revision_proposal_393") or {}
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "investigator_dialogue": True,
            "challenge_engine": True,
            "free_text_mode_router": True,
            "weakest_assumption_challenge": True,
            "counter_argument_challenge": True,
            "falsification_challenge": True,
            "blind_spot_challenge": True,
            "alternative_explanation_prompt": True,
            "source_independence_challenge": True,
            "plan_red_team": True,
            "revision_proposals": True,
            "human_revision_review_required": True,
            "kernel_notebook_challenge_bridge": True,
            "epistemic_layers_preserved": True,
            "truth_probability": False,
            "automatic_truth_acceptance": False,
            "automatic_upstream_mutation": False,
            "automatic_claim_revision": False,
            "automatic_hypothesis_revision": False,
            "automatic_plan_revision": False,
            "automatic_evidence_promotion": False,
            "automatic_go_issuance": False,
            "automatic_live_confirmation": False,
            "execution_authority": False,
            "direct_network_fetch": False,
            "automatic_identity_merge": False,
            "sessions": int(s.get("total") or 0),
            "turns": int(t.get("total") or 0),
            "revision_proposals_total": int(p.get("total") or 0),
            "revision_proposals_reviewed": int(p.get("reviewed") or 0),
        }
