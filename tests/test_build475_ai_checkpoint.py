import hashlib
import io
import json
from copy import deepcopy
from unittest.mock import patch
import pytest
from eagleeye.interfaces.web.app475 import create_workspace_app475
from eagleeye.interfaces.web.app448 import COOKIE
from eagleeye.application.assistant471 import Summary, digest, validate_quote_bindings
from eagleeye.application.checkpoint475 import policy_benchmark, review_inventory
from eagleeye.application.local_ollama471 import NoRedirect
from test_build471_local_ai import workspace, csrf, reply, provider
from test_build474_review_safety import form_for

pytestmark=pytest.mark.parametrize('workspace',[create_workspace_app475],indirect=True)


def member(workspace,role):
    app,client,admin,case_id,*_=workspace;ctx=app.state.context
    username='member475';password='Independent!Secret_881'
    ctx.team_identity_359.create_user(identity=admin,username=username,display_name='Independent QA',
        global_role='investigator',password=password)
    ctx.team_governance_359.assign_case_role(identity=admin,case_id=case_id,username=username,case_role=role)
    fp=hashlib.sha256(b'testclient||testclient').hexdigest()
    session=ctx.team_identity_359.authenticate(username=username,password=password,client_fingerprint=fp)
    client.cookies.clear();client.cookies.set(COOKIE,session.token)
    return ctx.team_identity_359.validate_session(session.token,client_fingerprint=fp,touch=False)


def generate(workspace):
    app,client,user,case_id,doc_id,*_=workspace;service=app.state.assistant471
    with patch.object(service,'request',side_effect=provider(reply(service,user,case_id,doc_id),[])):
        return service.generate(user,case_id,[doc_id],'mistral:latest')


def test_checkpoint_counts_persisted_item_reviews_and_explicit_unknowns(workspace):
    app,client,user,case_id,*_=workspace;service=app.state.assistant471
    run=generate(workspace)
    before=client.get('/ai-checkpoint475',params={'case_id':case_id})
    assert before.status_code==200 and before.headers['cache-control']=='no-store'
    assert 'N/A' in before.text and 'Keine Produktivfreigabe' in before.text
    assert review_inventory(service,user,case_id)['review_required']==1
    assert client.post('/assistant471/review',data=form_for(client,case_id,run),follow_redirects=False).status_code==303
    fresh=type(service)(app.state.context)
    counts=review_inventory(fresh,user,case_id)
    assert counts['total']==counts['acknowledged']==counts['complete_item_reviews']==1
    assert counts['review_required']==counts['acknowledged_without_item_reviews']==0
    assert '/ai-checkpoint475?' in client.get('/',params={'case_id':case_id}).text
    assert app.version=='475.0' and client.get('/health').json()['next_checkpoint']=='480.0'
    assert client.get('/health').json()['production_release_ready'] is False
    client.cookies.clear()
    assert client.get('/ai-checkpoint475',params={'case_id':case_id}).status_code==401


@pytest.mark.parametrize('role',['read_only','investigator','reviewer'])
def test_real_case_roles_and_cross_case_authorization(workspace,role):
    app,client,admin,case_id,doc_id,other,*_=workspace;service=app.state.assistant471
    run=generate(workspace);user=member(workspace,role)
    assert client.get('/ai-checkpoint475',params={'case_id':case_id}).status_code==200
    assert client.get('/ai-checkpoint475',params={'case_id':other}).status_code==403
    if role!='investigator':
        with patch.object(service,'request') as network:
            with pytest.raises(PermissionError):service.generate(user,case_id,[doc_id],'mistral:latest')
        network.assert_not_called()
    else:
        with patch.object(service,'request',side_effect=provider(reply(service,user,case_id,doc_id),[])):
            assert service.generate(user,case_id,[doc_id],'mistral:latest')['status']=='review_required'
    if role!='reviewer':
        with pytest.raises(PermissionError):service.review(user,case_id,run['run_id'],'rejected','Weitere Prüfung ist erforderlich.')
    else:
        service.review(user,case_id,run['run_id'],'rejected','Weitere Prüfung ist erforderlich.')
        assert service.history(user,case_id)[0]['status']=='rejected'


def test_real_membership_revoked_during_model_call_prevents_commit(workspace):
    app,client,admin,case_id,doc_id,*_=workspace;service=app.state.assistant471
    user=member(workspace,'investigator');fake=provider(reply(service,user,case_id,doc_id),[])
    def request(method,path,payload=None,**kwargs):
        result=fake(method,path,payload,**kwargs)
        if path=='/api/chat':
            app.state.context.team_governance_359.revoke_case_role(identity=admin,case_id=case_id,
                username=user['username'],case_role='investigator',reason='Revoked during policy checkpoint')
        return result
    with patch.object(service,'request',side_effect=request):
        with pytest.raises(PermissionError):service.generate(user,case_id,[doc_id],'mistral:latest')
    assert service.history(admin,case_id)==[]


