from __future__ import annotations
from datetime import datetime,timezone
import hashlib,json,re,secrets
BUILD='423.0';POLICY_ID='phase19.content-store-dedup.v423'
def _now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _sha_bytes(v):return hashlib.sha256(v).hexdigest()
def _norm_text(v):return re.sub(r'\s+',' ',v.strip().lower())
def _tokens(v):return set(re.findall(r'[\w-]{2,}',_norm_text(v),flags=re.UNICODE))
class ContentStore423:
 def __init__(self,db,audit,*,events422,actor='local-analyst'):self.db=db;self.audit=audit;self.events422=events422;self.actor=actor;self._init_schema()
 def _init_schema(self):
  self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS content_object_423(content_id TEXT PRIMARY KEY,sha256 TEXT NOT NULL UNIQUE,media_type TEXT NOT NULL,bytes_count INTEGER NOT NULL,text_fingerprint TEXT NOT NULL,token_json TEXT NOT NULL,metadata_json TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL);CREATE TABLE IF NOT EXISTS content_observation_423(observation_id TEXT PRIMARY KEY,content_id TEXT NOT NULL,event_id TEXT NOT NULL,case_id TEXT NOT NULL,source_id TEXT NOT NULL,target TEXT NOT NULL,duplicate_kind TEXT NOT NULL,similarity REAL NOT NULL,related_content_id TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL,FOREIGN KEY(content_id) REFERENCES content_object_423(content_id));CREATE INDEX IF NOT EXISTS idx_co423_case ON content_observation_423(case_id,content_id);CREATE INDEX IF NOT EXISTS idx_co423_event ON content_observation_423(event_id);""")
  cols={r['name'] for r in self.db.all('PRAGMA table_info(content_observation_423)')}
  if 'record_hash' not in cols:self.db.execute("ALTER TABLE content_observation_423 ADD COLUMN record_hash TEXT NOT NULL DEFAULT ''")
  for row in self.db.all("SELECT * FROM content_observation_423 WHERE record_hash='' OR record_hash IS NULL"):
   d=dict(row);self.db.execute('UPDATE content_observation_423 SET record_hash=? WHERE observation_id=?',(self._hash(d),d['observation_id']))
  self.db.conn.commit()
 def _hash(self,r):return _sha_bytes(_canon({k:r[k] for k in r if k!='record_hash'}).encode())
 def ingest(self,*,identity,event_id,content,media_type='text/plain',metadata=None,near_threshold=.88):
  if not identity:raise PermissionError('active identity required')
  if not 0.0<=float(near_threshold)<=1.0:raise ValueError('near_threshold must be between 0 and 1')
  actor=str(identity.get('user_id') or identity.get('username') or self.actor);ev=self.events422.get(event_id);raw=content.encode('utf-8') if isinstance(content,str) else bytes(content);digest=_sha_bytes(raw);actual_media=str(media_type or 'application/octet-stream');
  if ev.get('content_sha256') and ev['content_sha256']!=digest:raise ValueError('content digest does not match acquisition event')
  if int(ev.get('bytes_count') or 0) and int(ev['bytes_count'])!=len(raw):raise ValueError('content byte count does not match acquisition event')
  if ev.get('media_type') and str(ev['media_type'])!=actual_media:raise ValueError('content media type does not match acquisition event')
  existing=self.db.one('SELECT * FROM content_object_423 WHERE sha256=?',(digest,));kind='unique';related='';sim=1.0 if existing else 0.0
  if existing:obj=dict(existing);kind='exact';cid=obj['content_id'];related=cid
  else:
   text=raw.decode('utf-8',errors='replace') if str(media_type).startswith('text/') else '';toks=_tokens(text);best=(0.0,'')
   if toks:
    for row in self.db.all("SELECT content_id,token_json FROM content_object_423 WHERE token_json!='[]'"):
     other=set(json.loads(row['token_json']));score=len(toks&other)/len(toks|other) if toks|other else 0.0
     if score>best[0]:best=(score,row['content_id'])
   sim,related=best
   if sim>=float(near_threshold):kind='near'
   cid='cnt423_'+secrets.token_hex(10);r={'content_id':cid,'sha256':digest,'media_type':str(media_type or 'application/octet-stream'),'bytes_count':len(raw),'text_fingerprint':_sha_bytes(_norm_text(text).encode()) if text else '','token_json':_canon(sorted(toks)),'metadata_json':_canon(metadata or {}),'created_by':actor,'created_at':_now()};r['record_hash']=self._hash(r);self.db.execute('INSERT INTO content_object_423 VALUES(?,?,?,?,?,?,?,?,?,?)',tuple(r.values()))
  oid='obs423_'+secrets.token_hex(10);obs={'observation_id':oid,'content_id':cid,'event_id':event_id,'case_id':ev['case_id'],'source_id':ev['source_id'],'target':ev['target'],'duplicate_kind':kind,'similarity':float(sim),'related_content_id':related,'created_at':_now()};obs['record_hash']=self._hash(obs);self.db.execute('INSERT INTO content_observation_423 VALUES(?,?,?,?,?,?,?,?,?,?,?)',tuple(obs.values()));self.audit.log('content_ingested_423','content_object_423',cid,ev['case_id'],{'event_id':event_id,'duplicate_kind':kind,'related_content_id':related,'similarity':sim});return {'content_id':cid,'observation_id':oid,'sha256':digest,'duplicate_kind':kind,'similarity':float(sim),'related_content_id':related,'bytes_count':len(raw)}
 def verify_integrity(self):
  bad=[]
  for row in self.db.all('SELECT * FROM content_object_423'):
   d=dict(row)
   if self._hash(d)!=d['record_hash']:bad.append({'content_id':d['content_id'],'reason':'content_record_hash_mismatch'})
  for row in self.db.all('SELECT * FROM content_observation_423'):
   d=dict(row)
   if d.get('record_hash') and self._hash(d)!=d['record_hash']:bad.append({'observation_id':d['observation_id'],'reason':'observation_record_hash_mismatch'})
  return {'build':BUILD,'valid':not bad,'violations':bad}
 def status(self):
  n=self.db.one('SELECT COUNT(*) n FROM content_object_423')['n'];o=self.db.one('SELECT COUNT(*) n FROM content_observation_423')['n'];return {'build':BUILD,'policy':POLICY_ID,'content_objects':int(n),'observations':int(o),'integrity_valid':self.verify_integrity()['valid'],'stores_raw_payload':False,'direct_network_authority':False,'deduplication':['sha256_exact','token_jaccard_near']}
