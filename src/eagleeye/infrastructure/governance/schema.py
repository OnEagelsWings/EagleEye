from __future__ import annotations

from typing import Any

from eagleeye_pro.core.database import dumps, now_ts


ROLE_POLICIES = {
    "administrator": {
        "label": "Administrator",
        "permissions": ["*"],
        "rank": 100,
    },
    "lead_investigator": {
        "label": "Lead Investigator",
        "permissions": [
            "case.read", "case.create", "case.update", "case.assign", "research.execute",
            "intake.write", "intake.review", "evidence.capture", "evidence.review",
            "identity.create", "identity.review", "hypothesis.write", "hypothesis.review",
            "report.write", "report.request_review", "report.review", "ai.plan", "ai.execute",
            "ai.review", "comment.write", "lock.manage", "approval.request", "approval.decide",
            "audit.read", "export.request", "persona.create", "persona.manage", "persona.use", "persona.approve", "persona.session.start", "persona.session.use", "persona.session.close", "egress.manage", "egress.approve", "security.review",
        ],
        "rank": 80,
    },
    "investigator": {
        "label": "Investigator",
        "permissions": [
            "case.read", "case.update", "research.execute", "intake.write", "intake.review",
            "evidence.capture", "identity.create", "hypothesis.write", "report.write",
            "report.request_review", "ai.plan", "ai.execute", "ai.review", "comment.write",
            "lock.manage", "approval.request", "persona.create", "persona.manage", "persona.use", "persona.session.start", "persona.session.use", "persona.session.close", "egress.manage",
        ],
        "rank": 60,
    },
    "research_analyst": {
        "label": "Research Analyst",
        "permissions": [
            "case.read", "research.execute", "intake.write", "evidence.capture",
            "identity.create", "hypothesis.write", "report.write", "ai.plan", "comment.write",
            "lock.manage", "approval.request", "persona.create", "persona.use", "persona.session.start", "persona.session.use", "persona.session.close",
        ],
        "rank": 50,
    },
    "evidence_reviewer": {
        "label": "Evidence Reviewer",
        "permissions": [
            "case.read", "intake.review", "evidence.review", "identity.review",
            "hypothesis.review", "report.review", "ai.review", "comment.write",
            "lock.manage", "approval.decide", "audit.read", "persona.approve", "egress.approve", "security.review",
        ],
        "rank": 70,
    },
    "legal_compliance_reviewer": {
        "label": "Legal / Compliance Reviewer",
        "permissions": [
            "case.read", "legal.review", "report.review", "export.approve", "approval.decide",
            "comment.write", "audit.read", "security.review", "persona.approve", "egress.approve",
        ],
        "rank": 75,
    },
    "auditor": {
        "label": "Read-only Auditor",
        "permissions": ["case.read", "audit.read", "comment.read", "report.read", "evidence.read"],
        "rank": 20,
    },
}


