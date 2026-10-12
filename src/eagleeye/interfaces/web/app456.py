from __future__ import annotations

import hashlib

from fastapi import HTTPException, Request

from .app455 import create_workspace_app455
from .app448 import COOKIE
from .app449 import _drop


def create_workspace_app456(*, base_dir=None):
    app = create_workspace_app455(base_dir=base_dir)
    ctx = app.state.context
    app.title = "EagleEye Build 456.0 Multilingual Entity Resolution + Source Lineage"
    app.version = "456.0"
    _drop(app, "/health", {"GET"})

    @app.get("/health")
    def health():
        return {"ok": True, "status": "ok", "build": "456.0"}

    def auth(request: Request):
        material = "|".join((
            request.headers.get("user-agent", ""),
            request.headers.get("accept-language", ""),
            request.client.host if request.client else "",
        ))
        identity = ctx.team_identity_359.validate_session(
            request.cookies.get(COOKIE, ""),
            client_fingerprint=hashlib.sha256(material.encode()).hexdigest(),
            touch=True,
        )
        if not identity:
            raise HTTPException(401, "Anmeldung erforderlich")
        return identity

    def authorize_case(identity, case_id, capability="case.read"):
        try:
            ctx.team_governance_359.authorize(
                identity,
                case_id=case_id,
                capability=capability,
                object_type="build456",
                object_id=case_id,
            )
        except PermissionError as exc:
            raise HTTPException(403, "Keine Berechtigung für diesen Fall") from exc

    @app.get("/api/build456/status")
    def status(request: Request):
        auth(request)
        return ctx.build456.build456_status()

    @app.get("/api/build456/cases/{case_id}/report")
    def case_report(case_id: str, request: Request):
        identity = auth(request)
        authorize_case(identity, case_id, "case.read")
        return ctx.entity_lineage_456.case_report(identity=identity, case_id=case_id)

    @app.post("/api/build456/cases/{case_id}/entity-scan")
    async def entity_scan(case_id: str, request: Request):
        identity = auth(request)
        authorize_case(identity, case_id, "research.run")
        payload = await request.json()
        with ctx.audit.actor_scope(identity["username"]):
            return ctx.build456.scan_multilingual_entities_456(
                identity=identity,
                case_id=case_id,
                min_pair_score=float(payload.get("min_pair_score", 0.72)),
                max_entities=int(payload.get("max_entities", 250)),
                max_pairs=int(payload.get("max_pairs", 5000)),
            )

    @app.get("/api/build456/cases/{case_id}/claims/{claim_id}/source-lineage")
    def claim_lineage(case_id: str, claim_id: str, request: Request):
        identity = auth(request)
        authorize_case(identity, case_id, "case.read")
        item = ctx.build456.claim_source_lineage_456(identity=identity, claim_id=claim_id)
        if item["case_id"] != case_id:
            raise HTTPException(404, "Claim nicht in diesem Fall")
        return item

    @app.post("/api/build456/aliases/{candidate_id}/review")
    async def alias_review(candidate_id: str, request: Request):
        identity = auth(request)
        payload = await request.json()
        try:
            with ctx.audit.actor_scope(identity["username"]):
                return ctx.build456.review_multilingual_alias_456(
                    identity=identity,
                    candidate_id=candidate_id,
                    decision=payload.get("decision", ""),
                    rationale=payload.get("rationale", ""),
                    confirmation=payload.get("confirmation", ""),
                )
        except (KeyError, ValueError) as exc:
            raise HTTPException(400, str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc

    @app.post("/api/build456/pairs/{pair_id}/review")
    async def pair_review(pair_id: str, request: Request):
        identity = auth(request)
        payload = await request.json()
        try:
            with ctx.audit.actor_scope(identity["username"]):
                return ctx.build456.review_multilingual_pair_456(
                    identity=identity,
                    pair_id=pair_id,
                    decision=payload.get("decision", ""),
                    rationale=payload.get("rationale", ""),
                    confirmation=payload.get("confirmation", ""),
                )
        except (KeyError, ValueError) as exc:
            raise HTTPException(400, str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc

    @app.post("/api/build456/evidence/{evidence_id}/source-lineage-review")
    async def lineage_review(evidence_id: str, request: Request):
        identity = auth(request)
        payload = await request.json()
        if "countable" not in payload or type(payload.get("countable")) is not bool:
            raise HTTPException(422, "countable muss ein JSON-Boolean sein")
        expected_hash = payload.get("expected_evidence_hash")
        if not isinstance(expected_hash, str) or not expected_hash:
            raise HTTPException(422, "expected_evidence_hash ist erforderlich")
        try:
            with ctx.audit.actor_scope(identity["username"]):
                return ctx.build456.review_source_lineage_456(
                    identity=identity,
                    evidence_id=evidence_id,
                    source_family=payload.get("source_family", ""),
                    independence_group=payload.get("independence_group", ""),
                    origin_key=payload.get("origin_key", ""),
                    source_role=payload.get("source_role", "unknown"),
                    countable=payload["countable"],
                    rationale=payload.get("rationale", ""),
                    confirmation=payload.get("confirmation", ""),
                    expected_evidence_hash=expected_hash,
                )
        except (KeyError, ValueError) as exc:
            raise HTTPException(400, str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc

    return app
