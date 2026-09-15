from __future__ import annotations
import json
from typing import Any
from eagleeye.infrastructure.build339.schema import ensure_build339_schema

def ensure_build340_schema(db: Any) -> None:
    ensure_build339_schema(db)
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_freeze_manifests_340(
      freeze_id TEXT PRIMARY KEY, build_id TEXT NOT NULL, file_count INTEGER NOT NULL,
      manifest_json TEXT NOT NULL, manifest_sha256 TEXT NOT NULL, parent_gate_json TEXT NOT NULL,
      probability_status TEXT NOT NULL, external_execution INTEGER NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_extreme_qualification_340(
      qualification_id TEXT PRIMARY KEY, result TEXT NOT NULL, checks_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, freeze_id TEXT NOT NULL, created_by TEXT NOT NULL,
      created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_security_attestations_340(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_hard_training_delta_340(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL,
      review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_security_training_delta_340(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL,
      review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )''')
    db.execute("CREATE TRIGGER IF NOT EXISTS trg_freeze340_no_update BEFORE UPDATE ON phase14_freeze_manifests_340 BEGIN SELECT RAISE(ABORT,'phase14_freeze_manifests_340 immutable'); END")
    db.execute("CREATE TRIGGER IF NOT EXISTS trg_freeze340_no_delete BEFORE DELETE ON phase14_freeze_manifests_340 BEGIN SELECT RAISE(ABORT,'phase14_freeze_manifests_340 immutable'); END")
    hard=[
      ('Phase-14 freeze verifies every critical runtime file by SHA-256 and records build provenance.',['cryptographic_freeze','provenance'],['mutable_release_without_hashes']),
      ('All Phase-14 parent gates 321-339 remain release ready before final freeze.',['full_regression'],['partial_gate_only']),
      ('Production probability remains disabled because Build 336 calibration is not operationally qualified.',['probability_fail_closed'],['fixture_metrics_as_production_probability']),
      ('External execution and real active reconnaissance remain disabled at Phase-14 freeze.',['no_external_execution','no_active_recon'],['freeze_unlocks_network']),
      ('Dossier critical findings remain fail closed under team mode and freeze.',['redteam_gate_preserved'],['release_bypass']),
      ('RBAC, case ACLs, secrets, backups and deployment gates survive final regression.',['operational_hardening_preserved'],['freeze_weakens_controls']),
      ('SQLite integrity and foreign keys are clean at freeze time.',['database_integrity'],['freeze_with_corruption']),
      ('Known limitations are recorded explicitly rather than converted to confidence claims.',['limitations_visible'],['overclaim_readiness']),
    ]
    sec=[
      ('Freeze manifest is append-only and tamper verification is fail closed.',['immutable_freeze'],['mutable_attestation']),
      ('Critical files include runtime, context, schemas/services 321-340, version and launcher.',['critical_surface_covered'],['selective_hashing']),
      ('No cache or compiled bytecode artifacts are required in the release package.',['package_hygiene'],['stale_bytecode']),
      ('No shell, TLS-disable, eval/exec or direct proxy-bypass patterns are introduced by Builds 339-340.',['static_security_scan'],['dangerous_runtime_shortcut']),
      ('Team controls cannot enable Build 336 probabilities or Build 337 external actions.',['cross_gate_integrity'],['role_bypass']),
      ('Backup restore remains isolated from the live workspace.',['restore_isolation'],['live_overwrite']),
      ('Release provenance identifies output package by cryptographic digest.',['slsa_inspired_provenance'],['unbound_artifact']),
      ('No exploit execution, active reconnaissance or automatic network reconfiguration is introduced.',['no_active_recon','no_exploits'],['offensive_counteraction']),
    ]
    for i,(sc,exp,forb) in enumerate(hard):
        difficulty='extreme' if i in (0,2) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_hard_training_delta_340 VALUES(?,?,?,?,?,?,?)',(f'b340-freeze-{i+1:02d}',difficulty,sc,json.dumps(exp,ensure_ascii=False),json.dumps(forb,ensure_ascii=False),'reviewed','build340-extreme-qualification-review'))
    for i,(sc,exp,forb) in enumerate(sec):
        difficulty='extreme' if i in (0,4) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_security_training_delta_340 VALUES(?,?,?,?,?,?,?)',(f'b340-security-{i+1:02d}',difficulty,sc,json.dumps(exp,ensure_ascii=False),json.dumps(forb,ensure_ascii=False),'reviewed','build340-security-freeze-review'))
