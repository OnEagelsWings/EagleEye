from __future__ import annotations
from typing import Dict, List
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

FAST_LANE_ACTIONS: Dict[str, Dict[str, str]] = {
    "R": {"label":"Relevant / als Lead behalten","status":"accepted_as_lead","requires_note":"0","risk":"normal"},
    "D": {"label":"Duplikat","status":"duplicate","requires_note":"0","risk":"normal"},
    "N": {"label":"Namensdoppler / falscher Kandidat","status":"rejected","requires_note":"1","risk":"normal"},
    "S": {"label":"Sensibel / Legal-Review","status":"sensitive","requires_note":"1","risk":"high"},
    "L": {"label":"Quellenprüfung erforderlich","status":"needs_source_review","requires_note":"0","risk":"normal"},
    "C": {"label":"Gegenbeleg / widersprüchlich","status":"conflicting","requires_note":"1","risk":"normal"},
    "A": {"label":"Ablehnen / irrelevant","status":"rejected","requires_note":"1","risk":"normal"},
    "E": {"label":"Zu Evidence hochstufen","status":"ready_for_evidence","requires_note":"1","risk":"normal"},
}
DOPPLER_TERMS = ["same name","namensdoppler","anderer ort","anderes profil","not the same","different person","verwechslung"]

class ReviewFastLaneService:
    """Build 37.0 Review Fast Lane: fast, auditable candidate-grade review decisions."""
    def __init__(self, db: Database, audit: AuditService, review_service=None, evidence_service=None):
        self.db=db; self.audit=audit; self.review_service=review_service; self.evidence_service=evidence_service
        self.ensure_schema(); self.seed_shortcuts()
    def ensure_schema(self):
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS review_fast_lane_sessions (
          session_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, lane_key TEXT DEFAULT 'all', status_filter TEXT DEFAULT '',
          item_count INTEGER DEFAULT 0, decided_count INTEGER DEFAULT 0, evidence_promoted_count INTEGER DEFAULT 0,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL, actor TEXT DEFAULT 'local-analyst', notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS review_fast_lane_decisions (
          decision_id TEXT PRIMARY KEY, session_id TEXT DEFAULT '', case_id TEXT NOT NULL, item_id TEXT NOT NULL,
          action_key TEXT NOT NULL, decision_label TEXT NOT NULL, old_status TEXT DEFAULT '', new_status TEXT NOT NULL,
          evidence_id TEXT DEFAULT '', note_required INTEGER DEFAULT 0, analyst_note TEXT DEFAULT '', created_at TEXT NOT NULL,
          actor TEXT DEFAULT 'local-analyst', details_json TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(item_id) REFERENCES review_items(item_id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS review_fast_lane_shortcuts (
          shortcut_key TEXT PRIMARY KEY, label TEXT NOT NULL, action_key TEXT NOT NULL, status TEXT NOT NULL,
          requires_note INTEGER DEFAULT 0, risk_level TEXT DEFAULT 'normal', active INTEGER DEFAULT 1, notes TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS review_bulk_actions (
          bulk_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, action_key TEXT NOT NULL, item_ids_json TEXT NOT NULL,
          affected_count INTEGER DEFAULT 0, blocked_count INTEGER DEFAULT 0, created_at TEXT NOT NULL,
          actor TEXT DEFAULT 'local-analyst', notes TEXT DEFAULT '', details_json TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS review_name_doppler_flags (
          flag_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, item_id TEXT NOT NULL, severity TEXT DEFAULT 'review',
          reason TEXT NOT NULL, markers_json TEXT NOT NULL, created_at TEXT NOT NULL, resolved INTEGER DEFAULT 0,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(item_id) REFERENCES review_items(item_id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS review_fast_lane_metrics (
          metric_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, status_counts_json TEXT NOT NULL,
          queue_count INTEGER DEFAULT 0, duplicate_count INTEGER DEFAULT 0, doppler_flag_count INTEGER DEFAULT 0,
          ready_for_evidence_count INTEGER DEFAULT 0, created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE);
        '''); self.db.conn.commit()
    def seed_shortcuts(self):
        for k,m in FAST_LANE_ACTIONS.items():
            self.db.execute("""INSERT OR REPLACE INTO review_fast_lane_shortcuts(shortcut_key,label,action_key,status,requires_note,risk_level,active,notes) VALUES(?,?,?,?,?,?,?,?)""", [k,m['label'],k,m['status'],int(m.get('requires_note')=='1'),m.get('risk','normal'),1,'Build 37.0 default shortcut'])
        return {'total':len(FAST_LANE_ACTIONS),'shortcuts':list(FAST_LANE_ACTIONS)}
    def shortcuts(self): return self.db.all("SELECT * FROM review_fast_lane_shortcuts WHERE active=1 ORDER BY shortcut_key")
    def _action(self, action_key):
        k=(action_key or '').upper().strip()
        if k not in FAST_LANE_ACTIONS: raise ValueError('Unbekannte Fast-Lane-Aktion.')
        return {'key':k, **FAST_LANE_ACTIONS[k]}
    def queue(self, case_id, lane_key='all', limit=100):
        clauses=['case_id=?']; params=[case_id]
        if lane_key=='ready': clauses.append("status='ready_for_evidence'")
        elif lane_key=='duplicates': clauses.append("status='duplicate'")
        elif lane_key=='sensitive': clauses.append("sensitivity_level='high' OR status='sensitive'")
        elif lane_key=='new': clauses.append("status IN ('new','in_review','needs_source_review')")
        elif lane_key=='doppler': clauses.append("status IN ('new','in_review','conflicting','rejected')")
        else: clauses.append("status NOT IN ('promoted_to_evidence')")
        rows=self.db.all("SELECT * FROM review_items WHERE "+" AND ".join(clauses)+" ORDER BY quality_score DESC, created_at DESC LIMIT ?", params+[int(limit)])
        for r in rows: r['markers']=loads(r.get('markers_json'), [])
        return rows
    def create_session(self, case_id, lane_key='all', actor='local-analyst', notes=''):
        q=self.queue(case_id, lane_key); sid=new_id('rfls'); ts=now_ts()
        self.db.execute("""INSERT INTO review_fast_lane_sessions(session_id,case_id,lane_key,status_filter,item_count,created_at,updated_at,actor,notes) VALUES(?,?,?,?,?,?,?,?,?)""", [sid,case_id,lane_key,'new,in_review,needs_source_review,ready_for_evidence',len(q),ts,ts,actor,notes])
        self.audit.log('create','review_fast_lane_session',sid,case_id,{'lane_key':lane_key,'items':len(q)})
        return self.db.one('SELECT * FROM review_fast_lane_sessions WHERE session_id=?',[sid])
    def decide_item(self, item_id, action_key, analyst_note='', session_id='', actor='local-analyst', evidence_category='Identitätsanker'):
        action=self._action(action_key); item=self.db.one('SELECT * FROM review_items WHERE item_id=?',[item_id])
        if not item: raise KeyError('Review Item nicht gefunden.')
        requires_note=action.get('requires_note')=='1'
        if requires_note and not (analyst_note or '').strip(): raise ValueError('Diese Fast-Lane-Entscheidung benötigt eine kurze Analystennotiz.')
        old=item.get('status') or ''; new=action['status']; evidence_id=''
        details={'action_key':action['key'],'old_status':old,'new_status':new,'candidate_only':True,'no_auto_identity_confirmation':True}
        if action['key']=='E' and self.evidence_service:
            ev=self.evidence_service.promote_review_item(item_id,category=evidence_category,confidence='candidate',export_allowed=False,notes=analyst_note)
            evidence_id=ev.get('evidence_id',''); new='promoted_to_evidence'; details['evidence_id']=evidence_id
        else:
            self.db.execute('UPDATE review_items SET status=?, notes=?, updated_at=? WHERE item_id=?',[new,analyst_note or item.get('notes') or '',now_ts(),item_id])
        did=new_id('rfld'); ts=now_ts()
        self.db.execute("""INSERT INTO review_fast_lane_decisions(decision_id,session_id,case_id,item_id,action_key,decision_label,old_status,new_status,evidence_id,note_required,analyst_note,created_at,actor,details_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", [did,session_id or '',item['case_id'],item_id,action['key'],action['label'],old,new,evidence_id,int(requires_note),analyst_note,ts,actor,dumps(details)])
        if session_id: self.db.execute('UPDATE review_fast_lane_sessions SET decided_count=decided_count+1,evidence_promoted_count=evidence_promoted_count+?,updated_at=? WHERE session_id=?',[1 if evidence_id else 0,ts,session_id])
        self.audit.log('fast_lane_decision','review_item',item_id,item['case_id'],details)
        return {'decision_id':did,'item_id':item_id,'old_status':old,'new_status':new,'evidence_id':evidence_id,'action':action}
    def bulk_decide(self, case_id, item_ids: List[str], action_key, analyst_note='', actor='local-analyst'):
        action=self._action(action_key); affected=[]; blocked=[]; session=self.create_session(case_id,'bulk',actor,f'Bulk {action_key}')
        for iid in item_ids[:250]:
            try: affected.append(self.decide_item(iid,action_key,analyst_note,session['session_id'],actor))
            except Exception as e: blocked.append({'item_id':iid,'reason':str(e)})
        bid=new_id('rflb')
        self.db.execute("""INSERT INTO review_bulk_actions(bulk_id,case_id,action_key,item_ids_json,affected_count,blocked_count,created_at,actor,notes,details_json) VALUES(?,?,?,?,?,?,?,?,?,?)""", [bid,case_id,action['key'],dumps(item_ids),len(affected),len(blocked),now_ts(),actor,analyst_note,dumps({'blocked':blocked})])
        return {'bulk_id':bid,'affected_count':len(affected),'blocked_count':len(blocked),'blocked':blocked,'session_id':session['session_id']}
    def name_doppler_scan(self, case_id):
        rows=self.db.all('SELECT * FROM review_items WHERE case_id=?',[case_id]); created=[]
        existing={(r['item_id'],r['reason']) for r in self.db.all('SELECT item_id,reason FROM review_name_doppler_flags WHERE case_id=?',[case_id])}
        for r in rows:
            text=' '.join([r.get('title') or '',r.get('url') or '',r.get('snippet') or '',r.get('query') or '',r.get('triage_reason') or '']).lower(); reasons=[]
            if any(t in text for t in DOPPLER_TERMS): reasons.append('expliziter Namensdoppler-/Verwechslungsmarker')
            if float(r.get('score') or 0)<0.30 and float(r.get('quality_score') or 0)>=0.35: reasons.append('niedriger Treffer-Score bei brauchbarer Quellenqualität')
            if r.get('status')=='conflicting': reasons.append('bereits als widersprüchlich markiert')
            for reason in reasons:
                if (r['item_id'],reason) in existing: continue
                fid=new_id('dop'); markers=loads(r.get('markers_json'), [])
                self.db.execute("""INSERT INTO review_name_doppler_flags(flag_id,case_id,item_id,severity,reason,markers_json,created_at,resolved) VALUES(?,?,?,?,?,?,?,0)""", [fid,case_id,r['item_id'],'review',reason,dumps(markers),now_ts()])
                created.append({'flag_id':fid,'item_id':r['item_id'],'reason':reason})
        self.audit.log('scan','review_name_doppler_flags',case_id,case_id,{'created':len(created)})
        return {'created':len(created),'flags':created}
    def promote_ready_to_evidence(self, case_id, analyst_note, evidence_category='Identitätsanker', limit=25):
        if not (analyst_note or '').strip(): raise ValueError('Evidence-Promotion benötigt eine Pflichtnotiz.')
        rows=self.db.all("SELECT item_id FROM review_items WHERE case_id=? AND status='ready_for_evidence' ORDER BY quality_score DESC LIMIT ?",[case_id,int(limit)])
        affected=[]; blocked=[]; session=self.create_session(case_id,'ready',notes='Bulk Evidence Promotion')
        for r in rows:
            try: affected.append(self.decide_item(r['item_id'],'E',analyst_note,session['session_id'],evidence_category=evidence_category))
            except Exception as e: blocked.append({'item_id':r['item_id'],'reason':str(e)})
        return {'promoted_count':len(affected),'blocked_count':len(blocked),'session_id':session['session_id'],'items':affected,'blocked':blocked}
    def metrics_snapshot(self, case_id):
        counts={r['status']:r['n'] for r in self.db.all('SELECT status, COUNT(*) AS n FROM review_items WHERE case_id=? GROUP BY status',[case_id])}
        duplicate=int((self.db.one('SELECT COUNT(*) AS n FROM duplicate_clusters WHERE case_id=?',[case_id]) or {'n':0})['n'] or 0)
        doppler=int((self.db.one('SELECT COUNT(*) AS n FROM review_name_doppler_flags WHERE case_id=? AND resolved=0',[case_id]) or {'n':0})['n'] or 0)
        ready=int(counts.get('ready_for_evidence',0)); queue=sum(counts.get(s,0) for s in ['new','in_review','needs_source_review','ready_for_evidence','duplicate','sensitive','conflicting'])
        mid=new_id('rflm'); self.db.execute("""INSERT INTO review_fast_lane_metrics(metric_id,case_id,status_counts_json,queue_count,duplicate_count,doppler_flag_count,ready_for_evidence_count,created_at) VALUES(?,?,?,?,?,?,?,?)""", [mid,case_id,dumps(counts),queue,duplicate,doppler,ready,now_ts()])
        return {'metric_id':mid,'status_counts':counts,'queue_count':queue,'duplicate_count':duplicate,'doppler_flag_count':doppler,'ready_for_evidence_count':ready}
    def dashboard(self, case_id):
        self.name_doppler_scan(case_id); metrics=self.metrics_snapshot(case_id)
        doppler=self.db.all("SELECT f.*, r.title, r.url, r.status FROM review_name_doppler_flags f JOIN review_items r ON r.item_id=f.item_id WHERE f.case_id=? AND f.resolved=0 ORDER BY f.created_at DESC LIMIT 50",[case_id])
        return {'status':'review_fast_lane_ready','metrics':metrics,'shortcuts':self.shortcuts(),'queue':self.queue(case_id,'new',50),'ready_queue':self.queue(case_id,'ready',50),'doppler_flags':doppler,'next_action':'Queue prüfen: R/D/N/S/L/C/A/E – Evidence nur mit Pflichtnotiz und candidate-grade.'}
    def security_checks(self, case_id):
        bad=[]
        for d in self.db.all('SELECT * FROM review_fast_lane_decisions WHERE case_id=?',[case_id]):
            details=loads(d.get('details_json'), {})
            if not details.get('candidate_only'): bad.append({'decision_id':d['decision_id'],'issue':'missing_candidate_only_marker'})
            if d.get('action_key')=='E' and not d.get('analyst_note'): bad.append({'decision_id':d['decision_id'],'issue':'evidence_promotion_without_note'})
        gate='REVIEW_FAST_LANE_SECURITY_PASS' if not bad else 'REVIEW_FAST_LANE_SECURITY_REVIEW'
        return {'gate':gate,'issues':bad,'guardrails':['candidate_only','no_auto_identity_confirmation','evidence_note_required','no_private_source_shortcuts']}
