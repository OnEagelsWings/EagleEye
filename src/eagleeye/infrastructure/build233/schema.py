from __future__ import annotations
from typing import Any

SCHEMA_233 = r'''
CREATE TABLE IF NOT EXISTS qualification_campaigns_233 (
  campaign_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  suite_id TEXT NOT NULL,
  title TEXT NOT NULL,
  baseline_build TEXT NOT NULL DEFAULT '223.0',
  candidate_build TEXT NOT NULL DEFAULT '232.0',
  baseline_arm_code TEXT NOT NULL UNIQUE,
  candidate_arm_code TEXT NOT NULL UNIQUE,
  protocol_version INTEGER NOT NULL DEFAULT 1,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(suite_id) REFERENCES qualification_suites_232(suite_id) ON DELETE CASCADE,
  UNIQUE(case_id,suite_id,protocol_version)
);
CREATE INDEX IF NOT EXISTS idx_campaign233_case ON qualification_campaigns_233(case_id,created_at);

CREATE TABLE IF NOT EXISTS qualification_manifests_233 (
  manifest_id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL UNIQUE,
  case_id TEXT NOT NULL,
  environment_json TEXT NOT NULL,
  environment_sha256 TEXT NOT NULL,
  suite_sha256 TEXT NOT NULL,
  protocol_notes TEXT NOT NULL,
  network_policy TEXT NOT NULL DEFAULT 'no_autonomous_network',
  execution_policy TEXT NOT NULL DEFAULT 'human_governed',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(campaign_id) REFERENCES qualification_campaigns_233(campaign_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  CHECK(network_policy='no_autonomous_network'),
  CHECK(execution_policy='human_governed')
);

CREATE TABLE IF NOT EXISTS qualification_arm_links_233 (
  arm_link_id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  arm_code TEXT NOT NULL,
  arm_role TEXT NOT NULL,
  trial_id TEXT NOT NULL UNIQUE,
  submitted_by TEXT NOT NULL,
  submitted_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(campaign_id) REFERENCES qualification_campaigns_233(campaign_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(trial_id) REFERENCES qualification_trials_232(trial_id),
  CHECK(arm_role IN ('baseline','candidate')),
  UNIQUE(campaign_id,arm_role)
);
CREATE INDEX IF NOT EXISTS idx_arm233_campaign ON qualification_arm_links_233(campaign_id,arm_role);

CREATE TABLE IF NOT EXISTS qualification_cycles_233 (
  cycle_id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  cycle_number INTEGER NOT NULL,
  baseline_scorecard_id TEXT NOT NULL,
  candidate_scorecard_id TEXT NOT NULL,
  comparison_id TEXT NOT NULL UNIQUE,
  failed_gates_json TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL,
  synthetic_qualification INTEGER NOT NULL DEFAULT 1,
  real_world_claim_allowed INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(campaign_id) REFERENCES qualification_campaigns_233(campaign_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(baseline_scorecard_id) REFERENCES qualification_scorecards_232(scorecard_id),
  FOREIGN KEY(candidate_scorecard_id) REFERENCES qualification_scorecards_232(scorecard_id),
  FOREIGN KEY(comparison_id) REFERENCES qualification_comparisons_232(comparison_id),
  CHECK(status IN ('pass_pending_review','needs_remediation','incomplete')),
  CHECK(synthetic_qualification=1),
  CHECK(real_world_claim_allowed=0),
  UNIQUE(campaign_id,cycle_number)
);
CREATE INDEX IF NOT EXISTS idx_cycle233_campaign ON qualification_cycles_233(campaign_id,cycle_number);

CREATE TABLE IF NOT EXISTS remediation_tickets_233 (
  ticket_id TEXT PRIMARY KEY,
  cycle_id TEXT NOT NULL,
  campaign_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  metric_key TEXT NOT NULL,
  severity TEXT NOT NULL,
  title TEXT NOT NULL,
  finding_json TEXT NOT NULL,
  impacted_cases_json TEXT NOT NULL DEFAULT '[]',
  recommended_action TEXT NOT NULL,
  target_build TEXT NOT NULL DEFAULT '234.0',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(cycle_id) REFERENCES qualification_cycles_233(cycle_id) ON DELETE CASCADE,
  FOREIGN KEY(campaign_id) REFERENCES qualification_campaigns_233(campaign_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  CHECK(severity IN ('critical','high','medium','low')),
  UNIQUE(cycle_id,metric_key)
);
CREATE INDEX IF NOT EXISTS idx_ticket233_campaign ON remediation_tickets_233(campaign_id,severity,created_at);

CREATE TABLE IF NOT EXISTS remediation_ticket_actions_233 (
  action_id TEXT PRIMARY KEY,
  ticket_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  status TEXT NOT NULL,
  note TEXT NOT NULL,
  actor TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(ticket_id) REFERENCES remediation_tickets_233(ticket_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  CHECK(status IN ('open','accepted_for_234','in_progress','resolved','wont_fix'))
);
CREATE INDEX IF NOT EXISTS idx_ticket_action233_ticket ON remediation_ticket_actions_233(ticket_id,created_at);

CREATE TABLE IF NOT EXISTS qualification_cycle_reviews_233 (
  cycle_review_id TEXT PRIMARY KEY,
  cycle_id TEXT NOT NULL UNIQUE,
  campaign_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  decision TEXT NOT NULL,
  rationale TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  reviewed_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(cycle_id) REFERENCES qualification_cycles_233(cycle_id) ON DELETE CASCADE,
  FOREIGN KEY(campaign_id) REFERENCES qualification_campaigns_233(campaign_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  CHECK(decision IN ('phase8_qualified','needs_remediation','rejected'))
);

CREATE TABLE IF NOT EXISTS build233_events (
  event_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,
  actor TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  previous_hash TEXT NOT NULL,
  event_hash TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_events233_case ON build233_events(case_id,created_at,event_id);

CREATE TRIGGER IF NOT EXISTS trg_campaign233_no_update BEFORE UPDATE ON qualification_campaigns_233 BEGIN SELECT RAISE(ABORT,'qualification_campaigns_233 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_campaign233_no_delete BEFORE DELETE ON qualification_campaigns_233 BEGIN SELECT RAISE(ABORT,'qualification_campaigns_233 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_manifest233_no_update BEFORE UPDATE ON qualification_manifests_233 BEGIN SELECT RAISE(ABORT,'qualification_manifests_233 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_manifest233_no_delete BEFORE DELETE ON qualification_manifests_233 BEGIN SELECT RAISE(ABORT,'qualification_manifests_233 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_armlink233_no_update BEFORE UPDATE ON qualification_arm_links_233 BEGIN SELECT RAISE(ABORT,'qualification_arm_links_233 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_armlink233_no_delete BEFORE DELETE ON qualification_arm_links_233 BEGIN SELECT RAISE(ABORT,'qualification_arm_links_233 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_cycle233_no_update BEFORE UPDATE ON qualification_cycles_233 BEGIN SELECT RAISE(ABORT,'qualification_cycles_233 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_cycle233_no_delete BEFORE DELETE ON qualification_cycles_233 BEGIN SELECT RAISE(ABORT,'qualification_cycles_233 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_ticket233_no_update BEFORE UPDATE ON remediation_tickets_233 BEGIN SELECT RAISE(ABORT,'remediation_tickets_233 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_ticket233_no_delete BEFORE DELETE ON remediation_tickets_233 BEGIN SELECT RAISE(ABORT,'remediation_tickets_233 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_ticketaction233_no_update BEFORE UPDATE ON remediation_ticket_actions_233 BEGIN SELECT RAISE(ABORT,'remediation_ticket_actions_233 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_ticketaction233_no_delete BEFORE DELETE ON remediation_ticket_actions_233 BEGIN SELECT RAISE(ABORT,'remediation_ticket_actions_233 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_cyclereview233_no_update BEFORE UPDATE ON qualification_cycle_reviews_233 BEGIN SELECT RAISE(ABORT,'qualification_cycle_reviews_233 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_cyclereview233_no_delete BEFORE DELETE ON qualification_cycle_reviews_233 BEGIN SELECT RAISE(ABORT,'qualification_cycle_reviews_233 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_events233_no_update BEFORE UPDATE ON build233_events BEGIN SELECT RAISE(ABORT,'build233_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_events233_no_delete BEFORE DELETE ON build233_events BEGIN SELECT RAISE(ABORT,'build233_events is immutable'); END;
'''


def ensure_build233_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_233)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','233.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','233.0')")
    db.conn.commit()
