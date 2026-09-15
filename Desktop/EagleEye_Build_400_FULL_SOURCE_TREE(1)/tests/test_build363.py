from __future__ import annotations
import ast, os, tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext


def ctx(tmp_path): return AppContext(base_dir=tmp_path)
def case(c,title='P16-363'): return c.cases.create_case(title=title,client='QA',purpose='phase16 object/search test',legal_basis='authorized public-source test')

class FakeBody:
    def __init__(self,b): self.b=b
    def read(self): return self.b
class FakeS3:
    def __init__(self): self.d={}; self.puts=[]; self.deletes=[]
    def put_object(self,**kw): self.d[(kw['Bucket'],kw['Key'])]=bytes(kw['Body']); self.puts.append(kw); return {'ETag':'x'}
    def get_object(self,**kw): return {'Body':FakeBody(self.d[(kw['Bucket'],kw['Key'])])}
    def delete_object(self,**kw): self.d.pop((kw['Bucket'],kw['Key']),None); self.deletes.append(kw); return {}

def test_version_schema(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build363.version_status()=={'runtime_build':'363.0','schema_version':'363.0','package_version':'363.0.0','coherent':True}
        m=c.build363.schema_metrics(); assert m['within_gate'] and (m['table'],m['index'],m['trigger'])==(141,128,8)

def test_truthful_external_status_without_endpoints(tmp_path,monkeypatch):
    for k in ['EAGLEEYE_S3_ENDPOINT','EAGLEEYE_S3_BUCKET','EAGLEEYE_TEAM_SEARCH_DSN','EAGLEEYE_POSTGRES_DSN']: monkeypatch.delenv(k,raising=False)
    with ctx(tmp_path) as c:
        s=c.build363.storage_search_status(); assert not s['s3']['externally_validated']; assert not s['team_search']['externally_validated']; assert not s['automatic_external_connections']

def test_local_cas_roundtrip(tmp_path):
    with ctx(tmp_path) as c:
        x=c.local_object_store_347.put_bytes(b'abc363'); assert c.local_object_store_347.read_bytes(x['object_key'],x['sha256'])==b'abc363'

def test_local_fts_search(tmp_path):
    with ctx(tmp_path) as c:
        cid=case(c)['case_id']; c.search_platform_348.local.index_document(doc_id='d363',case_id=cid,title='Alpha',body='evidence alpha beta',security_state='local_safe')
        r=c.search_platform_348.local.search(case_id=cid,query='alpha'); assert r and r[0]['doc_id']=='d363'

def test_s3_contract_injected_not_external(tmp_path,monkeypatch):
    monkeypatch.setenv('EAGLEEYE_S3_ENDPOINT','http://127.0.0.1:9000'); monkeypatch.setenv('EAGLEEYE_S3_BUCKET','qa')
    with ctx(tmp_path) as c:
        f=FakeS3(); r=c.build363.s3_live_validation(client=f,external_client=False); assert r['status']=='pass' and r['roundtrip']=='pass' and not r['externally_validated'] and f.puts and f.deletes

def test_s3_external_flag_only_explicit_real_client(tmp_path,monkeypatch):
    monkeypatch.setenv('EAGLEEYE_S3_ENDPOINT','http://127.0.0.1:9000'); monkeypatch.setenv('EAGLEEYE_S3_BUCKET','qa')
    with ctx(tmp_path) as c:
        r=c.build363.s3_live_validation(client=FakeS3(),external_client=True); assert r['externally_validated'] and r['external_connection_opened']

def test_insecure_s3_endpoint_blocked(tmp_path,monkeypatch):
    monkeypatch.setenv('EAGLEEYE_S3_ENDPOINT','http://example.invalid:9000'); monkeypatch.setenv('EAGLEEYE_S3_BUCKET','qa')
    with ctx(tmp_path) as c:
        r=c.build363.s3_live_validation(client=FakeS3()); assert r['status']=='blocked' and not r['externally_validated']

def test_team_search_contract_injected_not_external(tmp_path):
    def ex(sql,params): return [{'probe':params[0]}]
    with ctx(tmp_path) as c:
        r=c.build363.team_search_live_validation(executor=ex,external_executor=False); assert r['status']=='pass' and r['contract_validated'] and not r['live_validated']

def test_team_search_external_flag_requires_external_executor(tmp_path):
    def ex(sql,params): return [{'probe':params[0]}]
    with ctx(tmp_path) as c:
        r=c.build363.team_search_live_validation(executor=ex,external_executor=True); assert r['live_validated'] and r['external_connection_opened']

def test_ai_requires_go(tmp_path):
    with ctx(tmp_path) as c:
        cid=case(c)['case_id']; assert c.build363.run_autonomous_investigation(case_id=cid)['state']=='go_required'

def test_ai_dossier_storage_search_context(tmp_path):
    with ctx(tmp_path) as c:
        cid=case(c)['case_id']; c.build363.create_investigation_intake(case_id=cid,objective='Research public facts',key_questions=['What is supported?']); c.build363.start_investigation_go(case_id=cid,go='GO')
        r=c.build363.run_autonomous_investigation(case_id=cid,max_ticks=1); d=r['dossier']; assert d['lead_review_required']; assert 'phase16_storage_search_context' in d; assert d['phase16_storage_search_context']['degraded_mode_disclosed']

def test_opsec_status(tmp_path):
    with ctx(tmp_path) as c:
        s=c.opsec_supervisor_363.status(); assert s['storage_search_health_monitor'] and s['insecure_external_storage_endpoint_block'] and not s['system_mutations']

def test_opsec_insecure_endpoint_stops_jobs(tmp_path,monkeypatch):
    monkeypatch.setenv('EAGLEEYE_S3_ENDPOINT','http://bad.example:9000'); monkeypatch.setenv('EAGLEEYE_S3_BUCKET','qa')
    with ctx(tmp_path) as c:
        cid=case(c)['case_id']; c.db.execute("INSERT INTO phase15_jobs(job_id,idempotency_key,job_type,case_id,search_run_id,status,priority,attempts,max_attempts,available_at,lease_owner,lease_expires_at,payload_json,resource_budget_json,rate_budget_json,checkpoint_json,result_json,error_text,created_at,updated_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",('j363','i363','crawler',cid,'','queued',1,0,1,'2000-01-01','','','{}','{}','{}','{}','{}','','2000-01-01','2000-01-01','x'))
        r=c.build363.autonomous_opsec_protect(case_id=cid); assert r['storage_search_findings']; assert 'j363' in r['storage_search_jobs_stopped']

def test_crawler_improvement(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build363.crawler_status(); assert s['crawler_improvement_build']==363 and s['object_store_health_aware'] and s['search_index_health_aware']

def test_phase16_status(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build363.phase16_status(); assert s['phase']=='16' and s['build']=='363.0' and s['builds_completed']==3

def test_capabilities_do_not_claim_external_without_live(tmp_path,monkeypatch):
    for k in ['EAGLEEYE_S3_ENDPOINT','EAGLEEYE_S3_BUCKET','EAGLEEYE_TEAM_SEARCH_DSN','EAGLEEYE_POSTGRES_DSN']: monkeypatch.delenv(k,raising=False)
    with ctx(tmp_path) as c:
        caps={x['key']:x for x in c.build363.capabilities()}; assert not caps['s3_minio_team_object_store_v363']['states']['externally_validated']; assert not caps['team_search_backend_v363']['states']['externally_validated']

def test_production_false(tmp_path):
    with ctx(tmp_path) as c: assert c.build363.qualified_gate()['production_release_ready'] is False

def test_no_literal_true_gate(tmp_path):
    with ctx(tmp_path) as c: assert c.build363.active_gate_literal_true_lines()==[]

def test_new_modules_no_direct_http_subprocess_imports():
    names=set()
    for p in [Path('src/eagleeye/phase16/storage_search363.py'),Path('src/eagleeye/application/build363/service.py')]:
        tree=ast.parse(p.read_text())
        for n in ast.walk(tree):
            if isinstance(n,ast.Import): names.update(x.name.split('.')[0] for x in n.names)
            elif isinstance(n,ast.ImportFrom) and n.module:names.add(n.module.split('.')[0])
    assert not names.intersection({'requests','httpx','aiohttp','socket','subprocess'})

def test_web_health_and_status_auth(tmp_path):
    from fastapi.testclient import TestClient
    from eagleeye.interfaces.web.app363 import create_workspace_app363
    app=create_workspace_app363(base_dir=tmp_path/'web')
    with TestClient(app) as client:
        h=client.get('/health'); assert h.status_code==200 and h.json()['build']=='363.0'
        assert client.get('/api/build363').status_code==401
