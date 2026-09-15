from __future__ import annotations
import hashlib, html, json
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse
from eagleeye_pro.core.database import dumps, new_id, now_ts


def _canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)

def _hash(v: Any) -> str:
    return hashlib.sha256(v if isinstance(v, bytes) else _canon(v).encode('utf-8')).hexdigest()

def _text(v: Any, n: int = 10000) -> str:
    return str(v or '').replace('\x00', '').strip()[:n]

def _loads(v: Any, default: Any) -> Any:
    try: return json.loads(v) if v else default
    except Exception: return default

def _clamp(v: Any) -> float:
    try: return max(0.0, min(1.0, float(v)))
    except Exception: return 0.0

def _plus_minutes(ts: str, minutes: int) -> str:
    try:
        dt = datetime.strptime(ts, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    except Exception:
        dt = datetime.now(timezone.utc)
    return (dt + timedelta(minutes=max(5, int(minutes)))).strftime('%Y-%m-%dT%H:%M:%SZ')


class Build246MonitoringWatchlistsService:
    BUILD = '246.0'
    TARGET_TYPES = {'person','organization','account','domain','claim','source'}
    CHANGE_DECISIONS = {'accepted','rejected','needs_context'}

    def __init__(self, db: Any, audit: Any, *, workflow: Any, cockpit: Any, kernel: Any,
                 source_fabric: Any, evidence_vault: Any, verification: Any, orchestration: Any,
                 opsec: Any, sentinel: Any, training: Any, conversation: Any,
                 actor: str = 'local-analyst') -> None:
        self.db, self.audit = db, audit
        self.workflow, self.cockpit, self.kernel = workflow, cockpit, kernel
        self.source_fabric, self.evidence_vault, self.verification = source_fabric, evidence_vault, verification
        self.orchestration, self.opsec, self.sentinel, self.training = orchestration, opsec, sentinel, training
        self.conversation, self.actor = conversation, actor
        conversation._monitoring246 = self
        cockpit._monitoring246 = self

    def _case(self, case_id: str) -> None:
        if not self.db.one('SELECT case_id FROM cases WHERE case_id=?', (case_id,)):
            raise KeyError(case_id)

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: dict[str, Any], actor: str) -> None:
        prev = self.db.one('SELECT event_hash FROM monitoring_events_246 WHERE case_id=? ORDER BY rowid DESC LIMIT 1', (case_id,))
        ph = (prev or {}).get('event_hash', '')
        eid, now = new_id('mon_evt246'), now_ts()
        eh = _hash({'previous': ph, 'event_id': eid, 'event_type': event_type, 'object_id': object_id, 'payload': payload, 'actor': actor, 'at': now})
        self.db.execute('INSERT INTO monitoring_events_246 VALUES(?,?,?,?,?,?,?,?,?,?)', (eid, case_id, event_type, object_type, object_id, actor, dumps(payload), ph, eh, now))
        try: self.audit.log('build246_' + event_type, object_type, object_id, case_id, payload)
        except Exception: pass

    def create_watchlist(self, *, case_id: str, name: str, purpose: str, owner: str, actor: str, confirmation: str) -> dict[str, Any]:
        self._case(case_id)
        if confirmation != f'WATCHLIST 246 {case_id} ANLEGEN': raise PermissionError('explicit approval required')
        name, purpose = _text(name, 300), _text(purpose, 3000)
        if len(name) < 3 or len(purpose) < 12: raise ValueError('substantive watchlist name and purpose required')
        wid, now = new_id('watch246'), now_ts()
        payload = {'watchlist_id': wid, 'case_id': case_id, 'name': name, 'purpose': purpose, 'owner': _text(owner,200) or actor, 'status': 'active', 'created_by': actor, 'created_at': now}
        self.db.execute('INSERT INTO watchlists_246 VALUES(?,?,?,?,?,?,?,?,?)', (wid, case_id, name, purpose, payload['owner'], 'active', actor, now, _hash(payload)))
        self._event(case_id, 'watchlist_created', 'watchlist', wid, {'name': name}, actor)
        return payload

    def add_target(self, *, watchlist_id: str, target_type: str, target_ref: str, label: str,
                   source_key: str, source_url: str, interval_minutes: int, actor: str, confirmation: str) -> dict[str, Any]:
        w = self.db.one('SELECT * FROM watchlists_246 WHERE watchlist_id=?', (watchlist_id,))
        if not w: raise KeyError(watchlist_id)
        if confirmation != f'WATCH TARGET 246 {watchlist_id} ANLEGEN': raise PermissionError('explicit approval required')
        typ = _text(target_type,80).lower()
        if typ not in self.TARGET_TYPES: raise ValueError('unsupported target type')
        ref, label = _text(target_ref,500), _text(label,500)
        if len(ref) < 2 or len(label) < 2: raise ValueError('target ref and label required')
        skey, surl = _text(source_key,200), _text(source_url,4000)
        if skey:
            constraint = self.source_fabric.ranking_constraint(source_key=skey)
            if constraint.get('managed') and not constraint.get('eligible'):
                raise PermissionError('source is not governance/health eligible')
        if surl and urlparse(surl).scheme not in {'http','https','urn','file'}: raise ValueError('unsupported source URL scheme')
        interval = max(15, min(60*24*30, int(interval_minutes)))
        tid, now = new_id('watchtarget246'), now_ts()
        payload = {'target_id': tid, 'watchlist_id': watchlist_id, 'case_id': w['case_id'], 'target_type': typ, 'target_ref': ref, 'label': label, 'source_key': skey, 'source_url': surl, 'interval_minutes': interval, 'created_by': actor, 'created_at': now}
        self.db.execute('INSERT INTO watch_targets_246 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)', (tid, watchlist_id, w['case_id'], typ, ref, label, skey, surl, interval, actor, now, _hash(payload)))
        self.db.execute('INSERT INTO watch_target_state_246 VALUES(?,?,?,?,?,?,?,?)', (tid, w['case_id'], 'active', '', now, '', '', now))
        self._event(w['case_id'], 'watch_target_added', 'watch_target', tid, {'type': typ, 'source_key': skey, 'interval_minutes': interval}, actor)
        return {**payload, 'next_due_at': now, 'automatic_network_monitoring': False}

    def due_targets(self, *, case_id: str, at: str = '', limit: int = 100) -> list[dict[str, Any]]:
        self._case(case_id); when = _text(at,100) or now_ts()
        rows = self.db.all('''SELECT t.*,s.status,s.last_observed_at,s.next_due_at,s.last_observation_id,s.last_change_id
                              FROM watch_targets_246 t JOIN watch_target_state_246 s ON s.target_id=t.target_id
                              WHERE t.case_id=? AND s.status='active' AND (s.next_due_at='' OR s.next_due_at<=?)
                              ORDER BY s.next_due_at,t.created_at LIMIT ?''', (case_id, when, max(1,min(500,int(limit)))))
        return [dict(x) for x in rows]

    def request_agent_check(self, *, target_id: str, actor: str, confirmation: str) -> dict[str, Any]:
        t = self.db.one('SELECT * FROM watch_targets_246 WHERE target_id=?', (target_id,))
        if not t: raise KeyError(target_id)
        if confirmation != f'WATCH CHECK 246 {target_id} VORBEREITEN': raise PermissionError('explicit approval required')
        ass = self.sentinel.scan_case(case_id=t['case_id'], actor='opsec-sentinel-246', auto_contain=True)
        if ass['risk_level'] in {'high','critical'}: raise PermissionError('OPSEC Sentinel blocks monitoring preparation')
        egress = {'decision':'review','rule_id':'','automatic_network_change':False}
        if t['source_url']:
            host = urlparse(t['source_url']).hostname or t['source_url']
            egress = self.opsec.egress_decision(case_id=t['case_id'], destination_class='monitoring_source', destination_ref=host)
            if egress['decision'] == 'block':
                self._stage_opsec_signal(t, actor, 'blocked egress policy for monitoring source')
                raise PermissionError('approved OPSEC egress policy blocks this monitoring target')
        objective = f"Prepare a bounded monitoring check for {t['target_type']} '{t['label']}'. Compare only lawfully obtained/publicly supplied observations, preserve provenance, and do not treat changes as facts before analyst review."
        run = self.orchestration.create_run(case_id=t['case_id'], objective=objective, priority=65, max_tokens=12000, max_cost=0.0, max_seconds=1200, actor=actor, confirmation=f"AGENT RUN 242 {t['case_id']} ANLEGEN")
        mid, now = new_id('monrun246'), now_ts()
        self.db.execute('INSERT INTO monitor_agent_links_246 VALUES(?,?,?,?,?,?,?,?)', (mid, target_id, t['case_id'], run['run_id'], egress['decision'], actor, now, _hash({'monitor_run':mid,'agent_run':run['run_id'],'egress':egress['decision']})))
        self._event(t['case_id'], 'monitor_check_prepared', 'watch_target', target_id, {'agent_run_id':run['run_id'],'egress_decision':egress['decision'],'automatic_external_action':False}, actor)
        return {'monitor_run_id':mid,'agent_run_id':run['run_id'],'egress_decision':egress['decision'],'human_gates_preserved':True,'automatic_external_action':False}

    def record_observation(self, *, target_id: str, summary: str, source_ref: str, observed_at: str,
                           metadata: dict[str,Any] | None, actor: str, confirmation: str) -> dict[str, Any]:
        t = self.db.one('SELECT * FROM watch_targets_246 WHERE target_id=?', (target_id,))
        if not t: raise KeyError(target_id)
        if confirmation != f'WATCH OBSERVATION 246 {target_id} SPEICHERN': raise PermissionError('explicit approval required')
        summary = _text(summary,20000)
        if len(summary) < 8: raise ValueError('observation summary too short')
        observed = _text(observed_at,100) or now_ts(); ref = _text(source_ref,1000)
        content_hash = _hash({'summary':summary,'source_ref':ref,'source_key':t['source_key'],'source_url':t['source_url']})
        oid, now = new_id('monobs246'), now_ts(); meta = dict(metadata or {})
        payload = {'observation_id':oid,'target_id':target_id,'watchlist_id':t['watchlist_id'],'case_id':t['case_id'],'observed_at':observed,'content_sha256':content_hash,'summary':summary,'source_ref':ref,'source_key':t['source_key'],'source_url':t['source_url'],'metadata':meta,'created_by':actor,'created_at':now}
        self.db.execute('INSERT INTO monitor_observations_246 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (oid,target_id,t['watchlist_id'],t['case_id'],observed,content_hash,summary,ref,t['source_key'],t['source_url'],dumps(meta),actor,now,_hash(payload)))
        prev = self.db.one('SELECT * FROM monitor_observations_246 WHERE target_id=? AND observation_id<>? ORDER BY observed_at DESC,created_at DESC LIMIT 1', (target_id,oid))
        change = None
        if prev and prev['content_sha256'] != content_hash:
            cid = new_id('monchg246'); significance = _clamp(meta.get('significance',.5)); csum = _text(meta.get('change_summary') or f"Observed content changed for {t['label']}.",5000)
            cp = {'change_id':cid,'target_id':target_id,'previous_observation_id':prev['observation_id'],'current_observation_id':oid,'case_id':t['case_id'],'change_type':_text(meta.get('change_type') or 'content_changed',120),'significance':significance,'summary':csum,'created_by':actor,'created_at':now}
            self.db.execute('INSERT INTO monitor_changes_246 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)', (cid,target_id,t['watchlist_id'],t['case_id'],prev['observation_id'],oid,cp['change_type'],significance,csum,actor,now,_hash(cp)))
            change = cp
        next_due = _plus_minutes(observed, int(t['interval_minutes']))
        self.db.execute('UPDATE watch_target_state_246 SET last_observed_at=?,next_due_at=?,last_observation_id=?,last_change_id=?,updated_at=? WHERE target_id=?', (observed,next_due,oid,(change or {}).get('change_id',''),now,target_id))
        self._event(t['case_id'], 'monitor_observation_recorded', 'monitor_observation', oid, {'target_id':target_id,'change_candidate_id':(change or {}).get('change_id',''),'automatic_truth_promotion':False}, actor)
        return {**payload,'change_candidate':change,'next_due_at':next_due,'automatic_truth_promotion':False}

    def review_change(self, *, change_id: str, decision: str, reviewed_significance: float, rationale: str, reviewer: str, confirmation: str) -> dict[str, Any]:
        c = self.db.one('SELECT * FROM monitor_changes_246 WHERE change_id=?', (change_id,))
        if not c: raise KeyError(change_id)
        if confirmation != f'WATCH CHANGE 246 {change_id} PRUEFEN': raise PermissionError('explicit approval required')
        if reviewer == c['created_by']: raise PermissionError('independent reviewer required')
        if decision not in self.CHANGE_DECISIONS: raise ValueError('invalid decision')
        if len(_text(rationale,5000)) < 15: raise ValueError('substantive rationale required')
        if self.db.one('SELECT review_id FROM monitor_change_reviews_246 WHERE change_id=?',(change_id,)): raise ValueError('already reviewed')
        rid, now = new_id('monrev246'), now_ts(); sig = _clamp(reviewed_significance)
        payload = {'review_id':rid,'change_id':change_id,'case_id':c['case_id'],'decision':decision,'reviewed_significance':sig,'rationale':_text(rationale,5000),'reviewer':reviewer,'reviewed_at':now}
        self.db.execute('INSERT INTO monitor_change_reviews_246 VALUES(?,?,?,?,?,?,?,?,?)',(rid,change_id,c['case_id'],decision,sig,payload['rationale'],reviewer,now,_hash(payload)))
        self._event(c['case_id'],'monitor_change_reviewed','monitor_change',change_id,{'decision':decision,'reviewed_significance':sig},reviewer)
        return payload

    def stage_change_as_evidence(self, *, change_id: str, actor: str, confirmation: str) -> dict[str, Any]:
        c = self.db.one('''SELECT c.*,r.decision,r.rationale review_rationale,r.reviewer,
                                  o.summary observation_summary,o.source_key,o.source_url,o.source_ref,o.observed_at
                           FROM monitor_changes_246 c JOIN monitor_change_reviews_246 r ON r.change_id=c.change_id
                           JOIN monitor_observations_246 o ON o.observation_id=c.current_observation_id
                           WHERE c.change_id=?''',(change_id,))
        if not c: raise KeyError(change_id)
        if confirmation != f'WATCH EVIDENCE 246 {change_id} VORBEREITEN': raise PermissionError('explicit approval required')
        if c['decision'] != 'accepted': raise PermissionError('accepted independent change review required')
        existing = self.db.one('SELECT * FROM monitor_evidence_links_246 WHERE change_id=?',(change_id,))
        if existing: return {'vault_item_id':existing['vault_item_id'],'idempotent':True,'review_status':'pending'}
        text = f"Monitoring change candidate (review accepted, still subject to Evidence Vault review)\nTarget: {c['target_id']}\nChange: {c['summary']}\nObserved: {c['observation_summary']}\nSource ref: {c['source_ref']}\nReview rationale: {c['review_rationale']}"
        item = self.evidence_vault.capture_text(case_id=c['case_id'],text=text,media_type='text/plain; charset=utf-8',original_filename=f"monitoring_change_{change_id}.txt",source_key=c['source_key'],source_url=c['source_url'],captured_at=c['observed_at'],acquisition_method='monitoring_observation_246',metadata={'monitor_change_id':change_id,'current_observation_id':c['current_observation_id'],'reviewer':c['reviewer']},created_by=actor,confirmation=f"EVIDENCE VAULT 239 {c['case_id']} CAPTURE")
        lid, now = new_id('monevlink246'), now_ts()
        self.db.execute('INSERT INTO monitor_evidence_links_246 VALUES(?,?,?,?,?,?,?)',(lid,change_id,c['case_id'],item['vault_item_id'],actor,now,_hash({'link':lid,'change':change_id,'vault':item['vault_item_id']})))
        self._event(c['case_id'],'monitor_change_staged_as_evidence','monitor_change',change_id,{'vault_item_id':item['vault_item_id'],'evidence_review_required':True},actor)
        return {'vault_item_id':item['vault_item_id'],'idempotent':False,'review_status':'pending','evidence_review_required':True}

    def _stage_opsec_signal(self, target: Any, actor: str, reason: str) -> dict[str, Any]:
        out = self.sentinel.record_observation(case_id=target['case_id'],category='external_link_exposure',severity='medium',confidence=.75,source_type='monitoring_watchlists_246',details={'target_id':target['target_id'],'reason':reason,'source_url':target['source_url']},detector='monitoring-opsec-246',source_ref=target['target_id'],confirmation=f"OPSEC OBSERVATION 242 {target['case_id']} SPEICHERN")
        lid, now = new_id('monopsec246'), now_ts()
        self.db.execute('INSERT INTO monitor_opsec_links_246 VALUES(?,?,?,?,?,?,?)',(lid,target['target_id'],target['case_id'],out['observation_id'],actor,now,_hash({'link':lid,'observation':out['observation_id']})))
        return out

    def stage_training(self, *, case_id: str, actor: str, limit: int = 50, confirmation: str) -> dict[str, Any]:
        if confirmation != f'WATCH TRAINING 246 {case_id} VORBEREITEN': raise PermissionError('explicit approval required')
        self._case(case_id)
        rows = self.db.all('''SELECT c.*,r.decision,r.reviewed_significance,r.rationale,r.reviewer,t.target_type,t.label,t.source_key
                              FROM monitor_changes_246 c JOIN monitor_change_reviews_246 r ON r.change_id=c.change_id
                              JOIN watch_targets_246 t ON t.target_id=c.target_id
                              LEFT JOIN monitor_training_links_246 l ON l.change_id=c.change_id
                              WHERE c.case_id=? AND r.decision IN ('accepted','rejected') AND l.change_id IS NULL
                              ORDER BY r.reviewed_at LIMIT ?''',(case_id,max(1,min(200,int(limit)))))
        ids=[]
        for x in rows:
            instruction = 'Bewerte eine Monitoring-Aenderung. Trenne beobachtete Veraenderung von Schlussfolgerung, nenne Evidenzbedarf und behandle neue Inhalte bis zur Verifikation nur als Kandidat.'
            response = f"Review: {x['decision']}; significance: {x['reviewed_significance']}. {x['rationale']}"
            context = {'target_type':x['target_type'],'label':x['label'],'source_key':x['source_key'],'change_type':x['change_type'],'change_summary':x['summary'],'review_decision':x['decision'],'safe_boundary':'change_candidate_not_fact_until_evidence_and_verification'}
            ex = self.training.add_example(case_id=case_id,instruction=instruction,response=response,context=context,source_type='monitoring_watchlists_246',source_ref=x['change_id'],created_by=actor,confirmation=f'TRAINING EXAMPLE 228 {case_id} ANLEGEN')
            lid, now = new_id('montrain246'), now_ts(); self.db.execute('INSERT INTO monitor_training_links_246 VALUES(?,?,?,?,?,?,?)',(lid,x['change_id'],case_id,ex['example_id'],actor,now,_hash({'link':lid,'example':ex['example_id']}))); ids.append(ex['example_id'])
        return {'case_id':case_id,'created':len(ids),'training_example_ids':ids,'review_status':'pending','automatic_model_activation':False}

    def context(self, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        accepted = [dict(x) for x in self.db.all('''SELECT c.change_id,c.target_id,c.change_type,c.summary,r.reviewed_significance,r.rationale,t.label,t.target_type
            FROM monitor_changes_246 c JOIN monitor_change_reviews_246 r ON r.change_id=c.change_id JOIN watch_targets_246 t ON t.target_id=c.target_id
            WHERE c.case_id=? AND r.decision='accepted' ORDER BY r.reviewed_at DESC LIMIT 30''',(case_id,))]
        pending = [dict(x) for x in self.db.all('''SELECT c.change_id,c.target_id,c.change_type,c.summary,t.label FROM monitor_changes_246 c JOIN watch_targets_246 t ON t.target_id=c.target_id LEFT JOIN monitor_change_reviews_246 r ON r.change_id=c.change_id WHERE c.case_id=? AND r.review_id IS NULL ORDER BY c.created_at DESC LIMIT 30''',(case_id,))]
        due = self.due_targets(case_id=case_id,limit=30)
        return {'monitoring_watchlists_246':{'due_targets':due,'accepted_change_candidates_not_yet_verified_facts':accepted,'pending_changes_not_facts':pending},'rules':['A monitored change is not automatically a fact.','Only independently reviewed changes may be staged to Evidence Vault; Evidence Vault and verification gates still apply.','Monitoring does not authorize autonomous network access; OPSEC, source governance, egress and human gates remain mandatory.']}

    def dashboard(self, *, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        def n(sql: str) -> int: return int((self.db.one(sql,(case_id,)) or {'n':0})['n'])
        return {'build':self.BUILD,'watchlists':n('SELECT COUNT(*) n FROM watchlists_246 WHERE case_id=?'),'targets':n('SELECT COUNT(*) n FROM watch_targets_246 WHERE case_id=?'),'due':len(self.due_targets(case_id=case_id,limit=500)),'observations':n('SELECT COUNT(*) n FROM monitor_observations_246 WHERE case_id=?'),'changes':n('SELECT COUNT(*) n FROM monitor_changes_246 WHERE case_id=?'),'reviewed_changes':n('SELECT COUNT(*) n FROM monitor_change_reviews_246 WHERE case_id=?'),'evidence_candidates':n('SELECT COUNT(*) n FROM monitor_evidence_links_246 WHERE case_id=?'),'training':n('SELECT COUNT(*) n FROM monitor_training_links_246 WHERE case_id=?')}

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        d=self.dashboard(case_id=case_id); e=lambda x:html.escape(str(x or ''),quote=True)
        lists=self.db.all('SELECT watchlist_id,name,purpose FROM watchlists_246 WHERE case_id=? ORDER BY created_at DESC LIMIT 12',(case_id,))
        options=''.join(f"<option value='{e(x['watchlist_id'])}'>{e(x['name'])}</option>" for x in lists)
        due=self.due_targets(case_id=case_id,limit=20); rows=''.join(f"<tr><td>{e(x['label'])}</td><td>{e(x['target_type'])}</td><td>{e(x['source_key'])}</td><td>{e(x['next_due_at'])}</td><td><code>{e(x['target_id'])}</code></td></tr>" for x in due) or "<tr><td colspan='5'>Keine faelligen Targets.</td></tr>"
        return f"""<section class='panel'><h2>Monitoring &amp; Watchlists · Build 246</h2><p class='muted'>Kontrollierte Weiterbeobachtung: Watchlist → Observation → Change Candidate → unabhängiges Review → Evidence Vault → Verification. Kein autonomes Crawling.</p><div class='metrics'><div class='metric'><div class='label'>Watchlists</div><div class='value'>{d['watchlists']}</div></div><div class='metric'><div class='label'>Targets</div><div class='value'>{d['targets']}</div></div><div class='metric'><div class='label'>Fällig</div><div class='value'>{d['due']}</div></div><div class='metric'><div class='label'>Changes</div><div class='value'>{d['changes']}</div></div></div>
        <div class='grid'><div class='card'><h3>Watchlist anlegen</h3><form method='post' action='/build246/watchlist'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='name' placeholder='Watchlist' required><textarea name='purpose' placeholder='Beobachtungszweck' required></textarea><input name='owner' value='analyst'><button>Anlegen</button></form></div>
        <div class='card'><h3>Target hinzufügen</h3><form method='post' action='/build246/target'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><select name='watchlist_id'>{options}</select><select name='target_type'><option>person</option><option>organization</option><option>account</option><option>domain</option><option>claim</option><option>source</option></select><input name='target_ref' placeholder='Canonical-/Source-Ref' required><input name='label' placeholder='Label' required><input name='source_key' placeholder='Source key'><input name='source_url' placeholder='https://...'><input name='interval_minutes' value='1440'><button>Target hinzufügen</button></form></div>
        <div class='card'><h3>Observation erfassen</h3><form method='post' action='/build246/observation'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='target_id' placeholder='Target-ID' required><textarea name='summary' placeholder='Kontrolliert beobachteter Inhalt' required></textarea><input name='source_ref' placeholder='Capture-/Source-Ref'><button>Observation speichern</button></form></div>
        <div class='card'><h3>Change Review / Evidence</h3><form method='post' action='/build246/change-review'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='change_id' placeholder='Change-ID' required><select name='decision'><option>accepted</option><option>rejected</option><option>needs_context</option></select><input name='significance' value='0.7'><textarea name='rationale' placeholder='Unabhängige Begründung' required></textarea><button>Review</button></form><form method='post' action='/build246/evidence-stage'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='change_id' placeholder='akzeptierte Change-ID' required><button>Als Evidence-Kandidat</button></form></div>
        <div class='card'><h3>Agentencheck</h3><form method='post' action='/build246/agent-check'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='target_id' placeholder='Target-ID' required><button>Check vorbereiten</button></form><p class='muted'>Nur Vorbereitung; externe Schritte bleiben Human-/OPSEC-gated.</p></div>
        <div class='card'><h3>Training</h3><form method='post' action='/build246/training'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Reviewte Changes fürs Training</button></form><p class='muted'>Training bleibt pending; keine automatische Modellaktivierung.</p></div></div>
        <h3>Fällige Targets</h3><table><thead><tr><th>Target</th><th>Typ</th><th>Quelle</th><th>Fällig</th><th>ID</th></tr></thead><tbody>{rows}</tbody></table></section>"""
