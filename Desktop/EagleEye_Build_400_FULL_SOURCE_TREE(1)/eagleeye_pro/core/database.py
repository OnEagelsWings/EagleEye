from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional

from eagleeye_pro.version import BUILD, SCHEMA_VERSION


def now_ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def loads(value: Optional[str], default: Any = None) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


_PROCESS_BOOTSTRAP_LOCK = threading.RLock()


@contextmanager
def _file_lock(path: Path, timeout: float = 30.0) -> Iterator[None]:
    """Cross-process lock used only while bootstrapping/migrating a database."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"0")
        handle.flush()
    deadline = time.monotonic() + timeout
    locked = False
    try:
        while not locked:
            try:
                if os.name == "nt":
                    import msvcrt

                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except (OSError, BlockingIOError):
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"database bootstrap lock timed out: {path}")
                time.sleep(0.05)
        yield
    finally:
        if locked:
            try:
                if os.name == "nt":
                    import msvcrt

                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        handle.close()


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._transaction_depth = 0
        self.conn = sqlite3.connect(str(self.path), timeout=30.0, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA busy_timeout=30000")

    @contextmanager
    def bootstrap_lock(self, timeout: float = 30.0) -> Iterator[None]:
        with _PROCESS_BOOTSTRAP_LOCK:
            with _file_lock(Path(str(self.path) + ".bootstrap.lock"), timeout=timeout):
                yield

    @property
    def in_transaction(self) -> bool:
        return self._transaction_depth > 0

    @contextmanager
    def transaction(self, *, immediate: bool = False) -> Iterator["Database"]:
        """Serialize a unit of work and commit or roll it back as one operation.

        Nested calls use SQLite savepoints. ``immediate=True`` obtains the write
        reservation before a terminal review decision is evaluated.
        """
        with self._lock:
            outermost = self._transaction_depth == 0
            savepoint = f"ee_sp_{self._transaction_depth + 1}"
            if outermost:
                self.conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            else:
                self.conn.execute(f"SAVEPOINT {savepoint}")
            self._transaction_depth += 1
            try:
                yield self
            except BaseException:
                self._transaction_depth -= 1
                if outermost:
                    self.conn.rollback()
                else:
                    self.conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    self.conn.execute(f"RELEASE SAVEPOINT {savepoint}")
                raise
            else:
                self._transaction_depth -= 1
                if outermost:
                    self.conn.commit()
                else:
                    self.conn.execute(f"RELEASE SAVEPOINT {savepoint}")

    def close(self) -> None:
        with self._lock:
            self.conn.close()

    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            try:
                cur = self.conn.execute(sql, tuple(params))
                if not self.in_transaction:
                    self.conn.commit()
                return cur
            except BaseException:
                # A failed standalone SQLite statement (for example an immutable-table
                # trigger) may leave the connection inside an implicit transaction.
                # Roll it back so later, unrelated case operations remain usable.
                if not self.in_transaction:
                    self.conn.rollback()
                raise

    def one(self, sql: str, params: Iterable[Any] = ()) -> Optional[Dict[str, Any]]:
        with self._lock:
            cur = self.conn.execute(sql, tuple(params))
            row = cur.fetchone()
            return dict(row) if row else None

    def all(self, sql: str, params: Iterable[Any] = ()) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self.conn.execute(sql, tuple(params))
            return [dict(r) for r in cur.fetchall()]

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        with self._lock:
            existing = {row[1] for row in self.conn.execute(f"PRAGMA table_info({table})").fetchall()}
            if column not in existing:
                self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
                if not self.in_transaction:
                    self.conn.commit()

    def init_schema(self) -> None:
        with self._lock:
            self.conn.executescript('''
        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit_events (
          event_id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, actor TEXT NOT NULL, case_id TEXT,
          action TEXT NOT NULL, object_type TEXT NOT NULL, object_id TEXT, details_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS cases (
          case_id TEXT PRIMARY KEY, title TEXT NOT NULL, client TEXT, purpose TEXT NOT NULL,
          legal_basis TEXT NOT NULL, jurisdiction TEXT DEFAULT 'DE/EU', risk_level TEXT DEFAULT 'medium',
          status TEXT DEFAULT 'draft', retention_until TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS legal_reviews (
          review_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, purpose TEXT NOT NULL, legal_basis TEXT NOT NULL,
          necessity TEXT NOT NULL, balancing TEXT NOT NULL, source_scope_json TEXT NOT NULL,
          prohibited_scope_json TEXT NOT NULL, special_categories INTEGER DEFAULT 0, minor_data INTEGER DEFAULT 0,
          criminal_data INTEGER DEFAULT 0, approved INTEGER DEFAULT 0, review_level TEXT DEFAULT 'analyst',
          created_at TEXT NOT NULL, reviewer TEXT, notes TEXT,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS targets (
          target_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, name TEXT NOT NULL,
          aliases_json TEXT NOT NULL, emails_json TEXT NOT NULL, usernames_json TEXT NOT NULL,
          locations_json TEXT NOT NULL, companies_json TEXT NOT NULL, domains_json TEXT NOT NULL,
          notes TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS search_tasks (
          task_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT,
          category TEXT NOT NULL, query TEXT NOT NULL, engine TEXT NOT NULL, url TEXT NOT NULL,
          status TEXT DEFAULT 'planned', created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS search_packages (
          package_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT,
          package_key TEXT NOT NULL, name TEXT NOT NULL, objective TEXT NOT NULL,
          status TEXT DEFAULT 'active', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS search_package_tasks (
          package_id TEXT NOT NULL, task_id TEXT NOT NULL, created_at TEXT NOT NULL,
          PRIMARY KEY(package_id, task_id),
          FOREIGN KEY(package_id) REFERENCES search_packages(package_id) ON DELETE CASCADE,
          FOREIGN KEY(task_id) REFERENCES search_tasks(task_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS source_captures (
          capture_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, task_id TEXT, review_item_id TEXT,
          title TEXT NOT NULL, url TEXT NOT NULL, host TEXT DEFAULT '', snippet TEXT DEFAULT '', query TEXT DEFAULT '',
          storage_path TEXT NOT NULL, content_hash TEXT NOT NULL, metadata_hash TEXT NOT NULL,
          captured_at TEXT NOT NULL, captured_by TEXT DEFAULT 'local-analyst',
          capture_mode TEXT DEFAULT 'manual_public_snapshot', chain_status TEXT DEFAULT 'captured_to_review', notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(task_id) REFERENCES search_tasks(task_id) ON DELETE SET NULL,
          FOREIGN KEY(review_item_id) REFERENCES review_items(item_id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS chain_events (
          chain_event_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, object_type TEXT NOT NULL, object_id TEXT NOT NULL,
          event_type TEXT NOT NULL, timestamp TEXT NOT NULL, actor TEXT NOT NULL, details_json TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS review_items (
          item_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, source_type TEXT NOT NULL, provider TEXT NOT NULL,
          title TEXT NOT NULL, url TEXT, snippet TEXT, query TEXT, score REAL DEFAULT 0.0,
          status TEXT DEFAULT 'new', sensitivity_level TEXT DEFAULT 'normal', markers_json TEXT NOT NULL,
          normalized_url TEXT DEFAULT '', fingerprint TEXT DEFAULT '', duplicate_cluster_id TEXT DEFAULT '',
          quality_score REAL DEFAULT 0.0, triage_reason TEXT DEFAULT '', reviewer TEXT DEFAULT 'local-analyst',
          notes TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS evidence_items (
          evidence_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, review_item_id TEXT, category TEXT NOT NULL,
          title TEXT NOT NULL, source_url TEXT, statement TEXT NOT NULL, confidence TEXT DEFAULT 'candidate',
          content_hash TEXT NOT NULL, metadata_hash TEXT NOT NULL, captured_at TEXT NOT NULL,
          captured_by TEXT DEFAULT 'analyst', custody_status TEXT DEFAULT 'captured', export_allowed INTEGER DEFAULT 0,
          redaction_required INTEGER DEFAULT 1, evidence_rank TEXT DEFAULT 'candidate', reliability_score REAL DEFAULT 0.0,
          source_reliability TEXT DEFAULT 'unknown', review_decision TEXT DEFAULT 'pending', redaction_profile TEXT DEFAULT 'client_safe', notes TEXT,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(review_item_id) REFERENCES review_items(item_id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS graph_nodes (
          node_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, node_type TEXT NOT NULL, label TEXT NOT NULL,
          confidence REAL DEFAULT 0.5, review_status TEXT DEFAULT 'candidate', properties_json TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS graph_edges (
          edge_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, source_node_id TEXT NOT NULL, target_node_id TEXT NOT NULL,
          relationship_type TEXT NOT NULL, source_evidence_id TEXT, confidence REAL DEFAULT 0.5,
          explanation TEXT, review_status TEXT DEFAULT 'candidate', relationship_category TEXT DEFAULT 'association',
          counter_evidence_json TEXT DEFAULT '[]', analysis_tags_json TEXT DEFAULT '[]',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS timeline_events (
          event_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, event_date TEXT NOT NULL, title TEXT NOT NULL,
          description TEXT, source_evidence_id TEXT, confidence TEXT DEFAULT 'candidate', review_status TEXT DEFAULT 'candidate',
          event_type TEXT DEFAULT 'osint_finding', actor TEXT DEFAULT '', location TEXT DEFAULT '',
          narrative_weight REAL DEFAULT 0.5, uncertainty_note TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS source_catalog (
          source_id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL, access_model TEXT NOT NULL,
          jurisdiction TEXT DEFAULT 'global', requires_api_key INTEGER DEFAULT 0, allowed_use TEXT NOT NULL,
          prohibited_use TEXT NOT NULL, default_risk TEXT DEFAULT 'low', active INTEGER DEFAULT 1,
          retention_hint TEXT DEFAULT '', notes TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS provider_registry (
          provider_id TEXT PRIMARY KEY, name TEXT NOT NULL, provider_type TEXT NOT NULL, base_url TEXT,
          enabled INTEGER DEFAULT 1, requires_api_key INTEGER DEFAULT 0, rate_limit_hint TEXT DEFAULT '',
          public_only INTEGER DEFAULT 1, compliance_tags_json TEXT NOT NULL, notes TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS provider_capabilities (
          capability_id TEXT PRIMARY KEY, provider_id TEXT NOT NULL, capability_key TEXT NOT NULL,
          mode TEXT NOT NULL, requires_api_key INTEGER DEFAULT 0, public_only INTEGER DEFAULT 1,
          url_template TEXT NOT NULL, compliance_tags_json TEXT NOT NULL, default_reliability TEXT DEFAULT 'medium', notes TEXT DEFAULT '',
          UNIQUE(provider_id, capability_key),
          FOREIGN KEY(provider_id) REFERENCES provider_registry(provider_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS provider_secret_refs (
          secret_id TEXT PRIMARY KEY, provider_id TEXT NOT NULL, env_var_name TEXT NOT NULL, key_last4 TEXT DEFAULT '',
          configured INTEGER DEFAULT 0, created_at TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(provider_id) REFERENCES provider_registry(provider_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS provider_rate_limits (
          rate_id TEXT PRIMARY KEY, provider_id TEXT NOT NULL UNIQUE, window_seconds INTEGER DEFAULT 3600,
          max_requests INTEGER DEFAULT 120, used_requests INTEGER DEFAULT 0, window_started_at TEXT NOT NULL,
          last_request_at TEXT DEFAULT '', notes TEXT DEFAULT '',
          FOREIGN KEY(provider_id) REFERENCES provider_registry(provider_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS provider_health_checks (
          health_id TEXT PRIMARY KEY, provider_id TEXT NOT NULL, status TEXT NOT NULL, checked_at TEXT NOT NULL,
          latency_ms INTEGER DEFAULT 0, issues_json TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(provider_id) REFERENCES provider_registry(provider_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS provider_jobs (
          job_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT DEFAULT '', provider_id TEXT NOT NULL,
          capability_key TEXT NOT NULL, query TEXT NOT NULL, purpose TEXT NOT NULL, request_url TEXT NOT NULL,
          status TEXT DEFAULT 'prepared', result_count INTEGER DEFAULT 0, sensitivity_json TEXT NOT NULL,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(provider_id) REFERENCES provider_registry(provider_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS provider_results (
          result_id TEXT PRIMARY KEY, job_id TEXT NOT NULL, case_id TEXT NOT NULL, provider_id TEXT NOT NULL,
          title TEXT NOT NULL, source_url TEXT DEFAULT '', snippet TEXT DEFAULT '', raw_payload_json TEXT NOT NULL,
          raw_hash TEXT NOT NULL, confidence TEXT DEFAULT 'candidate', reliability TEXT DEFAULT 'medium',
          review_item_id TEXT DEFAULT '', created_at TEXT NOT NULL,
          FOREIGN KEY(job_id) REFERENCES provider_jobs(job_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(provider_id) REFERENCES provider_registry(provider_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS provider_logs (
          log_id TEXT PRIMARY KEY, case_id TEXT DEFAULT '', provider_id TEXT NOT NULL, job_id TEXT DEFAULT '',
          event_type TEXT NOT NULL, status TEXT NOT NULL, details_json TEXT NOT NULL, created_at TEXT NOT NULL,
          FOREIGN KEY(provider_id) REFERENCES provider_registry(provider_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS privacy_assessments (
          assessment_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, assessment_type TEXT DEFAULT 'legal_case_wizard',
          lawful_basis TEXT NOT NULL, legitimate_interest TEXT DEFAULT '', necessity_test TEXT NOT NULL,
          balancing_test TEXT NOT NULL, proportionality_test TEXT DEFAULT '', data_minimization_notes TEXT DEFAULT '',
          expected_data_classes_json TEXT NOT NULL, prohibited_processing_json TEXT NOT NULL,
          decision TEXT DEFAULT 'review_required', risk_level TEXT DEFAULT 'medium', reviewer TEXT DEFAULT 'local-analyst',
          created_at TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS processing_scope_rules (
          rule_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, allowed_sources_json TEXT NOT NULL,
          prohibited_sources_json TEXT NOT NULL, allowed_data_classes_json TEXT NOT NULL,
          prohibited_data_classes_json TEXT NOT NULL, retention_until TEXT DEFAULT '', active INTEGER DEFAULT 1,
          created_at TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS sensitive_data_flags (
          flag_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, object_type TEXT NOT NULL, object_id TEXT DEFAULT '',
          data_category TEXT NOT NULL, article_reference TEXT NOT NULL, severity TEXT DEFAULT 'medium',
          action_required TEXT NOT NULL, status TEXT DEFAULT 'open', detected_at TEXT NOT NULL,
          reviewer TEXT DEFAULT 'local-analyst', notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS dpia_checks (
          dpia_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, trigger_level TEXT NOT NULL,
          required INTEGER DEFAULT 0, triggers_json TEXT NOT NULL, status TEXT DEFAULT 'not_required',
          reviewer TEXT DEFAULT 'local-analyst', created_at TEXT NOT NULL, decided_at TEXT DEFAULT '', notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS privacy_export_blockers (
          blocker_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, blocker_type TEXT NOT NULL,
          severity TEXT DEFAULT 'medium', description TEXT NOT NULL, status TEXT DEFAULT 'open',
          related_object_type TEXT DEFAULT '', related_object_id TEXT DEFAULT '', created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS retention_deletion_jobs (
          job_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, action TEXT NOT NULL, reason TEXT NOT NULL,
          status TEXT DEFAULT 'planned', scheduled_for TEXT DEFAULT '', executed_at TEXT DEFAULT '',
          affected_counts_json TEXT NOT NULL, reviewer TEXT DEFAULT 'local-analyst', created_at TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS workflow_steps (
          step_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, phase TEXT NOT NULL, title TEXT NOT NULL,
          status TEXT DEFAULT 'todo', owner TEXT DEFAULT 'analyst', due_date TEXT DEFAULT '',
          gate_required TEXT DEFAULT '', output_object_type TEXT DEFAULT '', output_object_id TEXT DEFAULT '',
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS identity_candidates (
          candidate_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT, label TEXT NOT NULL,
          score REAL DEFAULT 0.0, positive_markers_json TEXT NOT NULL, negative_markers_json TEXT NOT NULL,
          evidence_ids_json TEXT NOT NULL, status TEXT DEFAULT 'candidate', analyst_decision TEXT DEFAULT '',
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS risk_findings (
          finding_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, category TEXT NOT NULL, severity TEXT DEFAULT 'info',
          title TEXT NOT NULL, rationale TEXT NOT NULL, source_evidence_id TEXT DEFAULT '',
          status TEXT DEFAULT 'candidate', created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS export_reviews (
          export_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, report_type TEXT NOT NULL,
          decision TEXT NOT NULL, issues_json TEXT NOT NULL, reviewer TEXT DEFAULT 'local-analyst',
          created_at TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS retention_policies (
          policy_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, retention_until TEXT NOT NULL,
          deletion_mode TEXT DEFAULT 'review_required', reason TEXT NOT NULL, created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS evidence_categories (
          category_id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT NOT NULL,
          default_export_allowed INTEGER DEFAULT 0, default_redaction_required INTEGER DEFAULT 1,
          risk_level TEXT DEFAULT 'medium', notes TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS duplicate_clusters (
          cluster_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, fingerprint TEXT NOT NULL, normalized_url TEXT DEFAULT '',
          item_ids_json TEXT NOT NULL, status TEXT DEFAULT 'candidate_duplicate', representative_item_id TEXT DEFAULT '',
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL, analyst_decision TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS redaction_reviews (
          redaction_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, evidence_id TEXT NOT NULL, profile TEXT NOT NULL,
          decision TEXT NOT NULL, summary_json TEXT NOT NULL, redacted_statement TEXT NOT NULL,
          reviewer TEXT DEFAULT 'local-analyst', created_at TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(evidence_id) REFERENCES evidence_items(evidence_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS evidence_package_manifests (
          manifest_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, manifest_hash TEXT NOT NULL, item_count INTEGER NOT NULL,
          exportable_count INTEGER NOT NULL, redaction_blocked_count INTEGER NOT NULL, created_at TEXT NOT NULL,
          storage_path TEXT DEFAULT '', notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS review_quality_checks (
          check_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, item_id TEXT NOT NULL, quality_score REAL DEFAULT 0.0,
          issues_json TEXT NOT NULL, created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(item_id) REFERENCES review_items(item_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS graph_hypotheses (
          hypothesis_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, title TEXT NOT NULL,
          hypothesis_type TEXT DEFAULT 'relationship', statement TEXT NOT NULL,
          status TEXT DEFAULT 'open', confidence REAL DEFAULT 0.5,
          supporting_evidence_json TEXT NOT NULL, counter_evidence_json TEXT NOT NULL,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL, analyst TEXT DEFAULT 'local-analyst', notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS graph_contradictions (
          contradiction_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, title TEXT NOT NULL,
          contradiction_type TEXT DEFAULT 'conflict', description TEXT NOT NULL,
          severity TEXT DEFAULT 'medium', status TEXT DEFAULT 'open',
          related_node_ids_json TEXT NOT NULL, related_edge_ids_json TEXT NOT NULL, related_evidence_ids_json TEXT NOT NULL,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL, analyst TEXT DEFAULT 'local-analyst', notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS analysis_narratives (
          narrative_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, narrative_type TEXT NOT NULL, title TEXT NOT NULL,
          body TEXT NOT NULL, confidence_summary TEXT DEFAULT 'candidate',
          source_object_ids_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, analyst TEXT DEFAULT 'local-analyst',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS report_blueprints (
          blueprint_id TEXT PRIMARY KEY, report_type TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
          audience TEXT NOT NULL, default_redaction_profile TEXT NOT NULL,
          mandatory_sections_json TEXT NOT NULL, export_policy TEXT DEFAULT 'review_required',
          notes TEXT DEFAULT '', active INTEGER DEFAULT 1, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS report_readiness_checks (
          check_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, report_type TEXT NOT NULL,
          status TEXT NOT NULL, blockers_json TEXT NOT NULL, warnings_json TEXT NOT NULL,
          metrics_json TEXT NOT NULL, created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS professional_reports (
          report_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, report_type TEXT NOT NULL,
          audience TEXT NOT NULL, redaction_profile TEXT NOT NULL, readiness_status TEXT NOT NULL,
          executive_summary TEXT NOT NULL, methodology TEXT NOT NULL,
          source_critique_json TEXT NOT NULL, uncertainty_register_json TEXT NOT NULL,
          evidence_annex_json TEXT NOT NULL, section_manifest_json TEXT NOT NULL,
          export_paths_json TEXT NOT NULL, content_hash TEXT NOT NULL,
          created_at TEXT NOT NULL, created_by TEXT DEFAULT 'local-analyst', notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );


        CREATE TABLE IF NOT EXISTS local_users (
          user_id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL,
          role TEXT NOT NULL DEFAULT 'analyst', password_salt TEXT NOT NULL, password_hash TEXT NOT NULL,
          password_kdf TEXT DEFAULT 'pbkdf2_sha256_200k', active INTEGER DEFAULT 1,
          created_at TEXT NOT NULL, last_login_at TEXT DEFAULT '', notes TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS user_roles (
          role_id TEXT PRIMARY KEY, role_key TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
          permissions_json TEXT NOT NULL, description TEXT DEFAULT '', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS auth_sessions (
          session_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, username TEXT NOT NULL,
          role TEXT NOT NULL, session_token_hash TEXT NOT NULL, created_at TEXT NOT NULL,
          expires_at TEXT NOT NULL, revoked INTEGER DEFAULT 0, last_seen_at TEXT DEFAULT '',
          FOREIGN KEY(user_id) REFERENCES local_users(user_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS security_settings (
          setting_key TEXT PRIMARY KEY, setting_value TEXT NOT NULL, classification TEXT DEFAULT 'internal',
          updated_at TEXT NOT NULL, updated_by TEXT DEFAULT 'system'
        );
        CREATE TABLE IF NOT EXISTS secret_references (
          secret_id TEXT PRIMARY KEY, name TEXT NOT NULL, env_var TEXT NOT NULL UNIQUE,
          purpose TEXT NOT NULL, provider_id TEXT DEFAULT '', required INTEGER DEFAULT 0,
          last_checked_at TEXT DEFAULT '', status TEXT DEFAULT 'unchecked', notes TEXT DEFAULT '', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS integrity_baselines (
          baseline_id TEXT PRIMARY KEY, label TEXT NOT NULL, root_path TEXT NOT NULL,
          manifest_json TEXT NOT NULL, manifest_hash TEXT NOT NULL, created_at TEXT NOT NULL,
          created_by TEXT DEFAULT 'local-security', notes TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS integrity_checks (
          check_id TEXT PRIMARY KEY, baseline_id TEXT NOT NULL, status TEXT NOT NULL,
          changed_files_json TEXT NOT NULL, missing_files_json TEXT NOT NULL, new_files_json TEXT NOT NULL,
          checked_at TEXT NOT NULL, checked_by TEXT DEFAULT 'local-security', notes TEXT DEFAULT '',
          FOREIGN KEY(baseline_id) REFERENCES integrity_baselines(baseline_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS audit_chain_hashes (
          chain_id TEXT PRIMARY KEY, event_id TEXT NOT NULL UNIQUE, sequence_no INTEGER NOT NULL,
          previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL, chained_at TEXT NOT NULL,
          FOREIGN KEY(event_id) REFERENCES audit_events(event_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS backup_manifests (
          backup_id TEXT PRIMARY KEY, backup_path TEXT NOT NULL, backup_hash TEXT NOT NULL,
          file_count INTEGER NOT NULL, total_bytes INTEGER NOT NULL, created_at TEXT NOT NULL,
          created_by TEXT DEFAULT 'local-security', includes_data INTEGER DEFAULT 1,
          includes_reports INTEGER DEFAULT 1, notes TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS export_watermarks (
          watermark_id TEXT PRIMARY KEY, case_id TEXT, report_id TEXT, audience TEXT NOT NULL,
          watermark_text TEXT NOT NULL, token_hash TEXT NOT NULL, created_at TEXT NOT NULL,
          created_by TEXT DEFAULT 'local-security', notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS security_findings (
          finding_id TEXT PRIMARY KEY, case_id TEXT, severity TEXT NOT NULL, finding_type TEXT NOT NULL,
          title TEXT NOT NULL, description TEXT NOT NULL, status TEXT DEFAULT 'open',
          created_at TEXT NOT NULL, resolved_at TEXT DEFAULT '', notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );



        CREATE TABLE IF NOT EXISTS clients (
          client_id TEXT PRIMARY KEY, name TEXT NOT NULL, client_type TEXT DEFAULT 'mandant',
          contact TEXT DEFAULT '', jurisdiction TEXT DEFAULT 'DE/EU', status TEXT DEFAULT 'active',
          created_at TEXT NOT NULL, notes TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS case_client_assignments (
          assignment_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, client_id TEXT NOT NULL,
          assignment_type TEXT DEFAULT 'primary', data_boundary TEXT DEFAULT 'strict_client_boundary',
          active INTEGER DEFAULT 1, created_at TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(client_id) REFERENCES clients(client_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS team_members (
          member_id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL,
          email TEXT DEFAULT '', organization TEXT DEFAULT 'internal', role_key TEXT DEFAULT 'analyst',
          active INTEGER DEFAULT 1, created_at TEXT NOT NULL, notes TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS case_access_assignments (
          access_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, member_id TEXT NOT NULL,
          role_key TEXT NOT NULL, permissions_json TEXT NOT NULL, granted_by TEXT DEFAULT 'local-admin',
          granted_at TEXT NOT NULL, active INTEGER DEFAULT 1, notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(member_id) REFERENCES team_members(member_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS case_role_policies (
          policy_id TEXT PRIMARY KEY, role_key TEXT NOT NULL UNIQUE, permissions_json TEXT NOT NULL,
          requires_four_eyes INTEGER DEFAULT 0, can_export INTEGER DEFAULT 0, can_assign INTEGER DEFAULT 0,
          created_at TEXT NOT NULL, notes TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS approval_requests (
          request_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, request_type TEXT NOT NULL,
          object_type TEXT NOT NULL, object_id TEXT DEFAULT '', title TEXT NOT NULL, reason TEXT NOT NULL,
          required_role TEXT DEFAULT 'legal_reviewer', min_approvals INTEGER DEFAULT 1,
          status TEXT DEFAULT 'pending', requested_by TEXT NOT NULL, created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS approval_decisions (
          decision_id TEXT PRIMARY KEY, request_id TEXT NOT NULL, case_id TEXT NOT NULL,
          decision TEXT NOT NULL, decided_by TEXT NOT NULL, decider_role TEXT NOT NULL,
          comment TEXT DEFAULT '', decided_at TEXT NOT NULL,
          FOREIGN KEY(request_id) REFERENCES approval_requests(request_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS team_comments (
          comment_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, object_type TEXT NOT NULL,
          object_id TEXT DEFAULT '', author TEXT NOT NULL, visibility TEXT DEFAULT 'internal',
          body TEXT NOT NULL, created_at TEXT NOT NULL, resolved INTEGER DEFAULT 0, notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS release_history (
          release_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, request_id TEXT NOT NULL,
          release_type TEXT NOT NULL, audience TEXT NOT NULL, approved_by_json TEXT NOT NULL,
          content_hash TEXT NOT NULL, status TEXT DEFAULT 'released', created_at TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(request_id) REFERENCES approval_requests(request_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS cockpit_snapshots (
          snapshot_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, readiness_score INTEGER NOT NULL,
          traffic_light TEXT NOT NULL, kpis_json TEXT NOT NULL, gates_json TEXT NOT NULL,
          blockers_json TEXT NOT NULL, warnings_json TEXT NOT NULL, next_actions_json TEXT NOT NULL,
          created_at TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS cockpit_pinned_actions (
          action_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, priority INTEGER DEFAULT 50,
          area TEXT NOT NULL, title TEXT NOT NULL, detail TEXT DEFAULT '', status TEXT DEFAULT 'open',
          target_tab TEXT DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );


        CREATE TABLE IF NOT EXISTS ai_prompt_templates (
          template_id TEXT PRIMARY KEY, template_key TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
          description TEXT NOT NULL, guardrail_profile TEXT DEFAULT 'candidate_only_no_identity_guilt_or_address_decisions',
          created_at TEXT NOT NULL, active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS ai_assistant_tasks (
          task_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, task_type TEXT NOT NULL, title TEXT NOT NULL,
          instructions TEXT DEFAULT '', source_scope_json TEXT NOT NULL, status TEXT DEFAULT 'queued',
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL, result_hash TEXT DEFAULT '',
          guardrail_status TEXT DEFAULT 'pending', notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS ai_guardrail_checks (
          check_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, object_type TEXT NOT NULL, object_id TEXT DEFAULT '',
          status TEXT NOT NULL, blocked_terms_json TEXT NOT NULL, warnings_json TEXT NOT NULL,
          policy_result_json TEXT NOT NULL, created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS ai_summaries (
          summary_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, task_id TEXT DEFAULT '', summary_type TEXT NOT NULL,
          title TEXT NOT NULL, body TEXT NOT NULL, metrics_json TEXT NOT NULL, source_object_ids_json TEXT NOT NULL,
          guardrail_status TEXT DEFAULT 'pending', created_at TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS ai_contradiction_suggestions (
          suggestion_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, task_id TEXT DEFAULT '', contradiction_type TEXT NOT NULL,
          severity TEXT DEFAULT 'medium', title TEXT NOT NULL, description TEXT NOT NULL,
          related_object_ids_json TEXT NOT NULL, status TEXT DEFAULT 'suggested', guardrail_status TEXT DEFAULT 'pending',
          created_at TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS ai_hypothesis_suggestions (
          suggestion_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, task_id TEXT DEFAULT '', hypothesis_type TEXT NOT NULL,
          title TEXT NOT NULL, statement TEXT NOT NULL, confidence REAL DEFAULT 0.5,
          status TEXT DEFAULT 'suggested', guardrail_status TEXT DEFAULT 'pending', created_at TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS ai_timeline_drafts (
          draft_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, task_id TEXT DEFAULT '', source_evidence_id TEXT DEFAULT '',
          event_date TEXT NOT NULL, title TEXT NOT NULL, description TEXT DEFAULT '', event_type TEXT DEFAULT 'evidence_capture_candidate',
          confidence REAL DEFAULT 0.5, status TEXT DEFAULT 'draft', guardrail_status TEXT DEFAULT 'pending',
          created_at TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS ai_report_drafts (
          draft_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, task_id TEXT DEFAULT '', report_type TEXT NOT NULL,
          section_key TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
          status TEXT DEFAULT 'draft', guardrail_status TEXT DEFAULT 'pending', created_at TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );


        CREATE TABLE IF NOT EXISTS case_playbooks (
          playbook_id TEXT PRIMARY KEY, playbook_key TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
          case_type TEXT NOT NULL, risk_level TEXT DEFAULT 'medium', purpose_template TEXT NOT NULL,
          legal_basis_hint TEXT NOT NULL, description TEXT NOT NULL, allowed_sources_json TEXT NOT NULL,
          forbidden_actions_json TEXT NOT NULL, deliverables_json TEXT NOT NULL, quality_gates_json TEXT NOT NULL,
          created_at TEXT NOT NULL, active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS playbook_phase_templates (
          phase_template_id TEXT PRIMARY KEY, playbook_id TEXT NOT NULL, phase_order INTEGER NOT NULL,
          title TEXT NOT NULL, objective TEXT NOT NULL, required_gate TEXT DEFAULT 'HUMAN_REVIEW', created_at TEXT NOT NULL,
          FOREIGN KEY(playbook_id) REFERENCES case_playbooks(playbook_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS playbook_source_profiles (
          source_profile_id TEXT PRIMARY KEY, playbook_id TEXT NOT NULL, source_name TEXT NOT NULL,
          source_category TEXT DEFAULT 'public_web', allowed_use TEXT NOT NULL, risk_level TEXT DEFAULT 'medium', created_at TEXT NOT NULL,
          FOREIGN KEY(playbook_id) REFERENCES case_playbooks(playbook_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS playbook_guardrails (
          guardrail_id TEXT PRIMARY KEY, playbook_id TEXT NOT NULL, guardrail_type TEXT NOT NULL,
          rule_text TEXT NOT NULL, severity TEXT DEFAULT 'medium', created_at TEXT NOT NULL,
          FOREIGN KEY(playbook_id) REFERENCES case_playbooks(playbook_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS case_playbook_assignments (
          assignment_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, playbook_id TEXT NOT NULL,
          playbook_key TEXT NOT NULL, title TEXT NOT NULL, status TEXT DEFAULT 'active', assigned_by TEXT NOT NULL,
          assigned_at TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(playbook_id) REFERENCES case_playbooks(playbook_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS playbook_case_steps (
          case_step_id TEXT PRIMARY KEY, assignment_id TEXT NOT NULL, case_id TEXT NOT NULL, playbook_id TEXT NOT NULL,
          phase_order INTEGER NOT NULL, title TEXT NOT NULL, objective TEXT NOT NULL, required_gate TEXT DEFAULT 'HUMAN_REVIEW',
          status TEXT DEFAULT 'todo', owner TEXT DEFAULT 'analyst', created_at TEXT NOT NULL, updated_at TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(assignment_id) REFERENCES case_playbook_assignments(assignment_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(playbook_id) REFERENCES case_playbooks(playbook_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS playbook_source_plans (
          plan_id TEXT PRIMARY KEY, assignment_id TEXT NOT NULL, case_id TEXT NOT NULL,
          source_name TEXT NOT NULL, source_category TEXT NOT NULL, allowed_use TEXT NOT NULL,
          risk_level TEXT DEFAULT 'medium', status TEXT DEFAULT 'planned', created_at TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(assignment_id) REFERENCES case_playbook_assignments(assignment_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS playbook_deliverables (
          deliverable_id TEXT PRIMARY KEY, assignment_id TEXT NOT NULL, case_id TEXT NOT NULL,
          deliverable_type TEXT NOT NULL, status TEXT DEFAULT 'planned', required_review INTEGER DEFAULT 1,
          created_at TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(assignment_id) REFERENCES case_playbook_assignments(assignment_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS playbook_quality_gates (
          gate_id TEXT PRIMARY KEY, assignment_id TEXT NOT NULL, case_id TEXT NOT NULL,
          gate_name TEXT NOT NULL, status TEXT DEFAULT 'open', severity TEXT DEFAULT 'medium', created_at TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(assignment_id) REFERENCES case_playbook_assignments(assignment_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );


        CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
        CREATE INDEX IF NOT EXISTS idx_review_case_status ON review_items(case_id, status);
        CREATE INDEX IF NOT EXISTS idx_review_fingerprint ON review_items(case_id, fingerprint);
        CREATE INDEX IF NOT EXISTS idx_duplicate_clusters_case ON duplicate_clusters(case_id, fingerprint);
        CREATE INDEX IF NOT EXISTS idx_redaction_reviews_case ON redaction_reviews(case_id, evidence_id);
        CREATE INDEX IF NOT EXISTS idx_evidence_manifest_case ON evidence_package_manifests(case_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_evidence_case ON evidence_items(case_id);
        CREATE INDEX IF NOT EXISTS idx_audit_case ON audit_events(case_id, timestamp);
        CREATE INDEX IF NOT EXISTS idx_workflow_case ON workflow_steps(case_id, phase, status);
        CREATE INDEX IF NOT EXISTS idx_identity_case ON identity_candidates(case_id, score);
        CREATE INDEX IF NOT EXISTS idx_risk_case ON risk_findings(case_id, severity);
        CREATE INDEX IF NOT EXISTS idx_search_packages_case ON search_packages(case_id, status);
        CREATE INDEX IF NOT EXISTS idx_search_pkg_tasks_task ON search_package_tasks(task_id);
        CREATE INDEX IF NOT EXISTS idx_source_captures_case ON source_captures(case_id, captured_at);
        CREATE INDEX IF NOT EXISTS idx_chain_events_case ON chain_events(case_id, timestamp);
        CREATE INDEX IF NOT EXISTS idx_graph_hyp_case ON graph_hypotheses(case_id, status);
        CREATE INDEX IF NOT EXISTS idx_graph_contra_case ON graph_contradictions(case_id, severity, status);
        CREATE INDEX IF NOT EXISTS idx_analysis_narratives_case ON analysis_narratives(case_id, narrative_type, created_at);
        CREATE INDEX IF NOT EXISTS idx_graph_edges_case_rel ON graph_edges(case_id, relationship_type, confidence);
        CREATE INDEX IF NOT EXISTS idx_timeline_case_type ON timeline_events(case_id, event_type, event_date);
        CREATE INDEX IF NOT EXISTS idx_report_blueprints_type ON report_blueprints(report_type, active);
        CREATE INDEX IF NOT EXISTS idx_report_readiness_case ON report_readiness_checks(case_id, report_type, created_at);
        CREATE INDEX IF NOT EXISTS idx_professional_reports_case ON professional_reports(case_id, report_type, created_at);
        CREATE INDEX IF NOT EXISTS idx_provider_capabilities_provider ON provider_capabilities(provider_id, capability_key);
        CREATE INDEX IF NOT EXISTS idx_provider_jobs_case ON provider_jobs(case_id, status, created_at);
        CREATE INDEX IF NOT EXISTS idx_provider_results_case ON provider_results(case_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_provider_logs_case ON provider_logs(case_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_provider_health_provider ON provider_health_checks(provider_id, checked_at);
        CREATE INDEX IF NOT EXISTS idx_privacy_assessments_case ON privacy_assessments(case_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_processing_scope_rules_case ON processing_scope_rules(case_id, active);
        CREATE INDEX IF NOT EXISTS idx_sensitive_flags_case ON sensitive_data_flags(case_id, status, severity);
        CREATE INDEX IF NOT EXISTS idx_dpia_checks_case ON dpia_checks(case_id, status, created_at);
        CREATE INDEX IF NOT EXISTS idx_privacy_export_blockers_case ON privacy_export_blockers(case_id, status, severity);
        CREATE INDEX IF NOT EXISTS idx_retention_jobs_case ON retention_deletion_jobs(case_id, status, scheduled_for);

        CREATE INDEX IF NOT EXISTS idx_local_users_username ON local_users(username, active);
        CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id, revoked, expires_at);
        CREATE INDEX IF NOT EXISTS idx_secret_refs_env ON secret_references(env_var, status);
        CREATE INDEX IF NOT EXISTS idx_integrity_checks_baseline ON integrity_checks(baseline_id, checked_at);
        CREATE INDEX IF NOT EXISTS idx_audit_chain_event ON audit_chain_hashes(event_id, sequence_no);
        CREATE INDEX IF NOT EXISTS idx_backup_manifests_created ON backup_manifests(created_at);
        CREATE INDEX IF NOT EXISTS idx_export_watermarks_case ON export_watermarks(case_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_security_findings_case ON security_findings(case_id, status, severity);

        CREATE INDEX IF NOT EXISTS idx_clients_status ON clients(status, created_at);
        CREATE INDEX IF NOT EXISTS idx_case_client_case ON case_client_assignments(case_id, active);
        CREATE INDEX IF NOT EXISTS idx_team_members_user ON team_members(username, active);
        CREATE INDEX IF NOT EXISTS idx_case_access_case ON case_access_assignments(case_id, active, role_key);
        CREATE INDEX IF NOT EXISTS idx_approval_requests_case ON approval_requests(case_id, status, created_at);
        CREATE INDEX IF NOT EXISTS idx_approval_decisions_request ON approval_decisions(request_id, decision);
        CREATE INDEX IF NOT EXISTS idx_team_comments_case ON team_comments(case_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_release_history_case ON release_history(case_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_cockpit_snapshots_case ON cockpit_snapshots(case_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_cockpit_actions_case ON cockpit_pinned_actions(case_id, status, priority);


        CREATE INDEX IF NOT EXISTS idx_ai_tasks_case ON ai_assistant_tasks(case_id, status, created_at);
        CREATE INDEX IF NOT EXISTS idx_ai_guardrails_case ON ai_guardrail_checks(case_id, status, created_at);
        CREATE INDEX IF NOT EXISTS idx_ai_summaries_case ON ai_summaries(case_id, summary_type, created_at);
        CREATE INDEX IF NOT EXISTS idx_ai_contradictions_case ON ai_contradiction_suggestions(case_id, severity, status);
        CREATE INDEX IF NOT EXISTS idx_ai_hypotheses_case ON ai_hypothesis_suggestions(case_id, confidence, status);
        CREATE INDEX IF NOT EXISTS idx_ai_timeline_case ON ai_timeline_drafts(case_id, event_date, status);
        CREATE INDEX IF NOT EXISTS idx_ai_report_drafts_case ON ai_report_drafts(case_id, report_type, section_key);



        CREATE TABLE IF NOT EXISTS deployment_profiles (
          profile_id TEXT PRIMARY KEY, profile_key TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
          description TEXT NOT NULL, target TEXT DEFAULT 'single_workstation', includes_runtime_data INTEGER DEFAULT 0,
          requires_admin INTEGER DEFAULT 0, created_at TEXT NOT NULL, active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS release_artifacts (
          artifact_id TEXT PRIMARY KEY, build_version TEXT NOT NULL, artifact_type TEXT NOT NULL,
          profile_key TEXT NOT NULL, path TEXT NOT NULL, sha256 TEXT DEFAULT '', file_count INTEGER DEFAULT 0,
          total_bytes INTEGER DEFAULT 0, created_at TEXT NOT NULL, status TEXT DEFAULT 'created', notes TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS migration_plans (
          migration_id TEXT PRIMARY KEY, from_version TEXT NOT NULL, to_version TEXT NOT NULL,
          migration_type TEXT DEFAULT 'schema_and_release', status TEXT DEFAULT 'planned', required_backup INTEGER DEFAULT 1,
          created_at TEXT NOT NULL, completed_at TEXT DEFAULT '', notes TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS migration_events (
          event_id TEXT PRIMARY KEY, migration_id TEXT NOT NULL, step_key TEXT NOT NULL,
          status TEXT NOT NULL, message TEXT DEFAULT '', created_at TEXT NOT NULL,
          FOREIGN KEY(migration_id) REFERENCES migration_plans(migration_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS rollback_points (
          rollback_id TEXT PRIMARY KEY, build_version TEXT NOT NULL, label TEXT NOT NULL,
          backup_path TEXT NOT NULL, backup_hash TEXT DEFAULT '', file_count INTEGER DEFAULT 0,
          total_bytes INTEGER DEFAULT 0, created_at TEXT NOT NULL, status TEXT DEFAULT 'created', notes TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS installer_checklist (
          check_id TEXT PRIMARY KEY, profile_key TEXT NOT NULL, item_key TEXT NOT NULL, title TEXT NOT NULL,
          status TEXT DEFAULT 'open', severity TEXT DEFAULT 'medium', created_at TEXT NOT NULL, notes TEXT DEFAULT '',
          UNIQUE(profile_key, item_key)
        );
        CREATE TABLE IF NOT EXISTS deployment_settings (
          setting_key TEXT PRIMARY KEY, setting_value TEXT NOT NULL, updated_at TEXT NOT NULL, notes TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS release_validations (
          validation_id TEXT PRIMARY KEY, artifact_id TEXT DEFAULT '', validation_type TEXT NOT NULL,
          status TEXT NOT NULL, details_json TEXT NOT NULL, created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_case_playbooks_key ON case_playbooks(playbook_key, active);
        CREATE INDEX IF NOT EXISTS idx_case_playbook_assignments_case ON case_playbook_assignments(case_id, status, assigned_at);
        CREATE INDEX IF NOT EXISTS idx_playbook_case_steps_case ON playbook_case_steps(case_id, status, phase_order);
        CREATE INDEX IF NOT EXISTS idx_playbook_quality_gates_case ON playbook_quality_gates(case_id, status, severity);
        CREATE INDEX IF NOT EXISTS idx_playbook_source_plans_case ON playbook_source_plans(case_id, status, source_category);
        CREATE INDEX IF NOT EXISTS idx_playbook_deliverables_case ON playbook_deliverables(case_id, status, deliverable_type);

        CREATE INDEX IF NOT EXISTS idx_deployment_profiles_key ON deployment_profiles(profile_key, active);
        CREATE INDEX IF NOT EXISTS idx_release_artifacts_build ON release_artifacts(build_version, artifact_type, created_at);
        CREATE INDEX IF NOT EXISTS idx_migration_plans_versions ON migration_plans(from_version, to_version, status);
        CREATE INDEX IF NOT EXISTS idx_migration_events_plan ON migration_events(migration_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_rollback_points_build ON rollback_points(build_version, created_at);
        CREATE INDEX IF NOT EXISTS idx_installer_checklist_profile ON installer_checklist(profile_key, status, severity);
        CREATE INDEX IF NOT EXISTS idx_release_validations_artifact ON release_validations(artifact_id, status, created_at);

        CREATE TABLE IF NOT EXISTS ui_workspaces (
          workspace_id TEXT PRIMARY KEY, workspace_key TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
          purpose TEXT NOT NULL, display_order INTEGER DEFAULT 0, tabs_json TEXT NOT NULL,
          created_at TEXT NOT NULL, active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS search_category_bundles (
          bundle_id TEXT PRIMARY KEY, bundle_key TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
          objective TEXT NOT NULL, categories_json TEXT NOT NULL, source_mode TEXT DEFAULT 'public_osint_only',
          display_order INTEGER DEFAULT 0, created_at TEXT NOT NULL, active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS ux_workspace_snapshots (
          snapshot_id TEXT PRIMARY KEY, case_id TEXT DEFAULT '', snapshot_json TEXT NOT NULL,
          created_at TEXT NOT NULL, notes TEXT DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_ui_workspaces_key ON ui_workspaces(workspace_key, active, display_order);
        CREATE INDEX IF NOT EXISTS idx_search_category_bundles_key ON search_category_bundles(bundle_key, active, display_order);
        CREATE INDEX IF NOT EXISTS idx_ux_workspace_snapshots_case ON ux_workspace_snapshots(case_id, created_at);

        CREATE TABLE IF NOT EXISTS multi_search_presets (
          preset_id TEXT PRIMARY KEY, preset_key TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
          engines_json TEXT NOT NULL, description TEXT NOT NULL, display_order INTEGER DEFAULT 0,
          created_at TEXT NOT NULL, active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS multi_search_launches (
          launch_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT DEFAULT '', source_task_id TEXT DEFAULT '',
          bundle_key TEXT DEFAULT '', preset_key TEXT NOT NULL, query TEXT NOT NULL, engines_json TEXT NOT NULL,
          url_count INTEGER DEFAULT 0, status TEXT DEFAULT 'planned', created_at TEXT NOT NULL, opened_at TEXT DEFAULT '', notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS multi_search_launch_urls (
          launch_url_id TEXT PRIMARY KEY, launch_id TEXT NOT NULL, engine TEXT NOT NULL, url TEXT NOT NULL,
          status TEXT DEFAULT 'planned', opened_at TEXT DEFAULT '', created_at TEXT NOT NULL,
          FOREIGN KEY(launch_id) REFERENCES multi_search_launches(launch_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_multi_search_presets_key ON multi_search_presets(preset_key, active, display_order);
        CREATE INDEX IF NOT EXISTS idx_multi_search_launches_case ON multi_search_launches(case_id, created_at, status);
        CREATE INDEX IF NOT EXISTS idx_multi_search_launch_urls_launch ON multi_search_launch_urls(launch_id, engine, status);


        ''')
        self._ensure_column('review_items', 'normalized_url', "TEXT DEFAULT ''")
        self._ensure_column('review_items', 'fingerprint', "TEXT DEFAULT ''")
        self._ensure_column('review_items', 'duplicate_cluster_id', "TEXT DEFAULT ''")
        self._ensure_column('review_items', 'quality_score', "REAL DEFAULT 0.0")
        self._ensure_column('review_items', 'triage_reason', "TEXT DEFAULT ''")
        self._ensure_column('review_items', 'reviewer', "TEXT DEFAULT 'local-analyst'")
        self._ensure_column('evidence_items', 'evidence_rank', "TEXT DEFAULT 'candidate'")
        self._ensure_column('evidence_items', 'reliability_score', "REAL DEFAULT 0.0")
        self._ensure_column('evidence_items', 'source_reliability', "TEXT DEFAULT 'unknown'")
        self._ensure_column('evidence_items', 'review_decision', "TEXT DEFAULT 'pending'")
        self._ensure_column('evidence_items', 'redaction_profile', "TEXT DEFAULT 'client_safe'")
        self._ensure_column('graph_edges', 'relationship_category', "TEXT DEFAULT 'association'")
        self._ensure_column('graph_edges', 'counter_evidence_json', "TEXT DEFAULT '[]'")
        self._ensure_column('graph_edges', 'analysis_tags_json', "TEXT DEFAULT '[]'")
        self._ensure_column('timeline_events', 'event_type', "TEXT DEFAULT 'osint_finding'")
        self._ensure_column('timeline_events', 'actor', "TEXT DEFAULT ''")
        self._ensure_column('timeline_events', 'location', "TEXT DEFAULT ''")
        self._ensure_column('timeline_events', 'narrative_weight', "REAL DEFAULT 0.5")
        self._ensure_column('timeline_events', 'uncertainty_note', "TEXT DEFAULT ''")
        self.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version',?)", (SCHEMA_VERSION,))
        self.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build',?)", (BUILD,))
        if not self.in_transaction:
            self.conn.commit()
