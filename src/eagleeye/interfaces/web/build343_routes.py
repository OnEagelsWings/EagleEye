from __future__ import annotations

from typing import Any, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


def mount_build343_routes(app: FastAPI, *, ctx: Any, require_auth: Callable[[Request], dict[str, Any]]) -> None:
    """Dedicated Phase-15 router slice; avoids adding another inline route to app.py."""

    @app.get("/api/build343")
    def api_build343(request: Request):
        require_auth(request)
        return JSONResponse(ctx.build343.dashboard())
