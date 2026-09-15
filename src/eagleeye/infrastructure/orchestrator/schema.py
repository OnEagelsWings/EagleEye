from __future__ import annotations

import hashlib

from typing import Any


AGENTS_127 = (
    (
        "research_planner",
        "1.0",
        "Research Planner",
        "Plant begrenzte, fallgebundene Rechercheschritte und benennt Informationslücken.",
        '["case_inventory","research_gap_analysis","query_direction_suggestions"]',
        '["autonomous_network","identity_confirmation","evidence_promotion","guilt_or_risk_scoring"]',
    ),
    (
        "source_analyst",
        "1.0",
        "Source Analyst",
        "Ordnet gespeicherte Quellen nach Herkunft, Aktualität und Reviewbedarf.",
        '["source_inventory","host_clustering","review_prioritization"]',
        '["truth_certification","automatic_source_reliability_claim","external_fetch"]',
    ),
    (
        "verification_analyst",
        "1.0",
        "Verification Analyst",
        "Erzeugt Gegenprüfungsfragen und trennt bestätigende von widersprechenden Belegen.",
        '["verification_questions","counter_evidence_plan","claim_support_matrix"]',
        '["final_verdict","automatic_claim_confirmation","external_fetch"]',
    ),
    (
        "entity_analyst",
        "1.0",
        "Entity Analyst",
        "Strukturiert offene Identitäts- und Alias-Hypothesen ohne automatische Zusammenführung.",
        '["identity_gap_analysis","alias_hypotheses","merge_review_queue"]',
        '["automatic_merge","identity_confirmation","biometric_identification"]',
    ),
    (
        "timeline_analyst",
        "1.0",
        "Timeline Analyst",
        "Analysiert gespeicherte Zeitangaben, Lücken und Konflikte als Vorschläge.",
        '["timeline_inventory","date_gap_analysis","temporal_conflict_questions"]',
        '["automatic_event_promotion","causality_claim","external_fetch"]',
    ),
    (
        "contradiction_analyst",
        "1.0",
        "Contradiction Analyst",
        "Priorisiert offene Widersprüche und alternative Erklärungen.",
        '["contradiction_inventory","alternative_explanations","red_team_questions"]',
        '["guilt_assessment","risk_scoring","automatic_resolution"]',
    ),
    (
        "case_scribe",
        "1.0",
        "Case Scribe",
        "Erstellt eine quellengebundene Arbeitszusammenfassung mit klaren Unsicherheiten.",
        '["case_summary","source_reference_map","limitations_draft"]',
        '["unreferenced_factual_assertion","final_report_release","evidence_promotion"]',
    ),
)


