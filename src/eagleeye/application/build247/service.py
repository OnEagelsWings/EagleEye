from __future__ import annotations
import hashlib, html, json, os
from typing import Any
from eagleeye_pro.core.database import dumps, new_id, now_ts

def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v:Any)->str:return hashlib.sha256(v if isinstance(v,bytes) else _canon(v).encode('utf-8')).hexdigest()
def _text(v:Any,n:int=5000)->str:return str(v or '').replace('\x00','').strip()[:n]
def _loads(v:Any,d:Any)->Any:
    try:return json.loads(v) if v else d
    except Exception:return d

def _ram()->tuple[int,int]:
    try:
        import psutil
        m=psutil.virtual_memory(); return int(m.total/1048576),int(m.available/1048576)
    except Exception: pass
    try:
        pages=os.sysconf('SC_PHYS_PAGES'); size=os.sysconf('SC_PAGE_SIZE'); av=os.sysconf('SC_AVPHYS_PAGES')
        return int(pages*size/1048576),int(av*size/1048576)
    except Exception:return 0,0

class Build247ProductionAIRuntimeService:
    BUILD='247.0'
    TASKS={'investigation_dialogue','source_assessment','evidence_analysis','entity_resolution','translation','opsec','source_routing','contradiction_analysis','embeddings','reranking'}
    REVIEW={'approved','rejected'}
    ROUTE_REVIEW={'good_route','bad_route','needs_context'}
    def __init__(self,db,audit,*,local_ai,legacy_runtime,orchestration,opsec,sentinel,training,conversation,co_ai,actor='local-analyst'):
        self.db,self.audit=db,audit; self.local_ai,self.legacy_runtime=local_ai,legacy_runtime; self.orchestration,self.opsec,self.sentinel=orchestration,opsec,sentinel; self.training,self.conversation,self.co_ai,self.actor=training,conversation,co_ai,actor
        conversation._runtime247=self; co_ai._runtime247=self; sentinel._runtime247=self
    def _case(self,cid):
        if not self.db.one('SELECT case_id FROM cases WHERE case_id=?',(cid,)):raise KeyError(cid)
    def _event(self,cid,typ,obj,oid,payload,actor):
        prev=self.db.one('SELECT event_hash FROM ai_runtime_events_247 WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(cid,)); ph=(prev or {}).get('event_hash',''); eid,now=new_id('airtevt247'),now_ts(); eh=_hash({'previous':ph,'event':eid,'type':typ,'object':oid,'payload':payload,'actor':actor,'at':now}); self.db.execute('INSERT INTO ai_runtime_events_247 VALUES(?,?,?,?,?,?,?,?,?,?)',(eid,cid,typ,obj,oid,actor,dumps(payload),ph,eh,now))
        try:self.audit.log('build247_'+typ,obj,oid,cid,payload)
        except Exception:pass
    def sync_local_models(self,*,case_id,actor,confirmation):
        self._case(case_id)
        if confirmation!=f'AI MODELS 247 {case_id} SYNCHRONISIEREN':raise PermissionError('explicit approval required')
        rows=self.db.all('''SELECT s.* FROM ollama_model_snapshots_215 s JOIN (SELECT model_name,MAX(rowid) rid FROM ollama_model_snapshots_215 WHERE case_id=? GROUP BY model_name) x ON s.rowid=x.rid ORDER BY s.model_name''',(case_id,)); created=[]
        for r in rows:
            if self.db.one('SELECT model_id FROM ai_models_247 WHERE case_id=? AND model_name=? AND model_digest=?',(case_id,r['model_name'],r['digest'])):continue
            details=_loads(r.get('details_json'),{}); caps=_loads(r.get('capabilities_json'),['completion']); langs=['*']; ctx=int((details.get('model_info') or {}).get('general.context_length') or 8192); size=int(r.get('size_bytes') or 0); ram=max(1024,int(size/1048576*1.15)) if size else 4096; mid,now=new_id('aimodel247'),now_ts(); payload={'model_id':mid,'case_id':case_id,'model_name':r['model_name'],'digest':r['digest'],'backend':'ollama_local','capabilities':caps,'languages':langs,'context_window':ctx,'ram_mb':ram,'vram_mb':0}; self.db.execute('INSERT INTO ai_models_247 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(mid,case_id,r['model_name'],r['digest'],r['digest'] or r['model_name'],'ollama_local',dumps(caps),dumps(langs),ctx,ram,0,'candidate',actor,now,_hash(payload))); created.append(mid)
        self._event(case_id,'models_synced','case',case_id,{'created':len(created),'network_action':False},actor); return {'case_id':case_id,'created_model_ids':created,'count':len(created),'network_action':False,'review_required':True}
    def register_model(self,*,case_id,model_name,model_digest,version_ref,backend,capabilities,languages,context_window,ram_mb,vram_mb,actor,confirmation):
        self._case(case_id)
        if confirmation!=f'AI MODEL 247 {case_id} REGISTRIEREN':raise PermissionError('explicit approval required')
        if backend not in {'ollama_local','llama_cpp_local','sentence_transformers_local','rules_local'}:raise ValueError('only local/offline backends supported')
        if not _text(model_name,200) or len(_text(model_digest,256))<8:raise ValueError('model identity/digest required')
        mid,now=new_id('aimodel247'),now_ts(); payload={'model_id':mid,'case_id':case_id,'model_name':_text(model_name,200),'digest':_text(model_digest,256),'version_ref':_text(version_ref,300),'backend':backend,'capabilities':list(capabilities),'languages':list(languages),'context_window':max(1024,int(context_window)),'ram_mb':max(0,int(ram_mb)),'vram_mb':max(0,int(vram_mb))}; self.db.execute('INSERT INTO ai_models_247 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(mid,case_id,payload['model_name'],payload['digest'],payload['version_ref'],backend,dumps(payload['capabilities']),dumps(payload['languages']),payload['context_window'],payload['ram_mb'],payload['vram_mb'],'candidate',actor,now,_hash(payload))); return self.model(mid)
    def model(self,mid):
        r=self.db.one('SELECT * FROM ai_models_247 WHERE model_id=?',(mid,));
        if not r:raise KeyError(mid)
        d=dict(r); d['capabilities']=_loads(d['capabilities_json'],[]); d['languages']=_loads(d['languages_json'],[]); rv=self.db.one('SELECT * FROM ai_model_reviews_247 WHERE model_id=?',(mid,)); d['review']=dict(rv) if rv else None; h=self.db.one('SELECT * FROM ai_model_health_247 WHERE model_id=? ORDER BY observed_at DESC,rowid DESC LIMIT 1',(mid,)); d['health']=dict(h) if h else None; return d
    def review_model(self,*,model_id,decision,rationale,reviewer,confirmation):
        m=self.model(model_id)
        if confirmation!=f'AI MODEL 247 {model_id} PRUEFEN':raise PermissionError('explicit approval required')
        if reviewer==m['created_by']:raise PermissionError('independent reviewer required')
        if m['review']:raise ValueError('already reviewed')
        if decision not in self.REVIEW or len(_text(rationale))<20:raise ValueError('invalid review')
        rid,now=new_id('aimodelrev247'),now_ts(); self.db.execute('INSERT INTO ai_model_reviews_247 VALUES(?,?,?,?,?,?,?,?)',(rid,model_id,m['case_id'],decision,_text(rationale,3000),reviewer,now,_hash({'review':rid,'decision':decision}))); return dict(self.db.one('SELECT * FROM ai_model_reviews_247 WHERE review_id=?',(rid,)))
    def resource_snapshot(self,*,case_id,actor='runtime-247'):
        self._case(case_id); total,avail=_ram(); gpu={'backend':'cpu','devices':[]}
        try:gpu=self.legacy_runtime.detect_gpu()
        except Exception:pass
        sid,now=new_id('aires247'),now_ts(); payload={'snapshot_id':sid,'case_id':case_id,'cpu_count':os.cpu_count() or 1,'ram_total_mb':total,'ram_available_mb':avail,'gpu':gpu}; self.db.execute('INSERT INTO ai_resource_snapshots_247 VALUES(?,?,?,?,?,?,?,?,?,?)',(sid,case_id,payload['cpu_count'],total,avail,dumps(gpu),gpu.get('backend','cpu'),actor,now,_hash(payload))); return payload
    def record_health(self,*,model_id,status,latency_ms,error_rate,tokens_per_second,detail,actor,confirmation):
        m=self.model(model_id)
        if confirmation!=f'AI HEALTH 247 {model_id} SPEICHERN':raise PermissionError('explicit approval required')
        if status not in {'healthy','degraded','unhealthy'}:raise ValueError('invalid health status')
        hid,now=new_id('aihealth247'),now_ts(); payload={'health_id':hid,'model_id':model_id,'status':status,'latency_ms':max(0,float(latency_ms)),'error_rate':max(0,min(1,float(error_rate))),'tokens_per_second':max(0,float(tokens_per_second)),'detail':dict(detail or {})}; self.db.execute('INSERT INTO ai_model_health_247 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(hid,model_id,m['case_id'],status,payload['latency_ms'],payload['error_rate'],payload['tokens_per_second'],dumps(payload['detail']),actor,now,_hash(payload))); return payload
    def propose_policy(self,*,case_id,task_type,language,min_context,max_input_tokens,max_output_tokens,max_ram_mb,max_vram_mb,latency_class,rationale,actor,confirmation):
        self._case(case_id)
        if confirmation!=f'AI POLICY 247 {case_id} ANLEGEN':raise PermissionError('explicit approval required')
        if task_type not in self.TASKS or latency_class not in {'interactive','standard','background'}:raise ValueError('invalid policy')
        if len(_text(rationale))<20:raise ValueError('rationale too short')
        pid,now=new_id('aipolicy247'),now_ts(); vals=(pid,case_id,task_type,_text(language,20) or '*',max(1024,int(min_context)),max(256,int(max_input_tokens)),max(64,int(max_output_tokens)),max(0,int(max_ram_mb)),max(0,int(max_vram_mb)),latency_class,1,_text(rationale,3000),actor,now,''); payload={'policy_id':pid,'case_id':case_id,'task_type':task_type,'language':language,'budgets':vals[4:10],'local_only':True}; vals=vals[:-1]+(_hash(payload),); self.db.execute('INSERT INTO ai_routing_policies_247 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',vals); return dict(self.db.one('SELECT * FROM ai_routing_policies_247 WHERE policy_id=?',(pid,)))
    def review_policy(self,*,policy_id,decision,rationale,reviewer,confirmation):
        p=self.db.one('SELECT * FROM ai_routing_policies_247 WHERE policy_id=?',(policy_id,));
        if not p:raise KeyError(policy_id)
        if confirmation!=f'AI POLICY 247 {policy_id} PRUEFEN':raise PermissionError('explicit approval required')
        if reviewer==p['created_by']:raise PermissionError('independent reviewer required')
        if decision not in self.REVIEW or len(_text(rationale))<20:raise ValueError('invalid review')
        rid,now=new_id('aipolicyrev247'),now_ts(); self.db.execute('INSERT INTO ai_policy_reviews_247 VALUES(?,?,?,?,?,?,?,?)',(rid,policy_id,p['case_id'],decision,_text(rationale,3000),reviewer,now,_hash({'review':rid,'decision':decision}))); return dict(self.db.one('SELECT * FROM ai_policy_reviews_247 WHERE review_id=?',(rid,)))
    def activate_policy(self,*,policy_id,actor,confirmation):
        p=self.db.one('SELECT * FROM ai_routing_policies_247 WHERE policy_id=?',(policy_id,)); rv=self.db.one('SELECT * FROM ai_policy_reviews_247 WHERE policy_id=?',(policy_id,))
        if not p:raise KeyError(policy_id)
        if confirmation!=f'AI POLICY 247 {policy_id} AKTIVIEREN':raise PermissionError('explicit approval required')
        if not rv or rv['decision']!='approved':raise PermissionError('approved independent review required')
        aid,now=new_id('aipolicyact247'),now_ts(); self.db.execute('INSERT INTO ai_policy_activations_247 VALUES(?,?,?,?,?,?)',(aid,policy_id,p['case_id'],actor,now,_hash({'activation':aid,'policy':policy_id}))); return {'activation_id':aid,'policy_id':policy_id,'automatic_activation':False}
    def _policy(self,cid,task,lang):
        return self.db.one('''SELECT p.* FROM ai_policy_activations_247 a JOIN ai_routing_policies_247 p ON p.policy_id=a.policy_id WHERE a.case_id=? AND p.task_type=? AND p.language IN (?, '*') ORDER BY a.activated_at DESC LIMIT 1''',(cid,task,lang))
    def route(self,*,case_id,task_type,language,requested_context,input_tokens,output_tokens,actor):
        self._case(case_id)
        if task_type not in self.TASKS:raise ValueError('unsupported task type')
        resources=self.resource_snapshot(case_id=case_id,actor=actor); policy=self._policy(case_id,task_type,language); minctx=max(int(requested_context),int(policy['min_context']) if policy else 2048); maxin=int(policy['max_input_tokens']) if policy else 16000; maxout=int(policy['max_output_tokens']) if policy else 4096
        if int(input_tokens)>maxin or int(output_tokens)>maxout: status='budget_blocked'; selected=None; reason=['token budget exceeded']
        else:
            state=self.opsec.runtime_state(case_id); reason=['local-only runtime','approved model review required','health/resource fit']; selected=None; candidates=[]
            for row in self.db.all('SELECT * FROM ai_models_247 WHERE case_id=? ORDER BY created_at DESC',(case_id,)):
                m=self.model(row['model_id']); rv=m['review']; h=m['health']; caps=set(m['capabilities']); langs=set(m['languages']);
                if not rv or rv['decision']!='approved' or (h and h['status']=='unhealthy'):continue
                if task_type not in caps and 'general' not in caps and 'completion' not in caps:continue
                if language not in langs and '*' not in langs:continue
                if int(m['context_window'])<minctx:continue
                if policy and int(policy['max_ram_mb']) and int(m['ram_mb'])>int(policy['max_ram_mb']):continue
                if int(m['ram_mb']) and resources['ram_available_mb'] and int(m['ram_mb'])>resources['ram_available_mb']:continue
                score=(2 if h and h['status']=='healthy' else 1)+(float(h['tokens_per_second'])/1000 if h else 0)-float(h['error_rate'] if h else 0); candidates.append((score,m))
            if candidates:selected=max(candidates,key=lambda x:x[0])[1]; status='selected'; reason.append('deterministic best-fit local model')
            else:status='rules_only_fallback'; reason.append('no approved healthy resource-fit local model; no external fallback')
            if state.get('external_step_gate'):reason.append('OPSEC external-step gate active; local-only route retained')
        did,now=new_id('airoute247'),now_ts(); name=selected['model_name'] if selected else 'rules-only-fallback'; mid=selected['model_id'] if selected else ''; backend=selected['backend'] if selected else 'rules_local'; opsec=self.sentinel.opsec_state(case_id).get('risk_level','unknown') if hasattr(self.sentinel,'opsec_state') else 'unknown'; payload={'decision_id':did,'case_id':case_id,'task_type':task_type,'language':language,'selected_model':name,'status':status,'rationale':reason}; self.db.execute('INSERT INTO ai_route_decisions_247 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(did,case_id,task_type,_text(language,20),int(requested_context),int(input_tokens),int(output_tokens),mid,name,backend,status,dumps(reason),resources['snapshot_id'],opsec,actor,now,_hash(payload))); self._event(case_id,'route_decided','ai_route',did,{'status':status,'model':name,'backend':backend,'automatic_external_fallback':False},actor); return {**payload,'selected_model_id':mid,'backend':backend,'resource_snapshot':resources,'opsec_level':opsec,'automatic_external_fallback':False,'ready':status=='selected'}
    def apply_to_local_ai(self,*,decision_id,actor,confirmation):
        d=self.db.one('SELECT * FROM ai_route_decisions_247 WHERE decision_id=?',(decision_id,));
        if not d:raise KeyError(decision_id)
        if confirmation!=f'AI ROUTE 247 {decision_id} ANWENDEN':raise PermissionError('explicit approval required')
        if d['route_status']!='selected' or d['backend']!='ollama_local':raise PermissionError('route is not an approved local Ollama selection')
        latest={x['model_name'] for x in self.local_ai._latest_models(d['case_id'])};
        if d['selected_model_name'] not in latest:raise PermissionError('selected model not present in latest local model snapshot')
        cfg=self.local_ai.ensure_case_config(case_id=d['case_id'],actor=actor); out=self.local_ai.select_model(case_id=d['case_id'],model_name=d['selected_model_name'],context_window=max(2048,int(d['requested_context'])),temperature=float(cfg.get('temperature') or .15),actor=actor,confirmation=f"OLLAMA MODEL 215 {d['case_id']} AUSWAEHLEN"); self._event(d['case_id'],'route_applied','ai_route',decision_id,{'model':d['selected_model_name'],'automatic':False},actor); return {**out,'route_decision_id':decision_id,'automatic_activation':False}
    def review_route(self,*,decision_id,decision,rationale,reviewer,confirmation):
        d=self.db.one('SELECT * FROM ai_route_decisions_247 WHERE decision_id=?',(decision_id,));
        if not d:raise KeyError(decision_id)
        if confirmation!=f'AI ROUTE 247 {decision_id} PRUEFEN':raise PermissionError('explicit approval required')
        if reviewer==d['created_by']:raise PermissionError('independent reviewer required')
        if decision not in self.ROUTE_REVIEW or len(_text(rationale))<20:raise ValueError('invalid review')
        rid,now=new_id('airouterev247'),now_ts(); self.db.execute('INSERT INTO ai_route_reviews_247 VALUES(?,?,?,?,?,?,?,?)',(rid,decision_id,d['case_id'],decision,_text(rationale,3000),reviewer,now,_hash({'review':rid,'decision':decision}))); return dict(self.db.one('SELECT * FROM ai_route_reviews_247 WHERE review_id=?',(rid,)))
    def stage_training(self,*,case_id,actor,limit=50,confirmation):
        if confirmation!=f'AI RUNTIME TRAINING 247 {case_id} VORBEREITEN':raise PermissionError('explicit approval required')
        rows=self.db.all('''SELECT d.*,r.decision review_decision,r.rationale FROM ai_route_decisions_247 d JOIN ai_route_reviews_247 r ON r.decision_id=d.decision_id LEFT JOIN ai_training_links_247 l ON l.decision_id=d.decision_id WHERE d.case_id=? AND l.decision_id IS NULL ORDER BY r.reviewed_at LIMIT ?''',(case_id,max(1,min(200,int(limit))))); ids=[]
        for r in rows:
            context={'task_type':r['task_type'],'language':r['language'],'requested_context':r['requested_context'],'input_tokens':r['input_tokens'],'output_tokens':r['output_tokens'],'selected_model':r['selected_model_name'],'backend':r['backend'],'route_status':r['route_status'],'opsec_level':r['opsec_level'],'review_decision':r['review_decision'],'safe_boundary':'local_only_no_silent_external_fallback'}; inst='Waehle fuer die fallbezogene KI-Aufgabe ein geeignetes, lokal freigegebenes Modell. Beruecksichtige Sprache, Kontext, Ressourcen, Health, OPSEC und Tokenbudget. Nutze keinen stillen externen Fallback.'; resp=f"Review: {r['review_decision']}. {r['rationale']}"; ex=self.training.add_example(case_id=case_id,instruction=inst,response=resp,context=context,source_type=('opsec_runtime_routing_247' if r['task_type']=='opsec' else 'production_ai_runtime_247'),source_ref=r['decision_id'],created_by=actor,confirmation=f'TRAINING EXAMPLE 228 {case_id} ANLEGEN'); lid,now=new_id('airtrain247'),now_ts(); self.db.execute('INSERT INTO ai_training_links_247 VALUES(?,?,?,?,?,?,?)',(lid,case_id,r['decision_id'],ex['example_id'],actor,now,_hash({'link':lid,'example':ex['example_id']}))); ids.append(ex['example_id'])
        return {'case_id':case_id,'created':len(ids),'training_example_ids':ids,'review_status':'pending','automatic_model_or_policy_activation':False}
    def context(self,case_id):
        self._case(case_id); models=[]
        for r in self.db.all('SELECT model_id FROM ai_models_247 WHERE case_id=? ORDER BY created_at DESC LIMIT 30',(case_id,)): models.append(self.model(r['model_id']))
        routes=self.db.all('SELECT * FROM ai_route_decisions_247 WHERE case_id=? ORDER BY created_at DESC LIMIT 20',(case_id,)); return {'production_ai_runtime_247':{'models':models,'recent_routes':[dict(x) for x in routes],'rules':['Only independently approved local/offline models are routable.','No silent external-provider fallback.','OPSEC and resource limits remain binding.','Routing decisions are not evidence and do not change investigative truth status.']}}
    def dashboard(self,case_id):
        self._case(case_id); count=lambda sql:int(self.db.one(sql,(case_id,))['n']); return {'build':self.BUILD,'models':count('SELECT COUNT(*) n FROM ai_models_247 WHERE case_id=?'),'approved_models':count("SELECT COUNT(*) n FROM ai_models_247 m JOIN ai_model_reviews_247 r ON r.model_id=m.model_id WHERE m.case_id=? AND r.decision='approved'"),'routes':count('SELECT COUNT(*) n FROM ai_route_decisions_247 WHERE case_id=?'),'training':count('SELECT COUNT(*) n FROM ai_training_links_247 WHERE case_id=?')}
    def render_workspace_panel(self,*,case_id,csrf):
        d=self.dashboard(case_id); e=lambda x:html.escape(str(x or ''),quote=True)
        return f"""<section class='card' id='build247'><h2>Production AI Runtime · Build 247</h2><p>Task-/sprachbezogenes lokales Modellrouting mit Ressourcen-, Health-, Budget- und OPSEC-Gates. Kein stiller externer Fallback.</p><div class='metrics'><div class='metric'><div class='label'>Models</div><div class='value'>{d['models']}</div></div><div class='metric'><div class='label'>Approved</div><div class='value'>{d['approved_models']}</div></div><div class='metric'><div class='label'>Routes</div><div class='value'>{d['routes']}</div></div><div class='metric'><div class='label'>Training</div><div class='value'>{d['training']}</div></div></div><div class='grid'><div class='card'><h3>Lokale Modelle</h3><form method='post' action='/build247/sync'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Verifizierte lokale Modelle uebernehmen</button></form><p class='muted'>Nur aus bereits lokal beobachteten Build-215-Snapshots; kein Netzaufruf.</p></div><div class='card'><h3>Routing testen</h3><form method='post' action='/build247/route'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><select name='task_type'><option>investigation_dialogue</option><option>evidence_analysis</option><option>entity_resolution</option><option>translation</option><option>opsec</option><option>source_routing</option></select><input name='language' value='de'><input name='requested_context' type='number' value='8192'><input name='input_tokens' type='number' value='4000'><input name='output_tokens' type='number' value='1500'><button>Route berechnen</button></form></div><div class='card'><h3>Training</h3><form method='post' action='/build247/training'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Reviewte Routing-Entscheidungen vorbereiten</button></form><p class='muted'>Training bleibt pending; keine automatische Modell-/Policy-Aktivierung.</p></div></div></section>"""
