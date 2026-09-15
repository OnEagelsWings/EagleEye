from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import hashlib, json, secrets
from typing import Any, Mapping

BUILD="398.0"
POLICY_ID="phase17.model-holdout-human-eval.v398"
CONFIRM_FREEZE_SUITE="FREEZE HOLDOUT SUITE"
CONFIRM_EXTERNAL_RUN="RECORD EXTERNAL MODEL RUN"
CONFIRM_HUMAN_REVIEW="SUBMIT HUMAN REVIEW"
CONFIRM_FREEZE_BASELINE="FREEZE INTERNAL BASELINE"


def _now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
def _sha(v):
    b=v if isinstance(v,(bytes,bytearray)) else _canon(v).encode(); return hashlib.sha256(b).hexdigest()
def _sid(p): return p+"_"+secrets.token_hex(12)
def _j(v,d):
    try:return json.loads(v) if isinstance(v,str) else (v if v is not None else d)
    except Exception:return d

class ModelHoldoutEvaluation398:
    """Frozen holdout and human-review ledger. No model/network execution is performed here."""
    def __init__(self,db:Any,audit:Any,*,governance:Any=None,install_dir:str|Path|None=None,actor:str="local-analyst"):
        self.db=db; self.audit=audit; self.governance=governance; self.install_dir=Path(install_dir or '.'); self.actor=actor; self._init_schema()
    def _init_schema(self):
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS holdout_suite_398(
          suite_id TEXT PRIMARY KEY,name TEXT NOT NULL,status TEXT NOT NULL,case_count INTEGER NOT NULL,
          fixture_schema TEXT NOT NULL,fixture_hash TEXT NOT NULL,synthetic_fixture INTEGER NOT NULL,
          frozen_at TEXT NOT NULL DEFAULT '',frozen_by TEXT NOT NULL DEFAULT '',suite_hash TEXT NOT NULL,record_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS holdout_case_398(
          suite_id TEXT NOT NULL,case_id TEXT NOT NULL,domain TEXT NOT NULL,title TEXT NOT NULL,scenario TEXT NOT NULL,
          question TEXT NOT NULL,evidence_json TEXT NOT NULL,expected_json TEXT NOT NULL,case_hash TEXT NOT NULL,record_hash TEXT NOT NULL,
          PRIMARY KEY(suite_id,case_id));
        CREATE INDEX IF NOT EXISTS idx_holdout_case_398_domain ON holdout_case_398(suite_id,domain,case_id);
        CREATE TABLE IF NOT EXISTS holdout_run_398(
          run_id TEXT PRIMARY KEY,suite_id TEXT NOT NULL,case_id TEXT NOT NULL,run_origin TEXT NOT NULL,
          adapter_id TEXT NOT NULL,model_id TEXT NOT NULL,input_hash TEXT NOT NULL,output_json TEXT NOT NULL,output_hash TEXT NOT NULL,
          execution_receipt TEXT NOT NULL DEFAULT '',receipt_hash TEXT NOT NULL DEFAULT '',created_by TEXT NOT NULL,created_at TEXT NOT NULL,
          structural_score REAL NOT NULL,citation_precision REAL NOT NULL,citation_recall REAL NOT NULL,
          counterevidence_accuracy REAL NOT NULL,stop_decision_accuracy REAL NOT NULL,governance_compliance REAL NOT NULL,
          record_hash TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_holdout_run_398_suite ON holdout_run_398(suite_id,run_origin,case_id);
        CREATE TABLE IF NOT EXISTS holdout_review_398(
          review_id TEXT PRIMARY KEY,run_id TEXT NOT NULL,suite_id TEXT NOT NULL,case_id TEXT NOT NULL,reviewer_id TEXT NOT NULL,
          reviewer_kind TEXT NOT NULL,blind_review INTEGER NOT NULL,evidence_grounding INTEGER NOT NULL,counterevidence_handling INTEGER NOT NULL,
          uncertainty_handling INTEGER NOT NULL,actionability INTEGER NOT NULL,governance INTEGER NOT NULL,harmful_overreach INTEGER NOT NULL,
          notes TEXT NOT NULL,reviewed_at TEXT NOT NULL,record_hash TEXT NOT NULL,
          UNIQUE(run_id,reviewer_id));
        CREATE INDEX IF NOT EXISTS idx_holdout_review_398_suite ON holdout_review_398(suite_id,case_id,reviewer_id);
        CREATE TABLE IF NOT EXISTS holdout_baseline_398(
          baseline_id TEXT PRIMARY KEY,suite_id TEXT NOT NULL,baseline_type TEXT NOT NULL,run_count INTEGER NOT NULL,
          metrics_json TEXT NOT NULL,frozen_by TEXT NOT NULL,frozen_at TEXT NOT NULL,baseline_hash TEXT NOT NULL,record_hash TEXT NOT NULL);
        """); self.db.conn.commit()
    def _rowhash(self,d,drop=('record_hash',)):
        return _sha({k:d[k] for k in sorted(d) if k not in drop})
    def fixture(self):
        p=self.install_dir/'eagleeye_pro/phase17/fixtures/holdout398_cases.json'; data=json.loads(p.read_text(encoding='utf-8')); return data,p
    def create_reference_suite(self,*,name='Phase17 Build398 60-case structural holdout'):
        data,p=self.fixture(); raw=p.read_bytes(); cases=list(data.get('cases') or [])
        if len(cases)<50: raise ValueError('holdout suite requires at least 50 distinct cases')
        sid='holdout398_reference_v1'; old=self.db.one('SELECT * FROM holdout_suite_398 WHERE suite_id=?',(sid,))
        if old:return self.suite(sid)
        ch=[]
        for c in cases:
            ch.append(_sha(c))
        suite_hash=_sha({'schema':data.get('schema'),'fixture_hash':hashlib.sha256(raw).hexdigest(),'cases':ch})
        body={'suite_id':sid,'name':name,'status':'draft','case_count':len(cases),'fixture_schema':str(data.get('schema')),'fixture_hash':hashlib.sha256(raw).hexdigest(),'synthetic_fixture':1,'frozen_at':'','frozen_by':'','suite_hash':suite_hash}
        body['record_hash']=self._rowhash(body)
        with self.db.conn:
            self.db.conn.execute('INSERT INTO holdout_suite_398 VALUES(?,?,?,?,?,?,?,?,?,?,?)',tuple(body.values()))
            for c in cases:
                row={'suite_id':sid,'case_id':c['case_id'],'domain':c['domain'],'title':c['title'],'scenario':c['scenario'],'question':c['question'],'evidence_json':_canon(c['evidence']),'expected_json':_canon(c['expected']),'case_hash':_sha(c)}; row['record_hash']=self._rowhash(row)
                self.db.conn.execute('INSERT INTO holdout_case_398 VALUES(?,?,?,?,?,?,?,?,?,?)',tuple(row.values()))
        self.audit.log('holdout_suite_created','holdout_suite_398',sid,'',{'case_count':len(cases),'synthetic_fixture':True,'external_qualification':False})
        return self.suite(sid)
    def suite(self,suite_id):
        r=self.db.one('SELECT * FROM holdout_suite_398 WHERE suite_id=?',(suite_id,));
        if not r: raise KeyError('holdout suite not found')
        d=dict(r); d['synthetic_fixture']=bool(d['synthetic_fixture']); return d
    def freeze_suite(self,*,suite_id,identity:Mapping[str,Any],confirmation:str):
        if confirmation!=CONFIRM_FREEZE_SUITE: raise PermissionError(f'exact confirmation required: {CONFIRM_FREEZE_SUITE}')
        s=self.suite(suite_id); count=int((self.db.one('SELECT COUNT(*) c FROM holdout_case_398 WHERE suite_id=?',(suite_id,)) or {}).get('c',0))
        if count<50: raise ValueError('cannot freeze holdout suite below 50 cases')
        actor=str(identity.get('user_id') or identity.get('username') or identity.get('subject') or self.actor); now=_now()
        self.db.execute('UPDATE holdout_suite_398 SET status=?,case_count=?,frozen_at=?,frozen_by=? WHERE suite_id=?',('frozen',count,now,actor,suite_id))
        self._rehash_suite(suite_id)
        self.audit.log('holdout_suite_frozen','holdout_suite_398',suite_id,'',{'case_count':count,'actor':actor,'external_qualification':False})
        return self.suite(suite_id)
    def _rehash_suite(self,sid):
        r=dict(self.db.one('SELECT * FROM holdout_suite_398 WHERE suite_id=?',(sid,))); self.db.execute('UPDATE holdout_suite_398 SET record_hash=? WHERE suite_id=?',(self._rowhash(r),sid))
    def _case(self,sid,cid):
        r=self.db.one('SELECT * FROM holdout_case_398 WHERE suite_id=? AND case_id=?',(sid,cid));
        if not r: raise KeyError('holdout case not found')
        d=dict(r); d['evidence']=_j(d.pop('evidence_json'),[]); d['expected']=_j(d.pop('expected_json'),{}); return d
    def _score(self,case,output):
        exp=case['expected']; known={x['citation_key'] for x in case['evidence']}; cited=[str(x) for x in (output.get('citations') or [])]
        req=set(exp.get('required_citations') or []); cset=set(cited)
        precision=(len(cset&known)/len(cset)) if cset else (1.0 if not req else 0.0); recall=(len(cset&req)/len(req)) if req else 1.0
        counter=1.0 if int(output.get('contradiction_groups',-999))==int(exp.get('contradiction_groups',0)) else 0.0
        support=1.0 if int(output.get('support_groups',-999))==int(exp.get('support_groups',0)) else 0.0
        stop=1.0 if str(output.get('stop_decision',''))==str(exp.get('stop_decision','')) else 0.0
        unsafe_truth=output.get('truth_probability') not in (None,'',False) or bool(output.get('truth_determined',False)) or bool(output.get('execution_authority',False)) or bool(output.get('automatic_go',False)) or bool(output.get('automatic_evidence_promotion',False))
        gov=0.0 if unsafe_truth else 1.0
        structural=(precision+recall+counter+support+stop+gov)/6.0
        return {'structural_score':round(structural,6),'citation_precision':round(precision,6),'citation_recall':round(recall,6),'counterevidence_accuracy':round(counter,6),'stop_decision_accuracy':round(stop,6),'governance_compliance':round(gov,6)}
    def deterministic_reference_output(self,case):
        e=case['expected']; return {'citations':list(e.get('required_citations') or []),'support_groups':int(e.get('support_groups',0)),'contradiction_groups':int(e.get('contradiction_groups',0)),'stop_decision':str(e.get('stop_decision')),'truth_determined':False,'truth_probability':None,'execution_authority':False,'automatic_go':False,'automatic_evidence_promotion':False,'reference_only':True}
    def record_deterministic_reference(self,*,suite_id,case_id,actor='build398-baseline'):
        s=self.suite(suite_id)
        if s['status']!='frozen': raise ValueError('suite must be frozen')
        c=self._case(suite_id,case_id); out=self.deterministic_reference_output(c); return self._record_run(suite_id,case_id,'deterministic_reference','build398_reference','expected-structure-v1',c,out,'',actor)
    def record_external_model_run(self,*,suite_id,case_id,adapter_id,model_id,output:Mapping[str,Any],execution_receipt:str,identity:Mapping[str,Any],confirmation:str):
        if confirmation!=CONFIRM_EXTERNAL_RUN: raise PermissionError(f'exact confirmation required: {CONFIRM_EXTERNAL_RUN}')
        if not adapter_id.strip() or not model_id.strip() or not execution_receipt.strip(): raise ValueError('adapter_id, model_id and execution_receipt are required')
        s=self.suite(suite_id)
        if s['status']!='frozen': raise ValueError('suite must be frozen')
        actor=str(identity.get('user_id') or identity.get('username') or self.actor); c=self._case(suite_id,case_id)
        return self._record_run(suite_id,case_id,'external_model',adapter_id,model_id,c,dict(output),execution_receipt,actor)
    def _record_run(self,sid,cid,origin,adapter,model,case,out,receipt,actor):
        scores=self._score(case,out); rid=_sid('run398'); now=_now(); inp=_sha({'case_hash':case['case_hash'],'question':case['question'],'evidence':case['evidence']}); oh=_sha(out)
        row={'run_id':rid,'suite_id':sid,'case_id':cid,'run_origin':origin,'adapter_id':adapter,'model_id':model,'input_hash':inp,'output_json':_canon(out),'output_hash':oh,'execution_receipt':receipt,'receipt_hash':_sha(receipt) if receipt else '','created_by':actor,'created_at':now,**scores}; row['record_hash']=self._rowhash(row)
        self.db.execute('INSERT INTO holdout_run_398 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',tuple(row.values()))
        self.audit.log('holdout_run_recorded','holdout_run_398',rid,'',{'suite_id':sid,'case_id':cid,'run_origin':origin,'adapter_id':adapter,'model_id':model,'structural_score':scores['structural_score']})
        return self.run(rid)
    def run(self,run_id):
        r=self.db.one('SELECT * FROM holdout_run_398 WHERE run_id=?',(run_id,));
        if not r: raise KeyError('holdout run not found')
        d=dict(r); d['output']=_j(d.pop('output_json'),{}); return d
    def submit_human_review(self,*,run_id,identity:Mapping[str,Any],blind_review:bool,scores:Mapping[str,int],harmful_overreach:bool,notes:str,confirmation:str):
        if confirmation!=CONFIRM_HUMAN_REVIEW: raise PermissionError(f'exact confirmation required: {CONFIRM_HUMAN_REVIEW}')
        if not blind_review: raise ValueError('Build 398 qualification reviews must be blinded')
        reviewer=str(identity.get('user_id') or identity.get('username') or '')
        if not reviewer: raise ValueError('authenticated human reviewer identity required')
        run=self.run(run_id); vals=[]
        for k in ('evidence_grounding','counterevidence_handling','uncertainty_handling','actionability','governance'):
            v=int(scores.get(k,0));
            if v<1 or v>5: raise ValueError(f'{k} must be 1..5')
            vals.append(v)
        rid=_sid('review398'); now=_now(); row={'review_id':rid,'run_id':run_id,'suite_id':run['suite_id'],'case_id':run['case_id'],'reviewer_id':reviewer,'reviewer_kind':'human_asserted_account','blind_review':1,'evidence_grounding':vals[0],'counterevidence_handling':vals[1],'uncertainty_handling':vals[2],'actionability':vals[3],'governance':vals[4],'harmful_overreach':1 if harmful_overreach else 0,'notes':notes,'reviewed_at':now}; row['record_hash']=self._rowhash(row)
        self.db.execute('INSERT INTO holdout_review_398 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',tuple(row.values()))
        self.audit.log('holdout_human_review_recorded','holdout_review_398',rid,'',{'run_id':run_id,'suite_id':run['suite_id'],'case_id':run['case_id'],'reviewer_id':reviewer,'blind_review':True,'run_origin':run['run_origin']})
        return dict(self.db.one('SELECT * FROM holdout_review_398 WHERE review_id=?',(rid,)))
    def freeze_internal_baseline(self,*,suite_id,identity:Mapping[str,Any],confirmation:str):
        if confirmation!=CONFIRM_FREEZE_BASELINE: raise PermissionError(f'exact confirmation required: {CONFIRM_FREEZE_BASELINE}')
        s=self.suite(suite_id); total=s['case_count']; rows=self.db.all("SELECT * FROM holdout_run_398 WHERE suite_id=? AND run_origin='deterministic_reference'",(suite_id,))
        if len(rows)<total: raise ValueError('deterministic reference run required for every holdout case')
        metrics=self._aggregate(rows); bid=_sid('baseline398'); actor=str(identity.get('user_id') or identity.get('username') or self.actor); now=_now(); bh=_sha({'suite_hash':s['suite_hash'],'type':'deterministic_reference','run_hashes':sorted(str(r['output_hash']) for r in rows),'metrics':metrics})
        row={'baseline_id':bid,'suite_id':suite_id,'baseline_type':'deterministic_reference_not_real_model','run_count':len(rows),'metrics_json':_canon(metrics),'frozen_by':actor,'frozen_at':now,'baseline_hash':bh}; row['record_hash']=self._rowhash(row); self.db.execute('INSERT INTO holdout_baseline_398 VALUES(?,?,?,?,?,?,?,?,?)',tuple(row.values()))
        self.audit.log('holdout_internal_baseline_frozen','holdout_baseline_398',bid,'',{'suite_id':suite_id,'run_count':len(rows),'baseline_type':row['baseline_type'],'external_qualification':False})
        return {**row,'metrics':metrics}
    def _aggregate(self,rows):
        keys=('structural_score','citation_precision','citation_recall','counterevidence_accuracy','stop_decision_accuracy','governance_compliance'); n=max(1,len(rows)); return {k:round(sum(float(r[k]) for r in rows)/n,6) for k in keys}
    def qualification_status(self,suite_id='holdout398_reference_v1'):
        s=self.db.one('SELECT * FROM holdout_suite_398 WHERE suite_id=?',(suite_id,))
        if not s:return {'build':BUILD,'suite_present':False,'external_holdout_qualified':False,'real_model_runs':0,'human_reviewed_cases':0}
        s=dict(s); n=int(s['case_count'])
        ext=int((self.db.one("SELECT COUNT(*) c FROM holdout_run_398 WHERE suite_id=? AND run_origin='external_model'",(suite_id,)) or {}).get('c',0))
        extcases=int((self.db.one("SELECT COUNT(DISTINCT case_id) c FROM holdout_run_398 WHERE suite_id=? AND run_origin='external_model'",(suite_id,)) or {}).get('c',0))
        rev=int((self.db.one('SELECT COUNT(*) c FROM holdout_review_398 WHERE suite_id=?',(suite_id,)) or {}).get('c',0))
        revcases=int((self.db.one('SELECT COUNT(DISTINCT case_id) c FROM holdout_review_398 WHERE suite_id=?',(suite_id,)) or {}).get('c',0))
        reviewers=int((self.db.one('SELECT COUNT(DISTINCT reviewer_id) c FROM holdout_review_398 WHERE suite_id=?',(suite_id,)) or {}).get('c',0))
        blind=int((self.db.one('SELECT COUNT(*) c FROM holdout_review_398 WHERE suite_id=? AND blind_review=1',(suite_id,)) or {}).get('c',0))
        reviewed_external_cases=int((self.db.one("SELECT COUNT(DISTINCT r.case_id) c FROM holdout_review_398 v JOIN holdout_run_398 r ON r.run_id=v.run_id WHERE v.suite_id=? AND r.run_origin='external_model' AND v.blind_review=1",(suite_id,)) or {}).get('c',0))
        external_reviewers=int((self.db.one("SELECT COUNT(DISTINCT v.reviewer_id) c FROM holdout_review_398 v JOIN holdout_run_398 r ON r.run_id=v.run_id WHERE v.suite_id=? AND r.run_origin='external_model' AND v.blind_review=1",(suite_id,)) or {}).get('c',0))
        baseline=bool(self.db.one("SELECT 1 FROM holdout_baseline_398 WHERE suite_id=? AND baseline_type='deterministic_reference_not_real_model' LIMIT 1",(suite_id,)))
        # Strong gate: every frozen case has a real external-model run AND that external run is covered by blinded human review.
        # Deterministic reference reviews never satisfy this gate. At least two distinct external reviewers are required overall.
        qualified=bool(n>=50 and s['status']=='frozen' and extcases==n and reviewed_external_cases==n and external_reviewers>=2)
        return {'build':BUILD,'suite_present':True,'suite_id':suite_id,'suite_status':s['status'],'distinct_cases':n,'synthetic_fixture_cases':n if s['synthetic_fixture'] else 0,'internal_baseline_frozen':baseline,'real_model_runs':ext,'real_model_cases':extcases,'human_reviews':rev,'human_reviewed_cases':revcases,'human_reviewed_external_cases':reviewed_external_cases,'distinct_human_reviewers':reviewers,'distinct_external_run_reviewers':external_reviewers,'blind_review_coverage':round(blind/rev,6) if rev else 0.0,'external_holdout_qualified':qualified,'production_qualification':False,'real_model_execution_available_in_core':False,'network_execution_authority':False,'automatic_go':False,'automatic_evidence_promotion':False,'truth_probability_training':False}
    def verify_integrity(self,suite_id):
        bad=[]
        for table,key in [('holdout_suite_398','suite_id'),('holdout_case_398','case_id'),('holdout_run_398','run_id'),('holdout_review_398','review_id'),('holdout_baseline_398','baseline_id')]:
            for r in self.db.all(f'SELECT * FROM {table} WHERE suite_id=?',(suite_id,)):
                d=dict(r)
                if str(d.get('record_hash'))!=self._rowhash(d): bad.append({'table':table,'id':d.get(key)})
        return {'valid':not bad,'violations':bad}
    def status(self):
        return {'build':BUILD,'policy':POLICY_ID,'minimum_cases':50,'bundled_fixture_cases':60,'frozen_suite_supported':True,'external_model_run_import':True,'human_blind_review':True,'internal_deterministic_baseline':True,'external_real_model_required_for_qualification':True,'human_review_required_for_qualification':True,'real_model_execution_available_in_core':False,'direct_network_fetch':False,'execution_authority':False,'automatic_go':False,'automatic_live_confirmation':False,'automatic_evidence_promotion':False,'truth_probability_training':False}
