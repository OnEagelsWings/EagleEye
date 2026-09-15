from __future__ import annotations
from typing import Any, Dict
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
DEFAULT_SCENARIOS=[
 {'key':'name_doppler','title':'Namensdoppler-Falle','objective':'Trenne gleichnamige Personen anhand von Quellen, Zeit und Kontext.','checks':['candidate_not_claim','identity_before_claim','counter_evidence_visible']},
 {'key':'overclaiming','title':'Overclaiming erkennen','objective':'Schwache Hinweise nicht als starke Behauptung exportieren.','checks':['claim_grade','source_chain','redaction']},
 {'key':'paste_url_review','title':'Copy-Paste-Fund prüfen','objective':'Pasted URL als Kandidat importieren, Capture/Evidence verknüpfen, dann prüfen.','checks':['url_policy','evidence_hash','manual_review']},
]
class AnalystTraining93Service:
    """Build 93.0: analyst training mode with demo scenarios and checklist-based scoring."""
    def __init__(self,db:Database,audit:AuditService): self.db=db; self.audit=audit; self.ensure_schema(); self.seed_defaults()
    def ensure_schema(self):
        self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS training_scenarios_93(scenario_id TEXT PRIMARY KEY, key TEXT UNIQUE, title TEXT NOT NULL, objective TEXT NOT NULL, checks_json TEXT NOT NULL, created_at TEXT NOT NULL); CREATE TABLE IF NOT EXISTS training_runs_93(run_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, scenario_key TEXT NOT NULL, analyst TEXT NOT NULL, answers_json TEXT NOT NULL, score INTEGER NOT NULL, feedback_json TEXT NOT NULL, created_at TEXT NOT NULL);"""); self.db.conn.commit()
    def seed_defaults(self):
        for s in DEFAULT_SCENARIOS:
            if not self.db.one('SELECT key FROM training_scenarios_93 WHERE key=?',[s['key']]):
                self.db.execute('INSERT INTO training_scenarios_93 VALUES(?,?,?,?,?,?)',[new_id('scenario93'),s['key'],s['title'],s['objective'],dumps(s['checks']),now_ts()])
    def scenarios(self):
        rows=self.db.all('SELECT * FROM training_scenarios_93 ORDER BY key')
        for r in rows: r['checks']=loads(r.pop('checks_json','[]'),[])
        return rows
    def start(self,case_id:str,scenario_key:str,analyst:str='local-analyst')->Dict[str,Any]:
        s=self.db.one('SELECT * FROM training_scenarios_93 WHERE key=?',[scenario_key])
        if not s: raise KeyError(scenario_key)
        return {'case_id':case_id,'scenario_key':scenario_key,'analyst':analyst,'title':s['title'],'objective':s['objective'],'checklist':loads(s['checks_json'],[]),'status':'started'}
    def grade(self,case_id:str,scenario_key:str,answers:Dict[str,Any],analyst:str='local-analyst')->Dict[str,Any]:
        s=self.db.one('SELECT * FROM training_scenarios_93 WHERE key=?',[scenario_key])
        if not s: raise KeyError(scenario_key)
        checks=loads(s['checks_json'],[]); passed=[c for c in checks if answers.get(c) in (True,'yes','passed')]; score=int(100*len(passed)/max(1,len(checks))); feedback=[{'check':c,'message':'Review this capability before using it in a live case.'} for c in checks if c not in passed]
        rid=new_id('train93'); self.db.execute('INSERT INTO training_runs_93 VALUES(?,?,?,?,?,?,?,?)',[rid,case_id,scenario_key,analyst,dumps(answers),score,dumps(feedback),now_ts()]); self.audit.log('grade','analyst_training_93',rid,case_id,{'scenario':scenario_key,'score':score}); return {'run_id':rid,'case_id':case_id,'scenario_key':scenario_key,'score':score,'passed':passed,'feedback':feedback}
