from __future__ import annotations
from datetime import datetime, timezone
import hashlib, json, secrets
from typing import Any, Mapping, Iterable

BUILD='408.0'
POLICY_ID='phase18.federated-search.v408'
MAX_QUERY_CHARS=1000
MAX_RESULTS_PER_IMPORT=500

def _now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _sha(v): return hashlib.sha256(_canon(v).encode()).hexdigest()
def _id(prefix): return prefix+'_'+secrets.token_hex(12)

def _norm_text(v): return ' '.join(str(v or '').split())

def _dedupe_key(r):
    explicit=_norm_text(r.get('canonical_ref') or r.get('origin_ref')).casefold()
    if explicit: return explicit
    return _sha({'title':_norm_text(r.get('title')).casefold(),'snippet':_norm_text(r.get('snippet')).casefold()})

class FederatedSearch408:
    """Read-only federated search control plane.

    Produces source-aware search plans and normalizes caller/imported result sets.
    It never performs network requests, never bypasses GO/OPSEC, and never promotes
    normalized search results to evidence automatically.
    """
    def __init__(self,db,audit,*,fabric407,registry405,governance=None,actor='local-analyst'):
        self.db=db; self.audit=audit; self.fabric407=fabric407; self.registry405=registry405; self.governance=governance; self.actor=actor; self._init_schema()
    def _authorize(self,identity,case_id,object_id=''):
        if not identity: raise PermissionError('active case identity required')
        if self.governance is None: raise PermissionError('governance unavailable')
        return self.governance.authorize(identity,case_id=case_id,capability='research.run',object_type='federated_search_408',object_id=object_id or case_id)
    def _init_schema(self):
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS federated_search_session_408(
          search_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, query_text TEXT NOT NULL,
          source_plan_json TEXT NOT NULL, query_hash TEXT NOT NULL, created_by TEXT NOT NULL,
          created_at TEXT NOT NULL, network_execution INTEGER NOT NULL, automatic_go INTEGER NOT NULL,
          record_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS federated_search_result_408(
          result_id TEXT PRIMARY KEY, search_id TEXT NOT NULL, case_id TEXT NOT NULL,
          source_id TEXT NOT NULL, adapter_kind TEXT NOT NULL, title TEXT NOT NULL,
          snippet TEXT NOT NULL, canonical_ref TEXT NOT NULL, provenance_json TEXT NOT NULL,
          dedupe_key TEXT NOT NULL, imported_at TEXT NOT NULL, record_hash TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_fed408_search ON federated_search_result_408(search_id,source_id,dedupe_key);
        '''); self.db.conn.commit()
    def _eligible_sources(self, source_ids:Iterable[str]|None=None):
        wanted=set(str(x) for x in (source_ids or []))
        rows=[]
        for a in self.fabric407.adapters():
            if wanted and a['source_id'] not in wanted: continue
            src=self.registry405.get(a['source_id'])
            if src['health_state']=='disabled': continue
            rows.append((a,src))
        return rows
    def create_search(self,*,case_id,query,source_ids=None,identity:Mapping[str,Any]|None=None):
        case_id=_norm_text(case_id); query=_norm_text(query)
        if not case_id: raise ValueError('case_id required')
        if not query: raise ValueError('query required')
        if len(query)>MAX_QUERY_CHARS: raise ValueError('query too long')
        self._authorize(identity,case_id)
        source_plan=[]
        for a,src in self._eligible_sources(source_ids):
            source_plan.append({'source_id':a['source_id'],'adapter_kind':a['adapter_kind'],'remote':a['remote'],'requires_go':a['requires_go'],'health_state':src['health_state'],'provenance_class':src['provenance_class'],'network_execution':False})
        if source_ids and not source_plan: raise ValueError('no eligible requested sources')
        actor=str((identity or {}).get('user_id') or (identity or {}).get('username') or self.actor)
        body={'case_id':case_id,'query':query,'source_plan':source_plan,'network_execution':False,'automatic_go':False}
        qh=_sha(body); sid='fs408_'+qh[:24]; now=_now(); rh=_sha({**body,'search_id':sid,'created_by':actor,'created_at':now})
        self.db.execute('INSERT OR IGNORE INTO federated_search_session_408 VALUES(?,?,?,?,?,?,?,?,?,?)',(sid,case_id,query,_canon(source_plan),qh,actor,now,0,0,rh))
        self.audit.log('federated_search_planned','federated_search_session_408',sid,case_id,{'sources':len(source_plan),'network_requests':0,'automatic_go':False})
        return self.session(sid)
    def session(self,search_id):
        r=self.db.one('SELECT * FROM federated_search_session_408 WHERE search_id=?',(search_id,))
        if not r: raise KeyError('search not found')
        d=dict(r); d['source_plan']=json.loads(d.pop('source_plan_json')); d['network_execution']=bool(d['network_execution']); d['automatic_go']=bool(d['automatic_go']); return d
    def import_results(self,*,search_id,source_id,results,identity:Mapping[str,Any]|None=None):
        sess=self.session(search_id); self._authorize(identity,sess['case_id'],search_id); allowed={p['source_id']:p for p in sess['source_plan']}
        if source_id not in allowed: raise PermissionError('source not part of search plan')
        rows=list(results or [])
        if len(rows)>MAX_RESULTS_PER_IMPORT: raise ValueError('too many results')
        actor=str((identity or {}).get('user_id') or (identity or {}).get('username') or self.actor)
        out=[]; seen=set()
        for item in rows:
            item=dict(item or {}); title=_norm_text(item.get('title')); snippet=_norm_text(item.get('snippet')); ref=_norm_text(item.get('canonical_ref') or item.get('origin_ref'))
            prov=dict(item.get('provenance') or {})
            if not title and not snippet: continue
            if not _norm_text(prov.get('retrieved_at')) or not _norm_text(prov.get('collector')): raise ValueError('result provenance requires retrieved_at and collector')
            key=_dedupe_key({'title':title,'snippet':snippet,'canonical_ref':ref});
            if key in seen: continue
            seen.add(key); rid=_id('fsr408'); now=_now(); prov.update({'source_id':source_id,'search_id':search_id,'promotion_status':'search_result_unreviewed','network_execution_by_build408':False,'imported_by':actor})
            rec={'result_id':rid,'search_id':search_id,'case_id':sess['case_id'],'source_id':source_id,'adapter_kind':allowed[source_id]['adapter_kind'],'title':title,'snippet':snippet,'canonical_ref':ref,'provenance':prov,'dedupe_key':key,'imported_at':now}; rh=_sha(rec)
            self.db.execute('INSERT INTO federated_search_result_408 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(rid,search_id,sess['case_id'],source_id,allowed[source_id]['adapter_kind'],title,snippet,ref,_canon(prov),key,now,rh)); out.append(self.result(rid))
        self.audit.log('federated_search_results_imported','federated_search_session_408',search_id,sess['case_id'],{'source_id':source_id,'results':len(out),'network_requests':0,'evidence_promoted':False})
        return out
    def result(self,result_id):
        r=self.db.one('SELECT * FROM federated_search_result_408 WHERE result_id=?',(result_id,))
        if not r: raise KeyError('result not found')
        d=dict(r); d['provenance']=json.loads(d.pop('provenance_json')); return d
    def results(self,search_id): return [self.result(r['result_id']) for r in self.db.all('SELECT result_id FROM federated_search_result_408 WHERE search_id=? ORDER BY imported_at,result_id',(search_id,))]
    def merged_results(self,search_id):
        merged=[]; seen=set()
        for r in self.results(search_id):
            if r['dedupe_key'] in seen: continue
            seen.add(r['dedupe_key']); merged.append(r)
        return merged
    def verify_integrity(self):
        bad=[]
        for r in self.db.all('SELECT * FROM federated_search_session_408'):
            d=dict(r); body={'case_id':d['case_id'],'query':d['query_text'],'source_plan':json.loads(d['source_plan_json']),'network_execution':bool(d['network_execution']),'automatic_go':bool(d['automatic_go'])}
            rec={**body,'search_id':d['search_id'],'created_by':d['created_by'],'created_at':d['created_at']}
            if _sha(rec)!=d['record_hash']: bad.append({'table':'federated_search_session_408','id':d['search_id']})
        for r in self.db.all('SELECT * FROM federated_search_result_408'):
            d=dict(r); rec={'result_id':d['result_id'],'search_id':d['search_id'],'case_id':d['case_id'],'source_id':d['source_id'],'adapter_kind':d['adapter_kind'],'title':d['title'],'snippet':d['snippet'],'canonical_ref':d['canonical_ref'],'provenance':json.loads(d['provenance_json']),'dedupe_key':d['dedupe_key'],'imported_at':d['imported_at']}
            if _sha(rec)!=d['record_hash']: bad.append({'table':'federated_search_result_408','id':d['result_id']})
        return {'valid':not bad,'violations':bad}
    def status(self):
        sessions=int((self.db.one('SELECT COUNT(*) c FROM federated_search_session_408') or {}).get('c',0)); results=int((self.db.one('SELECT COUNT(*) c FROM federated_search_result_408') or {}).get('c',0))
        return {'build':BUILD,'policy':POLICY_ID,'federated_search':True,'sessions':sessions,'normalized_results':results,'network_execution':False,'execution_authority':False,'automatic_go':False,'automatic_evidence_promotion':False,'provenance_required':True,'source_registry_required':True,'connector_fabric_required':True}
