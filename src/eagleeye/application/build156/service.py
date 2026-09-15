from __future__ import annotations
import hashlib, json, re
from typing import Any, Iterable, Mapping
from eagleeye.application.build154.service import ConnectorRequest
from eagleeye_pro.core.database import dumps, loads, new_id, now_ts

PLAN_STATES={'draft','ready','running','partial_success','succeeded','failed','cancelled'}
CONFIDENCE={'low','medium','high'}

def _canonical(v: Any)->str:
    return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _digest(v: Any)->str:
    return hashlib.sha256(_canonical(v).encode('utf-8')).hexdigest()
def _text(v: Any)->str:
    return re.sub(r'\s+',' ',str(v or '')).strip()

class Build156CollectionOrchestratorService:
    BUILD='156.0'; MISSION='Collection Orchestrator'
    def __init__(self, db: Any, audit: Any, *, source_gate: Any, observability: Any|None=None, actor: str='system'):
        self.db=db; self.audit=audit; self.source_gate=source_gate; self.observability=observability; self.actor=actor

    def create_plan(self, *, title: str, seed: Mapping[str,Any], case_id: str|None=None,
                    connector_ids: Iterable[str]|None=None, actor: str|None=None) -> dict[str,Any]:
        title=_text(title)
        if not title: raise ValueError('Plan benötigt einen Titel')
        if not seed: raise ValueError('Plan benötigt mindestens einen Seed')
        selected=list(connector_ids or [])
        for cid in selected: self.source_gate.assert_executable(cid)
        pid=new_id('plan156'); corr=new_id('corr156'); policy={'connector_ids':selected,'review_required':True,'automatic_identity_confirmation':False,'max_connectors':12}
        if len(selected)>12: raise ValueError('Maximal 12 Connectoren pro Plan')
        payload={'title':title,'seed':dict(seed),'case_id':case_id,'policy':policy,'correlation_id':corr}
        ts=now_ts()
        self.db.execute('INSERT INTO collection_plans_156(plan_id,case_id,title,status,seed_json,policy_json,created_by,created_at,updated_at,correlation_id,snapshot_sha256) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(pid,case_id,title,'draft',dumps(dict(seed)),dumps(policy),actor or self.actor,ts,ts,corr,_digest(payload)))
        self._event(pid,'plan_created',payload,corr)
        self.audit.log('collection_plan_created_156','collection_plan',pid,case_id,{'title':title,'connectors':selected})
        return self.plan(pid)

    def generate_queries(self, plan_id: str) -> list[dict[str,Any]]:
        plan=self.plan(plan_id); seed=plan['seed']; values=[]
        for key in ('name','full_name','username','email','domain','organization','location','identifier'):
            value=_text(seed.get(key))
            if value: values.append((key,value))
        if not values: raise ValueError('Seed enthält keine unterstützten Suchwerte')
        out=[]
        for kind,value in values:
            qid=new_id('query156'); params=self._params_for(kind,value)
            self.db.execute('INSERT INTO collection_queries_156(query_id,plan_id,query_text,query_kind,params_json,created_at) VALUES(?,?,?,?,?,?)',(qid,plan_id,value,kind,dumps(params),now_ts()))
            out.append({'query_id':qid,'query_text':value,'query_kind':kind,'params':params})
        self.db.execute("UPDATE collection_plans_156 SET status='ready',updated_at=? WHERE plan_id=?",(now_ts(),plan_id))
        self._event(plan_id,'queries_generated',{'count':len(out)},plan['correlation_id'])
        return out

    @staticmethod
    def _params_for(kind: str, value: str)->dict[str,Any]:
        if kind in {'name','full_name','organization','location'}: return {'search':value,'query':value,'query.author':value}
        if kind=='username': return {'search':value,'query':value}
        if kind=='email': return {'query':value,'search':value}
        if kind=='domain': return {'query':value,'search':value}
        return {'query':value,'search':value}

    def execute(self, plan_id: str)->dict[str,Any]:
        plan=self.plan(plan_id)
        if plan['status']=='draft': self.generate_queries(plan_id); plan=self.plan(plan_id)
        if plan['status'] not in {'ready','partial_success','failed'}: raise ValueError('Plan ist nicht ausführbar')
        connectors=list(plan['policy'].get('connector_ids') or [])
        if not connectors: raise ValueError('Plan enthält keine freigegebenen Connectoren')
        queries=self.queries(plan_id)
        self.db.execute("UPDATE collection_plans_156 SET status='running',updated_at=? WHERE plan_id=?",(now_ts(),plan_id))
        succeeded=failed=records=0
        for connector_id in connectors:
            self.source_gate.assert_executable(connector_id)
            for query in queries:
                step_id=new_id('step156'); started=now_ts()
                self.db.execute('INSERT INTO collection_steps_156(step_id,plan_id,connector_id,query_id,status,started_at,records_count,provenance_json,correlation_id) VALUES(?,?,?,?,?,?,?,?,?)',(step_id,plan_id,connector_id,query['query_id'],'running',started,0,'{}',plan['correlation_id']))
                try:
                    result=self.source_gate.execute(ConnectorRequest(connector_id,self._connector_params(connector_id,query['params']),case_id=plan.get('case_id'),correlation_id=plan['correlation_id']))
                    count=self._ingest(plan_id,step_id,connector_id,result)
                    outcome=result.get('outcome_code','SUCCESS'); status='succeeded' if outcome=='SUCCESS' else 'partial_success'
                    self.db.execute('UPDATE collection_steps_156 SET status=?,outcome_code=?,finished_at=?,records_count=?,provenance_json=? WHERE step_id=?',(status,outcome,now_ts(),count,dumps(result.get('provenance') or result),step_id))
                    succeeded+=1; records+=count
                except Exception as exc:
                    failed+=1
                    self.db.execute("UPDATE collection_steps_156 SET status='failed',outcome_code='INTERNAL_ERROR',finished_at=?,error_text=? WHERE step_id=?",(now_ts(),f'{type(exc).__name__}: {exc}',step_id))
        final='succeeded' if succeeded and not failed else ('partial_success' if succeeded else 'failed')
        self.db.execute('UPDATE collection_plans_156 SET status=?,updated_at=? WHERE plan_id=?',(final,now_ts(),plan_id))
        summary={'plan_id':plan_id,'status':final,'steps_succeeded':succeeded,'steps_failed':failed,'records':records,'candidates':self._candidate_count(plan_id),'review_required':True,'automatic_identity_confirmation':False}
        self._event(plan_id,'plan_finished',summary,plan['correlation_id']); self.audit.log('collection_plan_finished_156','collection_plan',plan_id,plan.get('case_id'),summary)
        return summary

    @staticmethod
    def _connector_params(connector_id: str, params: Mapping[str,Any])->dict[str,Any]:
        value=params.get('search') or params.get('query') or ''
        if connector_id=='openalex_people': return {'search':value,'per-page':25}
        if connector_id=='crossref_works': return {'query.author':value,'rows':25}
        if connector_id=='orcid_public': return {'q':value}
        if connector_id=='wikidata_sparql': return {'query':value,'format':'json'}
        if connector_id=='gdelt_doc': return {'query':value,'mode':'ArtList','format':'json','maxrecords':25}
        return dict(params)

    def _ingest(self, plan_id: str, step_id: str, connector_id: str, result: Mapping[str,Any])->int:
        records=list(result.get('records') or [])
        provenance=result.get('provenance') or {'connector_id':connector_id,'run_id':result.get('run_id')}
        inserted=0
        for raw in records:
            if not isinstance(raw,Mapping): continue
            normalized=self._normalize(raw); digest=_digest(normalized)
            existing=self.db.one('SELECT record_id FROM normalized_records_156 WHERE plan_id=? AND canonical_sha256=?',(plan_id,digest))
            if existing: continue
            rid=new_id('record156'); source_id=_text(raw.get('id') or raw.get('orcid-identifier') or raw.get('DOI')) or None
            self.db.execute('INSERT INTO normalized_records_156(record_id,plan_id,step_id,connector_id,source_record_id,entity_kind,normalized_json,canonical_sha256,provenance_json,observed_at,review_status) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(rid,plan_id,step_id,connector_id,source_id,'person_or_related',dumps(normalized),digest,dumps(provenance),now_ts(),'candidate'))
            self._candidate(plan_id,rid,normalized); inserted+=1
        return inserted

    @staticmethod
    def _normalize(raw: Mapping[str,Any])->dict[str,Any]:
        keep={}
        for key,value in raw.items():
            if value is None or value=='' or value==[]: continue
            clean_key=str(key).strip().casefold().replace(' ','_')
            keep[clean_key]=value
        return keep

    def _candidate(self, plan_id: str, record_id: str, normalized: Mapping[str,Any])->None:
        label=_text(normalized.get('display_name') or normalized.get('name') or normalized.get('title') or normalized.get('orcid-identifier') or normalized.get('id'))[:300]
        if not label: return
        rationale={'signals':[k for k in ('display_name','name','orcid-identifier','affiliations','institution','location') if k in normalized],'record_id':record_id}
        band='medium' if len(rationale['signals'])>=2 else 'low'
        self.db.execute('INSERT INTO identity_candidates_156(candidate_id,plan_id,record_id,candidate_type,display_label,rationale_json,confidence_band,review_status,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(new_id('candidate156'),plan_id,record_id,'identity_or_relation',label,dumps(rationale),band,'pending',now_ts()))

    def review_candidate(self, candidate_id: str, *, decision: str, reviewer: str, note: str='')->dict[str,Any]:
        if decision not in {'accepted','rejected','needs_more_evidence'}: raise ValueError('Ungültige Review-Entscheidung')
        row=self.db.one('SELECT * FROM identity_candidates_156 WHERE candidate_id=?',(candidate_id,))
        if not row: raise KeyError('Kandidat nicht gefunden')
        self.db.execute('UPDATE identity_candidates_156 SET review_status=?,reviewed_at=?,reviewed_by=?,review_note=? WHERE candidate_id=?',(decision,now_ts(),reviewer,note,candidate_id))
        self.audit.log('identity_candidate_reviewed_156','identity_candidate',candidate_id,None,{'decision':decision,'reviewer':reviewer})
        return self.candidate(candidate_id)

    def plan(self, plan_id: str)->dict[str,Any]:
        row=self.db.one('SELECT * FROM collection_plans_156 WHERE plan_id=?',(plan_id,))
        if not row: raise KeyError('Plan nicht gefunden')
        row['seed']=loads(row.pop('seed_json'),{}); row['policy']=loads(row.pop('policy_json'),{})
        return row
    def queries(self, plan_id: str)->list[dict[str,Any]]:
        rows=self.db.all('SELECT * FROM collection_queries_156 WHERE plan_id=? ORDER BY created_at,query_id',(plan_id,))
        for row in rows: row['params']=loads(row.pop('params_json'),{})
        return rows
    def candidates(self, plan_id: str)->list[dict[str,Any]]:
        rows=self.db.all('SELECT * FROM identity_candidates_156 WHERE plan_id=? ORDER BY created_at,candidate_id',(plan_id,))
        for row in rows: row['rationale']=loads(row.pop('rationale_json'),{})
        return rows
    def candidate(self,candidate_id: str)->dict[str,Any]:
        row=self.db.one('SELECT * FROM identity_candidates_156 WHERE candidate_id=?',(candidate_id,))
        if not row: raise KeyError('Kandidat nicht gefunden')
        row['rationale']=loads(row.pop('rationale_json'),{}); return row
    def _candidate_count(self,plan_id: str)->int:
        return int(self.db.one('SELECT COUNT(*) AS n FROM identity_candidates_156 WHERE plan_id=?',(plan_id,))['n'])
    def _event(self,plan_id: str,event_type: str,payload: Mapping[str,Any],corr: str)->None:
        self.db.execute('INSERT INTO collection_events_156(event_id,plan_id,event_type,payload_json,occurred_at,correlation_id,payload_sha256) VALUES(?,?,?,?,?,?,?)',(new_id('event156'),plan_id,event_type,dumps(dict(payload)),now_ts(),corr,_digest(payload)))
