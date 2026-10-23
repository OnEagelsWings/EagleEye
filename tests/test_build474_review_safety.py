import json
from copy import deepcopy
from unittest.mock import patch
import pytest
from eagleeye.interfaces.web.app474 import create_workspace_app474
from eagleeye.application.assistant471 import digest
from eagleeye.application.review474 import review_items
from test_build471_local_ai import workspace, csrf, reply, provider

pytestmark=pytest.mark.parametrize('workspace',[create_workspace_app474],indirect=True)


def draft(workspace):
    app,client,user,case_id,doc_id,*_=workspace;service=app.state.assistant471
    with patch.object(service,'request',side_effect=provider(reply(service,user,case_id,doc_id),[])):
        run=service.generate(user,case_id,[doc_id],'mistral:latest')
    return service,run


def form_for(client,case_id,run):
    form={'case_id':case_id,'csrf_token':csrf(client,case_id),'run_id':run['run_id'],
          'decision':'acknowledged','note':'Einzelinhalte am Original und im Kontext geprüft.'}
    for item in review_items(run):
        form['verdict_'+item['item_id']]='unclear'
        form['item_note_'+item['item_id']]='Weitere unabhängige Belege bleiben erforderlich.'
    return form


def test_item_reviews_are_required_persisted_and_mapped_to_content(workspace):
    app,client,user,case_id,*_=workspace;service,run=draft(workspace)
    form=form_for(client,case_id,run)
    incomplete={k:v for k,v in form.items() if not k.startswith(('verdict_','item_note_'))}
    assert client.post('/assistant471/review',data=incomplete).status_code==422
    assert service.history(user,case_id)[0]['status']=='review_required'
    assert client.post('/assistant471/review',data=form,follow_redirects=False).status_code==303
    saved=service.history(user,case_id)[0]
    assert set(saved['review']['assessments'])=={x['item_id'] for x in review_items(run)}
    assert saved['review']['truth_determined'] is False and saved['truth_determined'] is False
    page=client.get('/assistant471',params={'case_id':case_id})
    assert 'Unklar' in page.text and 'Weitere unabhängige Belege' in page.text


def test_changed_source_cannot_be_acknowledged_but_can_be_rejected(workspace):
    app,client,user,case_id,doc_id,*_=workspace;service,run=draft(workspace)
    form=form_for(client,case_id,run)
    doc=service.documents._document(doc_id)
    (service.documents.root/doc['stored_relpath']).write_bytes(b'Changed after model generation')
    assert client.post('/assistant471/review',data=form).status_code==409
    assert service.history(user,case_id)[0]['status']=='review_required'
    form.update(decision='rejected',note='Wegen verändertem Originalbeleg verworfen.')
    assert client.post('/assistant471/review',data=form,follow_redirects=False).status_code==303
    assert service.history(user,case_id)[0]['status']=='rejected'


def test_forged_item_and_blank_rationale_cannot_be_reviewed(workspace):
    app,client,user,case_id,*_=workspace;service,run=draft(workspace)
    for mutation in ['extra','blank','bad_verdict']:
        form=form_for(client,case_id,run)
        if mutation=='extra':form['verdict_foreign']='supported';form['item_note_foreign']='Arbitrary extra review item.'
        if mutation=='blank':form['item_note_s0']=' '*15
        if mutation=='bad_verdict':form['verdict_s0']='confirmed_fact'
        assert client.post('/assistant471/review',data=form).status_code==422
    assert service.history(user,case_id)[0]['status']=='review_required'


def test_history_pagination_retrieves_older_runs_with_case_scope(workspace):
    app,client,user,case_id,*_=workspace;service,run=draft(workspace)
    for i in range(24):
        clone=deepcopy(run);clone['run_id']='page474_'+str(i)
        service.db.execute('INSERT INTO phase20_ai_summary_471 VALUES(?,?,?,?)',
            (clone['run_id'],case_id,json.dumps(clone),digest(clone)))
    first=client.get('/assistant471',params={'case_id':case_id})
    second=client.get('/assistant471',params={'case_id':case_id,'offset':20})
    assert 'Ältere Entwürfe' in first.text and 'Neuere Entwürfe' in second.text
    assert run['run_id'] not in first.text and run['run_id'] in second.text
    assert len(service.history(user,case_id,offset=20))==5
    assert client.get('/assistant471',params={'case_id':case_id,'offset':-1}).status_code==422


def test_form_budget_rejects_oversized_requests_before_model(workspace):
    app,client,user,case_id,*_=workspace
    with patch.object(app.state.assistant471,'request') as call:
        response=client.post('/assistant471/generate',content='question='+'x'*64000,
            headers={'Content-Type':'application/x-www-form-urlencoded'})
    assert response.status_code==413
    call.assert_not_called()


def test_disconnecting_request_does_not_free_running_model_slot(workspace):
    import asyncio, threading, httpx
    app,client,user,case_id,doc_id,*_=workspace
    token=csrf(client,case_id)
    started=threading.Event();release=threading.Event();finished=threading.Event()
    def slow_model(*args,**kwargs):
        started.set()
        try:
            release.wait(timeout=8)
            return {'run_id':'cancelled-http-transport-test'}
        finally:finished.set()
    async def scenario():
        transport=httpx.ASGITransport(app=app,client=('testclient',50000))
        async with httpx.AsyncClient(transport=transport,base_url='http://testserver',
                headers={'User-Agent':'testclient'},cookies=client.cookies) as http:
            data={'case_id':case_id,'csrf_token':token,'document_id':doc_id,'model':'mistral:latest'}
            task=asyncio.create_task(http.post('/assistant471/generate',data=data))
            try:
                assert await asyncio.to_thread(started.wait,5)
                task.cancel()
                with pytest.raises(asyncio.CancelledError):await task
                blocked=await http.post('/assistant471/generate',data=data)
                assert blocked.status_code==429
            finally:
                release.set()
                await asyncio.to_thread(finished.wait,5)
    with patch.object(app.state.assistant471,'generate',side_effect=slow_model):
        asyncio.run(scenario())


def test_maximum_multilingual_review_matrix_fits_bounded_form(workspace):
    app,client,user,case_id,doc_id,*_=workspace;service=app.state.assistant471
    answer=reply(service,user,case_id,doc_id)
    answer['statements']*=12
    answer['uncertainties']*=8
    answer['answer_status']='source_bound'
    answer['alternatives']=[{'title':'Alternative Erklärung '+str(i),
        'explanation':'Eine vorläufige Interpretation der Quellen.',
        'supporting':answer['statements'][0]['citations'],'contradicting':[],
        'missing_evidence':'Unabhängige Bestätigung ist weiterhin nötig.',
        'verification_question':'Welche weiteren Originalbelege gibt es?'} for i in range(3)]
    with patch.object(service,'request',side_effect=provider(answer,[])):
        run=service.generate(user,case_id,[doc_id],'mistral:latest',
            question='Welche Erklärungen sind möglich?',analysis_mode='alternatives')
    form=form_for(client,case_id,run)
    for key in form:
        if key.startswith('item_note_'):form[key]='\U0001f50e'*1000
    form['note']='\U0001f50e'*2000
    assert len(review_items(run))==23
    response=client.post('/assistant471/review',data=form,follow_redirects=False)
    assert response.status_code==303,response.text
    assert service.history(user,case_id)[0]['status']=='acknowledged'
