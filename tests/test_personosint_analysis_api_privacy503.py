"""Current-head regression: case-bound person analysis API must not be cached or leak referrers."""
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from eagleeye.interfaces.web import personosint_analysis502 as view


def test_person_analysis_api_has_private_response_headers(monkeypatch):
    app = FastAPI()
    app.state.context = object()
    monkeypatch.setattr(view, "case_access", lambda app, request, case_id: ("reviewer", object()))
    monkeypatch.setattr(view.po_analysis, "analyze", lambda ctx, user, case_id: {
        "available": True, "facts": [], "case_scoped": case_id,
    })
    view.attach_personosint_analysis502(app, 503)
    route = next(r for r in app.routes if getattr(r, "path", None) == "/api/research/personanalyse")
    response = route.endpoint(SimpleNamespace(), case_id="synthetic-case")
    assert isinstance(response, JSONResponse)
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert b"synthetic-case" in response.body
