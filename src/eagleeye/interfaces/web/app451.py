from fastapi import HTTPException, Request
from .app450 import create_workspace_app450
from .app448 import COOKIE
from .app449 import _drop
import hashlib


def create_workspace_app451(*, base_dir=None):
    app = create_workspace_app450(base_dir=base_dir)
    ctx = app.state.context
    app.title = "EagleEye Build 451.0 Retrieval Isolation"
    app.version = "451.0"
    _drop(app, "/health", {"GET"})

    @app.get("/health")
    def health():
        return {"ok": True, "status": "ok", "build": "451.0"}

    def auth(request):
        material = "|".join((request.headers.get("user-agent", ""),
                             request.headers.get("accept-language", ""),
                             request.client.host if request.client else ""))
        identity = ctx.team_identity_359.validate_session(
            request.cookies.get(COOKIE, ""),
            client_fingerprint=hashlib.sha256(material.encode()).hexdigest(), touch=True)
        if not identity:
            raise HTTPException(401, "Anmeldung erforderlich")
        return identity

    @app.get("/api/build451/status")
    def status(request: Request):
        auth(request)
        return ctx.build451.retrieval_isolation_status_451()

    @app.post("/api/build451/diagnose")
    def diagnose(request: Request):
        identity = auth(request)
        site = request.headers.get("sec-fetch-site", "")
        origin = request.headers.get("origin", "").rstrip("/")
        if site not in {"", "same-origin", "none"} or (origin and origin != str(request.base_url).rstrip("/")):
            raise HTTPException(403, "Cross-origin mutation blocked")
        # Match the established administrative permission contract.
        if identity.get("global_role") != "system_administrator":
            raise HTTPException(403, "Administration erforderlich")
        with ctx.audit.actor_scope(identity["username"]):
            return ctx.build451.diagnose_retrieval_isolation_451()

    return app
