from __future__ import annotations
import ast, json, tempfile
from pathlib import Path
import pytest
from eagleeye_pro.core.app_context import AppContext
from eagleeye.phase16.postgres362 import SQLiteMigrationSnapshot362, PostgresMigrationPlanner362, _pg_type, _quote_ident


def ctx(tmp_path): return AppContext(base_dir=tmp_path)
def case(c,title='P16-362'):
    return c.cases.create_case(title=title,client='QA',purpose='phase16 postgres team test',legal_basis='authorized public-source test')


def test_version_and_schema(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build362.version_status()=={'runtime_build':'362.0','schema_version':'362.0','package_version':'362.0.0','coherent':True}
        m=c.build362.schema_metrics(); assert m['within_gate'] and (m['table'],m['index'],m['trigger'])==(141,128,8)


def test_postgres_status_truthful_without_server(tmp_path,monkeypatch):
    monkeypatch.delenv('EAGLEEYE_POSTGRES_DSN',raising=False)
    with ctx(tmp_path) as c:
        s=c.build362.postgres_status(); assert s['live_validation_status']=='not_run'; assert not s['externally_validated']; assert s['automatic_external_connections'] is False


def test_live_validation_without_dsn_is_not_run(tmp_path,monkeypatch):
    monkeypatch.delenv('EAGLEEYE_POSTGRES_DSN',raising=False)
    with ctx(tmp_path) as c:
        r=c.build362.postgres_live_validation(); assert r['status']=='not_run' and not r['externally_validated'] and not r['external_connection_opened']


def test_migration_plan_is_deterministic_and_nonempty(tmp_path):
    with ctx(tmp_path) as c:
        a=c.build362.postgres_migration_plan(); b=c.build362.postgres_migration_plan()
        assert a['plan_hash']==b['plan_hash']; assert a['table_count']>100; assert a['row_count']>=0
        assert a['search_virtual_tables_rebuilt_separately']


def test_migration_excludes_virtual_fts_shadow_tables(tmp_path):
    with ctx(tmp_path) as c:
        names={x['table'] for x in c.build362.postgres_migration_plan()['tables']}
        assert not any(n.endswith(('_data','_idx','_content','_docsize','_config')) and n.startswith('phase15_search') for n in names)


def test_postgres_ddl_quotes_identifiers_and_types(tmp_path):
    with ctx(tmp_path) as c:
        plan=c.build362.postgres_migration_plan(); item=next(x for x in plan['tables'] if x['table']=='cases')
        assert 'CREATE TABLE IF NOT EXISTS "cases"' in item['create_sql']; assert '%s' in item['insert_sql']
    assert _pg_type('INTEGER')=='BIGINT'; assert _pg_type('BLOB')=='BYTEA'; assert _pg_type('TEXT')=='TEXT'
    with pytest.raises(ValueError): _quote_ident('bad;drop')


def test_local_backup_restore_rollback_drill(tmp_path):
    with ctx(tmp_path) as c:
        cid=case(c)['case_id']; c.db.execute("UPDATE cases SET status='active' WHERE case_id=?",(cid,))
        r=c.build362.local_rollback_drill(); assert r['status']=='pass' and r['rollback_verified']; assert r['source_manifest_hash']==r['restored_manifest_hash']; assert not r['external_postgresql_used']


def test_snapshot_bundle_hashes_rows(tmp_path):
    with ctx(tmp_path) as c:
        case(c)
        snap=SQLiteMigrationSnapshot362(c.db); target=tmp_path/'snapshot.jsonl.gz'; r=snap.export_jsonl_gz(target,['cases','phase15_schema_meta'])
        assert target.exists() and r['sha256'] and r['table_count']==2


def test_ai_still_requires_go(tmp_path):
    with ctx(tmp_path) as c:
        cid=case(c)['case_id']; r=c.build362.run_autonomous_investigation(case_id=cid); assert r['state']=='go_required'


def test_ai_adds_backend_context_and_plausibility_bands(tmp_path):
    with ctx(tmp_path) as c:
        cid=case(c)['case_id']; c.build362.create_investigation_intake(case_id=cid,objective='Research public facts',key_questions=['What is supported?']); c.build362.start_investigation_go(case_id=cid,go='GO')
        r=c.build362.run_autonomous_investigation(case_id=cid,max_ticks=2); d=r['dossier']; assert d['lead_review_required']; assert d['phase16_infrastructure_context']['team_backend']=='postgresql'; assert not d['phase16_infrastructure_context']['externally_validated']
        assert all(h.get('plausibility_band') in {'low','medium','high'} for h in d.get('hypotheses',[]))


def test_opsec_status_adds_backend_hygiene(tmp_path):
    with ctx(tmp_path) as c:
        s=c.opsec_supervisor_362.status(); assert s['backend_secret_hygiene_monitor']; assert not s['system_mutations']


def test_opsec_finds_no_secrets_in_normal_backend_config(tmp_path):
    with ctx(tmp_path) as c:
        cid=case(c)['case_id']; r=c.build362.autonomous_opsec_protect(case_id=cid); assert r['backend_secret_findings']==[] and r['system_mutations'] is False


def test_opsec_stops_case_jobs_if_backend_secret_is_persisted(tmp_path):
    with ctx(tmp_path) as c:
        cid=case(c)['case_id']
        c.db.execute("INSERT OR REPLACE INTO phase15_data_backends(backend_id,backend_kind,role,status,config_json,live_validated,last_checked_at,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?)",('badpg','postgresql','transactional_team','configured','{\"password\":\"plaintext\"}',0,'2026-01-01','2026-01-01','x'))
        c.db.execute("INSERT INTO phase15_jobs(job_id,idempotency_key,job_type,case_id,search_run_id,status,priority,attempts,max_attempts,available_at,lease_owner,lease_expires_at,payload_json,resource_budget_json,rate_budget_json,checkpoint_json,result_json,error_text,created_at,updated_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",('job362x','idem362x','crawler',cid,'','queued',1,0,1,'2000-01-01','','','{}','{}','{}','{}','{}','','2000-01-01','2000-01-01','x'))
        r=c.build362.autonomous_opsec_protect(case_id=cid); assert r['backend_secret_findings']; assert 'job362x' in r['backend_risk_jobs_stopped']; assert c.db.one("SELECT status FROM phase15_jobs WHERE job_id='job362x'")['status']=='cancelled'


def test_crawler_improvement_362(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build362.crawler_status(); assert s['crawler_improvement_build']==362 and s['backend_aware_backpressure'] and s['external_postgres_required_for_team_scale_claim']


def test_capabilities_do_not_claim_external_postgres(tmp_path):
    with ctx(tmp_path) as c:
        caps={x['key']:x for x in c.build362.capabilities()}; assert not caps['postgresql_team_profile_v362']['states']['externally_validated']


def test_phase16_status_moves_to_build362(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build362.phase16_status(); assert s['phase']=='16' and s['build']=='362.0' and s['builds_completed']==2 and s['crawler_improvement_build']==362


def test_production_remains_false(tmp_path):
    with ctx(tmp_path) as c: assert c.build362.qualified_gate()['production_release_ready'] is False


def test_no_literal_true_in_qualified_gate(tmp_path):
    with ctx(tmp_path) as c: assert c.build362.active_gate_literal_true_lines()==[]


def test_new_modules_no_direct_network_subprocess_imports():
    names=set()
    for p in [Path('src/eagleeye/phase16/postgres362.py'),Path('src/eagleeye/application/build362/service.py')]:
        tree=ast.parse(p.read_text())
        for n in ast.walk(tree):
            if isinstance(n,ast.Import): names.update(x.name.split('.')[0] for x in n.names)
            elif isinstance(n,ast.ImportFrom) and n.module:names.add(n.module.split('.')[0])
    assert not names.intersection({'requests','httpx','aiohttp','urllib','socket','subprocess'})


def test_web_health_and_status_auth_boundary(tmp_path):
    from fastapi.testclient import TestClient
    from eagleeye.interfaces.web.app362 import create_workspace_app362
    app=create_workspace_app362(base_dir=tmp_path/'web')
    with TestClient(app) as client:
        h=client.get('/health'); assert h.status_code==200 and h.json()['build']=='362.0'
        assert client.get('/api/build362/phase16-status').status_code==401
