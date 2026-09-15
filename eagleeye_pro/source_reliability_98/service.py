from __future__ import annotations
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

class SourceReliability98Service:
    """Build 98.0: source reliability scoring for public-source findings."""
    TYPE_BASE={'official_register':90,'court_or_authority':88,'primary_source':82,'public_profile':60,'news':58,'archive':55,'search_result':35,'paste_or_unknown':25}
    def __init__(self, db: Database, audit: AuditService): self.db=db; self.audit=audit; self.ensure_schema()
    def ensure_schema(self):
        self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS source_reliability_98 (
          rating_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, source_ref TEXT NOT NULL, source_type TEXT NOT NULL,
          score INTEGER NOT NULL, rating TEXT NOT NULL, factors_json TEXT NOT NULL, warnings_json TEXT NOT NULL, created_at TEXT NOT NULL
        );"""); self.db.conn.commit()
    def rate(self, case_id, source_ref, source_type='paste_or_unknown', factors=None):
        factors=factors or {}; warnings=[]; score=self.TYPE_BASE.get(source_type,40)
        for key,bonus in [('archived',8),('primary_source',12),('timestamped',6),('hash_verified',8)]:
            if factors.get(key): score+=bonus
        if factors.get('anonymous'): score-=20; warnings.append('Anonymous or weakly attributable source.')
        if factors.get('user_generated'): score-=10; warnings.append('User-generated content requires corroboration.')
        if factors.get('stale'): score-=10; warnings.append('Source may be stale.')
        if factors.get('contradicted'): score-=25; warnings.append('Contradicting evidence exists.')
        score=max(0,min(100,int(score))); rating='high' if score>=75 else 'medium' if score>=50 else 'low' if score>=30 else 'very_low'
        rid=new_id('sr98'); self.db.execute('INSERT INTO source_reliability_98 VALUES(?,?,?,?,?,?,?,?,?)',[rid,case_id,source_ref,source_type,score,rating,dumps(factors),dumps(warnings),now_ts()])
        self.audit.log('rate','source_reliability_98',rid,case_id,{'source_ref':source_ref,'score':score,'rating':rating})
        return self.get(rid)
    def get(self, rid):
        r=self.db.one('SELECT * FROM source_reliability_98 WHERE rating_id=?',[rid])
        if not r: raise KeyError(rid)
        r['factors']=loads(r.pop('factors_json','{}'),{}); r['warnings']=loads(r.pop('warnings_json','[]'),[]); return r
    def latest_for_case(self, case_id):
        return [self.get(r['rating_id']) for r in self.db.all('SELECT rating_id FROM source_reliability_98 WHERE case_id=? ORDER BY created_at DESC',[case_id])]
