from __future__ import annotations

import hashlib
import http.client
import ipaddress
import json
import socket
import ssl
import struct
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit

from eagleeye.crawler.engine import FetchResponse, StaticTransport, USER_AGENT, VALID_ONION

POLICY = "phase16.controlled-tor-gateway.v370"
AI_POLICY = "phase16.autonomous-investigation.v370"
OPSEC_POLICY = "phase16.defensive-opsec-supervisor.v370"
TOR_JOB = "governed_tor_crawl_v370"
FORBIDDEN_HEADERS = {"authorization", "cookie", "proxy-authorization", "referer", "x-api-key"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    raw = value if isinstance(value, (bytes, bytearray)) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_exact(sock: socket.socket, n: int) -> bytes:
    out = bytearray()
    while len(out) < n:
        chunk = sock.recv(n - len(out))
        if not chunk:
            raise ConnectionError("SOCKS gateway closed the connection")
        out.extend(chunk)
    return bytes(out)


def _clean_onion_url(url: str) -> tuple[str, str, int, str]:
    p = urlsplit(str(url or "").strip())
    if p.scheme.lower() not in {"http", "https"} or not p.hostname:
        raise ValueError("Tor gateway accepts absolute http/https onion URLs only")
    if p.username is not None or p.password is not None:
        raise ValueError("userinfo/credentials in onion URLs are forbidden")
    host = p.hostname.lower().rstrip(".")
    if not VALID_ONION.fullmatch(host):
        raise PermissionError("Build 370 Tor gateway is restricted to exact reviewed v3 onion hosts")
    port = p.port
    if port not in {None, 80, 443}:
        raise ValueError("non-standard target ports are not allowed")
    target_port = int(port or (443 if p.scheme.lower() == "https" else 80))
    netloc = host if port is None else f"{host}:{port}"
    clean = urlunsplit((p.scheme.lower(), netloc, p.path or "/", p.query, ""))
    path = (p.path or "/") + (("?" + p.query) if p.query else "")
    return clean, host, target_port, path


class StaticTorReplayTransport370(StaticTransport):
    """Deterministic Tor-labelled replay transport. It opens no sockets."""

    transport_kind = "tor_static_replay_v370"
    externally_configured = False


class Socks5TorReadOnlyTransport370:
    """Minimal read-only SOCKS5 client for a *local* Tor SOCKSPort.

    The transport never resolves the onion hostname locally, never talks to a Tor
    ControlPort, never starts/reconfigures Tor and never accepts credentials/cookies
    for the destination. A unique SOCKS username/password pair is used only as a
    Tor stream-isolation token for one search capsule.
    """

    transport_kind = "tor_socks5_loopback_isolated_v370"
    externally_configured = True

    def __init__(
        self,
        *,
        socks_host: str,
        socks_port: int,
        isolation_username: str,
        isolation_password: str,
        ca_file: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        try:
            ip = ipaddress.ip_address(str(socks_host).strip())
        except ValueError as exc:
            raise ValueError("Tor SOCKS endpoint must be a literal loopback IP") from exc
        if not ip.is_loopback:
            raise PermissionError("Tor SOCKS endpoint must be loopback-only")
        self.socks_host = str(ip)
        self.socks_port = int(socks_port)
        if not (1 <= self.socks_port <= 65535):
            raise ValueError("invalid Tor SOCKS port")
        self.isolation_username = str(isolation_username)[:200]
        self.isolation_password = str(isolation_password)[:200]
        if not self.isolation_username or not self.isolation_password:
            raise ValueError("SOCKS authentication isolation token required")
        if len(self.isolation_username.encode()) > 255 or len(self.isolation_password.encode()) > 255:
            raise ValueError("SOCKS isolation token too long")
        self.user_agent = str(user_agent or USER_AGENT)[:300]
        self._ssl = ssl.create_default_context(cafile=ca_file) if ca_file else ssl.create_default_context()
        self.last_target_host = ""
        self.last_socks_method = -1
        self.local_dns_used = False

    def _socks_connect(self, target_host: str, target_port: int, timeout_seconds: int) -> socket.socket:
        sock = socket.create_connection((self.socks_host, self.socks_port), timeout=max(1, min(int(timeout_seconds), 60)))
        sock.settimeout(max(1, min(int(timeout_seconds), 60)))
        try:
            # Offer only RFC1929 username/password so IsolateSOCKSAuth can separate capsules.
            sock.sendall(b"\x05\x01\x02")
            ver, method = _read_exact(sock, 2)
            self.last_socks_method = method
            if ver != 5 or method != 2:
                raise ConnectionError("Tor SOCKS endpoint did not accept authentication isolation")
            u = self.isolation_username.encode("utf-8"); p = self.isolation_password.encode("utf-8")
            sock.sendall(b"\x01" + bytes([len(u)]) + u + bytes([len(p)]) + p)
            av, status = _read_exact(sock, 2)
            if av != 1 or status != 0:
                raise ConnectionError("Tor SOCKS authentication/isolation negotiation failed")
            host_b = target_host.encode("ascii")
            if len(host_b) > 255:
                raise ValueError("target hostname too long for SOCKS5 domain request")
            # ATYP=DOMAIN sends the onion hostname to Tor; no local DNS lookup occurs.
            sock.sendall(b"\x05\x01\x00\x03" + bytes([len(host_b)]) + host_b + struct.pack("!H", int(target_port)))
            head = _read_exact(sock, 4)
            if head[0] != 5 or head[1] != 0:
                raise ConnectionError(f"Tor SOCKS connect failed with code {head[1] if len(head)>1 else -1}")
            atyp = head[3]
            if atyp == 1:
                _read_exact(sock, 4)
            elif atyp == 3:
                _read_exact(sock, _read_exact(sock, 1)[0])
            elif atyp == 4:
                _read_exact(sock, 16)
            else:
                raise ConnectionError("invalid SOCKS reply address type")
            _read_exact(sock, 2)
            self.last_target_host = target_host
            return sock
        except Exception:
            sock.close()
            raise

    def fetch(self, url: str, *, method: str = "GET", headers: Mapping[str, str] | None = None, timeout_seconds: int = 20, max_bytes: int = 2_000_000) -> FetchResponse:
        clean, host, target_port, path = _clean_onion_url(url)
        method_u = str(method or "GET").upper()
        if method_u not in {"GET", "HEAD"}:
            raise PermissionError("Build 370 Tor gateway is read-only")
        supplied = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
        if any(k in FORBIDDEN_HEADERS for k in supplied):
            raise PermissionError("destination credentials/cookies/referrers are forbidden")
        # Do not allow callers to override routing-critical headers.
        supplied.pop("host", None); supplied.pop("connection", None); supplied.pop("accept-encoding", None)
        request_headers = {"Host": host, "User-Agent": self.user_agent, "Accept": "text/html,text/plain,application/json,application/xml;q=0.9,*/*;q=0.5", "Connection": "close"}
        request_headers.update({k: v for k, v in supplied.items()})
        started = datetime.now(timezone.utc)
        raw = self._socks_connect(host, target_port, timeout_seconds)
        stream: socket.socket = raw
        try:
            if clean.startswith("https://"):
                stream = self._ssl.wrap_socket(raw, server_hostname=host)
            lines = [f"{method_u} {path} HTTP/1.1"] + [f"{k}: {v}" for k, v in request_headers.items()] + ["", ""]
            stream.sendall("\r\n".join(lines).encode("iso-8859-1"))
            response = http.client.HTTPResponse(stream)
            response.begin()
            body = response.read(max(1, int(max_bytes)) + 1) if method_u == "GET" else b""
            if len(body) > int(max_bytes):
                raise ValueError("response exceeds configured max_bytes")
            hdrs = {str(k).lower(): str(v) for k, v in response.getheaders()}
            elapsed = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
            return FetchResponse(url=clean, status=int(response.status), headers=hdrs, body=body, elapsed_ms=max(0, elapsed))
        finally:
            try: stream.close()
            except Exception: pass
            if stream is not raw:
                try: raw.close()
                except Exception: pass


class ControlledTorGateway370:
    """Operator-controlled Tor gateway + Tor-specific crawler queue overlay."""

    def __init__(self, db: Any, audit: Any, *, build369: Any, jobs: Any, crawler: Any, governance: Any, identity: Any, actor: str = "local-analyst") -> None:
        self.db=db; self.audit=audit; self.build369=build369; self.jobs=jobs; self.crawler=crawler; self.governance=governance; self.identity=identity; self.actor=actor

    @staticmethod
    def _config_from_row(row: Mapping[str, Any] | None) -> dict[str, Any]:
        row = row or {}
        try: cfg=json.loads(str(row.get("config_ref") or "{}"))
        except Exception: cfg={}
        if not isinstance(cfg,dict) or cfg.get("policy") != POLICY: cfg={}
        return {
            "enabled": bool(int(row.get("runtime_execution_enabled") or 0)) and bool(cfg.get("enabled")),
            "socks_host": str(cfg.get("socks_host") or "127.0.0.1"),
            "socks_port": int(cfg.get("socks_port") or 9050),
            "remote_dns_required": True,
            "isolate_socks_auth_required": True,
            "configured_at": str(cfg.get("configured_at") or ""),
            "configured_by": str(cfg.get("configured_by") or ""),
            "policy": POLICY,
        }

    def config(self) -> dict[str, Any]:
        row=self.db.one("SELECT * FROM phase15_network_profiles WHERE profile_id='tor_read_only_v1'")
        return self._config_from_row(row)

    def _require_admin(self, identity: dict[str, Any]) -> None:
        if str(identity.get("global_role") or "") != "system_administrator":
            raise PermissionError("system administrator required for Tor gateway configuration")

    def configure(self, *, identity: dict[str, Any], confirmation: str, enabled: bool, socks_host: str = "127.0.0.1", socks_port: int = 9050) -> dict[str, Any]:
        self._require_admin(identity)
        word=str(confirmation or "").strip().upper(); required="ENABLE_TOR" if enabled else "DISABLE_TOR"
        if word != required: raise PermissionError(f"explicit confirmation {required} required")
        try: ip=ipaddress.ip_address(str(socks_host).strip())
        except ValueError as exc: raise ValueError("Tor SOCKS host must be a literal loopback IP") from exc
        if not ip.is_loopback: raise PermissionError("Tor SOCKS endpoint must remain loopback-only")
        port=int(socks_port)
        if not (1 <= port <= 65535): raise ValueError("invalid Tor SOCKS port")
        cfg={"enabled":bool(enabled),"socks_host":str(ip),"socks_port":port,"remote_dns_required":True,"isolate_socks_auth_required":True,"configured_at":_now(),"configured_by":str(identity.get("username") or self.actor)[:160],"policy":POLICY}
        row=self.db.one("SELECT * FROM phase15_network_profiles WHERE profile_id='tor_read_only_v1'")
        if not row: raise KeyError("tor_read_only_v1")
        record={"profile_id":"tor_read_only_v1","profile_kind":"approved_tor","display_name":row["display_name"],"allowed_schemes_json":row["allowed_schemes_json"],"dns_mode":"proxy_resolution_required_no_local_onion_dns","webrtc_mode":row["webrtc_mode"],"system_mutation_allowed":0,"runtime_execution_enabled":1 if enabled else 0,"review_status":"approved_policy","config_ref":_canon(cfg),"created_at":row["created_at"]}
        self.db.execute("UPDATE phase15_network_profiles SET dns_mode=?,system_mutation_allowed=0,runtime_execution_enabled=?,review_status='approved_policy',config_ref=?,record_hash=? WHERE profile_id='tor_read_only_v1'",(record["dns_mode"],record["runtime_execution_enabled"],record["config_ref"],_sha(record)))
        self.audit.log("TOR370_GATEWAY_CONFIG","network_profile","tor_read_only_v1",details={"enabled":bool(enabled),"socks_host":str(ip),"socks_port":port,"configured_by":cfg["configured_by"],"policy":POLICY})
        return self.status()

    def isolation_credentials(self, search_run_id: str) -> dict[str, str]:
        cfg=self.config(); fp=_sha({"host":cfg["socks_host"],"port":cfg["socks_port"],"policy":POLICY})
        token=_sha({"search_run_id":str(search_run_id),"gateway":fp,"purpose":"socks_auth_isolation_v370"})
        return {"username":"ee370-"+token[:20],"password":token[20:60],"fingerprint":_sha(token)}

    def make_transport(self, *, search_run_id: str) -> Socks5TorReadOnlyTransport370:
        cfg=self.config()
        if not cfg["enabled"]: raise PermissionError("Tor gateway is disabled")
        creds=self.isolation_credentials(search_run_id)
        return Socks5TorReadOnlyTransport370(socks_host=cfg["socks_host"],socks_port=cfg["socks_port"],isolation_username=creds["username"],isolation_password=creds["password"])

    def local_socks_probe(self, *, timeout_seconds: int = 2) -> dict[str, Any]:
        cfg=self.config()
        if not cfg["enabled"]:
            return {"status":"not_run","reason":"gateway_disabled","policy":POLICY,"external_network":False}
        try:
            sock=socket.create_connection((cfg["socks_host"],cfg["socks_port"]),timeout=max(1,min(int(timeout_seconds),5)))
            with sock:
                sock.settimeout(max(1,min(int(timeout_seconds),5))); sock.sendall(b"\x05\x01\x02"); reply=_read_exact(sock,2)
            ok=reply==b"\x05\x02"
            return {"status":"pass" if ok else "fail","socks5_auth_isolation_method":ok,"loopback_endpoint":True,"external_network":False,"tor_daemon_identity_proven":False,"policy":POLICY}
        except Exception as exc:
            return {"status":"fail","error":type(exc).__name__,"loopback_endpoint":True,"external_network":False,"tor_daemon_identity_proven":False,"policy":POLICY}

    def _source(self, source_id: str) -> dict[str, Any]:
        return self.crawler._source(source_id)

    def tor_backpressure(self, *, case_id: str) -> dict[str, Any]:
        g=self.db.one("SELECT COUNT(*) c,SUM(CASE WHEN status='running' THEN 1 ELSE 0 END) r FROM phase15_jobs WHERE job_type=? AND status IN ('queued','running')",(TOR_JOB,)) or {}
        c=self.db.one("SELECT COUNT(*) c,SUM(CASE WHEN status='running' THEN 1 ELSE 0 END) r FROM phase15_jobs WHERE job_type=? AND case_id=? AND status IN ('queued','running')",(TOR_JOB,str(case_id))) or {}
        gd=int(g.get("c") or 0); cd=int(c.get("c") or 0)
        return {"policy":POLICY,"case_id":case_id,"global_depth":gd,"case_depth":cd,"global_running":int(g.get("r") or 0),"case_running":int(c.get("r") or 0),"global_high_watermark":8,"case_high_watermark":2,"accept_new_tor_work":gd<8 and cd<2}

    def enqueue_darknet_crawl(self, *, case_id: str, source_id: str, identity: dict[str, Any], confirmation: str) -> dict[str, Any]:
        self.governance.authorize(identity,case_id=case_id,capability="crawler.run",object_type="tor_crawl",object_id=source_id)
        if str(confirmation or "").strip().upper() != "TOR_LIVE": raise PermissionError("explicit confirmation TOR_LIVE required")
        cfg=self.config()
        if not cfg["enabled"]: raise PermissionError("Tor gateway must be explicitly enabled by an administrator")
        pressure=self.tor_backpressure(case_id=case_id)
        if not pressure["accept_new_tor_work"]: raise RuntimeError("Tor crawler backpressure hold")
        source=self._source(source_id)
        if source["source_kind"]!="darknet_onion" or source["review_status"]!="approved_read_only" or int(source["enabled"])!=1 or source["auth_type"]!="none":
            raise PermissionError("exact human-reviewed unauthenticated v3 onion source required")
        research=self.crawler.build348.create_darknet_research(case_id=case_id,query=f"controlled Tor crawl: {source['display_name']}",source_ids=[source_id],human_approved=True,max_requests=int(source["max_pages"])+3,actor=str(identity.get("username") or self.actor))
        search_run_id=research["capsule"]["search_run_id"]
        crawl_run_id="crawl370_"+uuid.uuid4().hex[:20]; now=_now()
        run={"crawl_run_id":crawl_run_id,"case_id":case_id,"source_id":source_id,"search_run_id":search_run_id,"status":"queued","pages_fetched":0,"pages_stored":0,"bytes_fetched":0,"started_at":None,"completed_at":None,"created_at":now,"summary_json":"{}"}
        self.db.execute("INSERT INTO phase15_crawl_runs(crawl_run_id,case_id,source_id,search_run_id,status,pages_fetched,pages_stored,bytes_fetched,started_at,completed_at,created_at,summary_json,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(*run.values(),_sha(run)))
        creds=self.isolation_credentials(search_run_id); config_fp=_sha(cfg)
        job=self.jobs.enqueue(job_type=TOR_JOB,case_id=case_id,search_run_id=search_run_id,idempotency_key=f"tor370:{crawl_run_id}",payload={"crawl_run_id":crawl_run_id,"source_id":source_id,"read_only":True,"phase16_tor370_manual":True,"phase16_tor370_confirmation":True,"gateway_profile":"tor_read_only_v1","gateway_config_fingerprint":config_fp,"isolation_fingerprint":creds["fingerprint"],"network_execution_by_tor370_worker":True},max_attempts=3,priority=90,resource_budget={"max_runtime_seconds":900,"max_memory_mb":512,"max_output_bytes":int(source["max_pages"])*int(source["max_response_bytes"])},rate_budget={"max_requests":int(source["max_pages"])+3,"requests_per_minute":min(int(source["requests_per_minute"]),12)})
        self.audit.log("TOR370_CRAWL_ENQUEUED","crawl_run",crawl_run_id,case_id=case_id,details={"source_id":source_id,"job_id":job["job_id"],"gateway_config_fingerprint":config_fp,"isolation_fingerprint":creds["fingerprint"],"policy":POLICY})
        return {"policy":POLICY,"crawl_run_id":crawl_run_id,"search_run_id":search_run_id,"job":job,"source_id":source_id,"manual_confirmation":True,"network_execution":False,"tor_backpressure":self.tor_backpressure(case_id=case_id)}

    def claim_next(self, *, worker_id: str, case_id: str = "", lease_seconds: int = 300) -> dict[str, Any] | None:
        now=_now(); from datetime import timedelta
        expiry=(datetime.now(timezone.utc)+timedelta(seconds=max(60,min(int(lease_seconds),1800)))).isoformat(timespec="seconds")
        params:[Any]=[TOR_JOB,now]; clause=""
        if case_id: clause=" AND case_id=?"; params.append(case_id)
        rows=self.db.all("SELECT job_id,payload_json,case_id FROM phase15_jobs WHERE job_type=? AND status='queued' AND available_at<=?"+clause+" ORDER BY priority ASC,created_at ASC LIMIT 20",tuple(params))
        for row in rows:
            payload=json.loads(row.get("payload_json") or "{}")
            if payload.get("phase16_tor370_manual") is not True or payload.get("phase16_tor370_confirmation") is not True: continue
            cur=self.db.execute("UPDATE phase15_jobs SET status='running',attempts=attempts+1,lease_owner=?,lease_expires_at=?,updated_at=? WHERE job_id=? AND status='queued'",(str(worker_id)[:120],expiry,now,row["job_id"]))
            if cur.rowcount==1: return self.jobs.get(row["job_id"])
        return None

    def renew_lease(self, *, job_id: str, worker_id: str, lease_seconds: int = 300) -> dict[str, Any]:
        expiry=(datetime.now(timezone.utc)+__import__('datetime').timedelta(seconds=max(60,min(int(lease_seconds),1800)))).isoformat(timespec="seconds")
        cur=self.db.execute("UPDATE phase15_jobs SET lease_expires_at=?,updated_at=? WHERE job_id=? AND job_type=? AND status='running' AND lease_owner=?",(expiry,_now(),job_id,TOR_JOB,worker_id))
        if cur.rowcount!=1: raise PermissionError("active Tor crawler worker lease required")
        return self.jobs.get(job_id)

    def recover_expired_leases(self, *, case_id: str = "") -> dict[str, Any]:
        params:[Any]=[TOR_JOB,_now()]; clause=""
        if case_id: clause=" AND case_id=?"; params.append(case_id)
        rows=self.db.all("SELECT job_id,search_run_id,case_id,lease_owner,checkpoint_json FROM phase15_jobs WHERE job_type=? AND status='running' AND lease_expires_at<>'' AND lease_expires_at<?"+clause,tuple(params)); recovered=[]
        for row in rows:
            self.db.execute("UPDATE phase15_jobs SET status='queued',lease_owner='',lease_expires_at='',available_at=?,updated_at=? WHERE job_id=? AND status='running'",(_now(),_now(),row["job_id"]))
            self.db.execute("UPDATE phase15_crawl_runs SET status='paused' WHERE search_run_id=? AND status='running'",(row["search_run_id"],)); recovered.append(row["job_id"])
        if recovered:self.audit.log("TOR370_LEASE_RECOVERY","case",case_id or "all",case_id=case_id or None,details={"recovered_jobs":recovered,"policy":POLICY})
        return {"policy":POLICY,"recovered_jobs":recovered,"checkpoint_preserved":True}

    def run_next(self, *, worker_id: str, case_id: str = "", transport: Any | None = None, lease_seconds: int = 300) -> dict[str, Any] | None:
        job=self.claim_next(worker_id=worker_id,case_id=case_id,lease_seconds=lease_seconds)
        if not job:return None
        cid=str(job.get("case_id") or ""); payload=json.loads(job.get("payload_json") or "{}")
        if cid:
            self.build369.autonomous_opsec_protect(case_id=cid)
            job=self.jobs.get(job["job_id"])
            if job["status"]!="running": return {"state":"opsec_stopped","job":job,"policy":POLICY}
        if not self.config()["enabled"]:
            self.jobs.cancel(job["job_id"],actor="tor370"); return {"state":"gateway_disabled","job":self.jobs.get(job["job_id"]),"policy":POLICY}
        tx=transport or self.make_transport(search_run_id=str(job["search_run_id"]))
        kind=str(getattr(tx,"transport_kind",""))
        if not kind.startswith("tor_"): raise PermissionError("Tor worker requires Tor-labelled transport")
        # Renew around each fetch without changing transport routing.
        outer=self
        class Heartbeat:
            transport_kind=kind; externally_configured=bool(getattr(tx,"externally_configured",False))
            def fetch(self,_url,**kw):
                outer.renew_lease(job_id=job["job_id"],worker_id=worker_id,lease_seconds=lease_seconds); out=tx.fetch(_url,**kw); outer.renew_lease(job_id=job["job_id"],worker_id=worker_id,lease_seconds=lease_seconds); return out
        result=self.crawler.execute_claimed_job(job_id=job["job_id"],worker_id=worker_id,transport=Heartbeat(),resolver=lambda _host: [])
        crawl_run_id=str(payload.get("crawl_run_id") or ""); sid=str(payload.get("source_id") or "")
        health=self.build369.crawler369.record_production_health(source_id=sid,crawl_run_id=crawl_run_id) if sid and crawl_run_id else {}
        self.audit.log("TOR370_WORKER_RESULT","crawler_job",job["job_id"],case_id=cid,details={"crawl_run_id":crawl_run_id,"source_id":sid,"status":result.get("status"),"transport_kind":kind,"policy":POLICY})
        return {"policy":POLICY,"job":result,"source_health_event":health,"transport_kind":kind,"tor_isolation_fingerprint":payload.get("isolation_fingerprint"),"local_onion_dns_used":False}

    def case_status(self, *, case_id: str) -> dict[str, Any]:
        rows=self.db.all("SELECT job_id,status,payload_json,search_run_id,created_at FROM phase15_jobs WHERE case_id=? AND job_type=? ORDER BY created_at DESC LIMIT 100",(str(case_id),TOR_JOB))
        return {"policy":POLICY,"case_id":case_id,"gateway":self.status(),"backpressure":self.tor_backpressure(case_id=case_id),"jobs":[{"job_id":r["job_id"],"status":r["status"],"search_run_id":r["search_run_id"],"created_at":r["created_at"]} for r in rows],"manual_only":True,"recurring_scheduler":False,"automatic_scope_expansion":False}

    def crawler_roadmap_370_380(self) -> list[dict[str, Any]]:
        return [
            {"build":370,"crawler_increment":"Tor-specific queue, SOCKS-auth capsule isolation, Tor backpressure, Tor lease/recovery"},
            {"build":371,"crawler_increment":"entity-linked crawl provenance and source-to-entity lead queues without auto-merge"},
            {"build":372,"crawler_increment":"crawler/entity-resolution evaluation corpus, false-link and source-quality calibration"},
            {"build":373,"crawler_increment":"graph-aware but human-bounded source navigation and traversal budgets"},
            {"build":374,"crawler_increment":"case workflow orchestration, source budgets, pause/resume and analyst handoff"},
            {"build":375,"crawler_increment":"AI crawl-planning evaluation, coverage metrics and scope-expansion denial tests"},
            {"build":376,"crawler_increment":"dossier source-coverage, negative-evidence and stale-source metrics"},
            {"build":377,"crawler_increment":"image/media crawling provenance, deduplication and object-store pressure controls"},
            {"build":378,"crawler_increment":"voice-to-crawl intent confirmation with no direct voice network authority"},
            {"build":379,"crawler_increment":"external soak/load/failure qualification and recovery SLO measurement"},
            {"build":380,"crawler_increment":"professional-pilot telemetry, SLO gate and production decision"},
        ]

    def status(self) -> dict[str, Any]:
        cfg=self.config(); row=self.db.one("SELECT COUNT(*) c FROM phase15_jobs WHERE job_type=? AND status IN ('queued','running')",(TOR_JOB,)) or {}
        return {"policy":POLICY,"gateway_enabled":cfg["enabled"],"socks_host":cfg["socks_host"],"socks_port":cfg["socks_port"],"loopback_only":True,"remote_dns_required":True,"isolate_socks_auth_required":True,"control_port_authority":False,"newnym_authority":False,"torrc_mutation":False,"tor_process_spawn":False,"destination_credentials_supported":False,"forms_uploads_payments_supported":False,"access_control_bypass_supported":False,"stolen_private_dataset_acquisition_supported":False,"manual_live_confirmation":"TOR_LIVE","recurring_darknet_scheduler":False,"active_tor_jobs":int(row.get("c") or 0),"local_tor_daemon_validation":"not_run","external_onion_validation":"not_run","automatic_external_connections_on_boot":0,"background_workers_started_on_boot":0,"continuous_crawler_expansion_370_380":True,"crawler_roadmap":self.crawler_roadmap_370_380(),"production_release_ready":False}


class AutonomousInvestigation370:
    def __init__(self, db: Any, *, base369: Any, tor370: ControlledTorGateway370):
        self.db=db; self.base369=base369; self.tor370=tor370
    def status(self) -> dict[str, Any]:
        base=dict(self.base369.status()); base.update({"policy_version":AI_POLICY,"tor_gateway_awareness":True,"direct_tor_gateway_configuration_authority":False,"direct_tor_job_enqueue_authority":False,"direct_tor_network_authority":False,"continuous_crawler_expansion_370_380":True}); return base
    def run_cycle(self, *, case_id: str, max_ticks: int = 8) -> dict[str, Any]:
        out=self.base369.run_cycle(case_id=case_id,max_ticks=max_ticks); dossier=out.get("dossier")
        if isinstance(dossier,dict):
            dossier["phase16_tor_gateway_context"]={"gateway_enabled":self.tor370.config()["enabled"],"case_tor_backpressure":self.tor370.tor_backpressure(case_id=case_id),"manual_only":True,"external_onion_validation":"not_run"}; dossier["tor_research_requires_explicit_human_live_confirmation"]=True; dossier["lead_review_required"]=True
        return out


class DefensiveOpsecSupervisor370:
    def __init__(self, db: Any, audit: Any, *, base369: Any, tor370: ControlledTorGateway370, jobs: Any):
        self.db=db; self.audit=audit; self.base369=base369; self.tor370=tor370; self.jobs=jobs
    def status(self) -> dict[str, Any]:
        base=dict(self.base369.status()); base.update({"policy_version":OPSEC_POLICY,"tor_job_integrity_monitor":True,"tor_gateway_loopback_enforced":True,"tor_dns_via_socks_enforced":True,"tor_control_port_authority":False,"newnym_authority":False,"tor_configuration_mutation":False,"firewall_mutation":False,"os_mutation":False,"credential_mutation":False,"acl_mutation":False,"system_mutations":False}); return base
    def protect_remote_session(self, **kw: Any) -> dict[str, Any]: return self.base369.protect_remote_session(**kw)
    def protect_case(self, *, case_id: str) -> dict[str, Any]:
        base=self.base369.protect_case(case_id=case_id); cancelled=[]; cfg=self.tor370.config()
        rows=self.db.all("SELECT job_id,payload_json,search_run_id FROM phase15_jobs WHERE case_id=? AND job_type=? AND status IN ('queued','running')",(case_id,TOR_JOB))
        for row in rows:
            try:
                p=json.loads(row.get("payload_json") or "{}"); source=self.tor370._source(str(p.get("source_id") or "")); cap=self.db.one("SELECT search_kind,network_profile_ref FROM phase15_search_runs WHERE search_run_id=?",(row["search_run_id"],)) or {}
                invalid=(not cfg["enabled"] or p.get("phase16_tor370_manual") is not True or p.get("phase16_tor370_confirmation") is not True or source["source_kind"]!="darknet_onion" or source["review_status"]!="approved_read_only" or int(source["enabled"])!=1 or cap.get("search_kind")!="darknet" or cap.get("network_profile_ref")!="tor_read_only_v1")
            except Exception: invalid=True
            if invalid:
                self.jobs.cancel(row["job_id"],actor="opsec370"); cancelled.append(row["job_id"])
        if cancelled:self.audit.log("OPSEC370_TOR_JOB_CANCEL","case",case_id,case_id=case_id,details={"cancelled_jobs":cancelled,"policy":OPSEC_POLICY})
        return {**base,"cancelled_invalid_tor_jobs":cancelled,"tor_case_status":self.tor370.case_status(case_id=case_id),"policy_version":OPSEC_POLICY,"system_mutations":False}
