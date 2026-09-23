from __future__ import annotations
from datetime import datetime,timezone
from urllib.parse import urlparse
import hashlib,json,secrets
BUILD='429.0';POLICY_ID='phase19.news-connector-layer.v429'
def _now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v):return hashlib.sha256(_canon(v).encode()).hexdigest()
def _iso(v):
 try:
  d=datetime.fromisoformat(str(v).replace('Z','+00:00'));d=d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc);return d.isoformat(timespec='seconds')
 except Exception:raise ValueError('published_at must be ISO-8601')
class NewsConnectors429:
 def __init__(self,db,audit,*,registry421,events422,content423,actor='local-analyst'):self.db=db;self.audit=audit;self.registry421=registry421;self.events422=events422;self.content423=content423;self.actor=actor;self._init_schema()
 def _init_schema(self):
  self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS news_item_429(news_item_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,source_id TEXT NOT NULL,event_id TEXT NOT NULL,content_id TEXT NOT NULL,canonical_url TEXT NOT NULL,title TEXT NOT NULL,publisher TEXT NOT NULL,author TEXT NOT NULL,published_at TEXT NOT NULL,language TEXT NOT NULL,external_id TEXT NOT NULL,connector_kind TEXT NOT NULL,metadata_json TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL);CREATE INDEX IF NOT EXISTS idx_news429_case_time ON news_item_429(case_id,published_at);CREATE INDEX IF NOT EXISTS idx_news429_external ON news_item_429(source_id,external_id);""")
  for row in self.db.all('SELECT * FROM news_item_429'):
   d=dict(row);canon=_iso(d['published_at'])
   if canon!=d['published_at']:
    d['published_at']=canon;d['record_hash']=self._rh(d);self.db.execute('UPDATE news_item_429 SET published_at=?,record_hash=? WHERE news_item_id=?',(canon,d['record_hash'],d['news_item_id']))
  self.db.conn.commit()
 def _rh(self,r):return _hash({k:r[k] for k in r if k!='record_hash'})
 def ingest_item(self,*,identity,case_id,source_id,event_id,content_id,canonical_url,title,publisher='',author='',published_at,language='',external_id='',connector_kind='rss',metadata=None):
  if not identity:raise PermissionError('active identity required')
  src=self.registry421.get(source_id)
  if src['source_type'] not in {'news','rss','api'}:raise ValueError('source is not news-capable')
  if connector_kind not in {'rss','atom','api','dataset','manual'}:raise ValueError('unsupported connector_kind')
  u=urlparse(str(canonical_url))
  if u.scheme not in {'http','https'} or not u.netloc or (u.hostname or '').lower().endswith('.onion'):raise ValueError('canonical_url must be public http(s)')
  ev=self.events422.get(event_id)
  if ev['case_id']!=case_id or ev['source_id']!=source_id:raise ValueError('news event does not match case/source')
  if not self.db.one('SELECT 1 FROM content_observation_423 WHERE event_id=? AND content_id=?',(event_id,content_id)):raise ValueError('content is not linked to acquisition event')
  ts=_iso(published_at);eid=str(external_id or '').strip()
  if eid and self.db.one('SELECT 1 FROM news_item_429 WHERE source_id=? AND external_id=?',(source_id,eid)):raise ValueError('duplicate source external_id')
  actor=str(identity.get('user_id') or identity.get('username') or self.actor);r={'news_item_id':'news429_'+secrets.token_hex(10),'case_id':case_id,'source_id':source_id,'event_id':event_id,'content_id':content_id,'canonical_url':str(canonical_url),'title':str(title).strip(),'publisher':str(publisher).strip(),'author':str(author).strip(),'published_at':ts,'language':str(language).lower().strip(),'external_id':eid,'connector_kind':connector_kind,'metadata_json':_canon(metadata or {}),'created_by':actor,'created_at':_now()}
  if not r['title']:raise ValueError('title required')
  r['record_hash']=self._rh(r);self.db.execute('INSERT INTO news_item_429 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',tuple(r.values()));self.audit.log('news_item_ingested_429','news_item_429',r['news_item_id'],case_id,{'publisher':r['publisher'],'published_at':ts,'connector_kind':connector_kind});return {**r,'metadata':metadata or {}}
 def case_items(self,case_id):return [dict(r) for r in self.db.all('SELECT * FROM news_item_429 WHERE case_id=? ORDER BY julianday(published_at) DESC,created_at DESC',(case_id,))]
 def verify_integrity(self):
  bad=[]
  for row in self.db.all('SELECT * FROM news_item_429'):
   d=dict(row)
   if self._rh(d)!=d['record_hash']:bad.append({'news_item_id':d['news_item_id'],'reason':'record_hash_mismatch'})
  return {'build':BUILD,'valid':not bad,'violations':bad}
 def status(self):
  n=self.db.one('SELECT COUNT(*) n FROM news_item_429')['n'];return {'build':BUILD,'policy':POLICY_ID,'news_items':int(n),'integrity_valid':self.verify_integrity()['valid'],'supported_connector_kinds':['rss','atom','api','dataset','manual'],'network_executor_implemented':False,'publisher_claim_is_not_independent_corroboration':True,'production_release_ready':False}
