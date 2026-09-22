from pathlib import Path
import pytest
from eagleeye_pro.core.app_context import AppContext
ROOT=Path(__file__).resolve().parents[1]
def ident():return {'username':'analyst','global_role':'system_administrator','user_id':'analyst-421','roles':['analyst']}
def test_registry_real_source_contract_and_filters(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  x=c.build421.register_source(identity=ident(),name='Example News',source_type='news',base_url='https://example.org',capabilities=['articles','search'],coverage={'regions':['global']},terms_url='https://example.org/terms')
  assert x['source_type']=='news';assert c.build421.sources(source_type='news',capability='articles')[0]['source_id']==x['source_id'];assert c.acquisition_source_registry_421.verify_integrity()['valid']
def test_registry_tor_is_descriptor_only_and_validates_boundary(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  x=c.build421.register_source(identity=ident(),name='Public Onion Fixture',source_type='tor_onion',base_url='http://exampleexample.onion',capabilities=['public_pages']);assert x['source_type']=='tor_onion';s=c.build421.acquisition_status();assert not s['direct_network_authority'] and not s['access_control_bypass']
  with pytest.raises(ValueError):c.build421.register_source(identity=ident(),name='Bad',source_type='website',base_url='http://exampleexample.onion',capabilities=['pages'])
def test_registry_tamper_detection(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  x=c.build421.register_source(identity=ident(),name='Fixture',source_type='dataset',capabilities=['records']);c.db.execute("UPDATE acquisition_source_421 SET name='tampered' WHERE source_id=?",(x['source_id'],));assert not c.acquisition_source_registry_421.verify_integrity()['valid']
def test_version_and_launcher_contract(tmp_path):
 with AppContext(base_dir=tmp_path) as c:assert c.build421.version_status()['coherent'];assert c.build421.acquisition_status()['phase19_builds_completed']==1
 assert 'app421 import create_workspace_app421' in (ROOT/'src/eagleeye/interfaces/web/server.py').read_text()
