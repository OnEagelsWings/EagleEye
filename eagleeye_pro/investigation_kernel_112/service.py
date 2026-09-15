from __future__ import annotations
import hashlib, json, re, secrets, uuid
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def uid(p): return f'{p}_{uuid.uuid4().hex}'
def js(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)

class InvestigationKernel112:
    ENTITY_TYPES={'person','organisation','location','domain','email','phone','social_account','document','image','vehicle','wallet','event','other'}
    ROLES={'administrator','lead_investigator','researcher','reviewer','observer'}
    PERMS={'administrator':{'*'},'lead_investigator':{'case.read','case.write','mission.approve','hypothesis.review','export.request'},'researcher':{'case.read','research.run','notebook.write'},'reviewer':{'case.read','evidence.review','hypothesis.review','export.approve'},'observer':{'case.read'}}
    DUAL={'export.release','cloud.transfer','evidence.delete','report.finalize'}
    def __init__(self,db,audit=None): self.db=db; self.audit=audit; self.ensure_schema()
    def ensure_schema(self):
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS entities_109(entity_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,entity_type TEXT NOT NULL,label TEXT NOT NULL,canonical_key TEXT NOT NULL,attributes_json TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'candidate',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(case_id,entity_type,canonical_key));
        CREATE INDEX IF NOT EXISTS idx_entities109_case_type ON entities_109(case_id,entity_type);
        CREATE TABLE IF NOT EXISTS entity_links_109(link_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,source_id TEXT NOT NULL,target_id TEXT NOT NULL,link_type TEXT NOT NULL,confidence REAL NOT NULL DEFAULT .5,status TEXT NOT NULL DEFAULT 'candidate',evidence_refs_json TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(case_id,source_id,target_id,link_type));
        CREATE TABLE IF NOT EXISTS event_journal_109(sequence INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT UNIQUE NOT NULL,case_id TEXT,actor TEXT NOT NULL,event_type TEXT NOT NULL,object_type TEXT NOT NULL,object_id TEXT,payload_json TEXT NOT NULL,previous_hash TEXT NOT NULL,event_hash TEXT UNIQUE NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS jobs_109(job_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,job_type TEXT NOT NULL,payload_json TEXT NOT NULL,state TEXT NOT NULL,priority INTEGER NOT NULL DEFAULT 100,attempts INTEGER NOT NULL DEFAULT 0,max_attempts INTEGER NOT NULL DEFAULT 3,lease_owner TEXT,lease_until TEXT,result_json TEXT,error_text TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_jobs109_queue ON jobs_109(state,priority,created_at);
        CREATE TABLE IF NOT EXISTS notebook_109(entry_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,actor TEXT NOT NULL,entry_type TEXT NOT NULL,title TEXT NOT NULL,body TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'active',related_ids_json TEXT NOT NULL,created_at TEXT NOT NULL,supersedes_id TEXT);
        CREATE TABLE IF NOT EXISTS specialist_runs_110(run_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,target_id TEXT,agent_type TEXT NOT NULL,input_json TEXT NOT NULL,output_json TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'candidate',created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS users_111(user_id TEXT PRIMARY KEY,username TEXT UNIQUE NOT NULL,display_name TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS case_roles_111(case_id TEXT NOT NULL,user_id TEXT NOT NULL,role TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(case_id,user_id));
        CREATE TABLE IF NOT EXISTS approvals_111(approval_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,action TEXT NOT NULL,object_id TEXT NOT NULL,requested_by TEXT NOT NULL,approved_by TEXT,status TEXT NOT NULL,nonce_hash TEXT NOT NULL,expires_at TEXT NOT NULL,created_at TEXT NOT NULL,decided_at TEXT);
        CREATE TABLE IF NOT EXISTS evidence_versions_111(version_id TEXT PRIMARY KEY,evidence_id TEXT NOT NULL,case_id TEXT NOT NULL,version_no INTEGER NOT NULL,content_hash TEXT NOT NULL,metadata_json TEXT NOT NULL,storage_ref TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(evidence_id,version_no));
        CREATE TABLE IF NOT EXISTS ai_audit_111(ai_event_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,actor TEXT NOT NULL,agent TEXT NOT NULL,model TEXT NOT NULL,prompt_hash TEXT NOT NULL,prompt_redacted TEXT NOT NULL,parameters_json TEXT NOT NULL,source_refs_json TEXT NOT NULL,response_hash TEXT NOT NULL,response_redacted TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS hypotheses_112(hypothesis_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,title TEXT NOT NULL,statement TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'draft',prior REAL NOT NULL DEFAULT .5,confidence REAL NOT NULL DEFAULT .5,created_by TEXT NOT NULL,created_at TEXT NOT NULL,reviewed_by TEXT,reviewed_at TEXT);
        CREATE TABLE IF NOT EXISTS hypothesis_evidence_112(binding_id TEXT PRIMARY KEY,hypothesis_id TEXT NOT NULL,evidence_ref TEXT NOT NULL,direction TEXT NOT NULL,weight REAL NOT NULL,reliability REAL NOT NULL,independence_group TEXT NOT NULL,rationale TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(hypothesis_id,evidence_ref,direction));
        CREATE TABLE IF NOT EXISTS hypothesis_dossiers_112(dossier_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,target_id TEXT,hypothesis_id TEXT NOT NULL,content_json TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'draft_for_lead_review',created_at TEXT NOT NULL);
        """); self.db.conn.commit()
    def event(self,case,actor,kind,obj_type,obj_id=None,payload=None):
        eid=uid('evt'); ts=now(); payload=payload or {}
        with self.db.conn:
            row=self.db.conn.execute('SELECT event_hash FROM event_journal_109 ORDER BY sequence DESC LIMIT 1').fetchone(); prev=row[0] if row else 'GENESIS'
            material=js([eid,case,actor,kind,obj_type,obj_id,payload,prev,ts]); h=hashlib.sha256(material.encode()).hexdigest()
            self.db.conn.execute('INSERT INTO event_journal_109(event_id,case_id,actor,event_type,object_type,object_id,payload_json,previous_hash,event_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(eid,case,actor,kind,obj_type,obj_id,js(payload),prev,h,ts))
        return eid
    def verify_journal(self):
        prev='GENESIS'; bad=[]; rows=self.db.all('SELECT * FROM event_journal_109 ORDER BY sequence')
        for r in rows:
            payload=json.loads(r['payload_json']); expected=hashlib.sha256(js([r['event_id'],r['case_id'],r['actor'],r['event_type'],r['object_type'],r['object_id'],payload,prev,r['created_at']]).encode()).hexdigest()
            if r['previous_hash']!=prev or r['event_hash']!=expected: bad.append(r['event_id'])
            prev=r['event_hash']
        return {'valid':not bad,'errors':bad,'events':len(rows)}
    def entity(self,case,typ,label,key,attrs=None,actor='lead'):
        if typ not in self.ENTITY_TYPES: raise ValueError('unsupported entity type')
        key=' '.join(str(key).lower().split())
        if not key or len(key)>512: raise ValueError('invalid canonical key')
        eid=uid('ent'); ts=now()
        with self.db.conn:
            self.db.conn.execute('INSERT INTO entities_109(entity_id,case_id,entity_type,label,canonical_key,attributes_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(case_id,entity_type,canonical_key) DO UPDATE SET label=excluded.label,attributes_json=excluded.attributes_json,updated_at=excluded.updated_at',(eid,case,typ,label[:500],key,js(attrs or {}),ts,ts))
            eid=self.db.conn.execute('SELECT entity_id FROM entities_109 WHERE case_id=? AND entity_type=? AND canonical_key=?',(case,typ,key)).fetchone()[0]
        self.event(case,actor,'EntityUpserted','entity',eid,{'type':typ}); return eid
    def link(self,case,source,target,kind,confidence=.5,evidence=None,actor='lead'):
        if source==target: raise ValueError('self-link prohibited')
        lid=uid('lnk'); c=max(0,min(1,float(confidence)))
        self.db.execute('INSERT INTO entity_links_109 VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(case_id,source_id,target_id,link_type) DO UPDATE SET confidence=excluded.confidence,evidence_refs_json=excluded.evidence_refs_json',(lid,case,source,target,kind[:120],c,'candidate',js(evidence or []),now())); self.event(case,actor,'EntityLinked','link',lid,{'kind':kind}); return lid
    def enqueue(self,case,kind,payload,priority=100,max_attempts=3):
        jid=uid('job'); ts=now(); self.db.execute('INSERT INTO jobs_109(job_id,case_id,job_type,payload_json,state,priority,max_attempts,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',(jid,case,kind,js(payload),'queued',int(priority),max(1,min(10,int(max_attempts))),ts,ts)); self.event(case,'lead','JobQueued','job',jid); return jid
    def lease(self,worker,until):
        with self.db.conn:
            row=self.db.conn.execute("SELECT job_id FROM jobs_109 WHERE state='queued' AND attempts<max_attempts ORDER BY priority,created_at LIMIT 1").fetchone()
            if not row:return None
            cur=self.db.conn.execute("UPDATE jobs_109 SET state='leased',lease_owner=?,lease_until=?,attempts=attempts+1,updated_at=? WHERE job_id=? AND state='queued'",(worker,until,now(),row[0]))
            return self.db.one('SELECT * FROM jobs_109 WHERE job_id=?',(row[0],)) if cur.rowcount==1 else None
    def finish(self,job_id,result=None,error=None):
        r=self.db.one('SELECT * FROM jobs_109 WHERE job_id=?',(job_id,));
        if not r or r['state']!='leased': raise ValueError('job not leased')
        state='failed' if error else 'completed'; self.db.execute('UPDATE jobs_109 SET state=?,result_json=?,error_text=?,updated_at=? WHERE job_id=?',(state,js(result or {}),str(error)[:4000] if error else None,now(),job_id)); self.event(r['case_id'],r['lease_owner'] or 'worker','JobFinished','job',job_id,{'state':state})
    def note(self,case,actor,kind,title,body,related=None):
        nid=uid('note'); self.db.execute('INSERT INTO notebook_109(entry_id,case_id,actor,entry_type,title,body,related_ids_json,created_at) VALUES(?,?,?,?,?,?,?,?)',(nid,case,actor,kind,title[:300],body[:20000],js(related or []),now())); self.event(case,actor,'NotebookEntryAdded','note',nid); return nid
    def specialist(self,case,target,agent,records):
        if agent=='timeline':
            out=[{'date':m.group(0),'source':r.get('url'),'status':'candidate'} for r in records for m in re.finditer(r'\b(?:19|20)\d{2}(?:-\d{2}-\d{2})?\b',' '.join(str(r.get(k,'')) for k in ('title','snippet','statement')))]
        elif agent=='source_quality':
            out=[]
            for r in records:
                u=r.get('url') or ''; host=(urlparse(u).hostname or '').lower(); score=.35+(.1 if u.startswith('https://') else 0)+(.35 if host.endswith(('.gov','.gov.uk','.bund.de','.europa.eu')) else 0); out.append({'url':u,'score':round(min(score,1),2),'status':'candidate'})
        elif agent=='identity':
            if len(records)!=2: raise ValueError('identity agent needs two records')
            a=set(re.findall(r'[\w@.-]+',js(records[0]).lower())); b=set(re.findall(r'[\w@.-]+',js(records[1]).lower())); out=[{'similarity':round(len(a&b)/len(a|b),3) if a|b else 0,'status':'candidate','warning':'similarity is not identity proof'}]
        elif agent=='contradiction':
            groups={}
            for r in records: groups.setdefault((str(r.get('subject','')).lower(),str(r.get('predicate','')).lower()),[]).append(r)
            out=[{'subject':k[0],'predicate':k[1],'objects':sorted({str(x.get('object','')).lower() for x in v}),'status':'needs_review'} for k,v in groups.items() if len({str(x.get('object','')).lower() for x in v})>1]
        else: raise ValueError('unknown specialist')
        rid=uid('run'); self.db.execute('INSERT INTO specialist_runs_110 VALUES(?,?,?,?,?,?,?,?)',(rid,case,target,agent,js(records),js(out),'candidate',now())); self.event(case,'agent',agent+'Completed','specialist_run',rid,{'count':len(out)}); return {'run_id':rid,'candidates':out}
    def user(self,username,name):
        x=uid('usr'); self.db.execute('INSERT INTO users_111 VALUES(?,?,?,?,?)',(x,username.lower().strip(),name[:200],1,now())); return x
    def role(self,case,user,role):
        if role not in self.ROLES: raise ValueError('invalid role')
        self.db.execute('INSERT INTO case_roles_111 VALUES(?,?,?,?) ON CONFLICT(case_id,user_id) DO UPDATE SET role=excluded.role',(case,user,role,now())); self.event(case,'admin','RoleAssigned','user',user,{'role':role})
    def allowed(self,case,user,perm):
        r=self.db.one('SELECT role FROM case_roles_111 WHERE case_id=? AND user_id=?',(case,user)); return bool(r and ('*' in self.PERMS[r['role']] or perm in self.PERMS[r['role']]))
    def approval(self,case,action,obj,requester,minutes=15):
        if action not in self.DUAL: raise ValueError('dual control not required')
        aid=uid('apr'); nonce=secrets.token_urlsafe(24); exp=(datetime.now(timezone.utc)+timedelta(minutes=max(1,min(60,minutes)))).isoformat(timespec='seconds'); self.db.execute('INSERT INTO approvals_111 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(aid,case,action,obj,requester,None,'pending',hashlib.sha256(nonce.encode()).hexdigest(),exp,now(),None)); return {'approval_id':aid,'nonce':nonce}
    def approve(self,aid,reviewer,nonce):
        r=self.db.one('SELECT * FROM approvals_111 WHERE approval_id=?',(aid,));
        if not r or r['status']!='pending': raise ValueError('approval unavailable')
        if r['requested_by']==reviewer: raise PermissionError('second person required')
        if datetime.fromisoformat(r['expires_at'])<datetime.now(timezone.utc): raise ValueError('expired')
        if not secrets.compare_digest(r['nonce_hash'],hashlib.sha256(nonce.encode()).hexdigest()): raise PermissionError('invalid secret')
        with self.db.conn:
            cur=self.db.conn.execute("UPDATE approvals_111 SET status='approved',approved_by=?,decided_at=? WHERE approval_id=? AND status='pending'",(reviewer,now(),aid))
            if cur.rowcount!=1: raise ValueError('already consumed')
        return True
    def evidence_version(self,case,evidence,content,metadata,storage,actor):
        if not isinstance(content,(bytes,bytearray)): raise TypeError('bytes required')
        n=self.db.one('SELECT COALESCE(MAX(version_no),0)+1 n FROM evidence_versions_111 WHERE evidence_id=?',(evidence,))['n']; vid=uid('evv'); h=hashlib.sha256(content).hexdigest(); self.db.execute('INSERT INTO evidence_versions_111 VALUES(?,?,?,?,?,?,?,?,?)',(vid,evidence,case,n,h,js(metadata),storage,actor,now())); return {'version_id':vid,'version_no':n,'sha256':h}
    def ai_log(self,case,actor,agent,model,prompt,params,sources,response):
        def clean(s): return re.sub(r'(?i)(api[_ -]?key|token|password)\s*[:=]\s*\S+',r'\1=[REDACTED]',str(s))[:20000]
        p,q=clean(prompt),clean(response); eid=uid('aia'); self.db.execute('INSERT INTO ai_audit_111 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(eid,case,actor,agent,model,hashlib.sha256(str(prompt).encode()).hexdigest(),p,js(params),js(sources),hashlib.sha256(str(response).encode()).hexdigest(),q,now())); return eid
    def hypothesis(self,case,title,statement,actor,prior=.5):
        hid=uid('hyp'); p=max(.01,min(.99,float(prior))); self.db.execute('INSERT INTO hypotheses_112(hypothesis_id,case_id,title,statement,prior,confidence,created_by,created_at) VALUES(?,?,?,?,?,?,?,?)',(hid,case,title[:300],statement[:10000],p,p,actor,now())); self.event(case,actor,'HypothesisCreated','hypothesis',hid); return hid
    def bind(self,hyp,evidence,direction,weight,reliability,group,rationale):
        if direction not in {'supports','contradicts','neutral'}: raise ValueError('invalid direction')
        bid=uid('hbe'); self.db.execute('INSERT INTO hypothesis_evidence_112 VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(hypothesis_id,evidence_ref,direction) DO UPDATE SET weight=excluded.weight,reliability=excluded.reliability,rationale=excluded.rationale',(bid,hyp,evidence,direction,max(0,min(1,float(weight))),max(0,min(1,float(reliability))),group[:200],rationale[:2000],now())); return self.recalculate(hyp)
    def recalculate(self,hyp):
        h=self.db.one('SELECT * FROM hypotheses_112 WHERE hypothesis_id=?',(hyp,)); rows=self.db.all('SELECT * FROM hypothesis_evidence_112 WHERE hypothesis_id=?',(hyp,)); odds=h['prior']/(1-h['prior']); groups={}
        for r in rows: groups[(r['independence_group'],r['direction'])]=max(groups.get((r['independence_group'],r['direction']),0),r['weight']*r['reliability'])
        for (_,d),s in groups.items(): odds=odds*(1+4*s) if d=='supports' else odds/(1+4*s) if d=='contradicts' else odds
        c=max(.01,min(.99,odds/(1+odds))); self.db.execute('UPDATE hypotheses_112 SET confidence=? WHERE hypothesis_id=?',(c,hyp)); return c
    def dossier(self,case,target,hyp):
        h=self.db.one('SELECT * FROM hypotheses_112 WHERE hypothesis_id=? AND case_id=?',(hyp,case));
        if not h: raise ValueError('missing hypothesis')
        rows=self.db.all('SELECT * FROM hypothesis_evidence_112 WHERE hypothesis_id=?',(hyp,)); content={'epistemic_status':'hypothesis_not_fact','hypothesis':h,'supporting':[r for r in rows if r['direction']=='supports'],'contradicting':[r for r in rows if r['direction']=='contradicts'],'mandatory_checks':['verify identity','preserve sources','test alternative explanation','review date and context'],'lead_decision_required':True}; did=uid('dos'); self.db.execute('INSERT INTO hypothesis_dossiers_112 VALUES(?,?,?,?,?,?,?)',(did,case,target,hyp,js(content),'draft_for_lead_review',now())); return {'dossier_id':did,**content}
    def dashboard(self,case):
        count=lambda t:self.db.one(f'SELECT COUNT(*) n FROM {t} WHERE case_id=?',(case,))['n']
        return {'entities':count('entities_109'),'links':count('entity_links_109'),'jobs':count('jobs_109'),'notebook':count('notebook_109'),'hypotheses':count('hypotheses_112'),'journal':self.verify_journal()}
