from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qsl, urlsplit

POLICY_VERSION = "phase15.opsec-intelligence.v2"

TRACKING_KEYS = {
    "fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid", "igshid",
    "vero_id", "wickedid", "yclid", "ttclid", "twclid",
}
TRACKING_PREFIXES = ("utm_", "pk_", "mtm_", "oly_")
SECRET_FIELD = re.compile(r"(^|[_-])(password|passwd|token|cookie|authorization|secret|api[_-]?key|private[_-]?key|bearer|session)([_-]|$)", re.I)
SECRET_VALUE_PATTERNS = (
    ("private_key_material", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("jwt_like_token", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("aws_access_key_like", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("generic_bearer", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}")),
)
PROMPT_INJECTION_PATTERNS = (
    ("override_instructions", re.compile(r"(?i)\b(ignore|disregard|forget)\b.{0,40}\b(previous|prior|system|developer)\b.{0,20}\b(instruction|prompt|message)s?\b")),
    ("reveal_system_prompt", re.compile(r"(?i)\b(reveal|print|show|exfiltrate)\b.{0,40}\b(system prompt|developer message|hidden instruction|secret|credential)s?\b")),
    ("tool_abuse_instruction", re.compile(r"(?i)\b(run|execute|call|invoke)\b.{0,30}\b(shell|terminal|powershell|cmd|tool|browser|database)\b")),
    ("download_execute", re.compile(r"(?i)\b(download|fetch)\b.{0,40}\b(execute|run|install|open)\b")),
)
MALICIOUS_CONTENT_PATTERNS = (
    ("script_payload", re.compile(r"(?is)<script\b[^>]*>.*?</script>")),
    ("powershell_command", re.compile(r"(?i)\bpowershell(?:\.exe)?\b.{0,80}(?:-enc|-encodedcommand|invoke-expression|iex)\b")),
    ("shell_command_chain", re.compile(r"(?i)\b(?:curl|wget)\b.{0,120}\|\s*(?:sh|bash|zsh)\b")),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    raw = value if isinstance(value, (bytes, bytearray)) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _is_public_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(str(value).strip())
    except ValueError:
        return False
    return bool(ip.is_global and not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified))


def _tracking_keys(url: str) -> list[str]:
    try:
        pairs = parse_qsl(urlsplit(str(url)).query, keep_blank_values=True)
    except ValueError:
        return []
    found = []
    for key, _ in pairs:
        low = key.casefold()
        if low in TRACKING_KEYS or low.startswith(TRACKING_PREFIXES):
            found.append(key)
    return sorted(set(found))


def _secret_signals(value: Any, path: str = "") -> list[str]:
    signals: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            name = str(key)
            child = f"{path}.{name}" if path else name
            if SECRET_FIELD.search(name):
                signals.append(f"secret_field:{child}")
            signals.extend(_secret_signals(item, child))
    elif isinstance(value, (list, tuple)):
        for idx, item in enumerate(value):
            signals.extend(_secret_signals(item, f"{path}[{idx}]"))
    elif isinstance(value, str):
        text = value[:200000]
        for label, pattern in SECRET_VALUE_PATTERNS:
            if pattern.search(text):
                signals.append(f"secret_value:{label}:{path or 'value'}")
    return sorted(set(signals))


class OPSECIntelligenceV2:
    """Deterministic, fail-closed OPSEC intelligence for Phase 15.

    This component does not open sockets, resolve DNS, change firewall/proxy/Tor/OS
    settings, or execute content. It evaluates descriptors/results supplied by a
    future controlled gateway and persists Security Evidence. Statistical/ML risk
    ranking may be added later, but cannot override these deterministic blocks.
    """

    def __init__(self, db: Any, actor: str = "local-analyst") -> None:
        self.db = db
        self.actor = actor

    def _capsule(self, search_run_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM phase15_search_capsules WHERE search_run_id=?", (search_run_id,))
        if not row:
            raise KeyError(search_run_id)
        row["egress_allowlist"] = json.loads(row["egress_allowlist_json"])
        return row

    def _record(self, *, search_run_id: str, stage: str, disposition: str, severity: str, risk_score: int, signals: Sequence[str], evidence: Mapping[str, Any]) -> dict[str, Any]:
        capsule = self._capsule(search_run_id)
        assessment_id = "opsec346_" + uuid.uuid4().hex[:20]
        created = _now()
        clean_evidence = dict(evidence)
        secret_signals = _secret_signals(clean_evidence)
        if secret_signals:
            clean_evidence = {"redacted": True, "secret_signal_count": len(secret_signals), "digest": _sha(evidence)}
        body = {
            "assessment_id": assessment_id,
            "search_run_id": search_run_id,
            "case_id": capsule["case_id"],
            "stage": stage,
            "disposition": disposition,
            "severity": severity,
            "risk_score": int(risk_score),
            "signals": sorted(set(signals)),
            "evidence": clean_evidence,
            "policy_version": POLICY_VERSION,
            "created_at": created,
        }
        self.db.execute(
            "INSERT INTO phase15_opsec_assessments(assessment_id,search_run_id,case_id,stage,disposition,severity,risk_score,signals_json,evidence_json,policy_version,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (assessment_id, search_run_id, capsule["case_id"], stage, disposition, severity, int(risk_score), _canon(body["signals"]), _canon(clean_evidence), POLICY_VERSION, self.actor, created, _sha(body)),
        )
        self.db.execute(
            "INSERT INTO phase15_security_events(security_event_id,case_id,search_run_id,event_type,disposition,severity,policy_version,evidence_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            ("sec346_" + uuid.uuid4().hex[:20], capsule["case_id"], search_run_id, f"opsec_v2_{stage}", disposition, severity, POLICY_VERSION, _canon({"assessment_id": assessment_id, "signals": body["signals"], "risk_score": int(risk_score), "evidence": clean_evidence}), created),
        )
        return body

    def assess_request_descriptor(
        self,
        search_run_id: str,
        *,
        url: str,
        headers: Mapping[str, Any] | None = None,
        resolved_ips: Sequence[str] | None = None,
        redirect_from: str | None = None,
        browser_webrtc_disabled: bool | None = None,
        dns_via_approved_profile: bool | None = None,
    ) -> dict[str, Any]:
        capsule = self._capsule(search_run_id)
        signals: list[str] = []
        hard_blocks: list[str] = []
        risk = 0
        try:
            parsed = urlsplit(str(url))
            host = (parsed.hostname or "").lower().rstrip(".")
        except ValueError:
            host = ""
            hard_blocks.append("invalid_url")
        tracking = _tracking_keys(url)
        if tracking:
            signals.append("tracking_parameters_present")
            risk += min(15, len(tracking) * 3)
        secret_signals = _secret_signals(dict(headers or {}))
        if secret_signals:
            signals.extend(secret_signals)
            hard_blocks.append("secret_exposure_in_headers")
            risk += 60
        ips = [str(v).strip() for v in (resolved_ips or []) if str(v).strip()]
        if capsule["search_kind"] == "darknet":
            if ips:
                hard_blocks.append("onion_resolution_must_not_use_local_dns")
                risk += 80
            if dns_via_approved_profile is False:
                hard_blocks.append("approved_tor_dns_path_not_confirmed")
                risk += 80
        else:
            for ip in ips:
                if not _is_public_ip(ip):
                    hard_blocks.append("ssrf_or_dns_rebinding_nonpublic_resolution")
                    risk += 90
                    break
        if browser_webrtc_disabled is not True:
            hard_blocks.append("webrtc_leakage_control_unverified" if browser_webrtc_disabled is None else "webrtc_leakage_control_failed")
            risk += 90
        if dns_via_approved_profile is not True:
            hard_blocks.append("dns_profile_control_unverified" if dns_via_approved_profile is None else "dns_profile_control_failed")
            risk += 90
        if capsule["search_kind"] == "clearnet" and not ips:
            hard_blocks.append("resolved_ip_evidence_missing")
            risk += 70
        if redirect_from:
            try:
                old_host = (urlsplit(redirect_from).hostname or "").lower().rstrip(".")
            except ValueError:
                old_host = ""
            if old_host and host and old_host != host:
                signals.append("cross_host_redirect")
                risk += 25
                if host not in set(capsule["egress_allowlist"]):
                    hard_blocks.append("redirect_egress_escape")
        disposition = "block" if hard_blocks else ("allow_with_sanitization" if tracking else "allow")
        if hard_blocks:
            severity = "critical" if risk >= 80 else "high"
        elif risk >= 30:
            severity = "medium"
        elif risk:
            severity = "low"
        else:
            severity = "info"
        return self._record(
            search_run_id=search_run_id,
            stage="request_descriptor",
            disposition=disposition,
            severity=severity,
            risk_score=min(100, risk),
            signals=signals + hard_blocks,
            evidence={"target_host": host, "tracking_keys": tracking, "resolved_ip_count": len(ips), "redirect_present": bool(redirect_from)},
        )

    def inspect_content(
        self,
        search_run_id: str,
        *,
        content_text: str,
        content_type: str = "text/plain",
        source_url: str = "",
        declared_download: bool = False,
        attachment_name: str = "",
    ) -> dict[str, Any]:
        text = str(content_text or "")[:500000]
        signals: list[str] = []
        risk = 0
        for label, pattern in PROMPT_INJECTION_PATTERNS:
            if pattern.search(text):
                signals.append(f"prompt_injection:{label}")
                risk += 35
        for label, pattern in MALICIOUS_CONTENT_PATTERNS:
            if pattern.search(text):
                signals.append(f"malicious_content:{label}")
                risk += 45
        secret_signals = _secret_signals(text)
        if secret_signals:
            signals.extend(secret_signals)
            risk += 60
        ext = attachment_name.lower().rsplit(".", 1)[-1] if "." in attachment_name else ""
        if declared_download or ext in {"exe", "dll", "msi", "scr", "bat", "cmd", "ps1", "jar", "apk"}:
            signals.append("active_or_executable_content")
            risk += 70
        disposition = "quarantine" if signals else "allow_for_analysis"
        severity = "critical" if risk >= 80 else "high" if risk >= 50 else "medium" if risk >= 25 else "info"
        return self._record(
            search_run_id=search_run_id,
            stage="content_inspection",
            disposition=disposition,
            severity=severity,
            risk_score=min(100, risk),
            signals=signals,
            evidence={"source_url_hash": _sha(source_url), "content_sha256": _sha(text.encode("utf-8")), "content_type": content_type, "attachment_name": attachment_name, "content_length": len(text)},
        )

    def register_training_case(
        self,
        *,
        case_key: str,
        category: str,
        source_ref: str,
        license_or_terms: str,
        payload: Mapping[str, Any],
        expected_label: str,
        split: str,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        split = str(split).strip().lower()
        if split not in {"train", "validation", "test"}:
            raise ValueError("split must be train, validation or test")
        training_id = "optrain346_" + uuid.uuid4().hex[:20]
        created = _now()
        payload_hash = _sha(payload)
        self.db.execute(
            "INSERT INTO phase15_opsec_training_cases(training_id,case_key,category,source_ref,license_or_terms,payload_hash,expected_label,split,review_state,reviewer_id,reviewed_at,label_reason,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (training_id, case_key, category, source_ref, license_or_terms, payload_hash, expected_label, split, "unreviewed", None, None, None, created_by or self.actor, created, _sha({"training_id": training_id, "case_key": case_key, "category": category, "payload_hash": payload_hash, "expected_label": expected_label, "split": split, "created_at": created})),
        )
        return self.db.one("SELECT * FROM phase15_opsec_training_cases WHERE training_id=?", (training_id,))

    def review_training_case(self, training_id: str, *, reviewer_id: str, label_reason: str, human_review: bool) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM phase15_opsec_training_cases WHERE training_id=?", (training_id,))
        if not row:
            raise KeyError(training_id)
        if row["review_state"] != "unreviewed":
            raise PermissionError("training review is append-once")
        if not reviewer_id.strip() or not label_reason.strip():
            raise ValueError("reviewer_id and label_reason required")
        state = "human_reviewed" if human_review else "automated_or_synthetic_review"
        reviewed_at = _now()
        self.db.execute(
            "UPDATE phase15_opsec_training_cases SET review_state=?,reviewer_id=?,reviewed_at=?,label_reason=? WHERE training_id=? AND review_state='unreviewed'",
            (state, reviewer_id.strip(), reviewed_at, label_reason.strip(), training_id),
        )
        return self.db.one("SELECT * FROM phase15_opsec_training_cases WHERE training_id=?", (training_id,))

    def training_status(self) -> dict[str, int]:
        rows = self.db.all("SELECT review_state,COUNT(*) c FROM phase15_opsec_training_cases GROUP BY review_state")
        counts = {str(r["review_state"]): int(r["c"]) for r in rows}
        return {
            "total": sum(counts.values()),
            "unreviewed": counts.get("unreviewed", 0),
            "human_reviewed": counts.get("human_reviewed", 0),
            "automated_or_synthetic_review": counts.get("automated_or_synthetic_review", 0),
        }

    def assessments(self, search_run_id: str, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.db.all("SELECT * FROM phase15_opsec_assessments WHERE search_run_id=? ORDER BY created_at,assessment_id LIMIT ?", (search_run_id, max(1, min(int(limit), 500))))
        for row in rows:
            row["signals"] = json.loads(row["signals_json"])
            row["evidence"] = json.loads(row["evidence_json"])
        return rows
