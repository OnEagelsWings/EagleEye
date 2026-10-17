from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from eagleeye_pro.core.app_context import AppContext
from eagleeye.interfaces.web.app459 import create_workspace_app459
from eagleeye.interfaces.web.app448 import COOKIE

ROOT=Path(__file__).resolve().parents[1]
PASSWORD="Build459!Admin_9941"
FP="build459-fixture"


def initial(ctx):
    ctx.team_identity_359.create_initial_admin(
        username="admin459",display_name="Build 459 Analyst",password=PASSWORD)
    return auth_and_case(ctx)


def auth_and_case(ctx,with_case=True):
    issued=ctx.team_identity_359.authenticate(
        username="admin459",password=PASSWORD,client_fingerprint=FP)
    ident=ctx.team_identity_359.validate_session(issued.token,client_fingerprint=FP,touch=False)
    if not with_case:
        return ident,None
    case=ctx.team_governance_359.create_case(
        identity=ident,title="Build 459 restart-bound field case",client="Internal QA",
        purpose="Check durable case state and reference consistency across restart.",
        legal_basis="public_data")
    return ident,case


def test_build459_close_then_reopen_resume_fails_closed_on_changed_document(tmp_path):
    original=AppContext(base_dir=tmp_path)
    second=None
    try:
        ident,case=initial(original)
        field=original.field_readiness_459
        docservice=original.document_intelligence_458
        item=docservice.import_bytes(
            identity=ident,case_id=case["case_id"],filename="bounded.txt",
            raw=b"Public document statement located in one reviewable block.",
            source_url="https://example.org/public/bounded.txt")
        checkpoint=field.checkpoint(identity=ident,case_id=case["case_id"])
        assert checkpoint["requires_restart_verification"]
        same=field.verify_reopened(identity=ident,run_id=checkpoint["run_id"])
        assert same["result"]=="hold"
        assert same["close_then_reopen_verified"] is False
        before=int(field.db.one("SELECT COUNT(*) AS n FROM phase20_case_resume_run_459")["n"])
        original.close()
        second=AppContext(base_dir=tmp_path)
        ident2,_=auth_and_case(second,with_case=False)
        pass1=second.field_readiness_459.verify_reopened(identity=ident2,run_id=checkpoint["run_id"])
        assert pass1["result"]=="pass",pass1
        assert pass1["source_state_current"] is True
        pass2=second.field_readiness_459.verify_reopened(identity=ident2,run_id=checkpoint["run_id"])
        assert pass2["result"]=="pass"
        after=int(second.field_readiness_459.db.one("SELECT COUNT(*) AS n FROM phase20_case_resume_run_459")["n"])
        assert after==before

        # Delete the saved bytes. The former PASS must immediately become HOLD.
        doc=second.document_intelligence_458.anchors(
            identity=ident2,document_id=item["document_id"])["document"]
        (second.document_intelligence_458.root/doc["stored_relpath"]).unlink()
        hold=second.field_readiness_459.verify_reopened(identity=ident2,run_id=checkpoint["run_id"])
        assert hold["result"]=="hold"
        assert hold["case_integrity_valid"] is False
        assert not hold["source_state_current"]
    finally:
        original.close()
        if second is not None:
            second.close()


def test_build459_overlap_is_not_a_restart(tmp_path):
    first=AppContext(base_dir=tmp_path)
    second=None
    try:
        ident,case=initial(first)
        check=first.field_readiness_459.checkpoint(identity=ident,case_id=case["case_id"])
        second=AppContext(base_dir=tmp_path)
        ident2,_=auth_and_case(second,with_case=False)
        assert second.field_readiness_459.verify_reopened(
            identity=ident2,run_id=check["run_id"])["result"]=="hold"
        first.close()
        # Second context opened before the first closed.
        assert second.field_readiness_459.verify_reopened(
            identity=ident2,run_id=check["run_id"])["result"]=="hold"
    finally:
        first.close()
        if second:
            second.close()


def test_build459_health_and_authenticated_case_readiness(tmp_path):
    app=create_workspace_app459(base_dir=tmp_path)
    ctx=app.state.context
    try:
        ctx.team_identity_359.create_initial_admin(
            username="web459",display_name="Build 459 Web",password="Build459!Web_2211")
        ua="build459-ci"
        lang="en"
        fingerprint=hashlib.sha256(f"{ua}|{lang}|testclient".encode()).hexdigest()
        issued=ctx.team_identity_359.authenticate(
            username="web459",password="Build459!Web_2211",
            client_fingerprint=fingerprint)
        ident=ctx.team_identity_359.validate_session(
            issued.token,client_fingerprint=fingerprint,touch=False)
        case=ctx.team_governance_359.create_case(
            identity=ident,title="Build 459 API",client="Internal QA",
            purpose="Test case resume API under authentication.",legal_basis="public_data")
        with TestClient(app,headers={"user-agent":ua,"accept-language":lang}) as client:
            health=client.get("/health")
            assert health.status_code==200
            assert health.json()["build"]=="459.0"
            response=client.get(f"/api/build459/cases/{case['case_id']}/readiness")
            assert response.status_code==401
            client.cookies.set(COOKIE,issued.token)
            snap=client.get(f"/api/build459/cases/{case['case_id']}/readiness")
            assert snap.status_code==200
            assert snap.json()["next_full_checkpoint"]=="460.0"
            posted=client.post(f"/api/build459/cases/{case['case_id']}/checkpoint")
            assert posted.status_code==200,posted.text
            assert posted.json()["requires_restart_verification"] is True
    finally:
        ctx.close()


def test_build459_release_contract():
    assert 'version = "459.0.0"' in (ROOT/"pyproject.toml").read_text()
    assert 'BUILD = "459.0"' in (ROOT/"eagleeye_pro/version.py").read_text()
    assert (ROOT/"INSTALL_EAGLEEYE_459.py").is_file()
    assert (ROOT/"EAGLEEYE_PRO_459_0.py").is_file()
