from __future__ import annotations
import json
from typing import Any
from eagleeye.infrastructure.build338.schema import ensure_build338_schema


def ensure_build339_schema(db: Any) -> None:
    ensure_build338_schema(db)
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_team_role_events_339(
      event_id TEXT PRIMARY KEY, actor_id TEXT NOT NULL, role_name TEXT NOT NULL,
      effect TEXT NOT NULL, granted_by TEXT NOT NULL, reason TEXT NOT NULL,
      created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_case_acl_events_339(
      event_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, actor_id TEXT NOT NULL,
      permission_name TEXT NOT NULL, effect TEXT NOT NULL, granted_by TEXT NOT NULL,
      reason TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_secret_versions_339(
      secret_id TEXT PRIMARY KEY, secret_label TEXT NOT NULL, version_no INTEGER NOT NULL,
      ciphertext_b64 TEXT NOT NULL, nonce_b64 TEXT NOT NULL, salt_b64 TEXT NOT NULL,
      kdf_name TEXT NOT NULL, cipher_name TEXT NOT NULL, allowed_roles_json TEXT NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_backup_records_339(
      backup_id TEXT PRIMARY KEY, envelope_relpath TEXT NOT NULL, manifest_sha256 TEXT NOT NULL,
      envelope_sha256 TEXT NOT NULL, item_count INTEGER NOT NULL, byte_count INTEGER NOT NULL,
      cipher_name TEXT NOT NULL, kdf_name TEXT NOT NULL, created_by TEXT NOT NULL,
      created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_restore_attestations_339(
      attestation_id TEXT PRIMARY KEY, backup_id TEXT NOT NULL, destination_path TEXT NOT NULL,
      result TEXT NOT NULL, integrity_result TEXT NOT NULL, restored_items INTEGER NOT NULL,
      manifest_verified INTEGER NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
      record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_deployment_profiles_339(
      profile_id TEXT PRIMARY KEY, profile_name TEXT NOT NULL, bind_host TEXT NOT NULL,
      tls_required INTEGER NOT NULL, authentication_required INTEGER NOT NULL,
      relational_backend TEXT NOT NULL, object_backend TEXT NOT NULL, secret_backend TEXT NOT NULL,
      remote_execution INTEGER NOT NULL, validation_status TEXT NOT NULL,
      findings_json TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
      record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_team_attestations_339(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_security_attestations_339(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_hard_training_delta_339(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL,
      review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_security_training_delta_339(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL,
      review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )''')
    for sql in (
      'CREATE INDEX IF NOT EXISTS idx_role339_actor ON phase14_team_role_events_339(actor_id,role_name,created_at)',
      'CREATE INDEX IF NOT EXISTS idx_acl339_case_actor ON phase14_case_acl_events_339(case_id,actor_id,permission_name,created_at)',
      'CREATE UNIQUE INDEX IF NOT EXISTS idx_secret339_label_ver ON phase14_secret_versions_339(secret_label,version_no)',
      'CREATE INDEX IF NOT EXISTS idx_backup339_created ON phase14_backup_records_339(created_at)',
    ): db.execute(sql)
    for table in ('phase14_team_role_events_339','phase14_case_acl_events_339','phase14_secret_versions_339','phase14_backup_records_339'):
        db.execute(f"CREATE TRIGGER IF NOT EXISTS trg_{table}_no_update BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT,'{table} append-only'); END")
        db.execute(f"CREATE TRIGGER IF NOT EXISTS trg_{table}_no_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT,'{table} append-only'); END")
    hard=[
      ('Team authorization requires both an active role and an explicit case ACL for case-scoped work.',['role_plus_case_acl','default_deny'],['role_only_access']),
      ('Revoking a role or case ACL takes effect on the next authorization decision without rewriting history.',['append_only_revocation','immediate_effect'],['stale_authorization_cache']),
      ('Dossier four-eyes review requires a reviewer distinct from the dossier creator.',['four_eyes'],['self_review']),
      ('Secrets are stored only as encrypted versioned envelopes and old versions are not silently reused after rotation.',['versioned_secrets','rotation'],['plaintext_secret','old_secret_reuse']),
      ('Backup restore verifies authenticated encryption, manifest hashes and SQLite integrity before attesting success.',['backup_integrity','restore_verification'],['blind_restore']),
      ('Remote deployment profiles fail closed unless TLS, authentication, server relational storage and external secret management are declared.',['deployment_fail_closed'],['insecure_remote_profile']),
      ('Portable local mode remains supported and does not silently enable remote services.',['local_first'],['silent_remote_enable']),
      ('Build 338 red-team and Build 336 probability gates remain authoritative in team mode.',['analytic_gates_preserved'],['team_role_bypasses_analytic_gate']),
    ]
    sec=[
      ('RBAC is default deny and case ACLs are cumulative with roles.',['least_privilege','default_deny'],['implicit_allow']),
      ('Secret ciphertext uses authenticated encryption and passphrases are never persisted.',['aead','no_passphrase_storage'],['plaintext_key_storage']),
      ('Backup envelopes are authenticated and tamper detection is fail closed.',['backup_tamper_detection'],['best_effort_decrypt']),
      ('Restore targets an isolated destination and does not overwrite the live workspace automatically.',['isolated_restore'],['automatic_live_overwrite']),
      ('Deployment validation never starts or connects remote infrastructure.',['blueprint_only'],['remote_execution']),
      ('Case permissions cannot cross case boundaries.',['case_isolation'],['cross_case_access']),
      ('Reviewer and investigator separation is enforced for dossier approval.',['four_eyes'],['self_approval']),
      ('No active reconnaissance, exploit execution or automatic network reconfiguration is introduced.',['no_active_recon','no_exploits'],['offensive_counteraction']),
    ]
    for i,(sc,exp,forb) in enumerate(hard):
        difficulty='extreme' if i in (2,4) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_hard_training_delta_339 VALUES(?,?,?,?,?,?,?)',(f'b339-team-{i+1:02d}',difficulty,sc,json.dumps(exp,ensure_ascii=False),json.dumps(forb,ensure_ascii=False),'reviewed','build339-team-hardening-review'))
    for i,(sc,exp,forb) in enumerate(sec):
        difficulty='extreme' if i in (1,2) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_security_training_delta_339 VALUES(?,?,?,?,?,?,?)',(f'b339-security-{i+1:02d}',difficulty,sc,json.dumps(exp,ensure_ascii=False),json.dumps(forb,ensure_ascii=False),'reviewed','build339-security-review'))
