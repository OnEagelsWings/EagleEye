import pytest
from eagleeye.interfaces.web.app480 import create_workspace_app480
from eagleeye.interfaces.web.findings478 import notes_for_case
from test_build471_local_ai import workspace
from test_build478_findings import form
from test_build479_report_recovery import review_form
pytestmark=pytest.mark.parametrize('workspace',[create_workspace_app480],indirect=True)

def test_checkpoint_counts_actual_review_and_source_state(workspace):
    app,client,user,cid,doc,*_=workspace
    assert client.get('/health').json()['next_checkpoint']=='485.0'
    assert app.version=='480.0'
    assert client.post('/workbench/findings',data=form(workspace),follow_redirects=False).status_code==303
    row=notes_for_case(app,cid)[0]
    assert client.post('/workbench/report/review',data=review_form(workspace,row),follow_redirects=False).status_code==303
    from eagleeye.interfaces.web.checkpoint480 import checkpoint_inventory
    counts=checkpoint_inventory(app,user,cid)
    assert counts['total']==counts['snapshot_match']==counts['reviewed_self']==1
    assert counts['reviewed_second_account']==counts['claims_created_automatically']==0
    service=app.state.context.document_intelligence_458
    (service.root/service._document(doc)['stored_relpath']).write_bytes(b'changed original')
    counts=checkpoint_inventory(app,user,cid)
    assert counts['changed_or_missing']==1 and counts['reviewed_self']==0
    page=client.get('/workbench/checkpoint',params={'case_id':cid})
    assert page.status_code==200 and 'NEIN' in page.text and 'KEINE' not in page.text
    assert page.headers['cache-control']=='no-store'
    assert client.get('/workbench/checkpoint',params={'case_id':'foreign'}).status_code==403
    client.cookies.clear()
    assert client.get('/workbench/checkpoint',params={'case_id':cid}).status_code==401

def test_checkpoint_rejects_tampered_review_history(workspace):
    app,client,user,cid,*_=workspace
    assert client.post('/workbench/findings',data=form(workspace),follow_redirects=False).status_code==303
    row=notes_for_case(app,cid)[0]
    assert client.post('/workbench/report/review',data=review_form(workspace,row),follow_redirects=False).status_code==303
    app.state.context.db.execute("UPDATE operational_finding_reviews_479 SET reason='changed'")
    assert client.get('/workbench/checkpoint',params={'case_id':cid}).status_code==409
