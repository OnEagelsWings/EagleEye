from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlsplit
import hashlib
import json
import secrets

BUILD = "446.0"
POLICY_ID = "phase20.live-ai-investigation-loop.v446"

CONFIRMATIONS = {
    "surface": "SURFACE442_LIVE",
    "news": "NEWS443_LIVE",
    "social": "SOCIAL444_LIVE",
}
SUPPORTED_ROUTES = {"surface", "news", "social"}
LIVE_STATES = {"awaiting_path_confirmation"}
TERMINAL_STATES = {"completed", "failed", "review_required"}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value):
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


class LiveAIInvestigationDispatcher446:
    """Routes an already-authorized Build-439 loop into specialized live adapters.

    Build 446 does not grant the AI investigator generic network authority. It
    creates reviewable per-source dispatch tickets. Each live ticket requires the
    exact confirmation of the underlying acquisition path and is revalidated
    against the active Build-439 loop immediately before execution.
    """

    def __init__(
        self,
        db,
        audit,
        *,
        loop439,
        registry421,
        crawler425,
        hardening442,
        news443,
        social444,
        qualification445,
        governance,
        actor="local-analyst",
    ):
        self.db = db
        self.audit = audit
        self.loop439 = loop439
        self.registry421 = registry421
        self.crawler425 = crawler425
        self.hardening442 = hardening442
        self.news443 = news443
        self.social444 = social444
        self.qualification445 = qualification445
        self.governance = governance
        self.actor = actor
        self._init_schema()

    def _init_schema(self):
        self.db.conn.executescript(
            """CREATE TABLE IF NOT EXISTS live_ai_dispatch_446(
            dispatch_id TEXT PRIMARY KEY,
            loop_id TEXT NOT NULL,
            case_id TEXT NOT NULL,
            cycle_number INTEGER NOT NULL,
            source_id TEXT NOT NULL,
            route TEXT NOT NULL,
            task_id TEXT NOT NULL,
            state TEXT NOT NULL,
            required_confirmation TEXT NOT NULL,
            reason TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_live446_loop
            ON live_ai_dispatch_446(loop_id,cycle_number,source_id,created_at);

            CREATE TABLE IF NOT EXISTS live_ai_execution_446(
            execution_id TEXT PRIMARY KEY,
            dispatch_id TEXT NOT NULL,
            loop_id TEXT NOT NULL,
            case_id TEXT NOT NULL,
            source_id TEXT NOT NULL,
            route TEXT NOT NULL,
            state TEXT NOT NULL,
            external_network INTEGER NOT NULL,
            result_json TEXT NOT NULL,
            analysis_json TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_live446_execution
            ON live_ai_execution_446(loop_id,dispatch_id,created_at);
            """
        )
        self.db.conn.commit()

    def _rh(self, row):
        return _sha({k: row[k] for k in row if k != "record_hash"})

    def _identity(self, identity):
        if not isinstance(identity, dict) or not identity.get("username") or not identity.get("user_id"):
            raise PermissionError("canonical active identity required")
        try:
            user = self.governance.identity.public_user(str(identity["username"]))
        except (KeyError, ValueError):
            raise PermissionError("canonical active identity required")
        if not user.get("active") or str(user.get("user_id")) != str(identity.get("user_id")):
            raise PermissionError("canonical active identity required")
        return {**user, "session_id": str(identity.get("session_id") or "live-loop446")}

    def _authorize(self, identity, case_id, *, capability="research.run", object_id=""):
        ident = self._identity(identity)
        self.governance.authorize(
            ident,
            case_id=str(case_id),
            capability=capability,
            object_type="live_ai_dispatch_446",
            object_id=str(object_id or case_id),
        )
        return ident

    def _loop(self, loop_id, *, require_active=True):
        loop = self.loop439.loop(str(loop_id))
        if require_active and loop["state"] != "active":
            raise PermissionError("Build-439 investigation loop is not actively authorized")
        return loop

    def _preflight(self):
        checks = {
            "loop439": self.loop439.verify_integrity()["valid"],
            "registry421": self.registry421.verify_integrity()["valid"],
            "crawler425": self.crawler425.verify_integrity()["valid"],
            "hardening442": self.hardening442.verify_integrity()["valid"],
            "news443": self.news443.verify_integrity()["valid"],
            "social444": self.social444.verify_integrity()["valid"],
            "qualification445": self.qualification445.verify_integrity()["valid"],
        }
        latest = self.qualification445.latest()
        if latest and latest.get("engineering_result") == "fail":
            checks["latest_445_engineering_not_failed"] = False
        else:
            checks["latest_445_engineering_not_failed"] = True
        if not all(checks.values()):
            raise RuntimeError(
                "Build-446 preflight failed: "
                + ",".join(k for k, value in checks.items() if not value)
            )
        return checks

    def _source_route(self, source):
        if int(source.get("enabled", 0)) != 1:
            return "review", "source_disabled"
        st = str(source.get("source_type") or "").lower()
        access = str(source.get("access_mode") or "").lower()
        coverage = source.get("coverage") or {}
        capabilities = {str(x).lower() for x in (source.get("capabilities") or [])}

        if st == "tor_onion" or access == "tor_public":
            return "review", "isolated_tor_worker_and_separate_approval_required"
        if access != "public":
            return "review", "non_public_access_mode_requires_separate_governance"
        if not str(source.get("base_url") or "").strip():
            return "review", "reviewed_base_url_required"

        if st == "social":
            if not str(coverage.get("social_adapter") or "").strip():
                return "review", "social_adapter_not_declared"
            return "social", ""

        if st in {"rss", "news"}:
            return "news", ""

        if st == "api":
            news_signals = {"news_feed", "rss", "atom", "jsonfeed"}
            if capabilities & news_signals or bool(coverage.get("news_feed")):
                return "news", ""
            return "surface", ""

        return "surface", ""

    def _surface_task(self, *, identity, loop, source):
        rows = self.db.all(
            "SELECT * FROM crawl_task_425 WHERE case_id=? AND source_id=? "
            "ORDER BY created_at DESC,rowid DESC",
            (loop["case_id"], source["source_id"]),
        )
        for row in rows:
            task = dict(row)
            if task["state"] not in {"planned", "deferred"}:
                continue
            try:
                scope = json.loads(task.get("scope_json") or "{}")
            except Exception:
                scope = {}
            if str(scope.get("build439_loop_id") or "") == loop["loop_id"]:
                return task

        target = str(source.get("base_url") or "").strip()
        parsed = urlsplit(target)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("surface source requires a reviewed public http(s) base URL")
        return self.crawler425.create_task(
            identity=identity,
            case_id=loop["case_id"],
            source_id=source["source_id"],
            target=target,
            objective=f"Build 446 live acquisition for investigation loop {loop['loop_id']}",
            scope={
                "allowed_hosts": [parsed.hostname.casefold()],
                "build439_loop_id": loop["loop_id"],
                "build446_dispatch": True,
                "case_scope_only": True,
            },
            budget={"max_pages": 1, "max_bytes": 1_000_000, "max_seconds": 20},
        )

    def _specialized_task(self, *, identity, loop, source, route):
        if route == "surface":
            return self._surface_task(identity=identity, loop=loop, source=source)
        if route == "news":
            return self.news443.create_feed_task(
                identity=identity,
                case_id=loop["case_id"],
                source_id=source["source_id"],
            )
        if route == "social":
            return self.social444.create_task(
                identity=identity,
                case_id=loop["case_id"],
                source_id=source["source_id"],
            )
        raise ValueError("unsupported Build-446 route")

    def _decode_dispatch(self, row):
        return dict(row)

    def dispatch(self, dispatch_id):
        row = self.db.one("SELECT * FROM live_ai_dispatch_446 WHERE dispatch_id=?", (str(dispatch_id),))
        if not row:
            raise KeyError("Build-446 dispatch not found")
        return self._decode_dispatch(row)

    def dispatches(self, loop_id):
        return [
            self._decode_dispatch(row)
            for row in self.db.all(
                "SELECT * FROM live_ai_dispatch_446 WHERE loop_id=? "
                "ORDER BY cycle_number,created_at,dispatch_id",
                (str(loop_id),),
            )
        ]

    def executions(self, loop_id):
        out = []
        for row in self.db.all(
            "SELECT * FROM live_ai_execution_446 WHERE loop_id=? ORDER BY created_at,execution_id",
            (str(loop_id),),
        ):
            item = dict(row)
            item["external_network"] = bool(item["external_network"])
            item["result"] = json.loads(item.pop("result_json"))
            item["analysis"] = json.loads(item.pop("analysis_json"))
            out.append(item)
        return out

    def _update_dispatch(self, dispatch_id, *, state, reason=None):
        row = dict(self.db.one("SELECT * FROM live_ai_dispatch_446 WHERE dispatch_id=?", (str(dispatch_id),)))
        row["state"] = str(state)
        if reason is not None:
            row["reason"] = str(reason)[:500]
        row["updated_at"] = _now()
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "UPDATE live_ai_dispatch_446 SET state=?,reason=?,updated_at=?,record_hash=? "
            "WHERE dispatch_id=?",
            (row["state"], row["reason"], row["updated_at"], row["record_hash"], dispatch_id),
        )
        return self.dispatch(dispatch_id)

    def _existing_dispatch(self, loop_id, cycle_number, source_id):
        row = self.db.one(
            "SELECT * FROM live_ai_dispatch_446 "
            "WHERE loop_id=? AND cycle_number=? AND source_id=? "
            "ORDER BY rowid DESC LIMIT 1",
            (str(loop_id), int(cycle_number), str(source_id)),
        )
        return dict(row) if row else None

    def prepare_loop_dispatches(self, *, identity, loop_id, source_ids=None):
        preflight = self._preflight()
        loop = self._loop(loop_id, require_active=True)
        ident = self._authorize(identity, loop["case_id"], object_id=loop_id)

        allowed = set(loop["scope"].get("allowed_source_ids") or [])
        requested = sorted({str(x) for x in (source_ids or allowed) if str(x)})
        outside = [x for x in requested if x not in allowed]
        if outside:
            raise PermissionError(
                "requested source outside authorized Build-439 loop scope: " + ",".join(outside)
            )

        maxn = int(loop["scope"].get("max_collection_tasks_per_cycle") or 4)
        if len(requested) > maxn:
            raise PermissionError("requested dispatch count exceeds authorized per-cycle collection budget")

        cycle = int(loop.get("current_cycle") or 0)
        prepared = []
        for source_id in requested:
            existing = self._existing_dispatch(loop_id, cycle, source_id)
            if existing and existing["state"] not in {"failed"}:
                prepared.append(existing)
                continue

            source = self.registry421.get(source_id)
            route, reason = self._source_route(source)
            task_id = ""
            required_confirmation = ""
            fixture = bool((source.get("coverage") or {}).get("fixture_only"))

            if route in SUPPORTED_ROUTES:
                task = self._specialized_task(
                    identity=ident,
                    loop=loop,
                    source=source,
                    route=route,
                )
                task_id = str(task["task_id"])
                required_confirmation = CONFIRMATIONS[route]
                state = "replay_ready" if fixture else "awaiting_path_confirmation"
                if fixture:
                    reason = "fixture_live_execution_forbidden_replay_only"
            else:
                state = "review_required"

            row = {
                "dispatch_id": "dispatch446_" + secrets.token_hex(10),
                "loop_id": loop["loop_id"],
                "case_id": loop["case_id"],
                "cycle_number": cycle,
                "source_id": source_id,
                "route": route,
                "task_id": task_id,
                "state": state,
                "required_confirmation": required_confirmation,
                "reason": str(reason or ""),
                "created_by": str(ident["username"]),
                "created_at": _now(),
                "updated_at": _now(),
            }
            row["record_hash"] = self._rh(row)
            self.db.execute(
                "INSERT INTO live_ai_dispatch_446 VALUES("
                + ",".join("?" for _ in row)
                + ")",
                tuple(row.values()),
            )
            self.audit.log(
                "live_ai_dispatch_prepared_446",
                "live_ai_dispatch_446",
                row["dispatch_id"],
                loop["case_id"],
                {
                    "loop_id": loop["loop_id"],
                    "source_id": source_id,
                    "route": route,
                    "state": state,
                    "network_execution": False,
                    "automatic_execution": False,
                },
            )
            prepared.append(self.dispatch(row["dispatch_id"]))

        return {
            "build": BUILD,
            "loop_id": loop["loop_id"],
            "case_id": loop["case_id"],
            "cycle_number": cycle,
            "dispatches": prepared,
            "preflight": preflight,
            "network_execution": False,
            "automatic_execution": False,
            "automatic_scope_expansion": False,
        }

    def _validate_dispatch_execution(self, *, identity, dispatch, replay=False):
        loop = self._loop(dispatch["loop_id"], require_active=True)
        ident = self._authorize(
            identity,
            loop["case_id"],
            capability="crawler.run",
            object_id=dispatch["dispatch_id"],
        )
        if dispatch["case_id"] != loop["case_id"]:
            raise PermissionError("dispatch/loop case mismatch")
        if dispatch["source_id"] not in set(loop["scope"].get("allowed_source_ids") or []):
            raise PermissionError("dispatch source is outside current authorized loop scope")
        if dispatch["route"] not in SUPPORTED_ROUTES:
            raise PermissionError("dispatch requires separate human review")
        source = self.registry421.get(dispatch["source_id"])
        fixture = bool((source.get("coverage") or {}).get("fixture_only"))
        if replay:
            if not fixture:
                raise PermissionError("deterministic Build-446 replay is restricted to fixture sources")
            if dispatch["state"] != "replay_ready":
                raise ValueError("fixture dispatch is not replay-ready")
        else:
            if fixture:
                raise PermissionError("fixture source cannot use Build-446 live execution")
            if dispatch["state"] not in LIVE_STATES:
                raise ValueError("dispatch is not awaiting live path confirmation")
        return ident, loop, source

    def _refresh_analysis(self, *, identity, loop):
        include_fixtures = bool(loop["scope"].get("include_fixtures"))
        resolution = self.loop439.resolution437.sync_case(
            identity=identity,
            case_id=loop["case_id"],
            include_fixtures=include_fixtures,
        )
        fusion = self.loop439.fusion438.fuse_case(
            identity=identity,
            case_id=loop["case_id"],
            include_fixtures=include_fixtures,
        )
        matrix = self.loop439.matrix418.matrix(
            session_id=loop["session_id"],
            identity=identity,
        )
        synthesis = self.loop439.synthesis419.synthesize(
            session_id=loop["session_id"],
            title=f"Build 446 acquisition refresh for {loop['loop_id']}",
            identity=identity,
        )
        return {
            "resolution_run_id": resolution["run_id"],
            "fusion_run_id": fusion["run_id"],
            "hypothesis_count": len(matrix.get("hypotheses") or []),
            "gap_count": len(matrix.get("gaps") or []),
            "conflict_count": len(matrix.get("conflicts") or []),
            "synthesis_id": synthesis["synthesis_id"],
            "automatic_truth_determination": False,
            "automatic_evidence_promotion": False,
        }

    def _record_execution(
        self,
        *,
        identity,
        dispatch,
        state,
        external_network,
        result,
        analysis,
    ):
        row = {
            "execution_id": "exec446_" + secrets.token_hex(10),
            "dispatch_id": dispatch["dispatch_id"],
            "loop_id": dispatch["loop_id"],
            "case_id": dispatch["case_id"],
            "source_id": dispatch["source_id"],
            "route": dispatch["route"],
            "state": str(state),
            "external_network": 1 if external_network else 0,
            "result_json": _canon(result),
            "analysis_json": _canon(analysis),
            "created_by": str(identity["username"]),
            "created_at": _now(),
        }
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "INSERT INTO live_ai_execution_446 VALUES("
            + ",".join("?" for _ in row)
            + ")",
            tuple(row.values()),
        )
        self.audit.log(
            "live_ai_dispatch_executed_446",
            "live_ai_execution_446",
            row["execution_id"],
            dispatch["case_id"],
            {
                "dispatch_id": dispatch["dispatch_id"],
                "route": dispatch["route"],
                "state": state,
                "external_network": bool(external_network),
                "truth_determined": False,
            },
        )
        item = dict(row)
        item["external_network"] = bool(item["external_network"])
        item["result"] = json.loads(item.pop("result_json"))
        item["analysis"] = json.loads(item.pop("analysis_json"))
        return item

    def execute_live(self, *, identity, dispatch_id, confirmation):
        dispatch = self.dispatch(dispatch_id)
        ident, loop, _source = self._validate_dispatch_execution(
            identity=identity,
            dispatch=dispatch,
            replay=False,
        )
        expected = dispatch["required_confirmation"]
        if str(confirmation or "").strip().upper() != expected:
            raise PermissionError(f"explicit {expected} confirmation required")

        try:
            if dispatch["route"] == "surface":
                result = self.hardening442.execute_authorized_loop_task(
                    identity=ident,
                    task_id=dispatch["task_id"],
                )
            elif dispatch["route"] == "news":
                result = self.news443.execute_live(
                    identity=ident,
                    case_id=dispatch["case_id"],
                    task_id=dispatch["task_id"],
                    confirmation=CONFIRMATIONS["news"],
                )
            elif dispatch["route"] == "social":
                result = self.social444.execute_live(
                    identity=ident,
                    case_id=dispatch["case_id"],
                    task_id=dispatch["task_id"],
                    confirmation=CONFIRMATIONS["social"],
                )
            else:
                raise PermissionError("unsupported live route")
            analysis = self._refresh_analysis(identity=ident, loop=loop)
            updated = self._update_dispatch(dispatch_id, state="completed", reason="")
            execution = self._record_execution(
                identity=ident,
                dispatch=updated,
                state="completed",
                external_network=True,
                result=result,
                analysis=analysis,
            )
            return {
                "build": BUILD,
                "dispatch": updated,
                "execution": execution,
                "network_execution": True,
                "automatic_execution": False,
                "automatic_scope_expansion": False,
                "truth_determined": False,
            }
        except Exception as exc:
            failed = self._update_dispatch(
                dispatch_id,
                state="failed",
                reason=type(exc).__name__,
            )
            self._record_execution(
                identity=ident,
                dispatch=failed,
                state="failed",
                external_network=False,
                result={"error": type(exc).__name__},
                analysis={},
            )
            raise

    def execute_replay(self, *, identity, dispatch_id, transport, resolver):
        dispatch = self.dispatch(dispatch_id)
        ident, loop, _source = self._validate_dispatch_execution(
            identity=identity,
            dispatch=dispatch,
            replay=True,
        )
        if dispatch["route"] == "surface":
            result = self.hardening442.execute_replay(
                identity=ident,
                task_id=dispatch["task_id"],
                transport=transport,
                resolver=resolver,
            )
        elif dispatch["route"] == "news":
            result = self.news443.execute_replay(
                identity=ident,
                case_id=dispatch["case_id"],
                task_id=dispatch["task_id"],
                transport=transport,
                resolver=resolver,
            )
        elif dispatch["route"] == "social":
            result = self.social444.execute_replay(
                identity=ident,
                case_id=dispatch["case_id"],
                task_id=dispatch["task_id"],
                transport=transport,
                resolver=resolver,
            )
        else:
            raise PermissionError("unsupported replay route")

        analysis = self._refresh_analysis(identity=ident, loop=loop)
        updated = self._update_dispatch(dispatch_id, state="completed", reason="")
        execution = self._record_execution(
            identity=ident,
            dispatch=updated,
            state="completed",
            external_network=False,
            result=result,
            analysis=analysis,
        )
        return {
            "build": BUILD,
            "dispatch": updated,
            "execution": execution,
            "network_execution": False,
            "automatic_execution": False,
            "automatic_scope_expansion": False,
            "truth_determined": False,
        }

    def run_case_selftest(self, *, identity, case_id):
        from eagleeye.crawler.engine import FetchResponse, StaticTransport

        ident = self._identity(identity)
        token = secrets.token_hex(5)

        surface_host = f"surface446-{token}.example.org"
        surface = self.registry421.register(
            identity=ident,
            name="Build 446 Surface Fixture " + token,
            source_type="website",
            access_mode="public",
            base_url=f"https://{surface_host}/page",
            capabilities=["public_pages"],
            coverage={"fixture_only": True, "live_execution_forbidden": True},
            license_note="Build 446 deterministic dispatcher fixture.",
        )

        news_host = f"news446-{token}.example.org"
        news = self.registry421.register(
            identity=ident,
            name="Build 446 News Fixture " + token,
            source_type="rss",
            access_mode="public",
            base_url=f"https://{news_host}/feed.xml",
            capabilities=["news_feed", "rss"],
            coverage={
                "fixture_only": True,
                "live_execution_forbidden": True,
                "allowed_article_hosts": [news_host],
            },
            license_note="Build 446 deterministic dispatcher fixture.",
        )

        social_host = f"social446-{token}.example.org"
        social = self.registry421.register(
            identity=ident,
            name="Build 446 Social Fixture " + token,
            source_type="social",
            access_mode="public",
            base_url=f"https://{social_host}/public.json",
            capabilities=["public_posts", "public_json"],
            coverage={
                "fixture_only": True,
                "live_execution_forbidden": True,
                "social_adapter": "generic_public",
                "generic_schema": "eagleeye_public_social_v1",
                "allowed_object_hosts": [social_host],
            },
            license_note="Build 446 deterministic dispatcher fixture.",
        )

        loop = self.loop439.create_loop(
            identity=ident,
            case_id=str(case_id),
            objective="Build 446 deterministic live-loop dispatch qualification",
            subquestions=["Can authorized sources be routed to the correct acquisition adapters?"],
            allowed_source_ids=[surface["source_id"], news["source_id"], social["source_id"]],
            include_fixtures=True,
            max_cycles=2,
            max_collection_tasks_per_cycle=3,
        )
        blocked_before_go = False
        try:
            self.prepare_loop_dispatches(identity=ident, loop_id=loop["loop_id"])
        except PermissionError:
            blocked_before_go = True

        self.loop439.authorize_loop(
            identity=ident,
            loop_id=loop["loop_id"],
            confirmation="AUTHORIZE INVESTIGATION LOOP",
        )
        prepared = self.prepare_loop_dispatches(
            identity=ident,
            loop_id=loop["loop_id"],
        )
        by_route = {x["route"]: x for x in prepared["dispatches"]}

        surface_robots = f"https://{surface_host}/robots.txt"
        surface_target = by_route["surface"]["task_id"]
        surface_task = self.crawler425.get(surface_target)
        surface_transport = StaticTransport(
            {
                surface_robots: FetchResponse(
                    surface_robots,
                    200,
                    {"content-type": "text/plain"},
                    b"User-agent: *\nAllow: /\n",
                    1,
                ),
                surface_task["target"]: FetchResponse(
                    surface_task["target"],
                    200,
                    {"content-type": "text/plain"},
                    b"Build 446 public surface fixture",
                    2,
                ),
            }
        )

        news_robots = f"https://{news_host}/robots.txt"
        news_task = self.crawler425.get(by_route["news"]["task_id"])
        article = f"https://{news_host}/article-1"
        feed = (
            f"<rss version='2.0'><channel><item><title>Build 446 report</title>"
            f"<link>{article}</link><guid>news-{token}</guid>"
            f"<pubDate>Sat, 26 Sep 2026 22:00:00 GMT</pubDate>"
            f"<description>Dispatcher news fixture.</description></item></channel></rss>"
        ).encode("utf-8")
        news_transport = StaticTransport(
            {
                news_robots: FetchResponse(
                    news_robots,
                    200,
                    {"content-type": "text/plain"},
                    b"User-agent: *\nAllow: /\n",
                    1,
                ),
                news_task["target"]: FetchResponse(
                    news_task["target"],
                    200,
                    {"content-type": "application/rss+xml"},
                    feed,
                    2,
                ),
            }
        )

        social_robots = f"https://{social_host}/robots.txt"
        social_task = self.crawler425.get(by_route["social"]["task_id"])
        social_payload = {
            "items": [
                {
                    "external_object_id": "social-" + token,
                    "canonical_url": f"https://{social_host}/post/{token}",
                    "published_at": "2026-09-26T22:30:00Z",
                    "text": "Build 446 public social fixture",
                    "platform": "generic",
                    "object_type": "post",
                    "visibility": "public",
                }
            ]
        }
        social_transport = StaticTransport(
            {
                social_robots: FetchResponse(
                    social_robots,
                    200,
                    {"content-type": "text/plain"},
                    b"User-agent: *\nAllow: /\n",
                    1,
                ),
                social_task["target"]: FetchResponse(
                    social_task["target"],
                    200,
                    {"content-type": "application/json"},
                    json.dumps(social_payload).encode("utf-8"),
                    2,
                ),
            }
        )

        old_sleep = self.hardening442.sleep
        self.hardening442.sleep = lambda _seconds: None
        try:
            surface_result = self.execute_replay(
                identity=ident,
                dispatch_id=by_route["surface"]["dispatch_id"],
                transport=surface_transport,
                resolver=lambda _host: ["93.184.216.34"],
            )
            news_result = self.execute_replay(
                identity=ident,
                dispatch_id=by_route["news"]["dispatch_id"],
                transport=news_transport,
                resolver=lambda _host: ["93.184.216.34"],
            )
            social_result = self.execute_replay(
                identity=ident,
                dispatch_id=by_route["social"]["dispatch_id"],
                transport=social_transport,
                resolver=lambda _host: ["93.184.216.34"],
            )
        finally:
            self.hardening442.sleep = old_sleep

        executions = self.executions(loop["loop_id"])
        checks = {
            "loop_go_required_before_dispatch": blocked_before_go,
            "three_routes_prepared": set(by_route) == {"surface", "news", "social"},
            "surface_confirmation_preserved": by_route["surface"]["required_confirmation"] == "SURFACE442_LIVE",
            "news_confirmation_preserved": by_route["news"]["required_confirmation"] == "NEWS443_LIVE",
            "social_confirmation_preserved": by_route["social"]["required_confirmation"] == "SOCIAL444_LIVE",
            "surface_replay_completed": surface_result["dispatch"]["state"] == "completed",
            "news_replay_completed": news_result["dispatch"]["state"] == "completed",
            "social_replay_completed": social_result["dispatch"]["state"] == "completed",
            "all_replays_no_external_network": all(not x["external_network"] for x in executions),
            "analysis_refreshed": all(bool(x["analysis"].get("synthesis_id")) for x in executions),
            "no_automatic_execution": all(
                item["network_execution"] is False
                for item in (surface_result, news_result, social_result)
            ),
            "integrity_valid": self.verify_integrity()["valid"],
        }
        return {
            "build": BUILD,
            "case_id": str(case_id),
            "loop_id": loop["loop_id"],
            "result": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks,
            "dispatches": self.dispatches(loop["loop_id"]),
            "executions": executions,
            "note": (
                "Deterministic replay validates loop-to-adapter routing and analytical refresh. "
                "No external sockets are opened and no live confirmation is consumed."
            ),
        }

    def verify_integrity(self):
        bad = []
        for table, key in (
            ("live_ai_dispatch_446", "dispatch_id"),
            ("live_ai_execution_446", "execution_id"),
        ):
            for row in self.db.all(f"SELECT * FROM {table}"):
                item = dict(row)
                if self._rh(item) != item.get("record_hash"):
                    bad.append(
                        {
                            "table": table,
                            "id": item.get(key),
                            "reason": "record_hash_mismatch",
                        }
                    )
        return {"build": BUILD, "valid": not bad, "violations": bad}

    def status(self):
        dispatch_count = int(self.db.one("SELECT COUNT(*) n FROM live_ai_dispatch_446")["n"])
        live_count = int(
            self.db.one(
                "SELECT COUNT(*) n FROM live_ai_execution_446 WHERE external_network=1"
            )["n"]
        )
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "dispatches": dispatch_count,
            "live_executions": live_count,
            "integrity_valid": self.verify_integrity()["valid"],
            "live_ai_investigation_dispatch": True,
            "build439_loop_required": True,
            "build439_loop_must_be_active": True,
            "source_must_be_in_authorized_loop_scope": True,
            "specialized_surface_dispatch": True,
            "specialized_news_dispatch": True,
            "specialized_social_dispatch": True,
            "specialized_news_social_dispatch_implemented": True,
            "per_path_confirmation_required": True,
            "confirmations": dict(CONFIRMATIONS),
            "automatic_live_execution": False,
            "batch_auto_execute": False,
            "automatic_scope_expansion": False,
            "generic_network_authority": False,
            "tor_routed_to_separate_review": True,
            "authenticated_collection_supported": False,
            "private_or_direct_social_supported": False,
            "analysis_refresh_after_acquisition": True,
            "automatic_truth_determination": False,
            "automatic_evidence_promotion": False,
            "production_release_ready": False,
        }
