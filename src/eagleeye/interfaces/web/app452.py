from fastapi import HTTPException, Request
from .app451 import create_workspace_app451
from .app448 import COOKIE
from .app449 import _drop
import hashlib


def create_workspace_app452(*, base_dir=None):
    app = create_workspace_app451(base_dir=base_dir)
    ctx = app.state.context
    app.title = "EagleEye Build 452.0 Deterministic Deployment"
    app.version = "452.0"
    _drop(app, "/health", {"GET"})

    @app.get("/health")
    def health():
        return {"ok": True, "status": "ok", "build": "452.0"}

    def auth(request):
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

    @app.get("/api/build452/status")
    def status(request: Request):
        auth(request)
        return ctx.build452.deployment_status_452()

    return app
