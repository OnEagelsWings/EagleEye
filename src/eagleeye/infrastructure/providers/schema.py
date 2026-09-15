from __future__ import annotations

from typing import Any


PROVIDER_SCHEMA_120 = r"""

            CREATE TABLE IF NOT EXISTS provider_catalog_120(
                provider_key TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                provider_type TEXT NOT NULL,
                public_only INTEGER NOT NULL,
                supports_live INTEGER NOT NULL,
                supports_replay INTEGER NOT NULL,
                allowed_hosts_json TEXT NOT NULL,
                rate_limit_per_minute INTEGER NOT NULL,
                min_interval_seconds REAL NOT NULL,
                timeout_seconds REAL NOT NULL,
                max_attempts INTEGER NOT NULL,
                backoff_base_seconds REAL NOT NULL,
                circuit_failure_threshold INTEGER NOT NULL,
                circuit_cooldown_seconds REAL NOT NULL,
                max_response_bytes INTEGER NOT NULL,
                terms_profile TEXT NOT NULL,
                enabled INTEGER NOT NULL,
                metadata_json TEXT NOT NULL,
                registered_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS provider_runs_120(
                run_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                target_id TEXT,
                provider_key TEXT NOT NULL,
                search_intent_id TEXT,
                search_query_id TEXT,
                query_text TEXT NOT NULL,
                purpose TEXT NOT NULL,
                approved_by TEXT NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                correlation_id TEXT NOT NULL,
                request_count INTEGER NOT NULL DEFAULT 0,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                result_count INTEGER NOT NULL DEFAULT 0,
                duplicate_count INTEGER NOT NULL DEFAULT 0,
                information_gain REAL NOT NULL DEFAULT 0,
                error_class TEXT NOT NULL DEFAULT '',
                error_text TEXT NOT NULL DEFAULT '',
                started_at TEXT NOT NULL,
                completed_at TEXT,
                FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
                FOREIGN KEY(provider_key) REFERENCES provider_catalog_120(provider_key)
            );
            CREATE INDEX IF NOT EXISTS idx_provider_runs120_case_time
                ON provider_runs_120(case_id,started_at DESC);
            CREATE INDEX IF NOT EXISTS idx_provider_runs120_provider_time
                ON provider_runs_120(provider_key,started_at DESC);
            CREATE TABLE IF NOT EXISTS provider_attempts_120(
                attempt_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                request_index INTEGER NOT NULL,
                attempt_number INTEGER NOT NULL,
                requested_url TEXT NOT NULL,
                final_url TEXT NOT NULL DEFAULT '',
                status_code INTEGER,
                outcome TEXT NOT NULL,
                error_class TEXT NOT NULL DEFAULT '',
                error_text TEXT NOT NULL DEFAULT '',
                response_sha256 TEXT NOT NULL DEFAULT '',
                response_bytes INTEGER NOT NULL DEFAULT 0,
                elapsed_ms INTEGER NOT NULL DEFAULT 0,
                attempted_at_epoch REAL NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES provider_runs_120(run_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_provider_attempts120_run
                ON provider_attempts_120(run_id,request_index,attempt_number);
            CREATE INDEX IF NOT EXISTS idx_provider_attempts120_rate
                ON provider_attempts_120(attempted_at_epoch);
            CREATE TABLE IF NOT EXISTS provider_intake_120(
                intake_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                target_id TEXT,
                run_id TEXT NOT NULL,
                provider_key TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                canonical_url TEXT NOT NULL,
                source_host TEXT NOT NULL,
                snippet TEXT NOT NULL,
                source_type TEXT NOT NULL,
                published_at TEXT NOT NULL DEFAULT '',
                content_fingerprint TEXT NOT NULL,
                raw_payload_json TEXT NOT NULL,
                review_status TEXT NOT NULL DEFAULT 'new',
                candidate_only INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(case_id,provider_key,canonical_url,content_fingerprint),
                FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
                FOREIGN KEY(run_id) REFERENCES provider_runs_120(run_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_provider_intake120_case_status
                ON provider_intake_120(case_id,review_status,created_at DESC);
            CREATE TABLE IF NOT EXISTS provider_state_120(
                provider_key TEXT PRIMARY KEY,
                circuit_state TEXT NOT NULL DEFAULT 'closed',
                consecutive_failures INTEGER NOT NULL DEFAULT 0,
                open_until_epoch REAL NOT NULL DEFAULT 0,
                next_allowed_epoch REAL NOT NULL DEFAULT 0,
                last_success_at TEXT NOT NULL DEFAULT '',
                last_failure_at TEXT NOT NULL DEFAULT '',
                total_runs INTEGER NOT NULL DEFAULT 0,
                successful_runs INTEGER NOT NULL DEFAULT 0,
                failed_runs INTEGER NOT NULL DEFAULT 0,
                total_latency_ms INTEGER NOT NULL DEFAULT 0,
                total_results INTEGER NOT NULL DEFAULT 0,
                total_duplicates INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(provider_key) REFERENCES provider_catalog_120(provider_key)
            );
            CREATE TABLE IF NOT EXISTS provider_replay_fixtures_120(
                fixture_id TEXT PRIMARY KEY,
                provider_key TEXT NOT NULL,
                request_fingerprint TEXT NOT NULL,
                fixture_path TEXT NOT NULL,
                fixture_sha256 TEXT NOT NULL,
                response_sha256 TEXT NOT NULL,
                source_run_id TEXT,
                sanitized INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                UNIQUE(provider_key,request_fingerprint,fixture_sha256),
                FOREIGN KEY(provider_key) REFERENCES provider_catalog_120(provider_key),
                FOREIGN KEY(source_run_id) REFERENCES provider_runs_120(run_id) ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS idx_provider_replay120_lookup
                ON provider_replay_fixtures_120(provider_key,request_fingerprint,created_at DESC);
            CREATE TABLE IF NOT EXISTS provider_events_120(
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                case_id TEXT NOT NULL,
                provider_key TEXT NOT NULL,
                run_id TEXT NOT NULL,
                actor TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                event_hash TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_provider_events120_chain
                ON provider_events_120(case_id,provider_key,sequence);

"""


def ensure_provider_schema_120(db: Any) -> None:
    """Install the Build 120 provider schema independently of service construction."""
    db.conn.executescript(PROVIDER_SCHEMA_120)
    db.conn.commit()
