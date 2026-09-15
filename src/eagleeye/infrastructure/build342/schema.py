from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def ensure_build342_schema(db: Any) -> None:
    # Build 342 deliberately adds only a minimal Phase-15 surface. Schema consolidation is Build 344.
    db.execute(
        """CREATE TABLE IF NOT EXISTS phase15_build342_state(
        state_key TEXT PRIMARY KEY,
        value_json TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        record_hash TEXT NOT NULL
        )"""
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS phase15_darknet_sources_342(
        source_id TEXT PRIMARY KEY,
        onion_host TEXT NOT NULL UNIQUE,
        display_name TEXT NOT NULL,
        source_class TEXT NOT NULL,
        jurisdiction TEXT NOT NULL,
        allowed_use TEXT NOT NULL,
        review_status TEXT NOT NULL,
        risk_class TEXT NOT NULL,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        record_hash TEXT NOT NULL
        )"""
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS phase15_darknet_review_events_342(
        event_id TEXT PRIMARY KEY,
        source_id TEXT NOT NULL,
        decision TEXT NOT NULL,
        rationale TEXT NOT NULL,
        reviewer TEXT NOT NULL,
        created_at TEXT NOT NULL,
        record_hash TEXT NOT NULL,
        FOREIGN KEY(source_id) REFERENCES phase15_darknet_sources_342(source_id)
        )"""
    )
    db.execute(
        "CREATE TRIGGER IF NOT EXISTS trg_phase15_darknet_review342_no_update "
        "BEFORE UPDATE ON phase15_darknet_review_events_342 BEGIN "
        "SELECT RAISE(ABORT,'phase15_darknet_review_events_342 immutable'); END"
    )
    db.execute(
        "CREATE TRIGGER IF NOT EXISTS trg_phase15_darknet_review342_no_delete "
        "BEFORE DELETE ON phase15_darknet_review_events_342 BEGIN "
        "SELECT RAISE(ABORT,'phase15_darknet_review_events_342 immutable'); END"
    )

    policy = {
        "build": "342.0",
        "network_execution": False,
        "policy": "public_or_authorized_read_only",
        "credentials": False,
        "forms": False,
        "uploads": False,
        "contact": False,
        "payments": False,
        "binary_execution": False,
        "access_control_bypass": False,
        "stolen_or_private_dataset_acquisition": False,
        "human_source_approval_required": True,
        "opsec_preflight_required_for_future_external_requests": True,
    }
    now = _now()
    db.execute(
        "INSERT OR REPLACE INTO phase15_build342_state(state_key,value_json,updated_at,record_hash) VALUES(?,?,?,?)",
        ("darknet_research_v2_policy", _canon(policy), now, _hash(policy)),
    )
