from __future__ import annotations
import hashlib, json, math, re
from collections import defaultdict
from typing import Any, Callable, Iterable, Mapping
from eagleeye_pro.core.database import dumps, loads, new_id, now_ts


def _canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)
def _hash(v: Any) -> str:
    return hashlib.sha256(_canon(v).encode('utf-8')).hexdigest()
def _div(a: float,b: float)->float:
    return a/b if b else 0.0

class Build165EntityResolutionFieldService:
    BUILD='165.0'
    MISSION='Field-grade entity-resolution benchmarks and AI-assisted error analysis'
    SENSITIVE=re.compile(r'(password|token|secret|api[_-]?key|authorization|cookie|session)',re.I)
    DIFFICULTIES={'routine','challenging','adversarial'}
    DEFAULT_GATE={
      'min_precision':.97,'min_recall':.85,'max_false_merge_rate':.03,
      'max_false_split_rate':.15,'max_ece':.10,'min_pairs':20,
    }
    def __init__(self, db: Any, audit: Any, *, benchmark: Any|None=None,
                 multilingual: Any|None=None, temporal: Any|None=None,
                 actor: str='system') -> None:
        self.db=db; self.audit=audit; self.benchmark=benchmark
        self.multilingual=multilingual; self.temporal=temporal; self.actor=actor

    def create_dataset(self, *, name: str, records: Iterable[Mapping[str,Any]],
                       pairs: Iterable[Mapping[str,Any]], description: str='',
                       provenance: Mapping[str,Any]|None=None,
                       governance: Mapping[str,Any]|None=None,
                       created_by: str|None=None, confirmation: str) -> dict[str,Any]:
        if confirmation!='FIELD BENCHMARK 165 DATENSATZ ANLEGEN':
            raise PermissionError('explicit benchmark dataset approval required')
        recs=[dict(r) for r in records]; prs=[dict(p) for p in pairs]
        if len(recs)<2 or not prs: raise ValueError('at least two records and one pair required')
        ids=set(); safe_records=[]
        for r in recs:
            rid=str(r.get('record_id') or new_id('fieldrec165'))
            if rid in ids: raise ValueError('duplicate record_id')
            ids.add(rid); data=dict(r.get('data') or {})
            if self.SENSITIVE.search(_canon(data)): raise ValueError('sensitive credentials are not permitted in benchmark records')
            safe_records.append({**r,'record_id':rid,'data':data,'entity_ref':str(r.get('entity_ref') or '')})
            if not safe_records[-1]['entity_ref']: raise ValueError('entity_ref ground truth required')
        pair_rows=[]
        for p in prs:
            l=str(p.get('left_record_id','')); rr=str(p.get('right_record_id',''))
            if l not in ids or rr not in ids or l==rr: raise ValueError('pair references invalid records')
            diff=str(p.get('difficulty','routine'))
            if diff not in self.DIFFICULTIES: raise ValueError('invalid difficulty')
            expected=bool(p.get('expected_match'))
            pair_rows.append({**p,'left_record_id':l,'right_record_id':rr,'expected_match':expected,'difficulty':diff,'scenario_tags':list(p.get('scenario_tags') or [])})
        prov=dict(provenance or {}); gov={
          'public_or_authorized_only':True,'no_credentials':True,'review_first':True,
          'automatic_identity_confirmation':False,'field_data_reuse_restricted':True,
          **dict(governance or {})}
        did=new_id('fieldset165'); payload={'records':safe_records,'pairs':pair_rows,'provenance':prov,'governance':gov}
        self.db.execute('INSERT INTO er_field_datasets_165 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(
          did,name.strip(),description.strip(),dumps(prov),dumps(gov),'curated',len(safe_records),len(pair_rows),_hash(payload),created_by or self.actor,now_ts()))
        for r in safe_records:
            self.db.execute('INSERT INTO er_field_records_165 VALUES(?,?,?,?,?,?,?,?,?,?)',(
              r['record_id'],did,r['entity_ref'],str(r.get('source_type','public_reference')),r.get('source_ref'),r.get('language'),r.get('script'),dumps(r['data']),_hash(r['data']),now_ts()))
        for p in pair_rows:
            adjud={'method':p.get('adjudication_method','human_ground_truth'),'note':str(p.get('note',''))[:500]}
            self.db.execute('INSERT INTO er_field_pairs_165 VALUES(?,?,?,?,?,?,?,?,?)',(
              new_id('fieldpair165'),did,p['left_record_id'],p['right_record_id'],int(p['expected_match']),p['difficulty'],dumps(p['scenario_tags']),dumps(adjud),now_ts()))
        self.audit.log('er_field_dataset_created_165','er_field_dataset',did,None,{'records':len(safe_records),'pairs':len(pair_rows)})
        return self.dataset(did)

    def run(self, dataset_id: str, scorer: Callable[[Mapping[str,Any],Mapping[str,Any]],Any]|None=None,
            *, threshold: float=.75, engine_name: str='multilingual_identity',
            engine_version: str='165') -> dict[str,Any]:
        if not 0<=threshold<=1: raise ValueError('threshold outside range')
        rows=self.db.all('''SELECT p.*,l.record_json left_json,r.record_json right_json
          FROM er_field_pairs_165 p JOIN er_field_records_165 l ON l.record_id=p.left_record_id
          JOIN er_field_records_165 r ON r.record_id=p.right_record_id WHERE p.dataset_id=? ORDER BY p.pair_id''',(dataset_id,))
        if not rows: raise KeyError('dataset not found or empty')
        started=now_ts(); outcomes=[]
        for row in rows:
            left=loads(row['left_json'],{}); right=loads(row['right_json'],{})
            result=(scorer(left,right) if scorer else self._default_score(left,right))
            if isinstance(result,Mapping): score=float(result.get('score',0)); explanation=dict(result.get('explanation') or result.get('signals') or {})
            else: score=float(result); explanation={}
            score=max(0,min(1,score)); actual=bool(row['expected_match']); predicted=score>=threshold
            outcomes.append({'pair_id':row['pair_id'],'actual':actual,'predicted':predicted,'score':score,
              'difficulty':row['difficulty'],'tags':loads(row['scenario_tags_json'],[]),'explanation':explanation})
        metrics=self._metrics(outcomes); slices=self._slices(outcomes)
        errors=[{**o,'error_type':'false_merge' if o['predicted'] else 'false_split'} for o in outcomes if o['actual']!=o['predicted']]
        rid=new_id('fieldrun165'); finished=now_ts(); payload={'dataset_id':dataset_id,'metrics':metrics,'slices':slices,'errors':errors,'threshold':threshold}
        self.db.execute('INSERT INTO er_field_runs_165 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(
          rid,dataset_id,engine_name,engine_version,threshold,dumps(metrics),dumps(slices),dumps(errors),started,finished,_hash(payload)))
        self.audit.log('er_field_run_completed_165','er_field_run',rid,None,{'precision':metrics['precision'],'false_merge_rate':metrics['false_merge_rate']})
        return {'run_id':rid,**payload,'review_required':True,'automatic_identity_confirmation':False}

    def _default_score(self,left:Mapping[str,Any],right:Mapping[str,Any])->dict[str,Any]:
        ln=str(left.get('name') or left.get('display_name') or left.get('handle') or '')
        rn=str(right.get('name') or right.get('display_name') or right.get('handle') or '')
        if self.multilingual and ln and rn:
            result=self.multilingual.compare(ln,rn)
            score=float(result.get('risk_adjusted_score',result.get('score',0)))
            signals=dict(result.get('signals') or {})
        else:
            a=' '.join(ln.casefold().split()); b=' '.join(rn.casefold().split()); score=1.0 if a and a==b else 0.0; signals={'exact':score==1.0}
        boosts=[]; conflicts=[]
        for key,weight in [('email',.35),('orcid',.40),('phone',.30),('organization',.12),('location',.08),('birth_date',.25),('handle',.18)]:
            lv=left.get(key); rv=right.get(key)
            if lv and rv:
                if str(lv).casefold()==str(rv).casefold(): score += weight*(1-score); boosts.append(key)
                elif key in {'email','orcid','phone','birth_date'}: score*=.55; conflicts.append(key)
        return {'score':max(0,min(1,score)),'explanation':{'name_signals':signals,'matching_fields':boosts,'conflicting_fields':conflicts}}

    @staticmethod
    def _metrics(rows:list[dict[str,Any]])->dict[str,Any]:
        tp=sum(r['actual'] and r['predicted'] for r in rows); fp=sum((not r['actual']) and r['predicted'] for r in rows)
        fn=sum(r['actual'] and not r['predicted'] for r in rows); tn=len(rows)-tp-fp-fn
        precision=_div(tp,tp+fp); recall=_div(tp,tp+fn); f1=_div(2*precision*recall,precision+recall)
        brier=sum((r['score']-int(r['actual']))**2 for r in rows)/len(rows)
        ece=0.0
        for lo in [i/10 for i in range(10)]:
            bucket=[r for r in rows if lo<=r['score']<lo+.1 or (lo==.9 and r['score']==1)]
            if bucket: ece += len(bucket)/len(rows)*abs(sum(r['score'] for r in bucket)/len(bucket)-sum(int(r['actual']) for r in bucket)/len(bucket))
        return {'n':len(rows),'tp':tp,'fp':fp,'fn':fn,'tn':tn,'precision':precision,'recall':recall,'f1':f1,
          'false_merge_rate':_div(fp,tp+fp),'false_split_rate':_div(fn,tp+fn),'brier_score':brier,'expected_calibration_error':ece}

    def _slices(self,rows:list[dict[str,Any]])->dict[str,Any]:
        groups=defaultdict(list)
        for r in rows:
            groups[f"difficulty:{r['difficulty']}"].append(r)
            for tag in r['tags']: groups[f'tag:{tag}'].append(r)
        return {k:self._metrics(v) for k,v in sorted(groups.items())}

    def ai_assess(self, run_id: str, *, case_id: str|None=None, task_type: str='root_cause',
                  context: Mapping[str,Any]|None=None) -> dict[str,Any]:
        if task_type not in {'root_cause','threshold_review','next_training_cases','operational_risk'}: raise ValueError('unsupported AI assessment')
        row=self.db.one('SELECT * FROM er_field_runs_165 WHERE run_id=?',(run_id,))
        if not row: raise KeyError('run not found')
        metrics=loads(row['metrics_json'],{}); errors=loads(row['error_analysis_json'],[]); slices=loads(row['slice_metrics_json'],{})
        safe={k:('[REDACTED]' if self.SENSITIVE.search(str(k)) else v) for k,v in dict(context or {}).items()}
        false_merges=[e for e in errors if e['error_type']=='false_merge']; false_splits=[e for e in errors if e['error_type']=='false_split']
        weak=sorted(((k,v.get('f1',0)) for k,v in slices.items()),key=lambda x:x[1])[:5]
        suggestions=[]
        if false_merges: suggestions.append({'priority':'critical','action':'raise_or_segment_threshold','reason':f'{len(false_merges)} false merges detected'})
        if false_splits: suggestions.append({'priority':'high','action':'expand_alias_and_cross_script_features','reason':f'{len(false_splits)} false splits detected'})
        if metrics.get('expected_calibration_error',0)>.1: suggestions.append({'priority':'high','action':'recalibrate_confidence_scores','reason':'confidence is not sufficiently calibrated'})
        for name,score in weak[:3]: suggestions.append({'priority':'medium','action':'collect_targeted_adjudicated_examples','slice':name,'observed_f1':score})
        if not suggestions: suggestions.append({'priority':'low','action':'expand_holdout_field_dataset','reason':'avoid overfitting to current benchmark'})
        output={'task_type':task_type,'metrics':metrics,'error_counts':{'false_merges':len(false_merges),'false_splits':len(false_splits)},
          'weakest_slices':weak,'suggestions':suggestions,'limitations':['advisory only','benchmark quality depends on ground truth','no automatic profile merge or operational action'],
          'review_required':True}
        opsec={'local_only':True,'external_model_called':False,'sensitive_content_persisted':False,'input_redacted':safe!=dict(context or {})}
        aid=new_id('aier165'); payload={'assessment_id':aid,'run_id':run_id,'case_id':case_id,'output':output,'opsec':opsec}
        self.db.execute('INSERT INTO ai_er_assessments_165 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(
          aid,run_id,case_id,task_type,_hash(safe),dumps(output),dumps(opsec),'local_deterministic',1,now_ts(),_hash(payload)))
        self.audit.log('ai_er_assessment_165','ai_er_assessment',aid,case_id,{'task_type':task_type,'review_required':True})
        return {**payload,'automatic_action':False,'automatic_identity_confirmation':False}

    def release_gate(self, run_id: str, *, thresholds: Mapping[str,Any]|None=None,
                     approved_by: str|None=None, confirmation: str|None=None) -> dict[str,Any]:
        row=self.db.one('SELECT * FROM er_field_runs_165 WHERE run_id=?',(run_id,))
        if not row: raise KeyError('run not found')
        t={**self.DEFAULT_GATE,**dict(thresholds or {})}; m=loads(row['metrics_json'],{})
        checks={'min_pairs':m['n']>=t['min_pairs'],'precision':m['precision']>=t['min_precision'],'recall':m['recall']>=t['min_recall'],
          'false_merge_rate':m['false_merge_rate']<=t['max_false_merge_rate'],'false_split_rate':m['false_split_rate']<=t['max_false_split_rate'],
          'calibration':m['expected_calibration_error']<=t['max_ece']}
        decision='eligible_for_human_approval' if all(checks.values()) else 'blocked'
        if approved_by:
            if confirmation!=f'ER GATE 165 {run_id} FREIGEBEN': raise PermissionError('explicit human release approval required')
            if decision!='eligible_for_human_approval': raise PermissionError('quality gate is not eligible')
            decision='approved_for_candidate_use'
        gid=new_id('ergate165'); payload={'gate_id':gid,'run_id':run_id,'decision':decision,'thresholds':t,'checks':checks}
        self.db.execute('INSERT INTO er_release_gates_165 VALUES(?,?,?,?,?,?,?,?,?)',(
          gid,run_id,decision,dumps(t),dumps(checks),approved_by,now_ts() if approved_by else None,now_ts(),_hash(payload)))
        return payload

    def dataset(self,dataset_id:str)->dict[str,Any]:
        row=self.db.one('SELECT * FROM er_field_datasets_165 WHERE dataset_id=?',(dataset_id,))
        if not row: raise KeyError('dataset not found')
        out=dict(row); out['provenance']=loads(out.pop('provenance_json'),{}); out['governance']=loads(out.pop('governance_json'),{}); return out
