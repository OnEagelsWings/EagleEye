from __future__ import annotations
import hashlib, html, json
from typing import Any
from eagleeye_pro.core.database import dumps, new_id, now_ts

def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v): return hashlib.sha256(v if isinstance(v,bytes) else _canon(v).encode()).hexdigest()
def _loads(v,default):
    try:return json.loads(v) if v else default
    except Exception:return default
def _text(v,n=5000): return str(v or '').replace('\x00','').strip()[:n]
def _clamp(v):
    try:return max(0.0,min(1.0,float(v)))
    except Exception:return 0.0

class Build243InvestigativeOpsec3Service:
    BUILD='243.0'
    IDENTITY_MODES=('dedicated_strict','dedicated_balanced','shared_review_required')
    BROWSER_MODES=('dedicated_case_profile','dedicated_investigation_profile','shared_profile_review_required')
    CREDENTIAL_SCOPES=('case_scoped','workspace_scoped','shared_review_required')
    TELEMETRY_MODES=('minimal_local','diagnostic_local','review_required')
    EGRESS_MODES=('explicit_reviewed_allow','review_each_external_step','monitor_only')
    TEMP_MODES=('ephemeral_case_scoped','encrypted_case_scoped','review_required')
    def __init__(self,db,audit,*,sentinel,training,source_fabric,conversation,actor='local-analyst'):
        self.db,self.audit,self.sentinel,self.training,self.source_fabric,self.conversation,self.actor=db,audit,sentinel,training,source_fabric,conversation,actor
        sentinel._opsec3_243=self
        conversation._opsec3_243=self
    def _case(self,case_id):
        if not self.db.one('SELECT case_id FROM cases WHERE case_id=?',(case_id,)):raise KeyError(case_id)
    def _event(self,case_id,event_type,obj_type,obj_id,payload,actor):
        prev=self.db.one('SELECT event_hash FROM build243_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(case_id,)); ph=(prev or {}).get('event_hash',''); eid,now=new_id('evt243'),now_ts(); eh=_hash({'previous':ph,'event_id':eid,'event_type':event_type,'object_id':obj_id,'payload':dict(payload),'actor':actor,'at':now}); self.db.execute('INSERT INTO build243_events VALUES(?,?,?,?,?,?,?,?,?,?)',(eid,case_id,event_type,obj_type,obj_id,actor,dumps(dict(payload)),ph,eh,now));
        try:self.audit.log('build243_'+event_type,obj_type,obj_id,case_id,dict(payload))
        except Exception:pass
    def propose_profile(self,*,case_id,identity_separation='dedicated_strict',browser_profile_mode='dedicated_case_profile',credential_scope='case_scoped',telemetry_mode='minimal_local',egress_mode='explicit_reviewed_allow',temp_data_mode='ephemeral_case_scoped',rationale,actor,confirmation):
        self._case(case_id)
        if confirmation!=f'OPSEC PROFILE 243 {case_id} ANLEGEN':raise PermissionError('explicit approval required')
        if identity_separation not in self.IDENTITY_MODES or browser_profile_mode not in self.BROWSER_MODES or credential_scope not in self.CREDENTIAL_SCOPES or telemetry_mode not in self.TELEMETRY_MODES or egress_mode not in self.EGRESS_MODES or temp_data_mode not in self.TEMP_MODES:raise ValueError('invalid OPSEC profile control')
        if len(_text(rationale))<20:raise ValueError('rationale too short')
        rev=int((self.db.one('SELECT COALESCE(MAX(revision_no),0) n FROM opsec_profiles_243 WHERE case_id=?',(case_id,)) or {'n':0})['n'])+1; pid,now=new_id('opsecprofile243'),now_ts(); data={'profile_id':pid,'case_id':case_id,'revision_no':rev,'identity_separation':identity_separation,'browser_profile_mode':browser_profile_mode,'credential_scope':credential_scope,'telemetry_mode':telemetry_mode,'egress_mode':egress_mode,'temp_data_mode':temp_data_mode,'rationale':_text(rationale)}; self.db.execute('INSERT INTO opsec_profiles_243 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(pid,case_id,rev,identity_separation,browser_profile_mode,credential_scope,telemetry_mode,egress_mode,temp_data_mode,_text(rationale),actor,now,_hash(data))); self._event(case_id,'profile_proposed','opsec_profile',pid,{'revision':rev},actor); return self.profile(pid)
    def profile(self,profile_id):
        p=self.db.one('SELECT * FROM opsec_profiles_243 WHERE profile_id=?',(profile_id,));
        if not p:raise KeyError(profile_id)
        d=dict(p); rv=self.db.one('SELECT * FROM opsec_profile_reviews_243 WHERE profile_id=?',(profile_id,)); d['review']=dict(rv) if rv else None; d['active']=bool(self.db.one('SELECT activation_id FROM opsec_profile_activations_243 WHERE profile_id=?',(profile_id,))); return d
    def review_profile(self,*,profile_id,decision,rationale,reviewer,confirmation):
        p=self.profile(profile_id)
        if confirmation!=f'OPSEC PROFILE 243 {profile_id} PRUEFEN':raise PermissionError('explicit approval required')
        if reviewer==p['created_by']:raise PermissionError('independent reviewer required')
        if p['review']:raise ValueError('already reviewed')
        if decision not in {'approved','rejected'}:raise ValueError('invalid decision')
        if len(_text(rationale))<20:raise ValueError('rationale too short')
        rid,now=new_id('opsecprofilerev243'),now_ts(); self.db.execute('INSERT INTO opsec_profile_reviews_243 VALUES(?,?,?,?,?,?,?,?)',(rid,profile_id,p['case_id'],decision,_text(rationale),reviewer,now,_hash({'review':rid,'decision':decision}))); return dict(self.db.one('SELECT * FROM opsec_profile_reviews_243 WHERE review_id=?',(rid,)))
    def activate_profile(self,*,profile_id,actor,confirmation):
        p=self.profile(profile_id)
        if confirmation!=f'OPSEC PROFILE 243 {profile_id} AKTIVIEREN':raise PermissionError('explicit approval required')
        if not p['review'] or p['review']['decision']!='approved':raise PermissionError('approved independent review required')
        aid,now=new_id('opsecprofileact243'),now_ts(); self.db.execute('INSERT INTO opsec_profile_activations_243 VALUES(?,?,?,?,?,?)',(aid,profile_id,p['case_id'],actor,now,_hash({'activation':aid,'profile':profile_id}))); self._event(p['case_id'],'profile_activated','opsec_profile',profile_id,{'automatic':False},actor); return {'activation_id':aid,'profile_id':profile_id,'automatic_activation':False}
    def active_profile(self,case_id):
        self._case(case_id); p=self.db.one('SELECT p.* FROM opsec_profile_activations_243 a JOIN opsec_profiles_243 p ON p.profile_id=a.profile_id WHERE a.case_id=? ORDER BY a.activated_at DESC LIMIT 1',(case_id,)); return dict(p) if p else None
    def propose_egress_rule(self,*,case_id,destination_class,destination_ref,action,purpose,rationale,actor,confirmation):
        self._case(case_id)
        if confirmation!=f'OPSEC EGRESS 243 {case_id} ANLEGEN':raise PermissionError('explicit approval required')
        if action not in {'allow','review','block'}:raise ValueError('invalid action')
        if len(_text(rationale))<15 or len(_text(purpose))<5:raise ValueError('purpose/rationale too short')
        rid,now=new_id('egress243'),now_ts(); self.db.execute('INSERT INTO opsec_egress_rules_243 VALUES(?,?,?,?,?,?,?,?,?,?)',(rid,case_id,_text(destination_class,120),_text(destination_ref,500),action,_text(purpose,1000),_text(rationale,3000),actor,now,_hash({'rule':rid,'action':action,'ref':destination_ref}))); return self.egress_rule(rid)
    def egress_rule(self,rule_id):
        r=self.db.one('SELECT * FROM opsec_egress_rules_243 WHERE rule_id=?',(rule_id,));
        if not r:raise KeyError(rule_id)
        d=dict(r); rv=self.db.one('SELECT * FROM opsec_egress_rule_reviews_243 WHERE rule_id=?',(rule_id,)); d['review']=dict(rv) if rv else None; return d
    def review_egress_rule(self,*,rule_id,decision,rationale,reviewer,confirmation):
        r=self.egress_rule(rule_id)
        if confirmation!=f'OPSEC EGRESS 243 {rule_id} PRUEFEN':raise PermissionError('explicit approval required')
        if reviewer==r['created_by']:raise PermissionError('independent reviewer required')
        if r['review']:raise ValueError('already reviewed')
        if decision not in {'approved','rejected'}:raise ValueError('invalid decision')
        if len(_text(rationale))<20:raise ValueError('rationale too short')
        vid,now=new_id('egressrev243'),now_ts(); self.db.execute('INSERT INTO opsec_egress_rule_reviews_243 VALUES(?,?,?,?,?,?,?,?)',(vid,rule_id,r['case_id'],decision,_text(rationale),reviewer,now,_hash({'review':vid,'decision':decision}))); return dict(self.db.one('SELECT * FROM opsec_egress_rule_reviews_243 WHERE review_id=?',(vid,)))
    def egress_decision(self,*,case_id,destination_class,destination_ref):
        p=self.active_profile(case_id)
        rows=self.db.all("SELECT r.*,v.decision FROM opsec_egress_rules_243 r JOIN opsec_egress_rule_reviews_243 v ON v.rule_id=r.rule_id WHERE r.case_id=? AND v.decision='approved' ORDER BY r.created_at DESC",(case_id,))
        for r in rows:
            if r['destination_class']==destination_class and (not r['destination_ref'] or r['destination_ref']==destination_ref):return {'decision':r['action'],'rule_id':r['rule_id'],'automatic_network_change':False}
        mode=(p or {}).get('egress_mode','review_each_external_step')
        return {'decision':'review' if mode!='monitor_only' else 'monitor','rule_id':'','automatic_network_change':False}
    def register_secret_ref(self,*,case_id,secret_ref,scope='case_scoped',storage_class='external_vault',exposure_status='unknown',rotation_status='current',note='',actor,confirmation):
        self._case(case_id)
        if confirmation!=f'OPSEC SECRET 243 {case_id} REFERENZIEREN':raise PermissionError('explicit approval required')
        if storage_class not in {'external_vault','os_keyring','app_reference_only'} or exposure_status not in {'unknown','clear','suspected','confirmed'} or rotation_status not in {'current','review_due','rotate_now'}:raise ValueError('invalid secret metadata')
        if any(x in _text(secret_ref,500).lower() for x in ('bearer ','password=','token=','apikey=','api_key=')):raise ValueError('secret_ref must be an identifier, never a secret value')
        sid,now=new_id('secret243'),now_ts(); self.db.execute('INSERT INTO opsec_secret_inventory_243 VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(case_id,secret_ref) DO UPDATE SET scope=excluded.scope,storage_class=excluded.storage_class,exposure_status=excluded.exposure_status,rotation_status=excluded.rotation_status,note=excluded.note,recorded_by=excluded.recorded_by,recorded_at=excluded.recorded_at,payload_sha256=excluded.payload_sha256',(sid,case_id,_text(secret_ref,300),_text(scope,120),storage_class,exposure_status,rotation_status,_text(note,1000),actor,now,_hash({'ref':secret_ref,'scope':scope,'exposure':exposure_status}))); return dict(self.db.one('SELECT * FROM opsec_secret_inventory_243 WHERE case_id=? AND secret_ref=?',(case_id,_text(secret_ref,300))))
    def _findings(self,case_id):
        findings=[]; p=self.active_profile(case_id)
        if not p: findings.append({'category':'opsec_profile_missing','severity':'medium','score':.60,'detail':'No independently approved active case OPSEC profile.'})
        else:
            if p['identity_separation']!='dedicated_strict':findings.append({'category':'personal_profile_reuse','severity':'medium','score':.52,'detail':'Identity separation is not strict dedicated mode.'})
            if p['browser_profile_mode']!='dedicated_case_profile':findings.append({'category':'personal_profile_reuse','severity':'medium','score':.48,'detail':'Browser profile is not dedicated per case.'})
            if p['credential_scope']!='case_scoped':findings.append({'category':'credential_exposure','severity':'medium','score':.50,'detail':'Credentials are not strictly case scoped.'})
            if p['telemetry_mode']!='minimal_local':findings.append({'category':'telemetry_exposure','severity':'low','score':.32,'detail':'Telemetry mode is broader than minimal local diagnostics.'})
            if p['egress_mode']!='explicit_reviewed_allow':findings.append({'category':'unexpected_egress','severity':'medium','score':.50,'detail':'External steps are not restricted to explicit reviewed allow rules.'})
        sec=self.db.all("SELECT * FROM opsec_secret_inventory_243 WHERE case_id=? AND (exposure_status IN ('suspected','confirmed') OR rotation_status IN ('review_due','rotate_now'))",(case_id,))
        for s in sec:
            score=.95 if s['exposure_status']=='confirmed' else .76 if s['exposure_status']=='suspected' else .55; findings.append({'category':'credential_exposure','severity':'critical' if score>=.9 else 'high' if score>=.7 else 'medium','score':score,'detail':'Secret reference requires defensive review/rotation.','secret_ref':s['secret_ref']})
        unreviewed=self.db.one('SELECT COUNT(*) n FROM opsec_egress_rules_243 r LEFT JOIN opsec_egress_rule_reviews_243 v ON v.rule_id=r.rule_id WHERE r.case_id=? AND v.review_id IS NULL',(case_id,));
        if unreviewed and int(unreviewed['n']):findings.append({'category':'unexpected_egress','severity':'medium','score':min(.65,.35+.06*int(unreviewed['n'])),'detail':'Unreviewed egress policy candidates exist.','count':int(unreviewed['n'])})
        return findings
    def sentinel_factors(self,case_id):
        return [{'category':x['category'],'score':x['score'],'source':'build243_opsec_control'} for x in self._findings(case_id)]
    def assess(self,*,case_id,actor='opsec-sentinel-243',auto_contain=True):
        self._case(case_id); findings=self._findings(case_id); vals=[float(x['score']) for x in findings]; exposure=0 if not vals else _clamp(max(vals)*.70+(sum(vals)/len(vals))*.30); level='critical' if exposure>=.88 else 'high' if exposure>=.70 else 'elevated' if exposure>=.50 else 'guarded' if exposure>=.30 else 'low'; profile=self.active_profile(case_id); controls=[]
        gate=1 if level in {'elevated','high','critical'} else 0; secret_gate=1 if any(x['category']=='credential_exposure' and float(x['score'])>=.7 for x in findings) else 0; mode='paused_opsec' if level in {'high','critical'} else 'restricted' if level=='elevated' else 'guarded' if level=='guarded' else 'normal';
        if auto_contain and gate:controls.append('external_step_human_gate')
        if auto_contain and secret_gate:controls.append('secret_use_human_gate')
        friction=(.15 if gate else 0)+(.10 if secret_gate else 0)+(.05 if profile and profile.get('egress_mode')=='explicit_reviewed_allow' else 0); efficiency=_clamp(1.0-friction-(.08*len([x for x in findings if float(x['score'])<.5])))
        rec=[]
        cats={x['category'] for x in findings}
        if 'opsec_profile_missing' in cats:rec.append('Create, independently review, and activate a case-scoped OPSEC profile.')
        if 'personal_profile_reuse' in cats:rec.append('Use a dedicated investigation/browser profile for this case; do not reuse personal identities.')
        if 'unexpected_egress' in cats:rec.append('Require reviewed destination/purpose policy before external investigation steps.')
        if 'credential_exposure' in cats:rec.append('Review the referenced credential in its external vault/keyring and rotate it if exposure is confirmed.')
        if 'telemetry_exposure' in cats:rec.append('Keep EagleEye diagnostics local and minimal unless broader diagnostics are explicitly reviewed.')
        rec.append('Do not infer invisibility from a low score; network and service providers may still observe activity.')
        aid,now=new_id('opsechealth243'),now_ts(); self.db.execute('INSERT INTO opsec_health_assessments_243 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(aid,case_id,(profile or {}).get('profile_id',''),round(exposure,4),round(efficiency,4),level,dumps(findings),dumps(rec),dumps(controls),actor,now,_hash({'assessment':aid,'exposure':exposure,'level':level,'findings':findings}))); self.db.execute('INSERT INTO opsec_runtime_state_243 VALUES(?,?,?,?,?,?) ON CONFLICT(case_id) DO UPDATE SET mode=excluded.mode,external_step_gate=excluded.external_step_gate,secret_use_gate=excluded.secret_use_gate,last_assessment_id=excluded.last_assessment_id,updated_at=excluded.updated_at',(case_id,mode,gate,secret_gate,aid,now));
        # Let the existing sentinel aggregate Build 243 factors and pause EagleEye agents when warranted.
        if auto_contain:
            try:self.sentinel.scan_case(case_id=case_id,actor='opsec-sentinel-243',auto_contain=True)
            except Exception:pass
        self._event(case_id,'health_assessed','opsec_health',aid,{'risk_level':level,'exposure_score':round(exposure,4),'efficiency_score':round(efficiency,4)},actor); return self.health(aid)
    def health(self,assessment_id):
        r=self.db.one('SELECT * FROM opsec_health_assessments_243 WHERE assessment_id=?',(assessment_id,));
        if not r:raise KeyError(assessment_id)
        d=dict(r); d['findings']=_loads(d['findings_json'],[]); d['recommendations']=_loads(d['recommendations_json'],[]); d['runtime_controls']=_loads(d['runtime_controls_json'],[]); rv=self.db.one('SELECT * FROM opsec_health_reviews_243 WHERE assessment_id=?',(assessment_id,)); d['review']=dict(rv) if rv else None; return d
    def review_health(self,*,assessment_id,decision,rationale,reviewer,confirmation):
        a=self.health(assessment_id)
        if confirmation!=f'OPSEC HEALTH 243 {assessment_id} PRUEFEN':raise PermissionError('explicit approval required')
        if reviewer==a['assessed_by']:raise PermissionError('independent reviewer required')
        if a['review']:raise ValueError('already reviewed')
        if decision not in {'confirmed','false_positive','needs_context'}:raise ValueError('invalid decision')
        if len(_text(rationale))<20:raise ValueError('rationale too short')
        rid,now=new_id('ophealthrev243'),now_ts(); self.db.execute('INSERT INTO opsec_health_reviews_243 VALUES(?,?,?,?,?,?,?,?)',(rid,assessment_id,a['case_id'],decision,_text(rationale),reviewer,now,_hash({'review':rid,'decision':decision}))); out=dict(self.db.one('SELECT * FROM opsec_health_reviews_243 WHERE review_id=?',(rid,))); out['training_example_id']=''
        # Controlled self-training: confirmed/false-positive reviews create pending examples only.
        if decision in {'confirmed','false_positive'}:
            try:out['training_example_id']=self._stage_one(a,decision,_text(rationale),reviewer)
            except Exception:pass
        return out
    def _stage_one(self,a,decision,rationale,actor):
        exists=self.db.one('SELECT training_example_id FROM opsec_training_links_243 WHERE assessment_id=?',(a['assessment_id'],));
        if exists:return exists['training_example_id']
        context={'risk_level':a['risk_level'],'exposure_score':a['exposure_score'],'efficiency_score':a['efficiency_score'],'findings':a['findings'],'review_decision':decision,'safe_boundary':'defensive_app_internal_only_no_untrackability_claim'}; instruction='Bewerte den OPSEC-Health-Zustand defensiv. Trenne messbare Exposition von Vermutungen, minimiere unnötige Angriffs-/Trackingfläche und schlage nur rechtmäßige, überprüfbare App-interne Kontrollen oder Human-Gates vor.'; response=f'Review: {decision}. {rationale}'
        ex=self.training.add_example(case_id=a['case_id'],instruction=instruction,response=response,context=context,source_type='opsec_health_243',source_ref=a['assessment_id'],created_by=actor,confirmation=f"TRAINING EXAMPLE 228 {a['case_id']} ANLEGEN"); lid,now=new_id('opsectrain243'),now_ts(); self.db.execute('INSERT INTO opsec_training_links_243 VALUES(?,?,?,?,?,?,?)',(lid,a['case_id'],a['assessment_id'],ex['example_id'],actor,now,_hash({'link':lid,'example':ex['example_id']}))); return ex['example_id']
    def stage_training(self,*,case_id,actor,limit=50,confirmation):
        if confirmation!=f'OPSEC TRAINING 243 {case_id} VORBEREITEN':raise PermissionError('explicit approval required')
        rows=self.db.all("SELECT a.*,r.decision,r.rationale,r.reviewer FROM opsec_health_assessments_243 a JOIN opsec_health_reviews_243 r ON r.assessment_id=a.assessment_id LEFT JOIN opsec_training_links_243 l ON l.assessment_id=a.assessment_id WHERE a.case_id=? AND r.decision IN ('confirmed','false_positive') AND l.assessment_id IS NULL ORDER BY r.reviewed_at LIMIT ?",(case_id,max(1,min(200,int(limit))))); created=[]
        for row in rows:
            a=self.health(row['assessment_id']); created.append(self._stage_one(a,row['decision'],row['rationale'],actor))
        return {'case_id':case_id,'created':created,'count':len(created),'review_status':'pending','automatic_model_or_policy_activation':False}
    def runtime_state(self,case_id):
        r=self.db.one('SELECT * FROM opsec_runtime_state_243 WHERE case_id=?',(case_id,)); return dict(r) if r else {'case_id':case_id,'mode':'normal','external_step_gate':0,'secret_use_gate':0,'last_assessment_id':''}
    def context(self,case_id):
        latest=self.db.one('SELECT assessment_id FROM opsec_health_assessments_243 WHERE case_id=? ORDER BY assessed_at DESC LIMIT 1',(case_id,)); return {'runtime_state':self.runtime_state(case_id),'latest_health':self.health(latest['assessment_id']) if latest else None,'rules':['A low exposure score never proves the investigation is untrackable.','Use case-scoped identities and credentials where feasible.','External steps remain subject to reviewed egress policy and human gates.','No OS/network reconfiguration, anti-forensics, access-control bypass, or covert evasion is authorized by Build 243.']}
    def dashboard(self,case_id):
        self._case(case_id); last=self.db.one('SELECT assessment_id FROM opsec_health_assessments_243 WHERE case_id=? ORDER BY assessed_at DESC LIMIT 1',(case_id,)); h=self.health(last['assessment_id']) if last else None; return {'build':self.BUILD,'active_profile':self.active_profile(case_id),'health':h,'runtime':self.runtime_state(case_id),'egress_rules':self.db.one('SELECT COUNT(*) n FROM opsec_egress_rules_243 WHERE case_id=?',(case_id,))['n'],'secret_refs':self.db.one('SELECT COUNT(*) n FROM opsec_secret_inventory_243 WHERE case_id=?',(case_id,))['n'],'training':self.db.one('SELECT COUNT(*) n FROM opsec_training_links_243 WHERE case_id=?',(case_id,))['n']}
    def render_workspace_panel(self,*,case_id,csrf):
        d=self.dashboard(case_id); e=lambda x:html.escape(str(x or ''),quote=True); h=d['health'] or {}; p=d['active_profile'] or {}
        return f"""<section class='card' id='build243'><h2>Investigative OPSEC 3.0 · Build 243</h2><p>Defensive Fallisolierung, reviewed Egress-Policy, Secret-Referenzen ohne Secretwerte, lokale Telemetrie-Minimierung und messbarer OPSEC-Health. Ein niedriger Score ist kein Unsichtbarkeitsversprechen.</p><div class='metrics'><div class='metric'><div class='label'>Risk</div><div class='value'>{e(h.get('risk_level','not assessed'))}</div></div><div class='metric'><div class='label'>Exposure</div><div class='value'>{e(h.get('exposure_score','-'))}</div></div><div class='metric'><div class='label'>Efficiency</div><div class='value'>{e(h.get('efficiency_score','-'))}</div></div><div class='metric'><div class='label'>Training</div><div class='value'>{d['training']}</div></div></div><div class='grid'><div class='card'><h3>Case OPSEC Profile</h3><p class='muted'>Aktiv: {e(p.get('profile_id','none'))}</p><form method='post' action='/build243/profile-create'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><textarea name='rationale' required>Dedicated case isolation with minimal local telemetry and reviewed egress.</textarea><button>Profil-Kandidat anlegen</button></form></div><div class='card'><h3>Health</h3><form method='post' action='/build243/health-scan'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>OPSEC-Health analysieren</button></form><p class='muted'>High/Critical kann nur EagleEye-interne Agenten pausieren/gaten.</p></div><div class='card'><h3>Egress Policy</h3><form method='post' action='/build243/egress-create'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='destination_class' value='source'><input name='destination_ref' placeholder='source_key / class'><select name='action'><option>review</option><option>allow</option><option>block</option></select><input name='purpose' placeholder='Investigative purpose'><textarea name='rationale'></textarea><button>Rule-Kandidat</button></form></div><div class='card'><h3>Training</h3><form method='post' action='/build243/training-stage'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Reviewte OPSEC-Fälle fürs Training</button></form><p class='muted'>Automatisch erzeugte Lernbeispiele bleiben pending; keine automatische Modell-/Policy-Aktivierung.</p></div></div></section>"""
