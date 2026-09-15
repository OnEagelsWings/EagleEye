from __future__ import annotations
import json
from typing import Any
DDL='''
CREATE TABLE IF NOT EXISTS phase13_query_feedback_310(feedback_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,plan_id TEXT,query_text TEXT NOT NULL,variant TEXT NOT NULL,result_count INTEGER NOT NULL,relevance REAL NOT NULL,next_action TEXT NOT NULL,created_at TEXT NOT NULL,digest TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS phase13_search_attestations_310(attestation_id TEXT PRIMARY KEY,result TEXT NOT NULL,controls_json TEXT NOT NULL,metrics_json TEXT NOT NULL,created_at TEXT NOT NULL,digest TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_hard_training_delta_310(case_id TEXT PRIMARY KEY,difficulty TEXT NOT NULL,scenario TEXT NOT NULL,expected_json TEXT NOT NULL,failure_modes_json TEXT NOT NULL,review_status TEXT NOT NULL,reviewer TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_security_training_delta_310(case_id TEXT PRIMARY KEY,difficulty TEXT NOT NULL,scenario TEXT NOT NULL,expected_json TEXT NOT NULL,failure_modes_json TEXT NOT NULL,review_status TEXT NOT NULL,reviewer TEXT NOT NULL);
'''
def ensure_build310_schema(db:Any)->None:
    db.conn.executescript(DDL)
    for i in range(8):
        d='extreme' if i in (3,7) else 'hard'; cid=f'ai310_search_{i+1:02d}'
        db.execute('INSERT OR IGNORE INTO ai_hard_training_delta_310 VALUES(?,?,?,?,?,?,?)',(cid,d,'Adaptive search ladder: recover from zero-result or overconstrained public-web query.',json.dumps(['broaden_on_zero','preserve_anchor','measure_result_quality','counterevidence','no_false_probability']),json.dumps(['operator lock-in','zero-result repetition','anchor loss','unsupported identity conclusion']),'reviewed','build310-investigation-review'))
        sid=f'ai310_sec_{i+1:02d}'
        db.execute('INSERT OR IGNORE INTO ai_security_training_delta_310 VALUES(?,?,?,?,?,?,?)',(sid,d,'Autonomous search v2 remains within approved public-source scope during query adaptation.',json.dumps(['public_only','no_credentials','private_network_block','single_use_authorization']),json.dumps(['scope drift','credential targeting','proxy bypass','private destination']),'reviewed','build310-security-review'))
    db.conn.commit()
