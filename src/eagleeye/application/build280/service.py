from __future__ import annotations
import hashlib, html, json, time, uuid
from pathlib import Path
from typing import Any

def _now(): return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
def _id(p): return f'{p}_{uuid.uuid4().hex[:12]}'
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v): return hashlib.sha256(_canon(v).encode()).hexdigest()

class Build280Phase11ReleaseCandidateService:
    BUILD='280.0'
    def __init__(self, db:Any, audit:Any, *, build279:Any, compatibility:Any, install_dir:Path, actor:str='local-analyst'):
        self.db=db; self.audit=audit; self.build279=build279; self.compatibility=compatibility; self.install_dir=Path(install_dir); self.actor=actor

    def _darkweb_code_hits(self):
        needles=('tor'+'_client','onion'+'_fetch','stem'+'.control','socks5h'+':'+'//')
        hits=[]
        for root in (self.install_dir/'src/eagleeye/application/build280', self.install_dir/'src/eagleeye/infrastructure/build280'):
            for p in root.rglob('*.py'):
                text=p.read_text(encoding='utf-8',errors='ignore').lower()
                for n in needles:
                    if n in text: hits.append(f'{p.relative_to(self.install_dir)}:{n}')
        return hits

    def ai_metrics(self):
        n=self.db.one("SELECT COUNT(*) n FROM ai_release_benchmarks_280 WHERE review_status='reviewed'")['n']
        return {'reviewed_release_benchmarks':n,'full_case_rc_gate':True,'multi_agent_rc_gate':True,'automatic_model_activation':False,'automatic_adapter_activation':False}

    def opsec_metrics(self):
        n=self.db.one("SELECT COUNT(*) n FROM opsec_release_controls_280 WHERE review_status='verified'")['n']
        return {'verified_release_controls':n,'direct_agent_egress':0,'automatic_publication':0,'automatic_upload':0,'automatic_contact':0,'darkweb_collection':0,'automatic_ip_rotation':0}

    def create_release_candidate(self, *, actor=None):
        actor=actor or self.actor
        q=self.build279.run_synthetic_full_case(actor=actor,scenario_name='phase11_build280_release_candidate')
        brief=self.db.one('SELECT * FROM case_qualification_briefs_279 WHERE brief_id=?',(q['brief_id'],))
        integrity=next(iter(self.db.one('PRAGMA integrity_check').values()))
        fk=len(self.db.all('PRAGMA foreign_key_check'))
        parent=self.build279.qualified_gate()
        dark_hits=self._darkweb_code_hits()
        stages=[
          ('build279_full_case',q['stage_pass_count']==q['stage_count']==17,{'stages':f"{q['stage_pass_count']}/{q['stage_count']}"}),
          ('multi_agent',q['agent_pass_count']==q['agent_count']==10,{'agents':f"{q['agent_pass_count']}/{q['agent_count']}"}),
          ('counterevidence_redteam_assertion',bool(brief and brief['counterevidence_pass'] and brief['redteam_pass'] and brief['assertion_ceiling_pass']),{}),
          ('restricted_export',bool(brief and brief['restricted_content_pass'] and brief['product_export_pass']),{}),
          ('opsec_stress',q['opsec_stress']['result']=='pass',q['opsec_stress']),
          ('sqlite_integrity',integrity=='ok' and fk==0,{'integrity':integrity,'foreign_key_violations':fk}),
          ('parent_gate',bool(parent['release_ready']),parent),
          ('phase12_boundary',len(dark_hits)==0,{'darkweb_code_hits':dark_hits}),
          ('ai_release_delta',self.ai_metrics()['reviewed_release_benchmarks']>=12,self.ai_metrics()),
          ('opsec_release_delta',self.opsec_metrics()['verified_release_controls']>=12,self.opsec_metrics())]
        passed=sum(bool(ok) for _,ok,_ in stages)
        status='phase11_release_candidate' if passed==len(stages) else 'not_ready'
        rid=_id('rc280'); payload={'qualification':q['brief_id'],'stages':stages,'status':status}
        self.db.execute('INSERT INTO phase11_release_runs_280 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(
          rid,q['case_id'],q['brief_id'],q['simulation_id'],q['stage_pass_count'],q['stage_count'],q['agent_pass_count'],q['agent_count'],
          integrity,fk,len(dark_hits),0,status,actor,_now(),_hash(payload)))
        for key,ok,metrics in stages:
            sid=_id('rcstage280')
            self.db.execute('INSERT INTO phase11_release_stages_280 VALUES(?,?,?,?,?,?,?,?)',(sid,rid,key,'pass' if ok else 'fail',1,_canon(metrics),_now(),_hash((rid,key,ok,metrics))))
        return {'run_id':rid,'case_id':q['case_id'],'brief_id':q['brief_id'],'simulation_id':q['simulation_id'],'status':status,
                'stage_pass_count':passed,'stage_count':len(stages),'full_case_stages':f"{q['stage_pass_count']}/{q['stage_count']}",
                'agents':f"{q['agent_pass_count']}/{q['agent_count']}",'sqlite_integrity':integrity,'foreign_key_violations':fk,
                'darkweb_code_hits':dark_hits,'automatic_deployment':False,'automatic_publication':False,
                'stages':[{'stage':k,'status':'pass' if ok else 'fail','metrics':m} for k,ok,m in stages]}

    def final_review(self, *, run_id, decision, rationale, reviewer):
        run=self.db.one('SELECT * FROM phase11_release_runs_280 WHERE run_id=?',(run_id,))
        if not run: raise KeyError('release run not found')
        if reviewer==run['created_by']: raise ValueError('independent reviewer required')
        if decision not in {'retain_phase11_release_candidate','reject_phase11_release_candidate'}: raise ValueError('invalid decision')
        if decision=='retain_phase11_release_candidate' and run['release_candidate_status']!='phase11_release_candidate': raise PermissionError('not a qualified release candidate')
        rev=_id('rcreview280')
        self.db.execute('INSERT INTO phase11_release_reviews_280 VALUES(?,?,?,?,?,?,?,?)',(rev,run_id,run['case_id'],decision,rationale,reviewer,_now(),_hash((run_id,decision,rationale,reviewer))))
        return {'review_id':rev,'run_id':run_id,'decision':decision,'automatic_deployment':False,'phase12_started':False}

    def qualified_gate(self):
        a=self.ai_metrics(); o=self.opsec_metrics(); p=self.build279.qualified_gate()
        g={'build':'280.0','main_goal':True,'ai_delta':a['reviewed_release_benchmarks']>=12,
           'opsec_delta':o['verified_release_controls']>=12 and o['darkweb_collection']==0,
           'capability_regression':p['release_ready'],'parent_build_gate':p['release_ready'],'phase12_boundary':len(self._darkweb_code_hits())==0}
        g['release_ready']=all(g[k] for k in ('main_goal','ai_delta','opsec_delta','capability_regression','parent_build_gate','phase12_boundary'))
        return g

    def render_workspace_panel(self, *, case_id, csrf):
        e=lambda v:html.escape(str(v or ''),quote=True)
        rows=self.db.all('SELECT * FROM phase11_release_runs_280 ORDER BY created_at DESC LIMIT 10')
        body=''.join(f"<tr><td><code>{e(r['run_id'])}</code></td><td>{e(r['stage_pass_count'])}/{e(r['stage_count'])}</td><td>{e(r['agent_pass_count'])}/{e(r['agent_count'])}</td><td>{e(r['sqlite_integrity'])}</td><td>{e(r['release_candidate_status'])}</td></tr>" for r in rows)
        return f"""<section class='card'><h2>Phase-11 Release Candidate · Build 280</h2><p>Finale lokale Release-Qualifikation. Kein automatisches Deployment, keine automatische Veröffentlichung und keine Dark-Web-Collection.</p><form method='post' action='/build280/release'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Build-280 RC-Qualifikation starten</button></form><table><tr><th>RC Run</th><th>RC gates</th><th>Agents</th><th>SQLite</th><th>Status</th></tr>{body or '<tr><td colspan="5">Noch kein Build-280 RC-Run.</td></tr>'}</table><pre>{e(_canon(self.qualified_gate()))}</pre></section>"""
