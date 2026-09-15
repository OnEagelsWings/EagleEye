from __future__ import annotations
import hashlib, html, json
from typing import Any
from eagleeye_pro.core.database import dumps,new_id,now_ts

def _text(v:Any,n:int=10000)->str:return str(v or '').replace('\x00','').strip()[:n]
def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v:Any)->str:return hashlib.sha256(_canon(v).encode()).hexdigest()
def _loads(v:Any,d:Any)->Any:
    try:return json.loads(v) if v else d
    except Exception:return d

DEP={'independent_primary','independent_secondary','derived','syndicated','self_report','unknown'}
STANCE={'supports','contradicts','context_only','neutral'}
STRENGTH={'weak','moderate','strong','direct'}

class Build258ClaimDependencyCounterEvidenceService:
    BUILD='258.0'
    def __init__(self,db:Any,audit:Any,*,verified_loop:Any,documents:Any,framing:Any,training:Any,opsec:Any,conversation:Any,actor:str='local-analyst')->None:
        self.db,self.audit=db,audit; self.verified_loop=verified_loop; self.documents=documents; self.framing=framing; self.training=training; self.opsec=opsec; self.conversation=conversation; self.actor=actor
        setattr(conversation,'_claims258',self)
    def _case(self,cid:str)->None:
        if not self.db.one('SELECT case_id FROM cases WHERE case_id=?',(cid,)):raise KeyError(cid)
    def _claim(self,cid:str,claim_id:str)->dict[str,Any]:
        r=self.db.one('SELECT * FROM verified_claims_229 WHERE verified_claim_id=? AND case_id=?',(claim_id,cid))
        if not r:raise KeyError(claim_id)
        return dict(r)
    def _event(self,cid:str,etype:str,otype:str,oid:str,payload:dict[str,Any],actor:str)->None:
        prev=self.db.one('SELECT event_hash FROM build258_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(cid,)); ph=(prev or {}).get('event_hash',''); eid,at=new_id('evt258'),now_ts(); eh=_hash({'previous':ph,'event_id':eid,'event_type':etype,'object_id':oid,'payload':payload,'actor':actor,'at':at})
        self.db.execute('INSERT INTO build258_events VALUES(?,?,?,?,?,?,?,?,?,?)',(eid,cid,etype,otype,oid,actor,dumps(payload),ph,eh,at))
    def add_lineage(self,*,case_id:str,verified_claim_id:str,source_ref:str,origin_key:str,publisher:str,dependency_class:str,parent_source_ref:str,stance:str,rationale:str,actor:str,confirmation:str)->dict[str,Any]:
        self._case(case_id); self._claim(case_id,verified_claim_id)
        if confirmation!=f'CLAIM SOURCE 258 {case_id} ANLEGEN':raise PermissionError('explicit approval required')
        if dependency_class not in DEP or stance not in STANCE:raise ValueError('invalid dependency/stance')
        if len(_text(source_ref,1000))<2 or len(_text(origin_key,1000))<2:raise ValueError('source_ref and origin_key required')
        lid,at=new_id('lin258'),now_ts(); p={'lineage_id':lid,'case_id':case_id,'verified_claim_id':verified_claim_id,'source_ref':_text(source_ref,1000),'origin_key':_text(origin_key,1000),'publisher':_text(publisher,500),'dependency_class':dependency_class,'parent_source_ref':_text(parent_source_ref,1000),'stance':stance,'rationale':_text(rationale,5000),'created_by':actor,'created_at':at}
        self.db.execute('INSERT INTO claim_source_lineage_258 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(lid,case_id,verified_claim_id,p['source_ref'],p['origin_key'],p['publisher'],dependency_class,p['parent_source_ref'],stance,p['rationale'],actor,at,_hash(p))); self._event(case_id,'lineage_added','verified_claim',verified_claim_id,{'lineage_id':lid,'dependency_class':dependency_class,'stance':stance},actor); return p
    def add_counterevidence(self,*,case_id:str,verified_claim_id:str,span_id:str,stance:str,strength:str,summary:str,actor:str,confirmation:str)->dict[str,Any]:
        self._case(case_id); self._claim(case_id,verified_claim_id)
        if confirmation!=f'COUNTEREVIDENCE 258 {case_id} ANLEGEN':raise PermissionError('explicit approval required')
        if stance not in {'contradicts','supports','context_only'} or strength not in STRENGTH:raise ValueError('invalid stance/strength')
        row=self.db.one('SELECT * FROM extraction_spans_255 WHERE span_id=? AND case_id=?',(span_id,case_id));
        if not row:raise KeyError(span_id)
        prov=self.documents.verify_span_provenance(span_id=span_id)
        if prov.get('status')!='ok':raise PermissionError('provenance failed')
        kid,at=new_id('ctr258'),now_ts(); p={'counterevidence_id':kid,'case_id':case_id,'verified_claim_id':verified_claim_id,'span_id':span_id,'stance':stance,'strength':strength,'summary':_text(summary,5000),'provenance_verified':True,'created_by':actor,'created_at':at}
        self.db.execute('INSERT INTO counterevidence_258 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(kid,case_id,verified_claim_id,span_id,stance,strength,p['summary'],1,actor,at,_hash(p))); self._event(case_id,'counterevidence_added','verified_claim',verified_claim_id,{'counterevidence_id':kid,'stance':stance,'strength':strength},actor); return p
    def analyze_claim(self,*,case_id:str,verified_claim_id:str)->dict[str,Any]:
        self._claim(case_id,verified_claim_id); rows=[dict(x) for x in self.db.all('SELECT * FROM claim_source_lineage_258 WHERE case_id=? AND verified_claim_id=? ORDER BY created_at',(case_id,verified_claim_id))]; ctr=[dict(x) for x in self.db.all('SELECT * FROM counterevidence_258 WHERE case_id=? AND verified_claim_id=?',(case_id,verified_claim_id))]
        independents={x['origin_key'] for x in rows if x['dependency_class'] in {'independent_primary','independent_secondary'}}; dependent=[x for x in rows if x['dependency_class'] in {'derived','syndicated','self_report'}]
        parent={x['source_ref']:x['parent_source_ref'] for x in rows if x['parent_source_ref']}; circular=False
        for start in list(parent):
            seen=set(); cur=start
            for _ in range(50):
                if cur in seen: circular=True; break
                seen.add(cur); cur=parent.get(cur,'')
                if not cur:break
            if circular:break
        contradictions=[x for x in rows if x['stance']=='contradicts']+[x for x in ctr if x['stance']=='contradicts']
        poisoning=sum(1 for x in rows if x['dependency_class']=='unknown' and ('mirror' in x['rationale'].casefold() or 'changed' in x['rationale'].casefold()))
        decision='needs_more_evidence'
        if circular or poisoning:decision='quarantine_dependency_review'
        elif contradictions:decision='challenged_counterevidence_present'
        elif len(independents)>=2:decision='independence_supported_review_required'
        return {'verified_claim_id':verified_claim_id,'independent_origin_count':len(independents),'dependent_source_count':len(dependent),'counterevidence_count':len(contradictions),'circular_dependency_detected':circular,'source_poisoning_signals':poisoning,'decision':decision,'automatic_claim_status_change':False}
    def review_analysis(self,*,case_id:str,verified_claim_id:str,decision:str,rationale:str,reviewer:str,confirmation:str)->dict[str,Any]:
        claim=self._claim(case_id,verified_claim_id)
        if confirmation!=f'CLAIM INDEPENDENCE REVIEW 258 {verified_claim_id} SPEICHERN':raise PermissionError('explicit approval required')
        if reviewer==claim.get('created_by'):raise PermissionError('independent reviewer required')
        if decision not in {'accepted_independence_assessment','challenged','needs_more_evidence','quarantine'}:raise ValueError('invalid review')
        a=self.analyze_claim(case_id=case_id,verified_claim_id=verified_claim_id); rid,at=new_id('rev258'),now_ts(); p={**a,'review_id':rid,'decision':decision,'rationale':_text(rationale,5000),'reviewer':reviewer,'reviewed_at':at}
        self.db.execute('INSERT INTO claim_independence_reviews_258 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(rid,case_id,verified_claim_id,decision,p['rationale'],a['independent_origin_count'],a['dependent_source_count'],a['counterevidence_count'],int(a['circular_dependency_detected']),reviewer,at,_hash(p))); self._event(case_id,'independence_reviewed','verified_claim',verified_claim_id,{'review_id':rid,'decision':decision},reviewer); return p
    def stage_training_candidate(self,*,case_id:str,review_id:str,actor:str,confirmation:str)->dict[str,Any]:
        if confirmation!=f'AI TRAINING CANDIDATE 258 {case_id} ANLEGEN':raise PermissionError('explicit approval required')
        rev=self.db.one('SELECT * FROM claim_independence_reviews_258 WHERE review_id=? AND case_id=?',(review_id,case_id));
        if not rev:raise KeyError(review_id)
        c=self._claim(case_id,rev['verified_claim_id']); instruction='Assess source independence, dependency, circularity and counter-evidence without converting repetition into independent corroboration.'; response=f"Claim: {c['claim_text']}\nReviewed decision: {rev['decision']}\nIndependent origins: {rev['independent_origin_count']}\nDependent sources: {rev['dependent_source_count']}\nCounter-evidence: {rev['counterevidence_count']}"
        ex=self.training.add_example(case_id=case_id,instruction=instruction,response=response,context={'build':'258.0','review_id':review_id,'human_reviewed':True,'source_content_is_instruction':False},evidence_refs=(),language='multi',source_type='build258_reviewed_claim_independence',source_ref=review_id,created_by=actor,confirmation=f'TRAINING EXAMPLE 228 {case_id} ANLEGEN')
        return {'example_id':ex['example_id'],'review_required':True,'automatic_approval':False}
    def record_ai_evaluation(self,*,case_id:str,benchmark_id:str,predicted_class:str,predicted_decision:str,model_or_ruleset:str,evaluated_by:str,confirmation:str)->dict[str,Any]:
        if confirmation!=f'AI BENCHMARK 258 {case_id} SPEICHERN':raise PermissionError('explicit approval required')
        b=self.db.one('SELECT * FROM ai_claim_benchmarks_258 WHERE benchmark_id=?',(benchmark_id,));
        if not b:raise KeyError(benchmark_id)
        cm=int(predicted_class==b['expected_class']); dm=int(predicted_decision==b['expected_decision']); eid,at=new_id('aie258'),now_ts(); p={'evaluation_id':eid,'case_id':case_id,'benchmark_id':benchmark_id,'predicted_class':predicted_class,'predicted_decision':predicted_decision,'passed':bool(cm and dm),'model_or_ruleset':model_or_ruleset,'evaluated_by':evaluated_by,'evaluated_at':at}
        self.db.execute('INSERT INTO ai_claim_evaluations_258 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(eid,case_id,benchmark_id,predicted_class,predicted_decision,cm,dm,int(p['passed']),model_or_ruleset,evaluated_by,at,_hash(p))); return p
    def source_catalog(self)->list[dict[str,Any]]:return [dict(x) for x in self.db.all('SELECT * FROM source_catalog_258 ORDER BY category,name')]
    def ai_metrics(self,case_id:str)->dict[str,Any]:
        curated=int(self.db.one("SELECT COUNT(*) n FROM ai_claim_benchmarks_258 WHERE review_status='curated_reviewed'")['n']); fam=int(self.db.one("SELECT COUNT(DISTINCT task_family) n FROM ai_claim_benchmarks_258 WHERE review_status='curated_reviewed'")['n']); ev=self.db.all('SELECT passed FROM ai_claim_evaluations_258 WHERE case_id=?',(case_id,)); return {'curated_reviewed_benchmarks':curated,'task_family_coverage':fam,'evaluations':len(ev),'pass_rate':round(sum(int(x['passed']) for x in ev)/len(ev),4) if ev else None,'auto_model_activation':False,'auto_adapter_activation':False}
    def opsec_metrics(self,case_id:str)->dict[str,Any]:
        total=int(self.db.one('SELECT COUNT(*) n FROM claim_opsec_controls_258')['n']); ver=int(self.db.one("SELECT COUNT(*) n FROM claim_opsec_controls_258 WHERE review_status='verified'")['n']); return {'verified_controls':ver,'control_coverage':ver/max(1,total),'autonomous_bulk_leak_ingestion':0,'access_control_bypass':0,'automatic_external_navigation':0}
    def capabilities(self)->dict[str,Any]:return {'counterevidence_ledger':True,'source_dependency_graph':True,'circularity_detection':True,'independence_review':True,'curated_clickable_source_catalog':True,'automatic_claim_verification':False,'autonomous_bulk_leak_ingestion':False,'access_control_bypass':False}
    def crosscut_release_gate(self,*,case_id:str)->dict[str,Any]:
        caps=self.capabilities(); ai=self.ai_metrics(case_id); op=self.opsec_metrics(case_id); parent=self.framing.crosscut_release_gate(case_id=case_id); main=all([caps['counterevidence_ledger'],caps['source_dependency_graph'],caps['circularity_detection'],caps['independence_review'],caps['curated_clickable_source_catalog']]) and not caps['automatic_claim_verification']; aiready=ai['curated_reviewed_benchmarks']>=12 and ai['task_family_coverage']>=7 and not ai['auto_model_activation']; opready=op['verified_controls']>=12 and op['control_coverage']==1 and op['autonomous_bulk_leak_ingestion']==0 and op['access_control_bypass']==0; return {'build':self.BUILD,'main_goal_ready':main,'ai_delta_ready':aiready,'opsec_delta_ready':opready,'parent_257_gate_ready':bool(parent.get('release_ready')),'release_ready':bool(main and aiready and opready and parent.get('release_ready')),'capabilities':caps}
    def render_workspace_panel(self,*,case_id:str,csrf:str='')->str:
        esc=html.escape; claims=[dict(x) for x in self.db.all('SELECT verified_claim_id,claim_text,status FROM verified_claims_229 WHERE case_id=? ORDER BY updated_at DESC LIMIT 100',(case_id,))]; spans=[dict(x) for x in self.db.all('SELECT span_id,page_number,text_content FROM extraction_spans_255 WHERE case_id=? ORDER BY created_at DESC LIMIT 100',(case_id,))]; co=''.join(f"<option value='{esc(x['verified_claim_id'])}'>{esc(_text(x['claim_text'],120))}</option>" for x in claims); so=''.join(f"<option value='{esc(x['span_id'])}'>S.{x['page_number']} · {esc(_text(x['text_content'],100))}</option>" for x in spans)
        grouped={}
        for s in self.source_catalog():grouped.setdefault(s['category'],[]).append(s)
        cards=''.join("<div class='card'><h3>"+esc(cat)+"</h3>"+''.join(f"<p><a class='button ghost' target='_blank' rel='noopener noreferrer' href='{esc(s['url'],quote=True)}'>{esc(s['name'])} ↗</a><br><span class='muted'>{esc(s['description'])}</span></p>" for s in arr)+"</div>" for cat,arr in grouped.items())
        ai=self.ai_metrics(case_id); op=self.opsec_metrics(case_id); gate=self.crosscut_release_gate(case_id=case_id)
        return f"""<section class='cockpit244'><h2>Claim Integrity + Source Independence · Build 258</h2><div class='notice'>Build 258 trennt Wiederholung von unabhängiger Bestätigung, hält Gegenbelege sichtbar und erkennt zirkuläre Quellenketten. Eine 258-Analyse ändert den Build-229-Claimstatus niemals automatisch.</div><div class='notice warn'>Externe Links sind ausschließlich <b>user-initiiert</b> und mit <code>noopener noreferrer</code> versehen. Kein Crawl, kein Bulk-Download, kein Login-/CAPTCHA-/Zugriffsschutz-Bypass.</div><div class='grid'><div class='card'><h3>Quellenabhängigkeit erfassen</h3><form method='post' action='/build258/lineage'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><select name='verified_claim_id' required>{co}</select><input name='source_ref' placeholder='Source-/Evidence-Ref' required><input name='origin_key' placeholder='Origin-Key / ursprüngliche Quelle' required><input name='publisher' placeholder='Publisher'><select name='dependency_class'>{''.join(f'<option>{x}</option>' for x in sorted(DEP))}</select><input name='parent_source_ref' placeholder='Parent Source Ref (optional)'><select name='stance'>{''.join(f'<option>{x}</option>' for x in sorted(STANCE))}</select><textarea name='rationale' placeholder='Warum unabhängig/abhängig?' required></textarea><button>Lineage speichern</button></form></div><div class='card'><h3>Gegenbeleg erfassen</h3><form method='post' action='/build258/counter'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><select name='verified_claim_id' required>{co}</select><select name='span_id' required>{so}</select><select name='stance'><option>contradicts</option><option>supports</option><option>context_only</option></select><select name='strength'>{''.join(f'<option>{x}</option>' for x in sorted(STRENGTH))}</select><textarea name='summary' required placeholder='Was trägt der Beleg tatsächlich?'></textarea><button>Evidence-bound speichern</button></form></div><div class='card'><h3>Unabhängigkeitsreview</h3><form method='post' action='/build258/review'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><select name='verified_claim_id' required>{co}</select><select name='decision'><option>accepted_independence_assessment</option><option>challenged</option><option>needs_more_evidence</option><option>quarantine</option></select><textarea name='rationale' required></textarea><button>Vier-Augen-Review</button></form></div></div><h2>Klickbare Leak-, Dokument- & Quellenplattformen</h2><div class='grid'>{cards}</div><div class='grid'><div class='card'><h3>AI-Delta 258</h3><p><b>{ai['curated_reviewed_benchmarks']}</b> reviewte Benchmarks · {ai['task_family_coverage']} Familien.</p><p>Source dependency, circularity, counter-evidence, source poisoning, abstention und Leak-Handling.</p></div><div class='card'><h3>OPSEC-Delta 258</h3><p>{op['verified_controls']} Controls · Coverage {op['control_coverage']:.0%}</p><p>Bulk-Leak-Ingestion: 0 · Bypass: 0 · Auto-Navigation: 0</p></div><div class='card'><h3>Release Gate</h3><p>Main: <b>{'PASS' if gate['main_goal_ready'] else 'FAIL'}</b><br>AI: <b>{'PASS' if gate['ai_delta_ready'] else 'FAIL'}</b><br>OPSEC: <b>{'PASS' if gate['opsec_delta_ready'] else 'FAIL'}</b><br>Parent 257: <b>{'PASS' if gate['parent_257_gate_ready'] else 'FAIL'}</b></p><p><b>{'RELEASE READY' if gate['release_ready'] else 'BLOCKED'}</b></p></div></div></section>"""
