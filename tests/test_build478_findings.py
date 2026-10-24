import hashlib,json,sqlite3
from copy import deepcopy
from unittest.mock import patch
import pytest
from eagleeye.interfaces.web.app478 import create_workspace_app478
from eagleeye.interfaces.web.app448 import COOKIE
from eagleeye.interfaces.web.app364 import CSRF_COOKIE
from eagleeye.interfaces.web.findings478 import notes_for_case,notes_db,finding_hash,BASE_COLUMNS
from test_build471_local_ai import workspace
from test_build475_ai_checkpoint import member

pytestmark=pytest.mark.parametrize('workspace',[create_workspace_app478],indirect=True)


def csrf_session(workspace,username='qa471',password='Build471!Password_88'):
    app,client,*_=workspace;ctx=app.state.context
    session=ctx.team_identity_359.authenticate(username=username,password=password,
        client_fingerprint=hashlib.sha256(b'testclient||testclient').hexdigest())
    client.cookies.clear();client.cookies.set(COOKIE,session.token);client.cookies.set(CSRF_COOKIE,session.csrf_token)
    return session.csrf_token


def form(workspace):
    app,client,user,case_id,doc_id,*_=workspace
    token=csrf_session(workspace)
    anchor=app.state.context.document_intelligence_458.anchors(identity=user,document_id=doc_id)['anchors'][0]
    return {'case_id':case_id,'csrf':token,'anchor_ref':doc_id+'|'+anchor['anchor_id'],
        'title':'Independent source interpretation','interpretation':'The source supports a working hypothesis, with independent checks still missing.',
        'kind':'hypothesis'}


def test_real_note_persists_in_canonical_database_and_links_original(workspace):
    app,client,user,case_id,doc_id,*_=workspace
    assert client.post('/workbench/findings',data=form(workspace),follow_redirects=False).status_code==303
    row=notes_for_case(app,case_id)[0]
    assert row['review_state']=='unreviewed' and row['kind']=='hypothesis'
    assert row['anchor_hash'] and finding_hash(row)==row['record_hash']
    assert app.state.context.db.one('SELECT COUNT(*) n FROM operational_findings_478')['n']==1
    assert not (app.state.context.base_dir/'data/operational_notes_478.sqlite3').exists()
    view=client.get('/workbench/findings',params={'case_id':case_id})
    assert row['title'] in view.text and '#anchor-'+row['anchor_id'] in view.text
    assert 'company was founded in 2001.' in row['source_excerpt']
    assert 'Befund notieren' in client.get('/workbench/sources',params={'case_id':case_id}).text


@pytest.mark.parametrize('mode',['foreign_anchor','missing_anchor','modified_file','modified_anchor','rejected_extraction'])
def test_source_boundaries_and_integrity_fail_closed(workspace,mode):
    app,client,user,case_id,doc_id,other,other_doc=workspace;ctx=app.state.context;service=ctx.document_intelligence_458
    data=form(workspace)
    if mode=='foreign_anchor':data['anchor_ref']=doc_id+'|'+service.anchors(identity=user,document_id=other_doc)['anchors'][0]['anchor_id']
    if mode=='missing_anchor':data['anchor_ref']=doc_id+'|missing'
    if mode=='modified_file':(service.root/service._document(doc_id)['stored_relpath']).write_bytes(b'changed source')
    if mode=='modified_anchor':ctx.db.execute('UPDATE phase20_document_anchor_458 SET text_excerpt=? WHERE document_id=?',('tampered quote',doc_id))
    if mode=='rejected_extraction':
        doc=service._document(doc_id);doc['state']='extraction_rejected'
        ctx.db.execute('UPDATE phase20_document_458 SET state=?,record_hash=? WHERE document_id=?',(doc['state'],service._rh(doc),doc_id))
    assert client.post('/workbench/findings',data=data).status_code in {403,409,422}
    assert notes_for_case(app,case_id)==[]


@pytest.mark.parametrize('mode',['csrf','origin','origin_null','oversized_chunked'])
def test_form_guards_prevent_note_creation(workspace,mode):
    app,client,user,case_id,*_=workspace;data=form(workspace);headers={}
    if mode=='csrf':data['csrf']='forged'
    if mode=='origin':headers['Origin']='https://evil.example'
    if mode=='origin_null':headers['Origin']='null'
    if mode=='oversized_chunked':
        response=client.post('/workbench/findings',content=iter([b'interpretation=',b'x'*40001]),headers={'Content-Type':'application/x-www-form-urlencoded'})
        assert response.status_code==413
    else:assert client.post('/workbench/findings',data=data,headers=headers).status_code==403
    assert notes_for_case(app,case_id)==[]


