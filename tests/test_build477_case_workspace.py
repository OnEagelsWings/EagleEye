from urllib.parse import urlencode
import pytest
from eagleeye.interfaces.web.app477 import create_workspace_app477
from test_build471_local_ai import workspace
from test_build475_ai_checkpoint import member

pytestmark=pytest.mark.parametrize('workspace',[create_workspace_app477],indirect=True)


def test_case_context_is_kept_between_home_workbench_and_sources(workspace):
    app,client,user,case_id,doc_id,*_=workspace
    home=client.get('/',params={'case_id':case_id})
    assert 'Geführte Recherche' in home.text
    work=client.get('/workbench',params={'case_id':case_id})
    assert work.status_code==200 and 'Synthetic AI case' in work.text
    assert 'Synthetic summary test' in work.text
    assert 'href="/?'+urlencode({'case_id':case_id})+'"' in work.text
    assert '/workbench/sources?'+urlencode({'case_id':case_id}) in work.text
    default=client.get('/')
    assert '/workbench?case_id=' in default.text and '/workbench?case_id="' not in default.text


def test_document_inventory_has_complete_paging_and_stays_case_scoped(workspace):
    app,client,user,case_id,doc_id,*_=workspace;docs=app.state.context.document_intelligence_458
    for i in range(50):
        docs.import_bytes(identity=user,case_id=case_id,filename=f'page{i}.txt',
            raw=f'Public document number {i} with sufficient source text.'.encode(),
            title=f'Inventory document {i}',source_url='https://example.org/'+str(i))
    first=client.get('/workbench/sources',params={'case_id':case_id})
    last=client.get('/workbench/sources',params={'case_id':case_id,'offset':50})
    assert '51 Dokumente' in first.text and 'Weitere Quellen' in first.text
    assert 'Inventory document 49' in first.text and 'Synthetic Source' not in first.text
    assert 'Synthetic Source' in last.text and 'Inventory document 49' not in last.text
    assert 'Foreign Source' not in first.text+last.text
    assert client.get('/workbench/sources',params={'case_id':case_id,'offset':-1}).status_code==422
    assert 'Synthetic Source' in client.get('/workbench/sources',params={'case_id':case_id,'offset':1000}).text


def test_case_denial_and_safe_metadata_rendering(workspace):
    app,client,admin,case_id,doc_id,other,*_=workspace
    app.state.context.document_intelligence_458.import_bytes(identity=admin,case_id=case_id,
        filename='safe.txt',raw=b'This public text contains an ordinary source excerpt.',
        title='<script>untrusted_title()</script>',source_url='https://example.org/source')
    member(workspace,'read_only')
    source=client.get('/workbench/sources',params={'case_id':case_id})
    assert source.status_code==200 and '&lt;script&gt;untrusted_title()' in source.text
    assert '<script>untrusted_title()' not in source.text
    for route in ['/workbench','/workbench/sources','/']:
        assert client.get(route,params={'case_id':other}).status_code==403
