from __future__ import annotations

import html
import secrets
from pathlib import Path
from typing import Any

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from eagleeye_pro.version import BUILD, BUILD_NAME
from .models import IntakeRequestModel


class ConnectorExecutionRequest(BaseModel):
    case_id: str = ""
    connector_id: str
    input_value: str
    options: dict[str, Any] = Field(default_factory=dict)
    explicit_live_confirmation: bool = False


def _token(base_dir: Path) -> str:
    target = base_dir / "data" / "security_104_1" / "local_api_token"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return target.read_text(encoding="utf-8").strip()
    value = secrets.token_urlsafe(32)
    target.write_text(value, encoding="utf-8")
    try:
        target.chmod(0o600)
    except OSError:
        pass
    return value


def create_app(*, base_dir: str | Path | None = None) -> FastAPI:
    root = Path(base_dir or Path.cwd()).resolve()
    local_token = _token(root)
    app = FastAPI(title=BUILD_NAME, version=BUILD, docs_url="/api/docs", redoc_url=None)
    app.state.base_dir = str(root)
    app.state.local_token = local_token

    async def require_local(request: Request, x_eagleeye_token: str = Header(default=""), ee_session: str = Cookie(default="")) -> str:
        host = request.client.host if request.client else ""
        if host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
            raise HTTPException(status_code=403, detail="Loopback access only")
        query_token = request.query_params.get("token", "")
        supplied = x_eagleeye_token or ee_session or query_token
        if not secrets.compare_digest(supplied, local_token):
            raise HTTPException(status_code=403, detail="Local session token required")
        return supplied

    def context():
        from eagleeye_pro.core.app_context import AppContext
        ctx = AppContext(base_dir=root)
        try:
            yield ctx
        finally:
            ctx.close()

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "build": BUILD, "architecture": "core-recomposition-104.1"}

    @app.get("/", response_class=HTMLResponse)
    def home(response: Response, _: str = Depends(require_local), ctx=Depends(context)) -> str:
        response.set_cookie("ee_session", local_token, httponly=True, samesite="strict")
        status = ctx.core_recomposition_104_1.status()
        case = ctx.platform_103_1.active_case()
        return f"""<!doctype html><html lang='de'><head><meta charset='utf-8'><title>{html.escape(BUILD_NAME)}</title>
<style>body{{font-family:system-ui;max-width:1100px;margin:40px auto;padding:0 20px;background:#f5f7fa}}.card{{background:white;padding:18px;border-radius:10px;margin:12px 0}}code,pre{{background:#101820;color:#e9f0f6;padding:10px;border-radius:6px;display:block;overflow:auto}}a{{color:#174f82}}</style></head><body>
<h1>{html.escape(BUILD_NAME)}</h1><div class='card'><b>Aktiver Fall:</b> {html.escape(case.get('title',''))}<br><b>Case-ID:</b> {html.escape(case.get('case_id',''))}</div>
<div class='card'><h2>Core Recomposition</h2><pre>{html.escape(__import__('json').dumps(status,ensure_ascii=False,indent=2))}</pre></div>
<div class='card'><h2>Collection</h2><p><a href='/collection'>Collection Engine 105 öffnen</a></p></div>
<div class='card'><h2>API</h2><p><a href='/api/docs'>OpenAPI / Swagger UI</a></p><code>POST /api/intake<br>GET /api/artifacts<br>GET /api/connectors<br>POST /api/connectors/execute<br>GET /api/status<br>GET /api/collection/readiness</code></div>
<p>Alle Funde bleiben <b>candidate_not_claim</b>. Live-Connectoren erfordern Legal Scope und Einzelbestätigung.</p></body></html>"""

    @app.get("/api/status")
    def api_status(_: str = Depends(require_local), ctx=Depends(context)) -> dict[str, Any]:
        return ctx.core_recomposition_104_1.status()

    @app.get("/api/cases")
    def cases(_: str = Depends(require_local), ctx=Depends(context)) -> list[dict[str, Any]]:
        return ctx.platform_103_1.list_cases()

    @app.post("/api/intake")
    def intake(payload: IntakeRequestModel, _: str = Depends(require_local), ctx=Depends(context)) -> dict[str, Any]:
        return ctx.core_recomposition_104_1.include_finding(**payload.model_dump())

    @app.get("/api/artifacts")
    def artifacts(case_id: str = "", _: str = Depends(require_local), ctx=Depends(context)) -> list[dict[str, Any]]:
        cid = ctx.platform_103_1.resolve_case_id(case_id)
        return [a.model_dump(mode="json") for a in ctx.core_recomposition_104_1.repository.list_artifacts(cid)]

    @app.get("/api/connectors")
    def connectors(_: str = Depends(require_local), ctx=Depends(context)) -> list[dict[str, Any]]:
        return ctx.core_recomposition_104_1.connectors.list_connectors()

    @app.post("/api/connectors/execute")
    def connector_execute(payload: ConnectorExecutionRequest, _: str = Depends(require_local), ctx=Depends(context)) -> dict[str, Any]:
        cid = ctx.platform_103_1.resolve_case_id(payload.case_id)
        return ctx.core_recomposition_104_1.connectors.execute(
            case_id=cid, connector_id=payload.connector_id, input_value=payload.input_value,
            options=payload.options, explicit_live_confirmation=payload.explicit_live_confirmation,
        )

    return app
