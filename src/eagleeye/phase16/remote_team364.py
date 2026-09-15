from __future__ import annotations

import hashlib
import ipaddress
import os
import ssl
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

POLICY = "phase16.remote-team.v364"
AI_POLICY = "phase16.autonomous-investigation.v364"
OPSEC_POLICY = "phase16.defensive-opsec-supervisor.v364"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().casefold() in {"1", "true", "yes", "on"}


def _split_env(name: str) -> list[str]:
    raw = os.environ.get(name, "")
    return [x.strip() for x in raw.replace(";", ",").split(",") if x.strip()]


class RemoteTeamProfile364:
    """Explicit remote-team transport/security profile.

    Local loopback remains the default. Remote mode is opt-in and requires direct
    TLS, explicit allowed hosts and explicit client CIDRs. Build 364 deliberately
    does not trust proxy forwarding headers; reverse-proxy deployment is a later,
    separately validated profile rather than an implicit trust boundary.
    """

    def __init__(self, db: Any, *, identity: Any, governance: Any, base363: Any):
        self.db = db
        self.identity = identity
        self.governance = governance
        self.base363 = base363
        self._last_contract: dict[str, Any] | None = None
        self._last_live: dict[str, Any] | None = None

    def config(self) -> dict[str, Any]:
        enabled = _truthy("EAGLEEYE_REMOTE_TEAM_ENABLED")
        bind_host = os.environ.get("EAGLEEYE_REMOTE_BIND_HOST", "").strip()
        hosts = [h.casefold() for h in _split_env("EAGLEEYE_REMOTE_ALLOWED_HOSTS")]
        cidr_raw = _split_env("EAGLEEYE_REMOTE_ALLOWED_CIDRS")
        cert = os.environ.get("EAGLEEYE_REMOTE_TLS_CERT", "").strip()
        key = os.environ.get("EAGLEEYE_REMOTE_TLS_KEY", "").strip()
        origin = os.environ.get("EAGLEEYE_REMOTE_PUBLIC_ORIGIN", "").strip()
        return {
            "enabled": enabled,
            "bind_host": bind_host,
            "allowed_hosts": hosts,
            "allowed_cidrs": cidr_raw,
            "tls_cert_path": cert,
            "tls_key_path": key,
            "public_origin": origin,
            "proxy_headers_trusted": False,
            "direct_tls_required": True,
        }

    def validate_config(self, *, load_cert_chain: bool = True) -> dict[str, Any]:
        cfg = self.config()
        if not cfg["enabled"]:
            return {"status": "local_only", "valid": True, "remote_enabled": False, "policy": POLICY}
        errors: list[str] = []
        host = cfg["bind_host"]
        if not host:
            errors.append("EAGLEEYE_REMOTE_BIND_HOST required")
        elif host in {"0.0.0.0", "::", "*"}:
            errors.append("wildcard bind is not allowed in Build 364; bind an explicit interface address")
        else:
            try:
                ipaddress.ip_address(host)
            except ValueError:
                errors.append("remote bind host must be an explicit IP address")
        if not cfg["allowed_hosts"]:
            errors.append("EAGLEEYE_REMOTE_ALLOWED_HOSTS required")
        nets = []
        for raw in cfg["allowed_cidrs"]:
            try:
                nets.append(ipaddress.ip_network(raw, strict=False))
            except ValueError:
                errors.append(f"invalid allowed CIDR: {raw}")
        if not nets:
            errors.append("EAGLEEYE_REMOTE_ALLOWED_CIDRS required")
        cert = Path(cfg["tls_cert_path"]) if cfg["tls_cert_path"] else None
        key = Path(cfg["tls_key_path"]) if cfg["tls_key_path"] else None
        if not cert or not cert.is_file():
            errors.append("TLS certificate file required")
        if not key or not key.is_file():
            errors.append("TLS private key file required")
        if cert and key and cert.is_file() and key.is_file() and load_cert_chain:
            try:
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.minimum_version = ssl.TLSVersion.TLSv1_2
                context.load_cert_chain(str(cert), str(key))
            except Exception as exc:
                errors.append(f"TLS certificate/key validation failed: {type(exc).__name__}")
        origin = cfg["public_origin"]
        if origin and not origin.casefold().startswith("https://"):
            errors.append("remote public origin must use https")
        return {
            "status": "pass" if not errors else "blocked",
            "valid": not errors,
            "remote_enabled": True,
            "errors": errors,
            "bind_host": host,
            "allowed_hosts": list(cfg["allowed_hosts"]),
            "allowed_cidrs": list(cfg["allowed_cidrs"]),
            "tls_configured": bool(cert and key and cert.is_file() and key.is_file()),
            "proxy_headers_trusted": False,
            "policy": POLICY,
        }

    @staticmethod
    def _host_without_port(raw: str) -> str:
        value = str(raw or "").strip().casefold()
        if value.startswith("[") and "]" in value:
            return value[1:value.index("]")]
        return value.split(":", 1)[0]

    def request_decision(self, *, scheme: str, host_header: str, client_ip: str, forwarded_headers_present: bool = False) -> dict[str, Any]:
        cfg = self.config()
        if not cfg["enabled"]:
            host = self._host_without_port(host_header)
            allowed = scheme == "http" and host in {"127.0.0.1", "localhost", "::1", "testserver"} and client_ip in {"127.0.0.1", "::1", "testclient"}
            return {"allowed": allowed, "mode": "local", "reason": "loopback_only" if allowed else "non_loopback_denied", "policy": POLICY}
        checked = self.validate_config(load_cert_chain=False)
        if not checked["valid"]:
            return {"allowed": False, "mode": "remote", "reason": "remote_config_invalid", "policy": POLICY}
        if forwarded_headers_present:
            return {"allowed": False, "mode": "remote", "reason": "untrusted_forwarding_headers", "policy": POLICY}
        if str(scheme).casefold() != "https":
            return {"allowed": False, "mode": "remote", "reason": "https_required", "policy": POLICY}
        host = self._host_without_port(host_header)
        if host not in set(cfg["allowed_hosts"]):
            return {"allowed": False, "mode": "remote", "reason": "host_not_allowlisted", "policy": POLICY}
        try:
            ip = ipaddress.ip_address(client_ip)
        except ValueError:
            return {"allowed": False, "mode": "remote", "reason": "invalid_client_ip", "policy": POLICY}
        nets = [ipaddress.ip_network(x, strict=False) for x in cfg["allowed_cidrs"]]
        if not any(ip in net for net in nets):
            return {"allowed": False, "mode": "remote", "reason": "client_network_not_allowlisted", "policy": POLICY}
        return {"allowed": True, "mode": "remote", "reason": "direct_tls_allowlist", "policy": POLICY}

    def status(self) -> dict[str, Any]:
        cfg = self.config(); checked = self.validate_config(load_cert_chain=False)
        contract = self._last_contract or {}
        live = self._last_live or {}
        return {
            "policy": POLICY,
            "mode": "remote" if cfg["enabled"] else "local",
            "remote_enabled": cfg["enabled"],
            "configuration_valid": checked["valid"],
            "direct_tls_required": True,
            "proxy_headers_trusted": False,
            "case_scoped_rbac": True,
            "session_client_binding": True,
            "cross_case_default_deny": True,
            "contract_validation_status": contract.get("status", "not_run"),
            "loopback_tls_validation_status": live.get("status", "not_run"),
            "externally_validated": bool(live.get("externally_validated", False)),
            "external_remote_clients_validated": bool(live.get("external_remote_clients_validated", False)),
            "automatic_external_connections": False,
        }

    def record_contract_validation(self, *, clients: int, cases: int, violations: int) -> dict[str, Any]:
        result = {
            "status": "pass" if clients >= 2 and cases >= 2 and violations == 0 else "fail",
            "clients": int(clients), "cases": int(cases), "violations": int(violations),
            "contract_validated": clients >= 2 and cases >= 2 and violations == 0,
            "externally_validated": False,
            "external_remote_clients_validated": False,
            "network_kind": "in_process_multi_client_contract",
            "policy": POLICY,
        }
        self._last_contract = result
        return result

    def record_loopback_tls_validation(self, *, passed: bool, external_remote_clients: bool = False) -> dict[str, Any]:
        # Loopback TLS proves the direct-TLS server profile, not remote deployment.
        result = {
            "status": "pass" if passed else "fail",
            "loopback_tls_live_validated": bool(passed),
            "external_remote_clients_validated": bool(passed and external_remote_clients),
            "externally_validated": bool(passed and external_remote_clients),
            "policy": POLICY,
            "truthful_note": "Loopback TLS is live transport evidence but is not external remote-team validation.",
        }
        self._last_live = result
        return result

    def session_anomaly(self, *, token: str, observed_fingerprint: str, observed_ip: str = "") -> dict[str, Any]:
        if not token:
            return {"state": "no_session", "blocked": False, "policy": POLICY}
        row = self.db.one("SELECT s.*,u.username FROM phase15_team_sessions s JOIN phase15_team_users u ON u.user_id=s.user_id WHERE s.token_hash=?", (_sha(token),))
        if not row:
            return {"state": "unknown_session", "blocked": False, "policy": POLICY}
        expected = str(row.get("client_fingerprint_hash") or "")
        actual = _sha(observed_fingerprint or "unknown")
        if expected == actual:
            return {"state": "consistent", "blocked": False, "session_id": row["session_id"], "policy": POLICY}
        self.db.execute("UPDATE phase15_team_sessions SET revoked=1,revoked_reason=?,updated_at=? WHERE session_id=?", ("remote_client_fingerprint_mismatch", _now(), row["session_id"]))
        self.identity.record_access(
            user_id=row.get("user_id") or "", username=row.get("username") or "", session_id=row.get("session_id") or "",
            event_type="remote_session_anomaly", capability="session.remote", allowed=False,
            reason="client_fingerprint_mismatch_session_revoked", details={"observed_ip": observed_ip[:128]},
        )
        return {"state": "revoked", "blocked": True, "session_id": row["session_id"], "reason": "client_fingerprint_mismatch", "policy": POLICY}