def ensure_governance_schema_132(db: Any) -> None:
    db.conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS governance_settings_132(
          settings_id TEXT PRIMARY KEY,
          team_mode_enabled INTEGER NOT NULL DEFAULT 0,
          require_four_eyes INTEGER NOT NULL DEFAULT 1,
          session_timeout_minutes INTEGER NOT NULL DEFAULT 30,
          max_failed_logins INTEGER NOT NULL DEFAULT 5,
          remote_server_mode TEXT NOT NULL DEFAULT 'disabled_loopback_only',
          updated_by TEXT NOT NULL DEFAULT 'system',
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS governance_roles_132(
          role_key TEXT PRIMARY KEY,
          label TEXT NOT NULL,
          permissions_json TEXT NOT NULL,
          rank INTEGER NOT NULL,
          active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS governance_users_132(
          user_id TEXT PRIMARY KEY,
          username TEXT NOT NULL UNIQUE COLLATE NOCASE,
          display_name TEXT NOT NULL,
          role_key TEXT NOT NULL,
          password_hash TEXT NOT NULL DEFAULT '',
          active INTEGER NOT NULL DEFAULT 1,
          failed_attempts INTEGER NOT NULL DEFAULT 0,
          lock_until_epoch INTEGER NOT NULL DEFAULT 0,
          session_generation INTEGER NOT NULL DEFAULT 1,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          last_login_at TEXT NOT NULL DEFAULT '',
          FOREIGN KEY(role_key) REFERENCES governance_roles_132(role_key)
        );
        CREATE TABLE IF NOT EXISTS governance_case_assignments_132(
          assignment_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          user_id TEXT NOT NULL,
          role_key TEXT NOT NULL,
          active INTEGER NOT NULL DEFAULT 1,
          granted_by TEXT NOT NULL,
          granted_at TEXT NOT NULL,
          revoked_by TEXT NOT NULL DEFAULT '',
          revoked_at TEXT NOT NULL DEFAULT '',
          notes TEXT NOT NULL DEFAULT '',
          UNIQUE(case_id,user_id,role_key),
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(user_id) REFERENCES governance_users_132(user_id) ON DELETE CASCADE,
          FOREIGN KEY(role_key) REFERENCES governance_roles_132(role_key)
        );
        CREATE INDEX IF NOT EXISTS idx_governance_assignments_case_132
          ON governance_case_assignments_132(case_id,active,role_key);
        CREATE INDEX IF NOT EXISTS idx_governance_assignments_user_132
          ON governance_case_assignments_132(user_id,active,case_id);
        CREATE TABLE IF NOT EXISTS governance_sessions_132(
          session_id TEXT PRIMARY KEY,
          token_hash TEXT NOT NULL UNIQUE,
          user_id TEXT NOT NULL,
          session_generation INTEGER NOT NULL,
          client_fingerprint TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          last_seen_epoch INTEGER NOT NULL,
          expires_epoch INTEGER NOT NULL,
          revoked INTEGER NOT NULL DEFAULT 0,
          revoked_by TEXT NOT NULL DEFAULT '',
          revoked_at TEXT NOT NULL DEFAULT '',
          FOREIGN KEY(user_id) REFERENCES governance_users_132(user_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_governance_sessions_user_132
          ON governance_sessions_132(user_id,revoked,expires_epoch);
        CREATE TABLE IF NOT EXISTS governance_approval_requests_132(
          request_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          action_key TEXT NOT NULL,
          object_type TEXT NOT NULL,
          object_id TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          payload_sha256 TEXT NOT NULL,
          required_permission TEXT NOT NULL,
          required_approvals INTEGER NOT NULL DEFAULT 1,
          status TEXT NOT NULL DEFAULT 'pending',
          requested_by TEXT NOT NULL,
          request_reason TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          executed_at TEXT NOT NULL DEFAULT '',
          execution_status TEXT NOT NULL DEFAULT 'not_executed',
          execution_error TEXT NOT NULL DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_governance_approvals_case_132
          ON governance_approval_requests_132(case_id,status,created_at DESC);
        CREATE TABLE IF NOT EXISTS governance_approval_decisions_132(
          decision_id TEXT PRIMARY KEY,
          request_id TEXT NOT NULL,
          decision TEXT NOT NULL,
          decided_by TEXT NOT NULL,
          reason TEXT NOT NULL,
          created_at TEXT NOT NULL,
          UNIQUE(request_id,decided_by),
          FOREIGN KEY(request_id) REFERENCES governance_approval_requests_132(request_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS governance_object_locks_132(
          lock_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          object_type TEXT NOT NULL,
          object_id TEXT NOT NULL,
          owner_username TEXT NOT NULL,
          purpose TEXT NOT NULL,
          acquired_at TEXT NOT NULL,
          expires_epoch INTEGER NOT NULL,
          released_at TEXT NOT NULL DEFAULT '',
          released_by TEXT NOT NULL DEFAULT '',
          active INTEGER NOT NULL DEFAULT 1,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_governance_locks_case_132
          ON governance_object_locks_132(case_id,active,expires_epoch);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_governance_active_lock_132
          ON governance_object_locks_132(case_id,object_type,object_id) WHERE active=1;
        CREATE TABLE IF NOT EXISTS governance_comments_132(
          comment_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          object_type TEXT NOT NULL,
          object_id TEXT NOT NULL,
          comment_text TEXT NOT NULL,
          comment_sha256 TEXT NOT NULL,
          author_username TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'active',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_governance_comments_case_132
          ON governance_comments_132(case_id,created_at DESC);
        CREATE TABLE IF NOT EXISTS governance_ai_briefs_132(
          brief_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          trust_state TEXT NOT NULL DEFAULT 'suggestions_only',
          review_status TEXT NOT NULL DEFAULT 'pending',
          content_json TEXT NOT NULL,
          content_sha256 TEXT NOT NULL,
          external_actions INTEGER NOT NULL DEFAULT 0,
          model_key TEXT NOT NULL,
          model_version TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS governance_opsec_events_132(
          event_id TEXT PRIMARY KEY,
          case_id TEXT,
          event_type TEXT NOT NULL,
          actor TEXT NOT NULL,
          object_type TEXT NOT NULL DEFAULT '',
          object_id TEXT NOT NULL DEFAULT '',
          details_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        """
    )
    ts = now_ts()
    db.execute(
        "INSERT OR IGNORE INTO governance_settings_132(settings_id,updated_at) VALUES('global',?)",
        (ts,),
    )
    for role_key, policy in ROLE_POLICIES.items():
        db.execute(
            """INSERT INTO governance_roles_132(role_key,label,permissions_json,rank,active,created_at,updated_at)
               VALUES(?,?,?,?,1,?,?)
               ON CONFLICT(role_key) DO UPDATE SET label=excluded.label,permissions_json=excluded.permissions_json,
                 rank=excluded.rank,active=1,updated_at=excluded.updated_at""",
            (role_key, policy["label"], dumps(policy["permissions"]), int(policy["rank"]), ts, ts),
        )
    db.execute(
        """INSERT OR IGNORE INTO governance_users_132(
             user_id,username,display_name,role_key,password_hash,active,created_by,created_at,updated_at)
           VALUES('govuser_local_owner_132','local-analyst','Lokaler Analyst / Administrator','administrator','',1,'system',?,?)""",
        (ts, ts),
    )
    db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','132.0')")
