from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
ROOT=Path(__file__).resolve().parents[1]
def ident():return {'username':'analyst','global_role':'system_administrator','user_id':'analyst-426','roles':['analyst']}
def task(c):
 s=c.build421.register_source(identity=ident(),name='Source',source_type='website',base_url='https://example.org',capabilities=['pages']);c.build424.record_source_health(identity=ident(),source_id=s['source_id'],state='healthy');return c.build425.create_crawl_task(identity=ident(),case_id='case426',source_id=s['source_id'],target='https://example.org/report',objective='collect report')
def test_priority_and_budget(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  t=task(c);r=c.build426.prioritize_crawl(identity=ident(),task_id=t['task_id'],relevance=.9,urgency=.8,budget={'max_pages':5});assert r['decision'] in {'queue_high','queue'};assert r['budget']['max_pages']==5;assert c.crawl_priority_426.verify_integrity()['valid']
def test_bounds(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  t=task(c)
  try:c.build426.prioritize_crawl(identity=ident(),task_id=t['task_id'],relevance=1.1);assert False
  except ValueError:pass
def test_contract(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=c.build426.prioritization_status();assert s['version_coherent'];assert s['advisory_only'];assert not s['network_authority'];assert not s['production_release_ready']
 assert 'app426 import create_workspace_app426' in (ROOT/'src/eagleeye/interfaces/web/server.py').read_text()
