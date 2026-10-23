from unittest.mock import patch
import pytest
from eagleeye.application.question472 import Answer472
from eagleeye.interfaces.web.app472 import create_workspace_app472
from test_build471_local_ai import workspace, csrf, reply, provider


def test_question_is_persisted_and_source_bound(workspace):
    app, client, user, case_id, doc_id, *_ = workspace
    service = app.state.assistant471
    answer = dict(reply(service, user, case_id, doc_id), answer_status='source_bound')
    calls=[]
    with patch.object(service,'request',side_effect=provider(answer,calls)):
        run=service.generate(user,case_id,[doc_id],'mistral:latest',question='Wann wurde das Unternehmen gegründet?')
    assert run['task']=='question' and run['question'].startswith('Wann')
    assert run['summary']['answer_status']=='source_bound'
    assert service.history(user,case_id)[0]['question']==run['question']
    sent=next(p for _,path,p in calls if path=='/api/chat')
    assert 'working_question' in sent['messages'][1]['content']
    assert 'insufficient_evidence' in sent['messages'][0]['content']
    page=client.get('/assistant471',params={'case_id':case_id})
    assert 'Wann wurde' in page.text and '#anchor-' in page.text


def test_missing_evidence_must_abstain_without_statements(workspace):
    app,client,user,case_id,doc_id,*_=workspace
    service=app.state.assistant471
    answer={'answer_status':'insufficient_evidence','statements':[],
            'uncertainties':['Die gewählten Auszüge nennen keinen Geschäftsführer.']}
    with patch.object(service,'request',side_effect=provider(answer,[])):
        run=service.generate(user,case_id,[doc_id],'mistral:latest',question='Wer führt das Unternehmen?')
    assert not run['summary']['statements']
    assert 'Quellen reichen' in client.get('/assistant471',params={'case_id':case_id}).text
    for invalid in [dict(answer,answer_status='source_bound'),
                    dict(answer,statements=reply(service,user,case_id,doc_id)['statements'])]:
        with pytest.raises(ValueError):Answer472.model_validate(invalid)


def test_invalid_question_rejected_before_model(workspace):
    app,_,user,case_id,doc_id,*_=workspace
    service=app.state.assistant471
    with patch.object(service,'request') as network:
        with pytest.raises(ValueError):service.generate(user,case_id,[doc_id],'mistral:latest',question='x'*1001)
    network.assert_not_called()


def test_current_factory_exposes_question_field_and_current_launcher(tmp_path):
    from fastapi.testclient import TestClient
    import hashlib
    from eagleeye.interfaces.web.app448 import COOKIE
    app=create_workspace_app472(base_dir=tmp_path);ctx=app.state.context
    try:
        ctx.team_identity_359.create_initial_admin(username='questionqa',display_name='QA',password='Synthetic!Password_88')
        fp=hashlib.sha256(b'testclient||testclient').hexdigest()
        session=ctx.team_identity_359.authenticate(username='questionqa',password='Synthetic!Password_88',client_fingerprint=fp)
        user=ctx.team_identity_359.validate_session(session.token,client_fingerprint=fp,touch=False)
        case=ctx.team_governance_359.create_case(identity=user,title='Question case',client='QA',purpose='Synthetic test',legal_basis='public_data')
        with TestClient(app) as client:
            client.cookies.set(COOKIE,session.token)
            page=client.get('/assistant471',params={'case_id':case['case_id']})
            assert 'name="question"' in page.text
            assert '/assistant471?' in client.get('/',params={'case_id':case['case_id']}).text
            assert client.get('/health').json()['build']=='472.0'
    finally:ctx.close()
