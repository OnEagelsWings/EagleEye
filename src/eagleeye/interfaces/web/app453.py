from __future__ import annotations

import hashlib

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field

from .app452 import create_workspace_app452
from .app448 import COOKIE
from .app449 import _drop


class HistoricalPlan453(BaseModel):
    case_id: str = Field(min_length=1, max_length=200)
    original_url: str = Field(min_length=8, max_length=4096)
    providers: list[str] = Field(default_factory=lambda: ["internet_archive", "common_crawl"], max_length=2)
    from_time: str = Field(default="", max_length=64)
    to_time: str = Field(default="", max_length=64)
    max_captures: int = Field(default=200, ge=1, le=1000)
    common_crawl_index: str = Field(default="", max_length=40)


class HistoricalImport453(BaseModel):
    query_id: str = Field(min_length=1, max_length=100)
    provider: str = Field(min_length=1, max_length=40)
    payload: str = Field(max_length=4_000_000)
    index_event_id: str = Field(min_length=1, max_length=100)
    index_content_id: str = Field(min_length=1, max_length=100)
    source_ref: str = Field(default="", max_length=4096)


class HistoricalCompare453(BaseModel):
    older_text: str = Field(max_length=2_000_000)
    newer_text: str = Field(max_length=2_000_000)


class RecoveryCreate453(BaseModel):
    label: str = Field(default="", max_length=200)
    confirmation: str = Field(min_length=1, max_length=80)


class RecoveryStage453(BaseModel):
    recovery_id: str = Field(min_length=1, max_length=100)
    confirmation: str = Field(min_length=1, max_length=80)


def create_workspace_app453(*, base_dir=None):
    app = create_workspace_app452(base_dir=base_dir)
    ctx = app.state.context
    app.title = "EagleEye Build 453.0 Historical Web Intelligence + Recovery"
    app.version = "453.0"
    _drop(app, "/health", {"GET"})

    @app.get("/health")
    def health():
        return {"ok": True, "status": "ok", "build": "453.0"}

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

    def mutation_auth(request: Request, *, admin=False):
        identity = auth(request)
        site = request.headers.get("sec-fetch-site", "")
        origin = request.headers.get("origin", "").rstrip("/")
        if site not in {"", "same-origin", "none"} or (origin and origin != str(request.base_url).rstrip("/")):
            raise HTTPException(403, "Cross-origin mutation blocked")
        if admin and identity.get("global_role") != "system_administrator":
            raise HTTPException(403, "Administration erforderlich")
        return identity

    @app.get("/api/build453/status")
    def status(request: Request):
        auth(request)
        return ctx.build453.build453_status()

    @app.post("/api/build453/history/plan")
    def historical_plan(body: HistoricalPlan453, request: Request):
        identity = mutation_auth(request)
        with ctx.audit.actor_scope(identity["username"]):
            return ctx.historical_web_453.create_query(identity=identity, **body.model_dump())

    @app.post("/api/build453/history/import")
    def historical_import(body: HistoricalImport453, request: Request):
        identity = mutation_auth(request)
        with ctx.audit.actor_scope(identity["username"]):
            return ctx.historical_web_453.import_index_payload(identity=identity, **body.model_dump())

    @app.get("/api/build453/history/{query_id}/candidates")
    def historical_candidates(query_id: str, request: Request, limit: int = 30):
        auth(request)
        return {
            "query_id": query_id,
            "ranked": ctx.historical_web_453.ranked_candidates(query_id, limit=limit),
        }

    @app.post("/api/build453/history/compare")
    def historical_compare(body: HistoricalCompare453, request: Request):
        mutation_auth(request)
        return ctx.historical_web_453.compare_texts(**body.model_dump())

    @app.post("/api/build453/recovery/create")
    def recovery_create(body: RecoveryCreate453, request: Request):
        identity = mutation_auth(request, admin=True)
        with ctx.audit.actor_scope(identity["username"]):
            return ctx.recovery_453.create_recovery_point(identity=identity, **body.model_dump())

    @app.get("/api/build453/recovery/{recovery_id}/verify")
    def recovery_verify(recovery_id: str, request: Request):
        identity = auth(request)
        if identity.get("global_role") != "system_administrator":
            raise HTTPException(403, "Administration erforderlich")
        return ctx.recovery_453.verify(recovery_id)

    @app.post("/api/build453/recovery/stage")
    def recovery_stage(body: RecoveryStage453, request: Request):
        identity = mutation_auth(request, admin=True)
        with ctx.audit.actor_scope(identity["username"]):
            return ctx.recovery_453.stage_restore(identity=identity, **body.model_dump())

    return app
