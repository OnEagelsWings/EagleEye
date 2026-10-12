from __future__ import annotations

import hashlib

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field

from .app453 import create_workspace_app453
from .app448 import COOKIE
from .app449 import _drop


class InfraDomainPlan454(BaseModel):
    case_id: str = Field(min_length=1, max_length=200)
    domain: str = Field(min_length=3, max_length=253)


class InfraImport454(BaseModel):
    lookup_id: str = Field(min_length=1, max_length=120)
    payload: str = Field(max_length=4_000_000)
    event_id: str = Field(min_length=1, max_length=120)
    content_id: str = Field(min_length=1, max_length=120)
    source_ref: str = Field(default="", max_length=4096)


class XRefRun454(BaseModel):
    case_id: str = Field(min_length=1, max_length=200)


def create_workspace_app454(*, base_dir=None):
    app = create_workspace_app453(base_dir=base_dir)
    ctx = app.state.context
    app.title = "EagleEye Build 454.0 Cross-Reference + Domain Infrastructure"
    app.version = "454.0"
    _drop(app, "/health", {"GET"})

    @app.get("/health")
    def health():
        return {"ok": True, "status": "ok", "build": "454.0"}

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

    def mutation_auth(request: Request):
        identity = auth(request)
        site = request.headers.get("sec-fetch-site", "")
        origin = request.headers.get("origin", "").rstrip("/")
        if site not in {"", "same-origin", "none"} or (origin and origin != str(request.base_url).rstrip("/")):
            raise HTTPException(403, "Cross-origin mutation blocked")
        return identity

    @app.get("/api/build454/status")
    def status(request: Request):
        auth(request)
        return ctx.build454.build454_status()

    @app.post("/api/build454/infrastructure/domain/plan")
    def plan_domain(body: InfraDomainPlan454, request: Request):
        identity = mutation_auth(request)
        with ctx.audit.actor_scope(identity["username"]):
            return ctx.infrastructure_454.plan_domain(identity=identity, **body.model_dump())

    @app.post("/api/build454/infrastructure/domain/pivots")
    def plan_domain_pivots(body: InfraDomainPlan454, request: Request):
        identity = mutation_auth(request)
        with ctx.audit.actor_scope(identity["username"]):
            return ctx.infrastructure_454.plan_ip_pivots(identity=identity, **body.model_dump())

    @app.post("/api/build454/infrastructure/import")
    def import_infrastructure(body: InfraImport454, request: Request):
        identity = mutation_auth(request)
        with ctx.audit.actor_scope(identity["username"]):
            return ctx.infrastructure_454.import_payload(identity=identity, **body.model_dump())

    @app.get("/api/build454/infrastructure/{case_id}/facts")
    def infrastructure_facts(case_id: str, request: Request, resource: str = "", fact_type: str = ""):
        auth(request)
        return {
            "case_id": case_id,
            "facts": ctx.infrastructure_454.facts(case_id, resource=resource, fact_type=fact_type),
        }

    @app.post("/api/build454/xref/run")
    def run_xref(body: XRefRun454, request: Request):
        identity = mutation_auth(request)
        with ctx.audit.actor_scope(identity["username"]):
            return ctx.xref_454.run_case(identity=identity, case_id=body.case_id)

    @app.get("/api/build454/xref/{case_id}/candidates")
    def xref_candidates(case_id: str, request: Request, min_score: float = 0.0, limit: int = 250):
        auth(request)
        return {
            "case_id": case_id,
            "candidates": ctx.xref_454.candidates(case_id, min_score=min_score, limit=limit),
        }

    @app.get("/api/build454/xref/{case_id}/path")
    def xref_path(case_id: str, request: Request, start_kind: str, start_ref: str,
                  end_kind: str, end_ref: str, min_score: float = 0.35, max_depth: int = 6):
        auth(request)
        return ctx.xref_454.shortest_candidate_path(
            case_id=case_id, start_kind=start_kind, start_ref=start_ref,
            end_kind=end_kind, end_ref=end_ref, min_score=min_score, max_depth=max_depth,
        )

    @app.get("/api/build454/xref/{case_id}/pivots")
    def xref_pivots(case_id: str, request: Request):
        auth(request)
        return ctx.xref_454.pivot_recommendations(case_id)

    return app