class AutonomousInvestigation364:
    def __init__(self, db: Any, *, base363: Any, remote364: RemoteTeamProfile364):
        self.db = db; self.base363 = base363; self.remote364 = remote364

    def status(self) -> dict[str, Any]:
        base = dict(self.base363.status())
        base.update({"policy_version": AI_POLICY, "remote_team_context_aware": True, "dossier_records_remote_validation": True, "cross_case_context_isolation_required": True})
        return base

    def run_cycle(self, *, case_id: str, max_ticks: int = 8) -> dict[str, Any]:
        out = self.base363.run_cycle(case_id=case_id, max_ticks=max_ticks)
        dossier = out.get("dossier")
        if isinstance(dossier, dict):
            st = self.remote364.status()
            dossier["phase16_remote_team_context"] = {
                "mode": st["mode"], "remote_enabled": st["remote_enabled"],
                "configuration_valid": st["configuration_valid"],
                "remote_team_externally_validated": st["externally_validated"],
                "cross_case_default_deny": True,
                "lead_review_required": True,
            }
            dossier["lead_review_required"] = True
        return out


class DefensiveOpsecSupervisor364:
    DENIAL_THRESHOLD = 5
    WINDOW_MINUTES = 15

    def __init__(self, db: Any, *, base363: Any, remote364: RemoteTeamProfile364):
        self.db = db; self.base363 = base363; self.remote364 = remote364

    def status(self) -> dict[str, Any]:
        base = dict(self.base363.status())
        base.update({
            "policy_version": OPSEC_POLICY,
            "remote_session_anomaly_monitor": True,
            "cross_case_denial_burst_monitor": True,
            "session_revocation_allowed": True,
            "firewall_mutation": False,
            "os_mutation": False,
            "tor_configuration_mutation": False,
            "system_mutations": False,
        })
        return base

    def protect_remote_session(self, *, token: str, observed_fingerprint: str, observed_ip: str = "") -> dict[str, Any]:
        return self.remote364.session_anomaly(token=token, observed_fingerprint=observed_fingerprint, observed_ip=observed_ip)

    def _revoke_denial_bursts(self, case_id: str) -> list[str]:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=self.WINDOW_MINUTES)).isoformat(timespec="seconds")
        rows = self.db.all(
            "SELECT session_id,COUNT(*) AS n FROM phase15_access_events WHERE case_id=? AND allowed=0 AND session_id<>'' AND created_at>=? GROUP BY session_id HAVING COUNT(*)>=?",
            (case_id, cutoff, self.DENIAL_THRESHOLD),
        )
        revoked: list[str] = []
        for row in rows:
            sid = str(row.get("session_id") or "")
            current = self.db.one("SELECT revoked,user_id FROM phase15_team_sessions WHERE session_id=?", (sid,))
            if not current or int(current.get("revoked") or 0):
                continue
            self.db.execute("UPDATE phase15_team_sessions SET revoked=1,revoked_reason=?,updated_at=? WHERE session_id=?", ("opsec364_denial_burst", _now(), sid))
            revoked.append(sid)
        return revoked

    def protect_case(self, *, case_id: str) -> dict[str, Any]:
        base = self.base363.protect_case(case_id=case_id)
        revoked = self._revoke_denial_bursts(case_id)
        return {**base, "remote_sessions_revoked": revoked, "remote_team_status": self.remote364.status(), "system_mutations": False, "policy_version": OPSEC_POLICY}
