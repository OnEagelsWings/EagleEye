from __future__ import annotations
import hashlib, json, uuid
from datetime import datetime, timezone
from typing import Any

def _now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _id(p): return f'{p}_{uuid.uuid4().hex[:16]}'
def _json(v): return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)
def _clamp(v): return max(0.0, min(1.0, float(v)))

class ContradictionEngine118Service:
    TYPES={'identity','temporal','location','source','relation','logic'}
    STATES={'open','needs_review','confirmed','resolved','dismissed'}
    DECISIONS={'confirmed','resolved','dismissed'}
    def __init__(self, db, audit=None, kernel=None, graph=None, timeline=None, resolution=None):
        self.db,self.audit,self.kernel,self.graph,self.timeline,self.resolution=db,audit,kernel,graph,timeline,resolution
        self._schema()
    def _schema(self):
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS contradictions_118(
          contradiction_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, conflict_type TEXT NOT NULL,
          title TEXT NOT NULL, rationale TEXT NOT NULL, severity REAL NOT NULL, impact REAL NOT NULL,
          state TEXT NOT NULL, candidate_only INTEGER NOT NULL DEFAULT 1, created_by TEXT NOT NULL,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_contradictions118_case ON contradictions_118(case_id,state,conflict_type);
        CREATE TABLE IF NOT EXISTS contradiction_items_118(
          item_id TEXT PRIMARY KEY, contradiction_id TEXT NOT NULL, object_type TEXT NOT NULL,
          object_id TEXT NOT NULL, stance TEXT NOT NULL, summary TEXT NOT NULL, created_at TEXT NOT NULL,
          UNIQUE(contradiction_id,object_type,object_id,stance));
        CREATE TABLE IF NOT EXISTS counter_hypotheses_118(
          hypothesis_id TEXT PRIMARY KEY, contradiction_id TEXT NOT NULL, text TEXT NOT NULL,
          test_plan TEXT NOT NULL, status TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS contradiction_reviews_118(
          review_id TEXT PRIMARY KEY, contradiction_id TEXT NOT NULL UNIQUE, requested_by TEXT NOT NULL,
          requested_at TEXT NOT NULL, state TEXT NOT NULL, reviewed_by TEXT, reviewed_at TEXT,
          decision TEXT, decision_reason TEXT);
        CREATE TABLE IF NOT EXISTS contradiction_events_118(
          sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL, case_id TEXT NOT NULL,
          actor TEXT NOT NULL, event_type TEXT NOT NULL, object_id TEXT NOT NULL, payload_json TEXT NOT NULL,
          previous_hash TEXT NOT NULL, event_hash TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL);
        '''); self.db.conn.commit()
    def _log(self, case, actor, typ, obj, payload=None):
        payload=payload or {}; eid,ts=_id('cevt'),_now()
        row=self.db.one('SELECT event_hash FROM contradiction_events_118 WHERE case_id=? ORDER BY sequence DESC LIMIT 1',(case,))
        prev=row['event_hash'] if row else 'GENESIS'; digest=hashlib.sha256(_json([eid,case,actor,typ,obj,payload,prev,ts]).encode()).hexdigest()
        self.db.execute('INSERT INTO contradiction_events_118(event_id,case_id,actor,event_type,object_id,payload_json,previous_hash,event_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(eid,case,actor,typ,obj,_json(payload),prev,digest,ts))
        if self.kernel: self.kernel.event(case,actor,typ,'contradiction',obj,payload)
    def create(self, case_id, conflict_type, title, rationale, created_by, severity=.5, impact=.5):
        if conflict_type not in self.TYPES: raise ValueError('unsupported conflict type')
        if len(title.strip())<3 or len(rationale.strip())<12: raise ValueError('title and rationale required')
        cid,ts=_id('conf'),_now(); self.db.execute('INSERT INTO contradictions_118 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(cid,case_id,conflict_type,title.strip()[:500],rationale.strip()[:10000],_clamp(severity),_clamp(impact),'open',1,created_by,ts,ts)); self._log(case_id,created_by,'ContradictionCreated',cid,{'type':conflict_type}); return cid
    def _conf(self,cid):
        r=self.db.one('SELECT * FROM contradictions_118 WHERE contradiction_id=?',(cid,))
        if not r: raise ValueError('contradiction not found')
        return r
    def add_item(self,cid,object_type,object_id,stance,summary,actor):
        if stance not in {'supports_conflict','opposes_conflict','context'}: raise ValueError('invalid stance')
        c=self._conf(cid)
        if object_type=='relation' and not self.db.one('SELECT 1 FROM graph_relations_116 WHERE relation_id=? AND case_id=?',(object_id,c['case_id'])): raise ValueError('relation not found in case')
        if object_type=='timeline_event' and not self.db.one('SELECT 1 FROM timeline_events_117 WHERE event_id=? AND case_id=?',(object_id,c['case_id'])): raise ValueError('event not found in case')
        if object_type=='entity' and not self.db.one('SELECT 1 FROM entities_109 WHERE entity_id=? AND case_id=?',(object_id,c['case_id'])): raise ValueError('entity not found in case')
        if object_type=='source' and not self.db.one('SELECT 1 FROM graph_sources_116 WHERE source_id=? AND case_id=?',(object_id,c['case_id'])): raise ValueError('source not found in case')
        if object_type not in {'relation','timeline_event','entity','source','claim'}: raise ValueError('invalid object type')
        iid=_id('citem'); self.db.execute('INSERT INTO contradiction_items_118 VALUES(?,?,?,?,?,?,?)',(iid,cid,object_type,object_id,stance,summary.strip()[:4000],_now())); self._log(c['case_id'],actor,'ContradictionItemAdded',cid,{'object_type':object_type,'object_id':object_id,'stance':stance}); return iid
    def add_counter_hypothesis(self,cid,text,test_plan,actor):
        c=self._conf(cid)
        if len(text.strip())<8 or len(test_plan.strip())<8: raise ValueError('hypothesis and test plan required')
        hid=_id('chyp'); self.db.execute('INSERT INTO counter_hypotheses_118 VALUES(?,?,?,?,?,?,?)',(hid,cid,text.strip()[:4000],test_plan.strip()[:4000],'open',actor,_now())); self._log(c['case_id'],actor,'CounterHypothesisAdded',cid,{'hypothesis_id':hid}); return hid
    def detect_temporal(self,case_id,actor='system-analysis'):
        out=[]
        for x in self.timeline.temporal_conflicts(case_id) if self.timeline else []:
            cid=self.create(case_id,'temporal','Möglicher zeitlicher Konflikt','Zeitlich überlappende Ereignisse derselben Entität mit abweichendem Kontext erfordern menschliche Prüfung.',actor,x.get('severity',.6),.6)
            for eid in (x['left_event_id'],x['right_event_id']): self.add_item(cid,'timeline_event',eid,'supports_conflict','Zeitlich überlappendes Ereignis.',actor)
            self.add_counter_hypothesis(cid,'Die Ereignisse waren trotz Überschneidung vereinbar.','Uhrzeiten, Teilnahmeform, Reisezeiten und Quellenpräzision prüfen.',actor); out.append(cid)
        return out
    def request_review(self,cid,actor):
        c=self._conf(cid)
        if c['state'] != 'open': raise ValueError('contradiction is not open for review')
        count=self.db.one('SELECT COUNT(*) AS n FROM contradiction_items_118 WHERE contradiction_id=?',(cid,))['n']
        if count<2: raise ValueError('at least two conflict items required')
        rid=_id('crev'); self.db.execute('INSERT INTO contradiction_reviews_118 VALUES(?,?,?,?,?,?,?,?,?)',(rid,cid,actor,_now(),'needs_review',None,None,None,None)); self.db.execute("UPDATE contradictions_118 SET state='needs_review',updated_at=? WHERE contradiction_id=?",(_now(),cid)); self._log(c['case_id'],actor,'ContradictionReviewRequested',cid); return rid
    def review(self,review_id,reviewer,decision,reason):
        if decision not in self.DECISIONS: raise ValueError('invalid decision')
        r=self.db.one('SELECT r.*,c.case_id FROM contradiction_reviews_118 r JOIN contradictions_118 c ON c.contradiction_id=r.contradiction_id WHERE review_id=?',(review_id,))
        if not r: raise ValueError('review not found')
        if r['state'] != 'needs_review': raise ValueError('review already completed')
        if r['requested_by']==reviewer: raise PermissionError('independent reviewer required')
        if len(reason.strip())<12: raise ValueError('substantive reason required')
        self.db.execute("UPDATE contradiction_reviews_118 SET state='completed',reviewed_by=?,reviewed_at=?,decision=?,decision_reason=? WHERE review_id=?",(reviewer,_now(),decision,reason[:4000],review_id))
        self.db.execute('UPDATE contradictions_118 SET state=?,candidate_only=1,updated_at=? WHERE contradiction_id=?',(decision,_now(),r['contradiction_id']))
        self._log(r['case_id'],reviewer,'ContradictionReviewed',r['contradiction_id'],{'decision':decision}); return True
    def record(self,cid):
        c=self._conf(cid); return {'contradiction':c,'items':self.db.all('SELECT * FROM contradiction_items_118 WHERE contradiction_id=? ORDER BY created_at',(cid,)),'counter_hypotheses':self.db.all('SELECT * FROM counter_hypotheses_118 WHERE contradiction_id=? ORDER BY created_at',(cid,)),'review':self.db.one('SELECT * FROM contradiction_reviews_118 WHERE contradiction_id=?',(cid,))}
    def verify_chain(self,case_id):
        prev='GENESIS'
        for r in self.db.all('SELECT * FROM contradiction_events_118 WHERE case_id=? ORDER BY sequence',(case_id,)):
            digest=hashlib.sha256(_json([r['event_id'],r['case_id'],r['actor'],r['event_type'],r['object_id'],json.loads(r['payload_json']),prev,r['created_at']]).encode()).hexdigest()
            if r['previous_hash']!=prev or r['event_hash']!=digest: return False
            prev=r['event_hash']
        return True