def test_real_read_only_role_cannot_create_findings(workspace):
    app,client,admin,case_id,*_=workspace;data=form(workspace)
    member(workspace,'read_only');data['csrf']=csrf_session(workspace,'member475','Independent!Secret_881')
    assert client.post('/workbench/findings',data=data).status_code==403
    assert notes_for_case(app,case_id)==[]
    assert 'Zum Anlegen' in client.get('/workbench/findings',params={'case_id':case_id}).text


def test_stored_note_tampering_is_detected_and_html_is_escaped(workspace):
    app,client,user,case_id,*_=workspace;data=form(workspace);data['title']='<script>note()</script>'
    assert client.post('/workbench/findings',data=data,follow_redirects=False).status_code==303
    html=client.get('/workbench/findings',params={'case_id':case_id}).text
    assert '&lt;script&gt;note()' in html and '<script>note()' not in html
    app.state.context.db.execute('UPDATE operational_findings_478 SET title=? WHERE case_id=?',('altered note',case_id))
    assert client.get('/workbench/findings',params={'case_id':case_id}).status_code==409


def test_late_source_change_prevents_commit(workspace):
    import eagleeye.interfaces.web.findings478 as module
    app,client,user,case_id,doc_id,*_=workspace;data=form(workspace)
    original=module.get_anchor;count=0
    def changing(*args,**kwargs):
        nonlocal count
        result=original(*args,**kwargs);count+=1
        if count==1:
            service=app.state.context.document_intelligence_458
            (service.root/service._document(doc_id)['stored_relpath']).write_bytes(b'Changed before final transaction')
        return result
    with patch.object(module,'get_anchor',side_effect=changing):
        assert client.post('/workbench/findings',data=data).status_code==409
    assert notes_for_case(app,case_id)==[]


def test_anchor_pages_are_not_silently_limited_to_first_fifty(workspace):
    app,client,user,case_id,*_=workspace;csrf_session(workspace)
    source=app.state.context.document_intelligence_458.import_bytes(identity=user,case_id=case_id,filename='long.txt',
        raw='\n\n'.join('Paragraph '+str(i)+' with a distinct original observation.' for i in range(60)).encode(),
        title='Sixty paragraphs',source_url='https://example.org/long')
    packet=app.state.context.document_intelligence_458.anchors(identity=user,document_id=source['document_id'])
    view=client.get('/workbench/findings',params={'case_id':case_id,'document_id':source['document_id'],'anchor_offset':50})
    assert view.status_code==200 and packet['anchors'][-1]['anchor_id'] in view.text
    assert packet['anchors'][0]['anchor_id'] not in view.text


def test_legacy_sidecar_work_is_retained_and_never_auto_approved(workspace):
    app,client,user,case_id,*_=workspace;client.post('/workbench/findings',data=form(workspace))
    saved=notes_for_case(app,case_id)[0]
    app.state.context.db.execute('DELETE FROM operational_findings_478 WHERE finding_id=?',(saved['finding_id'],))
    legacy=app.state.context.base_dir/'data/operational_notes_478.sqlite3'
    conn=sqlite3.connect(legacy)
    columns=BASE_COLUMNS[:14]
    conn.execute('CREATE TABLE operational_findings_478('+','.join(k+' TEXT' for k in columns)+')')
    saved['review_state']='reviewed_self'
    conn.execute('INSERT INTO operational_findings_478 VALUES('+','.join('?' for _ in columns)+')',tuple(saved[k] for k in columns))
    conn.commit();conn.close()
    restored=notes_for_case(app,case_id)[0]
    assert restored['finding_id']==saved['finding_id'] and restored['interpretation']==saved['interpretation']
    assert restored['review_state']=='unreviewed' and restored['legacy_imported']==1
    assert legacy.is_file() and finding_hash(restored)==restored['record_hash']



def test_original_source_jump_reaches_anchors_after_two_hundred(workspace):
    app,client,user,case_id,*_=workspace;data=form(workspace)
    source=app.state.context.document_intelligence_458.import_bytes(
        identity=user,case_id=case_id,filename='many-anchors.txt',
        raw='\n\n'.join('Original paragraph '+str(i)+' with independently inspectable evidence.' for i in range(230)).encode(),
        title='Long source document',source_url='https://example.org/long')
    anchors=app.state.context.document_intelligence_458.anchors(identity=user,document_id=source['document_id'])['anchors']
    chosen=anchors[-1]['anchor_id'];data['anchor_ref']=source['document_id']+'|'+chosen
    assert client.post('/workbench/findings',data=data,follow_redirects=False).status_code==303
    finding_page=client.get('/workbench/findings',params={'case_id':case_id})
    assert 'anchor_id='+chosen in finding_page.text
    original=client.get('/documents458',params={'case_id':case_id,'document_id':source['document_id'],'anchor_id':chosen})
    assert original.status_code==200 and 'id="anchor-'+chosen+'"' in original.text
    assert 'Original paragraph 229' in original.text and 'Frühere Fundstellen' in original.text
    assert 'id="anchor-'+anchors[0]['anchor_id']+'"' not in original.text
