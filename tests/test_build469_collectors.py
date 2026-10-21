from __future__ import annotations
import hashlib
import re
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from eagleeye.application.collectors469 import (
    collect, normalize_indicator, endpoint, _fetch_fixed_json,
)
from eagleeye.interfaces.web.app448 import COOKIE
from eagleeye.interfaces.web.app469 import create_workspace_app469
from eagleeye_pro.version import BUILD

def test_build469_fixed_host_validation():
    assert normalize_indicator("dns","Example.COM") == "example.com"
    assert normalize_indicator("dns","faß.de") == "xn--fa-hia.de"
    assert endpoint("dns","example.com").startswith("https://dns.google/resolve?")
    assert endpoint("rdap_com","example.com").startswith("https://rdap.verisign.com/com/v1/domain/")
    assert normalize_indicator("crossref","10.1234/Sample") == "10.1234/Sample"
    legacy="10.1002/(SICI)1097-4571(199706)48:6<369::AID-ASI4>3.0.CO;2-O"
    assert normalize_indicator("crossref",legacy)==legacy
    assert "%3C" in endpoint("crossref",legacy) and "%3E" in endpoint("crossref",legacy)
    assert "%23" in endpoint("crossref","10.1234/A#B")

    for value in ("http://127.0.0.1/","localhost","10.0.0.1", "-invalid.com"):
        with pytest.raises(ValueError):
            normalize_indicator("dns",value)
    with pytest.raises(ValueError):
        normalize_indicator("rdap_com","example.org")
    with pytest.raises(ValueError):
        _fetch_fixed_json("http://127.0.0.1/private")
    packet=collect("dns","example.com",fetcher=lambda url:{"Status":0,"Answer":[]})
    assert packet["verified_claim"] is False
    assert packet["source_url"].startswith("https://dns.google/")
    assert b"unverified" in packet["raw"]
    long_packet=collect("crossref","10.1234/Sample",
        fetcher=lambda url:{"message":{"abstract":"A"*7000}})
    chunks=long_packet["raw"].decode("utf-8").split("\n\n")
    assert len(chunks)>=4
    assert all(len(part)<=2500 for part in chunks[1:])
    assert sum(part.count("A") for part in chunks)==7000


def test_build469_authenticated_case_import_and_csrf(tmp_path):
    app=create_workspace_app469(base_dir=tmp_path)
    ctx=app.state.context
    try:
        with TestClient(app) as client:
            assert client.get("/collect469",params={"case_id":"fake"},follow_redirects=False).status_code==303
            ctx.team_identity_359.create_initial_admin(
                username="qa469",display_name="QA",password="Build469!Password_88")
            fp=hashlib.sha256(b"testclient||testclient").hexdigest()
            session=ctx.team_identity_359.authenticate(
                username="qa469",password="Build469!Password_88",client_fingerprint=fp)
            ident=ctx.team_identity_359.validate_session(
                session.token,client_fingerprint=fp,touch=False)
            case=ctx.team_governance_359.create_case(
                identity=ident,title="Collection case",client="QA",
                purpose="Synthetic public source capture",legal_basis="public_data")
            case_id=case["case_id"]
            client.cookies.set(COOKIE,session.token)
            page=client.get("/collect469",params={"case_id":case_id})
            assert page.status_code==200
            assert "RDAP" in page.text and "Crossref" in page.text
            token=re.search(r'name="csrf_token" value="([a-f0-9]{64})"',page.text)
            assert token
            data={"case_id":case_id,"provider":"dns","indicator":"example.com"}
            assert client.post("/collect469/import",data=data,follow_redirects=False).status_code==403
            # Denied research permission must prevent *all* network egress.
            with patch.object(ctx.team_governance_359,"authorize",side_effect=PermissionError("denied")):
                with patch("eagleeye.interfaces.web.app469.collect") as blocked_collector:
                    denied=client.post("/collect469/import",
                        data={**data,"csrf_token":token.group(1)},follow_redirects=False)
                    assert denied.status_code==403
                    blocked_collector.assert_not_called()
            with patch("eagleeye.interfaces.web.app469.collect",
                       side_effect=lambda provider,indicator: collect(
                         provider,indicator,fetcher=lambda url:{"Status":0,"Answer":[]})):
                response=client.post("/collect469/import",
                    data={**data,"csrf_token":token.group(1)},follow_redirects=False)
            assert response.status_code==303
            assert "/documents458?" in response.headers["location"]
            documents=ctx.document_intelligence_458.documents(identity=ident,case_id=case_id)
            assert len(documents)==1
            assert documents[0]["source_url"].startswith("https://dns.google/resolve?")
            assert client.get("/collect469",params={"case_id":"other"},follow_redirects=False).status_code==303
            home=client.get("/",params={"case_id":case_id})
            assert "/collect469?" in home.text
            health=client.get("/health").json()
            assert health["build"]=="469.0" and not health["production_release_ready"]
    finally:
        ctx.close()