def ensure_orchestrator_schema_127(db: Any) -> None:
    db.conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS agent_registry_127(
          agent_key TEXT PRIMARY KEY,
          agent_version TEXT NOT NULL,
          role_name TEXT NOT NULL,
          description TEXT NOT NULL,
          capabilities_json TEXT NOT NULL DEFAULT '[]',
          prohibited_json TEXT NOT NULL DEFAULT '[]',
          execution_mode TEXT NOT NULL DEFAULT 'local_deterministic',
          prompt_version TEXT NOT NULL DEFAULT '1.0',
          prompt_template_sha256 TEXT NOT NULL DEFAULT '',
          enabled INTEGER NOT NULL DEFAULT 1,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS orchestrator_policy_127(
          policy_id TEXT PRIMARY KEY,
          external_network_default TEXT NOT NULL DEFAULT 'blocked',
          output_trust_state TEXT NOT NULL DEFAULT 'suggestions_only',
          require_plan_approval INTEGER NOT NULL DEFAULT 1,
          require_output_review INTEGER NOT NULL DEFAULT 1,
          max_tasks_hard INTEGER NOT NULL DEFAULT 12,
          max_runtime_seconds_hard INTEGER NOT NULL DEFAULT 300,
          max_external_actions_hard INTEGER NOT NULL DEFAULT 0,
          prompt_injection_mode TEXT NOT NULL DEFAULT 'quarantine',
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS orchestration_plans_127(
          plan_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          target_id TEXT,
          objective TEXT NOT NULL,
          objective_sha256 TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'draft',
          max_tasks INTEGER NOT NULL,
          max_runtime_seconds INTEGER NOT NULL,
          max_external_actions INTEGER NOT NULL DEFAULT 0,
          task_count INTEGER NOT NULL DEFAULT 0,
          approval_required INTEGER NOT NULL DEFAULT 1,
          injection_flags_json TEXT NOT NULL DEFAULT '[]',
          created_by TEXT NOT NULL,
          approved_by TEXT NOT NULL DEFAULT '',
          approved_at TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS idx_orch_plans127_case
          ON orchestration_plans_127(case_id,created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_orch_plans127_status
          ON orchestration_plans_127(status,updated_at DESC);

        CREATE TABLE IF NOT EXISTS orchestration_tasks_127(
          task_id TEXT PRIMARY KEY,
          plan_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          sequence_no INTEGER NOT NULL,
          agent_key TEXT NOT NULL,
          task_type TEXT NOT NULL,
          instruction TEXT NOT NULL,
          scope_json TEXT NOT NULL DEFAULT '{}',
          source_refs_json TEXT NOT NULL DEFAULT '[]',
          status TEXT NOT NULL DEFAULT 'planned',
          requires_human_approval INTEGER NOT NULL DEFAULT 0,
          external_action INTEGER NOT NULL DEFAULT 0,
          budget_cost INTEGER NOT NULL DEFAULT 1,
          result_json TEXT NOT NULL DEFAULT '{}',
          error_text TEXT NOT NULL DEFAULT '',
          started_at TEXT NOT NULL DEFAULT '',
          completed_at TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY(plan_id) REFERENCES orchestration_plans_127(plan_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(agent_key) REFERENCES agent_registry_127(agent_key) ON DELETE RESTRICT,
          UNIQUE(plan_id,sequence_no)
        );
        CREATE INDEX IF NOT EXISTS idx_orch_tasks127_plan
          ON orchestration_tasks_127(plan_id,sequence_no);
        CREATE INDEX IF NOT EXISTS idx_orch_tasks127_status
          ON orchestration_tasks_127(case_id,status,updated_at DESC);

        CREATE TABLE IF NOT EXISTS orchestration_approvals_127(
          approval_id TEXT PRIMARY KEY,
          plan_id TEXT NOT NULL,
          task_id TEXT,
          case_id TEXT NOT NULL,
          approval_type TEXT NOT NULL,
          decision TEXT NOT NULL,
          reason TEXT NOT NULL DEFAULT '',
          actor TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(plan_id) REFERENCES orchestration_plans_127(plan_id) ON DELETE CASCADE,
          FOREIGN KEY(task_id) REFERENCES orchestration_tasks_127(task_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_orch_approvals127_plan
          ON orchestration_approvals_127(plan_id,created_at DESC);

        CREATE TABLE IF NOT EXISTS orchestration_runs_127(
          run_id TEXT PRIMARY KEY,
          plan_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          status TEXT NOT NULL,
          task_budget INTEGER NOT NULL,
          attempt_no INTEGER NOT NULL DEFAULT 1,
          max_attempts INTEGER NOT NULL DEFAULT 2,
          model_key TEXT NOT NULL DEFAULT 'deterministic_local_127',
          model_version TEXT NOT NULL DEFAULT '1.0',
          prompt_bundle_sha256 TEXT NOT NULL DEFAULT '',
          tasks_attempted INTEGER NOT NULL DEFAULT 0,
          tasks_completed INTEGER NOT NULL DEFAULT 0,
          external_actions INTEGER NOT NULL DEFAULT 0,
          runtime_ms INTEGER NOT NULL DEFAULT 0,
          report_json TEXT NOT NULL DEFAULT '{}',
          started_by TEXT NOT NULL,
          started_at TEXT NOT NULL,
          completed_at TEXT NOT NULL DEFAULT '',
          FOREIGN KEY(plan_id) REFERENCES orchestration_plans_127(plan_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_orch_runs127_case
          ON orchestration_runs_127(case_id,started_at DESC);

        CREATE TABLE IF NOT EXISTS orchestration_outputs_127(
          output_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          task_id TEXT NOT NULL,
          plan_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          agent_key TEXT NOT NULL,
          output_type TEXT NOT NULL,
          content_json TEXT NOT NULL,
          source_refs_json TEXT NOT NULL DEFAULT '[]',
          trust_state TEXT NOT NULL DEFAULT 'suggestions_only',
          review_status TEXT NOT NULL DEFAULT 'pending',
          reviewed_by TEXT NOT NULL DEFAULT '',
          reviewed_at TEXT NOT NULL DEFAULT '',
          review_reason TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          FOREIGN KEY(run_id) REFERENCES orchestration_runs_127(run_id) ON DELETE CASCADE,
          FOREIGN KEY(task_id) REFERENCES orchestration_tasks_127(task_id) ON DELETE CASCADE,
          FOREIGN KEY(plan_id) REFERENCES orchestration_plans_127(plan_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(agent_key) REFERENCES agent_registry_127(agent_key) ON DELETE RESTRICT
        );
        CREATE INDEX IF NOT EXISTS idx_orch_outputs127_case
          ON orchestration_outputs_127(case_id,created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_orch_outputs127_review
          ON orchestration_outputs_127(case_id,review_status,created_at DESC);

        CREATE TABLE IF NOT EXISTS orchestration_injection_events_127(
          event_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          plan_id TEXT,
          source_kind TEXT NOT NULL,
          source_id TEXT NOT NULL DEFAULT '',
          flags_json TEXT NOT NULL DEFAULT '[]',
          action TEXT NOT NULL,
          content_sha256 TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(plan_id) REFERENCES orchestration_plans_127(plan_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_orch_injection127_case
          ON orchestration_injection_events_127(case_id,created_at DESC);
        """
    )
    now_expr = "strftime('%Y-%m-%dT%H:%M:%SZ','now')"
    db.conn.execute(
        f"""INSERT OR IGNORE INTO orchestrator_policy_127(
          policy_id,external_network_default,output_trust_state,require_plan_approval,
          require_output_review,max_tasks_hard,max_runtime_seconds_hard,
          max_external_actions_hard,prompt_injection_mode,updated_at)
          VALUES('default','blocked','suggestions_only',1,1,12,300,0,'quarantine',{now_expr})"""
    )
    for agent in AGENTS_127:
        db.conn.execute(
            f"""INSERT OR IGNORE INTO agent_registry_127(
              agent_key,agent_version,role_name,description,capabilities_json,prohibited_json,
              execution_mode,prompt_version,prompt_template_sha256,enabled,updated_at)
              VALUES(?,?,?,?,?,?,'local_deterministic','1.0',?,1,{now_expr})""",
            (*agent, hashlib.sha256((agent[0] + '|' + agent[2] + '|' + agent[3]).encode('utf-8')).hexdigest()),
        )
    db.conn.commit()
