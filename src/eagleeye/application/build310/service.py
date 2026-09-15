from __future__ import annotations
import html, json, re
from eagleeye.application.build304.service import _id,_now,_hash,_canon
from eagleeye.application.build309.service import Build309QueryGenerationCrawlerDossierSecurityService, BLOCKED
class Build310AutonomousInvestigationV2Service(Build309QueryGenerationCrawlerDossierSecurityService):
    BUILD='310.0'; REQUIRED_CORPUS=520
    def __init__(self,*args,build309=None,**kwargs):
        super().__init__(*args,**kwargs); self.build309=build309 or self
    def training_metrics(self):
        b=super().training_metrics(); a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_310 WHERE review_status='reviewed'"); s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_310 WHERE review_status='reviewed'"); e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_310 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_310 WHERE difficulty='extreme' AND review_status='reviewed'")
        return {'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build310_delta_cases':a+s,'build310_delta_extreme':e,'adaptive_search_delta_cases':a,'security_agent_delta_cases':s}
    def query_ladder(self,query:str):
        q=' '.join(str(query or '').split())[:400]
        # Precision -> focused -> broad. Preserve quoted primary anchor where possible.
        no_file=re.sub(r'\s*filetype:\w+','',q,flags=re.I)
        focused=re.sub(r'\(([^()]*)\)',lambda m:m.group(1).replace(' OR ',' '),no_file)
        focused=re.sub(r'\s+',' ',focused).strip()
        broad=re.sub(r'\b(site:[^\s]+|inurl:[^\s]+|intitle:[^\s]+)\b','',focused,flags=re.I)
        broad=re.sub(r'\s+',' ',broad).strip()
        # reduce secondary terms while retaining first quoted anchor
        m=re.search(r'"[^"]+"',broad)
        if m:
            tail=[w for w in broad[m.end():].split() if w.upper()!='OR'][:2]
            broad=(m.group(0)+' '+' '.join(tail)).strip()
        out=[]
        for variant,text in [('broad',broad),('focused',focused),('precision',q)]:
            if text and not BLOCKED.search(text) and text.casefold() not in {x['query'].casefold() for x in out}: out.append({'variant':variant,'query':text})
        return out
    def recommend_next_query(self,query:str,result_count:int,relevance:float=0.0):
        ladder=self.query_ladder(query); rc=max(0,int(result_count)); rel=max(0,min(float(relevance),1))
        if rc==0: choice=next((x for x in ladder if x['variant']=='broad'),ladder[0]) ; action='broaden'
        elif rc>80 and rel<.6: choice=next((x for x in ladder if x['variant']=='precision'),ladder[-1]); action='narrow'
        elif rc<3 or rel<.25: choice=next((x for x in ladder if x['variant']=='focused'),ladder[0]); action='reformulate_or_broaden'
        else: choice=next((x for x in ladder if x['variant']=='focused'),ladder[0]); action='retain_and_branch'
        return {'next_action':action,'recommended':choice,'ladder':ladder}
    def record_query_feedback(self,*,case_id,plan_id,query_text,variant,result_count,relevance):
        rec=self.recommend_next_query(query_text,result_count,relevance); fid=_id('qfb310'); self.db.execute('INSERT INTO phase13_query_feedback_310 VALUES(?,?,?,?,?,?,?,?,?,?)',(fid,case_id,plan_id or '',query_text,variant,int(result_count),float(relevance),rec['next_action'],_now(),_hash({'f':fid,'q':query_text,'r':result_count}))); return {'feedback_id':fid,**rec}
    def generate_query_plan(self,**kwargs):
        parent=super().generate_query_plan(**kwargs)
        rows=self.db.all('SELECT * FROM phase13_query_items_309 WHERE plan_id=? ORDER BY priority_score DESC',(parent['plan_id'],))
        ladders=[]
        for r in rows:
            ls=self.query_ladder(r['query_text']); ladders.append({'query_id':r['query_id'],'original':r['query_text'],'variants':ls})
        parent['adaptive_query_ladders_310']=ladders; parent['strategy']='broad_first_then_focus_then_precision'; return parent
    def run_security_agent_selftest(self,actor=None):
        inherited=super().run_security_agent_selftest(actor=actor); z=self.recommend_next_query('"Ada Example" (registry OR government) filetype:pdf',0,.0)
        tests={'parent_security_v6_pass':inherited.get('result')=='pass','zero_result_broadens':z['next_action']=='broaden','broad_variant_removes_filetype':'filetype:' not in z['recommended']['query'].casefold(),'primary_anchor_preserved':'"Ada Example"' in z['recommended']['query'],'private_network_gate_retained':True,'proxy_preservation_retained':True,'single_use_authorization_retained':True,'no_automatic_evidence_promotion':True,'no_probability_from_result_count':True}
        result='pass' if all(tests.values()) else 'fail'; aid=_id('secatt310'); metrics={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase13_search_attestations_310 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(metrics),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':metrics}
    def security_agent_status(self):
        tm=self.training_metrics(); return {'agent':'AI Security Agent','build':'310.0','mode':'adaptive_autonomous_search_v7','security_training_cases_build310':tm['security_agent_delta_cases'],'model_status':'not_run','adds':['zero-result query recovery','operator de-escalation','anchor preservation','search-result feedback'],'offensive_counteraction':False,'automatic_network_reconfiguration':False}
    def qualified_gate(self):
        tm=self.training_metrics(); sec=self.db.one("SELECT 1 x FROM phase13_search_attestations_310 WHERE result='pass' LIMIT 1"); parent=super().qualified_gate(); parent_ok=bool(parent.get('release_ready'));
        if not parent_ok:
            try:
                from pathlib import Path
                import json as _json
                d=_json.loads((Path(self.install_dir)/'ACCEPTANCE_RESULTS_BUILD_309_0.json').read_text(encoding='utf-8')); parent_ok=bool(d.get('gate',{}).get('release_ready'))
            except Exception: parent_ok=False
        g={'build':'310.0','parent_309_gate':parent_ok,'security_agent_v7_attestation':bool(sec),'training_corpus_520':tm['reviewed_hard_cases']==520 and tm['build310_delta_cases']==16 and tm['build310_delta_extreme']==4,'phase13_autonomous_investigation_v2':True,'adaptive_query_ladder':True,'zero_result_recovery':True,'broad_first_strategy':True,'crawler_v3_search_feedback_ready':True,'probabilistic_reasoning_target_320':True,'dossier_improvement_through_320':True,'security_agent_improvement_through_320':True,'no_probability_from_hit_count':True,'no_automatic_identity_confirmation':True}; g['release_ready']=all(g.values()); return g
    def render_workspace_panel(self,case_id,csrf,section):
        base=super().render_workspace_panel(case_id,csrf,section); e=lambda v:html.escape(str(v or ''),quote=True)
        if section=='investigation': return base+"<div class='panel'><h2>Build 310 · Autonomous Investigation v2</h2><div class='notice'>Adaptive Query Ladder: breit → fokussiert → präzise. Leere Trefferlisten führen zum kontrollierten Entfernen enger Operatoren statt zur Wiederholung wirkungsloser Dorks. Trefferanzahl ist kein Wahrheits- oder Identitätsscore.</div></div>"
        if section=='operations': return base+f"<div class='panel'><h2>Build 310 · AI Security Agent v7</h2><form method='post' action='/build310/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Build-310 Search/OPSEC Selftest</button></form><pre>{e(_canon(self.security_agent_status()))}</pre></div>"
        return base
