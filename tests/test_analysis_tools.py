import json
import pytest
from eagleeye.interfaces.web.app478 import create_workspace_app478
from test_build471_local_ai import workspace
from test_build478_findings import csrf_session

pytestmark = pytest.mark.parametrize("workspace", [create_workspace_app478], indirect=True)

def test_local_analysis_handoff_and_case_document(workspace):
    _, client, _, case_id, *_ = workspace
    csrf_session(workspace)
    page = client.get("/workbench/analysis-tools", params={"case_id":case_id})
    assert page.status_code == 200
    assert "127.0.0.1:48137/#caseId=" in page.text
    assert "/workbench/analysis-tools" in client.get("/workbench",params={"case_id":case_id}).text
    raw = json.dumps({"format":"eagleeye-analysis/1","caseId":case_id,"tool":"metadata","body":"Synthetic test"})
    saved = client.post(f"/api/build458/cases/{case_id}/documents",
                        files={"file":("Analysebefund.txt",raw,"text/plain")},
                        data={"title":"Lokaler Analysebefund"})
    assert saved.status_code == 200, saved.text
    assert "Lokaler Analysebefund" in client.get(f"/api/build458/cases/{case_id}/documents").text
    client.cookies.clear()
    assert client.get("/workbench/analysis-tools",params={"case_id":case_id}).status_code == 401