@pytest.mark.parametrize('mode',['message_tools','top_level_tools','malformed_json','model_changed'])
def test_model_contract_failures_do_not_persist(workspace,mode):
    app,client,user,case_id,doc_id,*_=workspace;service=app.state.assistant471
    fake=provider(reply(service,user,case_id,doc_id),[]);tags=0
    def request(method,path,payload=None,**kwargs):
        nonlocal tags
        result=fake(method,path,payload,**kwargs)
        if path=='/api/tags':
            tags+=1
            if mode=='model_changed' and tags>1:result['models'][0]['digest']='b'*64
        if path=='/api/chat':
            if mode=='message_tools':result['message']['tool_calls']=[{'function':{'name':'merge_identity'}}]
            if mode=='top_level_tools':result['tool_calls']=[{'function':{'name':'external_request'}}]
            if mode=='malformed_json':result['message']['content']='{invalid JSON'
        return result
    with patch.object(service,'request',side_effect=request):
        with pytest.raises(ValueError):service.generate(user,case_id,[doc_id],'mistral:latest')
    assert service.history(user,case_id)==[]


def test_literal_quote_does_not_establish_semantic_entailment(workspace):
    app,client,user,case_id,doc_id,*_=workspace;service=app.state.assistant471
    answer=reply(service,user,case_id,doc_id);answer['statements'][0]['text']='Die Firma wurde 2099 gegründet.'
    validate_quote_bindings(Summary.model_validate(answer),service.sources(user,case_id,[doc_id]))
    with patch.object(service,'request',side_effect=provider(answer,[])):
        run=service.generate(user,case_id,[doc_id],'mistral:latest')
    assert run['status']=='review_required' and not run['truth_determined'] and run['claims_created']==0
    assert 'Ein gültiges Zitat beweist nicht die Aussage' in client.get('/ai-checkpoint475',params={'case_id':case_id}).text


def test_inventory_exposes_legacy_review_and_fails_on_tampering(workspace):
    app,client,user,case_id,*_=workspace;service=app.state.assistant471;run=generate(workspace)
    service.review(user,case_id,run['run_id'],'acknowledged','Legacy overall review without item matrix.')
    assert review_inventory(service,user,case_id)['acknowledged_without_item_reviews']==1
    service.db.execute('UPDATE phase20_ai_summary_471 SET record_hash=? WHERE run_id=?',('tampered',run['run_id']))
    assert client.get('/ai-checkpoint475',params={'case_id':case_id}).status_code==409


def test_deterministic_policy_report_is_reproducible_and_not_llm_quality(workspace):
    first=policy_benchmark();second=policy_benchmark()
    assert first['fixture_sha256']==second['fixture_sha256']
    assert first['case_count']==24 and first['passed']==24
    assert first['llm_evaluated'] is first['semantic_entailment_enforced'] is first['production_release_ready'] is False
    assert next(x for x in first['outcomes'] if x['name']=='semantic_entailment_not_enforced')['actual_accept']


@pytest.mark.parametrize('mode',['oversized','non_json','non_object','redirect'])
def test_transport_response_budget_content_type_object_and_redirect(workspace,mode):
    import urllib.error
    app,*_=workspace;transport=app.state.assistant471.transport
    if mode=='redirect':
        with pytest.raises(urllib.error.HTTPError):
            NoRedirect().redirect_request(type('Request',(),{'full_url':transport.ENDPOINT})(),None,302,'redirect',{},'https://evil.example')
        return
    class Response(io.BytesIO):
        headers={'Content-Type':'text/html' if mode=='non_json' else 'application/json'}
    content=b'x'*128001 if mode=='oversized' else (b'[]' if mode=='non_object' else b'{}')
    with patch.object(transport.opener,'open',return_value=Response(content)):
        with pytest.raises(ValueError):transport.request('GET','/api/tags')


def test_untrusted_model_markup_is_escaped_in_browser(workspace):
    app,client,user,case_id,doc_id,*_=workspace;service=app.state.assistant471
    answer=reply(service,user,case_id,doc_id)
    answer['statements'][0]['text']='<script>merge_identity()</script>'
    answer['uncertainties']=['<img src=x onerror="external_action()">']
    with patch.object(service,'request',side_effect=provider(answer,[])):
        run=service.generate(user,case_id,[doc_id],'mistral:latest')
    page=client.get('/assistant471',params={'case_id':case_id})
    assert '&lt;script&gt;merge_identity()&lt;/script&gt;' in page.text
    assert '<script>merge_identity()' not in page.text and '<img src=x' not in page.text
    assert run['status']=='review_required' and run['claims_created']==0


def test_forged_global_role_cannot_read_foreign_case(workspace):
    app,client,admin,case_id,doc_id,other,*_=workspace;service=app.state.assistant471
    user=member(workspace,'read_only')
    forged={**user,'global_role':'system_administrator'}
    with pytest.raises(PermissionError):review_inventory(service,forged,other)
    with pytest.raises(PermissionError):service.generate(forged,case_id,[doc_id],'mistral:latest')
