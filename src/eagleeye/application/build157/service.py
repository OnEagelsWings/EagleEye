from __future__ import annotations
import hashlib, json, math
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from eagleeye_pro.core.database import dumps, loads, new_id, now_ts

def _canonical(v: Any)->str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',',':'), default=str)
def _digest(v: Any)->str:
    return hashlib.sha256(_canonical(v).encode('utf-8')).hexdigest()

class Build157EntityResolutionBenchmarkService:
    BUILD='157.0'; MISSION='Entity Resolution Benchmark and Code Consolidation'
    def __init__(self, db: Any, audit: Any, *, canonical_resolution: Any|None=None, actor: str='system', project_root: str|Path|None=None):
        self.db=db; self.audit=audit; self.canonical_resolution=canonical_resolution; self.actor=actor
        self.project_root=Path(project_root or Path(__file__).resolve().parents[4])

    def create_benchmark(self, *, name: str, pairs: Iterable[Mapping[str,Any]], description: str='', actor: str|None=None)->dict[str,Any]:
        rows=[]
        for p in pairs:
            if 'left' not in p or 'right' not in p or 'match' not in p: raise ValueError('Jedes Paar benötigt left, right und match')
            rows.append({'left':dict(p['left']),'right':dict(p['right']),'match':bool(p['match'])})
        if not rows: raise ValueError('Benchmark benötigt mindestens ein Paar')
        bid=new_id('erbench157'); ts=now_ts(); policy={'review_first':True,'automatic_identity_confirmation':False,'primary_risk':'false_merge'}
        self.db.execute('INSERT INTO er_benchmarks_157 VALUES(?,?,?,?,?,?,?)',(bid,name.strip(),description.strip(),_digest(rows),actor or self.actor,ts,dumps(policy)))
        for p in rows:
            self.db.execute('INSERT INTO er_benchmark_pairs_157(pair_id,benchmark_id,left_record_json,right_record_json,expected_match) VALUES(?,?,?,?,?)',(new_id('erpair157'),bid,dumps(p['left']),dumps(p['right']),int(p['match'])))
        self.audit.log('er_benchmark_created_157','er_benchmark',bid,None,{'pairs':len(rows),'name':name})
        return self.benchmark(bid)

    def run(self, benchmark_id: str, scorer: Callable[[Mapping[str,Any],Mapping[str,Any]],Any], *, engine_name: str='canonical', engine_version: str='157', threshold: float=.75)->dict[str,Any]:
        if not 0 <= threshold <= 1: raise ValueError('threshold muss zwischen 0 und 1 liegen')
        pairs=self.db.all('SELECT * FROM er_benchmark_pairs_157 WHERE benchmark_id=? ORDER BY pair_id',(benchmark_id,))
        if not pairs: raise KeyError('Benchmark nicht gefunden oder leer')
        started=now_ts(); y=[]; pred=[]; scores=[]; errors=[]
        for row in pairs:
            left=loads(row['left_record_json'],{}); right=loads(row['right_record_json'],{})
            result=scorer(left,right)
            if isinstance(result,Mapping): score=float(result.get('score',0)); explanation=dict(result.get('explanation') or {})
            else: score=float(result); explanation={}
            score=max(0.0,min(1.0,score)); actual=bool(row['expected_match']); predicted=score>=threshold
            self.db.execute('UPDATE er_benchmark_pairs_157 SET predicted_match=?,predicted_score=?,explanation_json=? WHERE pair_id=?',(int(predicted),score,dumps(explanation),row['pair_id']))
            y.append(actual); pred.append(predicted); scores.append(score)
            if actual != predicted: errors.append({'pair_id':row['pair_id'],'type':'false_merge' if predicted else 'false_split','score':score,'left':left,'right':right})
        metrics=self._metrics(y,pred,scores); finished=now_ts(); payload={'benchmark_id':benchmark_id,'engine':engine_name,'version':engine_version,'threshold':threshold,'metrics':metrics,'errors':errors}
        rid=new_id('errun157')
        self.db.execute('INSERT INTO er_benchmark_runs_157 VALUES(?,?,?,?,?,?,?,?,?,?)',(rid,benchmark_id,engine_name,engine_version,threshold,dumps(metrics),dumps(errors),started,finished,_digest(payload)))
        self.audit.log('er_benchmark_run_157','er_benchmark_run',rid,None,metrics)
        return {'run_id':rid,**payload,'review_required':True,'automatic_identity_confirmation':False}

    @staticmethod
    def _metrics(y:list[bool], pred:list[bool], scores:list[float])->dict[str,Any]:
        tp=sum(a and p for a,p in zip(y,pred)); fp=sum((not a) and p for a,p in zip(y,pred)); fn=sum(a and (not p) for a,p in zip(y,pred)); tn=len(y)-tp-fp-fn
        div=lambda a,b: a/b if b else 0.0
        precision=div(tp,tp+fp); recall=div(tp,tp+fn)
        f1=div(2*precision*recall,precision+recall)
        brier=sum((s-int(a))**2 for a,s in zip(y,scores))/len(y)
        bins=[]; ece=0.0
        for low in [i/10 for i in range(10)]:
            idx=[i for i,s in enumerate(scores) if low <= s <= (1.0 if low==.9 else low+.1)]
            if not idx: continue
            conf=sum(scores[i] for i in idx)/len(idx); acc=sum(int(y[i]) for i in idx)/len(idx)
            ece += len(idx)/len(y)*abs(acc-conf); bins.append({'low':low,'count':len(idx),'accuracy':acc,'confidence':conf})
        return {'n':len(y),'tp':tp,'fp':fp,'fn':fn,'tn':tn,'precision':precision,'recall':recall,'f1':f1,'false_merge_rate':div(fp,tp+fp),'false_split_rate':div(fn,tp+fn),'brier_score':brier,'expected_calibration_error':ece,'calibration_bins':bins}

    def benchmark(self,bid:str)->dict[str,Any]:
        row=self.db.one('SELECT * FROM er_benchmarks_157 WHERE benchmark_id=?',(bid,))
        if not row: raise KeyError('Benchmark nicht gefunden')
        row['policy']=loads(row.pop('policy_json'),{}); row['pair_count']=self.db.one('SELECT COUNT(*) n FROM er_benchmark_pairs_157 WHERE benchmark_id=?',(bid,))['n']; return row

    def consolidate_code(self, *, confirmation: str)->dict[str,Any]:
        if confirmation!='CODEKONSOLIDIERUNG 157 AUSFÜHREN': raise PermissionError('Explizite Bestätigung erforderlich')
        mappings=[
          ('eagleeye.application.build115','eagleeye.domain.entity_resolution','adapter','legacy build-specific identity implementation'),
          ('eagleeye.application.build152','eagleeye.application.domain_ports','retain','canonical service resolver'),
          ('eagleeye.application.build156','eagleeye.application.collection','adapter','collection orchestrator canonical alias'),
          ('eagleeye_pro.core.database','eagleeye.infrastructure.database','adapter','legacy database compatibility boundary'),
        ]
        for legacy,canonical,disp,why in mappings:
            self.db.execute('INSERT OR REPLACE INTO code_consolidation_157 VALUES(?,?,?,?,?,?,?)',(new_id('consol157'),legacy,canonical,disp,'active',why,now_ts()))
        payload=self._inventory(); sid=new_id('consnap157')
        self.db.execute('INSERT INTO consolidation_snapshots_157 VALUES(?,?,?,?)',(sid,dumps(payload),_digest(payload),now_ts()))
        self.audit.log('code_consolidation_snapshot_157','consolidation_snapshot',sid,None,{'mappings':len(mappings),'python_files':payload['python_files']})
        return {'snapshot_id':sid,'sha256':_digest(payload),**payload,'destructive_deletion':False}

    def _inventory(self)->dict[str,Any]:
        py=list(self.project_root.rglob('*.py')); build_dirs=[]; large=[]
        for p in py:
            rel=p.relative_to(self.project_root).as_posix()
            if '/build' in '/'+rel or rel.startswith('eagleeye_pro/features/build'): build_dirs.append(rel)
            try: lines=sum(1 for _ in p.open('r',encoding='utf-8',errors='ignore'))
            except OSError: continue
            if lines>=1200: large.append({'path':rel,'lines':lines})
        return {'python_files':len(py),'build_specific_files':len(build_dirs),'large_modules':sorted(large,key=lambda x:x['lines'],reverse=True),'canonical_roots':['src/eagleeye/domain','src/eagleeye/application','src/eagleeye/infrastructure','src/eagleeye/interfaces'],'legacy_compatibility_root':'eagleeye_pro','automatic_identity_confirmation':False}
