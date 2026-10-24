"""Real source review, complete export, authorization and portable restore."""
import hashlib,json,sqlite3,zipfile
from copy import deepcopy
from unittest.mock import patch
from urllib.parse import urlencode
import pytest
from eagleeye.interfaces.web.app479 import create_workspace_app479
from eagleeye.interfaces.web.findings478 import notes_for_case,notes_db,finding_hash,BASE_COLUMNS,INSERT_FINDING_SQL
from eagleeye.interfaces.web.report479 import source_states
from eagleeye.bootstrap.recovery479 import create_backup,restore_backup,MANIFEST
from eagleeye.bootstrap.runtime_lock import workspace_runtime_lock
from test_build471_local_ai import workspace
from test_build478_findings import form,csrf_session
from test_build475_ai_checkpoint import member

pytestmark=pytest.mark.parametrize('workspace',[create_workspace_app479],indirect=True)

def saved(workspace):
    app,client,*_=workspace
    assert client.post('/workbench/findings',data=form(workspace),follow_redirects=False).status_code==303
    return notes_for_case(app,workspace[3])[0]

def review_form(workspace,row):
    return {'case_id':workspace[3],'finding_id':row['finding_id'],'expected_hash':row['record_hash'],
        'csrf':workspace[1].cookies.get('ee_auth_csrf'),'reason':'Compared the exact original and retained the remaining uncertainty.',
        'decision':'reviewed'}

def test_review_updates_integrity_history_and_working_export(workspace):
    app,client,user,cid,*_=workspace;row=saved(workspace);data=review_form(workspace,row)
    assert client.post('/workbench/report/review',data=data,follow_redirects=False).status_code==303
    current=notes_for_case(app,cid)[0]
    assert current['review_state']=='reviewed_self' and finding_hash(current)==current['record_hash']
    history=app.state.context.db.all('SELECT * FROM operational_finding_reviews_479 WHERE case_id=?',(cid,))
    assert len(history)==1 and history[0]['before_hash']==row['record_hash'] and history[0]['after_hash']==current['record_hash']
    output=client.get('/workbench/report.md',params={'case_id':cid})
    assert output.status_code==200 and row['title'] in output.text and 'reviewed_self' in output.text
    assert 'KEIN freigegebenes' in output.text and output.headers['cache-control']=='no-store'
    assert client.post('/workbench/report/review',data=data).status_code==409
    assert len(app.state.context.db.all('SELECT * FROM operational_finding_reviews_479'))==1

@pytest.mark.parametrize('mode',['csrf','origin','oversized','foreign'])
def test_review_form_and_case_guards(workspace,mode):
    app,client,user,cid,doc,other,*_=workspace;row=saved(workspace);data=review_form(workspace,row);headers={}
    if mode=='csrf':data['csrf']='forged'
    if mode=='origin':headers['Origin']='null'
    if mode=='foreign':data['case_id']=other
    if mode=='oversized':
        response=client.post('/workbench/report/review',content=iter([b'reason=',b'x'*24001]),headers={'Content-Type':'application/x-www-form-urlencoded'})
        assert response.status_code==413
    else:assert client.post('/workbench/report/review',data=data,headers=headers).status_code in {403,404}
    assert notes_for_case(app,cid)[0]['review_state']=='unreviewed'

def test_changed_original_prevents_acceptance_but_allows_recorded_rejection(workspace):
    app,client,user,cid,doc,*_=workspace;row=saved(workspace);data=review_form(workspace,row)
    service=app.state.context.document_intelligence_458
    (service.root/service._document(doc)['stored_relpath']).write_bytes(b'Original changed')
    assert client.post('/workbench/report/review',data=data).status_code==409
    data['decision']='rejected'
    assert client.post('/workbench/report/review',data=data,follow_redirects=False).status_code==303
    exported=client.get('/workbench/report.md',params={'case_id':cid})
    assert exported.status_code==200 and 'changed' in exported.text and 'rejected' in exported.text

def test_read_only_reviewer_and_second_account_are_distinct(workspace):
    app,client,admin,cid,*_=workspace;row=saved(workspace);data=review_form(workspace,row)
    member(workspace,'read_only');data['csrf']=csrf_session(workspace,'member475','Independent!Secret_881')
    assert client.post('/workbench/report/review',data=data).status_code==403
    page=client.get('/workbench/report',params={'case_id':cid})
    assert page.status_code==200 and '<form method="post"' not in page.text
    # Grant the canonical existing reviewer role; no forged dict-based authority.
    app.state.context.team_governance_359.assign_case_role(identity=admin,case_id=cid,username='member475',case_role='reviewer')
    assert client.post('/workbench/report/review',data=data,follow_redirects=False).status_code==303
    assert notes_for_case(app,cid)[0]['review_state']=='reviewed_second_account'

def test_unicode_reason_limit_and_history_tampering(workspace):
    app,client,user,cid,*_=workspace;row=saved(workspace);data=review_form(workspace,row);data['reason']='漢'*1200
    assert client.post('/workbench/report/review',data=data,follow_redirects=False).status_code==303
    app.state.context.db.execute("UPDATE operational_finding_reviews_479 SET reason='tampered'")
    assert client.get('/workbench/report.md',params={'case_id':cid}).status_code==409
    assert client.get('/workbench/report',params={'case_id':cid}).status_code==409

