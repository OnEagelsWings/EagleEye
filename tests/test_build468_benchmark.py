from __future__ import annotations
from eagleeye.application.benchmark468 import fixture, metrics, benchmark
from eagleeye.interfaces.web.app468 import create_workspace_app468
from eagleeye_pro.version import BUILD
from fastapi.testclient import TestClient

def test_build468_reproducible_goldset_metrics(tmp_path):
    assert BUILD=="468.0"
    rows,questions=fixture()
    assert len(rows)==len(questions)==100
    first=benchmark()
    second=benchmark()
    assert first["fixture_sha256"]==second["fixture_sha256"]
    assert first["not_product_search"] is True
    assert first["entity_resolution_f1"] is None
    assert all(0 <= v <= 1 for v in first["metrics"].values())
    assert first["metrics"]==second["metrics"]
    assert first["metrics"]["recall_at_50"]==1.0

def test_build468_dashboard_requires_auth_and_reports_non_product_status(tmp_path):
    app=create_workspace_app468(base_dir=tmp_path)
    ctx=app.state.context
    try:
        with TestClient(app) as client:
            unauthorized=client.get("/benchmark468",follow_redirects=False)
            assert unauthorized.status_code==303
            assert client.get("/health").json()["build"]=="468.0"
            assert not client.get("/health").json()["production_release_ready"]
    finally:
        ctx.close()
