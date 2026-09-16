from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from .app379 import COOKIE
from .app401 import create_workspace_app401

def create_workspace_app402(*, base_dir: str | Path | None = None) -> FastAPI:
    app = create_workspace_app401(base_dir=base_dir); ctx = app.state.context; team = ctx.team_identity_359; _ = ctx.build402
    app.title = "EagleEye Intelligence Platform – Build 402.0 Authorization Matrix Audit"; app.version = "402.0"
    old_health = next((r.endpoint for r in app.router.routes if getattr(r, "path", None) == "/health" and "GET" in set(getattr(r, "methods", set()) or set())), None)
    app.router.routes[:] = [r for r in app.router.routes if not (getattr(r, "path", None) == "/health" and "GET" in set(getattr(r, "methods", set()) or set()))]
    def auth(req: Request):
        import hashlib
        fp=hashlib.sha256("|".join((req.headers.get("user-agent", ""), req.headers.get("accept-language", ""), req.client.host if req.client else "")).encode()).hexdigest(); identity=team.validate_session(req.cookies.get(COOKIE, ""),client_fingerprint=fp,touch=True)
        if not identity: raise HTTPException(401,"Anmeldung erforderlich oder Sitzung abgelaufen")
        return identity
    @app.get("/health")
    def health402():
        prev=dict(old_health() if callable(old_health) else {"ok":True}); audit=ctx.build402.authorization_audit(); prev.update({"build":"402.0","phase":18,"phase18_builds_completed":2,"authorization_matrix_audit":audit["authorization_audit_pass"],"authorization_mutation_surfaces":len(audit["source_checks"]),"next_public_feedback_build":"405.0","production_release_ready":False}); return prev
    @app.get("/api/build402/authorization-matrix")
    def authorization_matrix(request:Request): auth(request); return ctx.build402.authorization_matrix()
    @app.get("/api/build402/authorization-audit")
    def authorization_audit(request:Request): auth(request); return ctx.build402.authorization_audit()
    @app.get("/api/build402/role-matrix")
    def role_matrix(request:Request): auth(request); return ctx.build402.role_matrix()
    @app.get("/api/build402/phase18-status")
    def phase18_status(request:Request): auth(request); return ctx.build402.phase18_status()
    return app
create_app=create_workspace_app402
