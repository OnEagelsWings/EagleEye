from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from .app379 import COOKIE
from .app400 import create_workspace_app400
from eagleeye_pro.phase18.bootstrap405 import install_phase18_405


def create_workspace_app401(*, base_dir: str | Path | None = None) -> FastAPI:
    app = create_workspace_app400(base_dir=base_dir)
    ctx = app.state.context
    if getattr(ctx, "build401", None) is None:
        ctx = install_phase18_405(ctx)
    team = ctx.team_identity_359
    _ = ctx.build401
    app.title = "EagleEye Intelligence Platform – Build 401.0 Security & Qualification Hardening"
    app.version = "401.0"
    old_health = next((r.endpoint for r in app.router.routes if getattr(r, "path", None) == "/health" and "GET" in set(getattr(r, "methods", set()) or set())), None)
    app.router.routes[:] = [r for r in app.router.routes if not (getattr(r, "path", None) == "/health" and "GET" in set(getattr(r, "methods", set()) or set()))]

    def auth(req: Request):
        import hashlib
        fp = hashlib.sha256("|".join((req.headers.get("user-agent", ""), req.headers.get("accept-language", ""), req.client.host if req.client else "")).encode()).hexdigest()
        identity = team.validate_session(req.cookies.get(COOKIE, ""), client_fingerprint=fp, touch=True)
        if not identity:
            raise HTTPException(401, "Anmeldung erforderlich oder Sitzung abgelaufen")
        return identity

    @app.get("/health")
    def health401():
        prev = dict(old_health() if callable(old_health) else {"ok": True})
        gate = ctx.build401.security_gate()
        prev.update({"build": "401.0", "phase": 18, "phase18_builds_completed": 1, "security_qualification_gate": gate["security_gate_pass"], "github_feedback_integrated": True, "next_public_feedback_build": "405.0", "production_release_ready": False})
        return prev

    @app.get("/api/build401/security-gate")
    def security_gate(request: Request):
        auth(request)
        return ctx.build401.security_gate()

    @app.get("/api/build401/phase18-status")
    def phase18_status(request: Request):
        auth(request)
        return ctx.build401.phase18_status()

    return app

create_app = create_workspace_app401