def test_complete_251_note_export_and_literal_remote_markup(workspace):
    app,client,user,cid,*_=workspace;data=form(workspace)
    data['title']='![remote](https://tracking.invalid/pixel)'
    data['interpretation']='<script>external_action()</script>\n![tracking](https://tracking.invalid/image)'
    assert client.post('/workbench/findings',data=data,follow_redirects=False).status_code==303
    first=notes_for_case(app,cid)[0]
    with notes_db(app) as db:
        for index in range(250):
            row=deepcopy(first);row['finding_id']='bulk479-'+str(index);row['title']='Distinct note '+str(index)
            row['record_hash']=finding_hash(row)
            db.execute(INSERT_FINDING_SQL,tuple(row[k] for k in BASE_COLUMNS+('record_hash',)))
    service=app.state.context.document_intelligence_458
    with patch.object(service,'_payload_current',wraps=service._payload_current) as payload:
        output=client.get('/workbench/report.md',params={'case_id':cid})
    assert payload.call_count==1 and output.status_code==200
    assert 'Arbeitsbefunde: 251' in output.text and 'Distinct note 0' in output.text and 'Distinct note 249' in output.text
    assert '\n    <script>external_action()' in output.text and '\n    ![tracking]' in output.text
    last=client.get('/workbench/report',params={'case_id':cid,'offset':250})
    assert last.status_code==200 and first['title'] in last.text
    assert client.get('/workbench/report.md',params={'case_id':'unavailable'}).status_code==403

def test_offline_backup_restore_preserves_case_original_note_and_revokes_sessions(workspace,tmp_path):
    app,client,user,cid,doc,*_=workspace;row=saved(workspace)
    assert client.post('/workbench/report/review',data=review_form(workspace,row),follow_redirects=False).status_code==303
    root=app.state.context.base_dir
    registry=root/'entity_registry_test.sqlite3'
    conn=sqlite3.connect(registry);conn.execute('CREATE TABLE test(value TEXT)');conn.execute("INSERT INTO test VALUES('entity-preserved')");conn.commit();conn.close()
    archive=tmp_path.parent/(tmp_path.name+'-backup.zip');target=tmp_path.parent/(tmp_path.name+'-restored')
    try:
        result=create_backup(root,archive)
        receipt=restore_backup(archive,target)
        assert result['files']==receipt['verified_files'] and receipt['sessions_revoked']>=1
        assert not (target/'data/security_364/local_session_token').exists()
        assert (target/registry.name).is_file()
        fresh=create_workspace_app479(base_dir=target)
        try:
            ctx=fresh.state.context
            issued=ctx.team_identity_359.authenticate(username='qa471',password='Build471!Password_88',client_fingerprint='restored')
            identity=ctx.team_identity_359.validate_session(issued.token,client_fingerprint='restored',touch=False)
            assert ctx.team_governance_359.visible_cases(identity)
            assert notes_for_case(fresh,cid)[0]['review_state']=='reviewed_self'
            assert source_states(fresh,identity,cid,notes_for_case(fresh,cid))[row['finding_id']]=='snapshot_match'
            assert ctx.team_identity_359.verify_access_chain()['ok']
        finally:fresh.state.context.close()
        with pytest.raises(FileExistsError):restore_backup(archive,target)
    finally:archive.unlink(missing_ok=True)

def test_backup_refuses_running_workspace_and_internal_target(workspace,tmp_path):
    app,*_=workspace;root=app.state.context.base_dir
    with workspace_runtime_lock(root):
        with pytest.raises(RuntimeError):create_backup(root,tmp_path.parent/(tmp_path.name+'-locked.zip'))
    with pytest.raises(ValueError):create_backup(root,root/'backup.zip')

@pytest.mark.parametrize('mode',['hash','traversal','duplicate'])
def test_corrupt_or_escaping_restore_leaves_no_target(workspace,tmp_path,mode):
    app,*_=workspace;root=app.state.context.base_dir
    archive=tmp_path.parent/(tmp_path.name+'-good.zip');bad=tmp_path.parent/(tmp_path.name+'-bad.zip');target=tmp_path.parent/(tmp_path.name+'-badrestore')
    try:
        create_backup(root,archive)
        with zipfile.ZipFile(archive) as incoming,zipfile.ZipFile(bad,'w') as out:
            for info in incoming.infolist():
                payload=incoming.read(info)
                if info.filename==MANIFEST:
                    data=json.loads(payload)
                    if mode=='hash':data['files'][0]['sha256']='0'*64
                    if mode=='traversal':data['files'][0]['path']='data/../../escaped'
                    payload=json.dumps(data).encode()
                out.writestr(info,payload)
            if mode=='duplicate':out.writestr('DATA/EAGLEEYE.DB',b'collision')
        with pytest.raises((ValueError,KeyError)):restore_backup(bad,target)
        assert not target.exists()
    finally:archive.unlink(missing_ok=True);bad.unlink(missing_ok=True)
