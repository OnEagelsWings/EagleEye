from __future__ import annotations
from datetime import datetime,timezone
from difflib import SequenceMatcher
from urllib.parse import urlparse
import hashlib,json,re,secrets

BUILD='437.0'
POLICY_ID='phase19.cross-source-entity-resolution.v437'
REVIEW_CLASSES={'strong_review_candidate','possible_review_candidate','weak_review_candidate','likely_distinct'}
SUPPORTED_NEWS_KINDS={
 'person':'person','people':'person','individual':'person',
 'organization':'organisation','organisation':'organisation','org':'organisation','company':'organisation','ngo':'organisation','foundation':'organisation','association':'organisation','government':'organisation','media':'organisation',
 'account':'account','username':'account','handle':'account',
 'email':'email','phone':'phone','domain':'domain'
}
def _now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v):return hashlib.sha256(_canon(v).encode()).hexdigest()
def _clean(v,n=1000):return re.sub(r'\s+',' ',str(v or '')).strip()[:n]
def _domain(v):
 try:return (urlparse(str(v or '')).hostname or '').casefold()
 except Exception:return ''
def _clamp(v,lo=0.0,hi=1.0):return max(lo,min(hi,float(v)))

class CrossSourceEntityResolution437:
 def __init__(self,db,audit,*,registry421,events422,content423,news429,news430,social432,organization433,registry434,surface436,entity371,base115,governance,actor='local-analyst'):
  self.db=db;self.audit=audit;self.registry421=registry421;self.events422=events422;self.content423=content423;self.news429=news429;self.news430=news430;self.social432=social432;self.organization433=organization433;self.registry434=registry434;self.surface436=surface436;self.entity371=entity371;self.base115=base115;self.governance=governance;self.actor=actor;self._init_schema()
 def _init_schema(self):
  self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS phase19_entity_binding_437(binding_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,source_kind TEXT NOT NULL,source_object_id TEXT NOT NULL,resolution_entity_id TEXT NOT NULL,source_id TEXT NOT NULL,event_id TEXT NOT NULL,content_id TEXT NOT NULL,source_ref TEXT NOT NULL,reliability REAL NOT NULL,provenance_json TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL,UNIQUE(case_id,source_kind,source_object_id));CREATE INDEX IF NOT EXISTS idx_peb437_case ON phase19_entity_binding_437(case_id,resolution_entity_id);CREATE INDEX IF NOT EXISTS idx_peb437_source ON phase19_entity_binding_437(case_id,source_id);
CREATE TABLE IF NOT EXISTS phase19_resolution_run_437(run_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,bindings_synced INTEGER NOT NULL,entities_considered INTEGER NOT NULL,pairs_compared INTEGER NOT NULL,review_candidates INTEGER NOT NULL,likely_distinct INTEGER NOT NULL,result_json TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL);CREATE INDEX IF NOT EXISTS idx_prr437_case ON phase19_resolution_run_437(case_id,created_at);""");self.db.conn.commit()
 def _rh(self,r):return _hash({k:r[k] for k in r if k!='record_hash'})
 def _identity(self,identity):
  if not isinstance(identity,dict) or not identity.get('username') or not identity.get('user_id'):raise PermissionError('canonical active identity required')
  try:u=self.governance.identity.public_user(str(identity['username']))
  except (KeyError,ValueError):raise PermissionError('canonical active identity required')
  if not u.get('active') or str(u.get('user_id'))!=str(identity.get('user_id')):raise PermissionError('canonical active identity required')
  return {**u,'session_id':str(identity.get('session_id') or 'entity437')}
 def _authorize(self,identity,case_id,capability='research.run',object_id=''):
  ident=self._identity(identity);self.governance.authorize(ident,case_id=str(case_id),capability=capability,object_type='cross_source_entity_resolution_437',object_id=str(object_id or case_id));return ident
 def _preflight(self):
  checks={'source_registry':self.registry421.verify_integrity()['valid'],'acquisition_events':self.events422.verify_integrity()['valid'],'content_store':self.content423.verify_integrity()['valid'],'news':self.news429.verify_integrity()['valid'],'news_extraction':self.news430.verify_integrity()['valid'],'social':self.social432.verify_integrity()['valid'],'organizations':self.organization433.verify_integrity()['valid'],'registry_organization':self.registry434.verify_integrity()['valid'],'surface_onion':self.surface436.verify_integrity()['valid']}
  if not all(checks.values()):raise RuntimeError('Phase-19 provenance preflight failed: '+','.join(k for k,v in checks.items() if not v))
  return checks
 def _verify_provenance(self,case_id,source_id,event_id,content_id):
  srcrow=self.db.one('SELECT * FROM acquisition_source_421 WHERE source_id=?',(source_id,))
  if not srcrow or self.registry421._record_hash(dict(srcrow))!=srcrow.get('record_hash'):raise RuntimeError('source integrity check failed')
  evrow=self.db.one('SELECT * FROM acquisition_event_422 WHERE event_id=?',(event_id,))
  if not evrow or self.events422._hash(dict(evrow))!=evrow.get('record_hash'):raise RuntimeError('acquisition event integrity check failed')
  if evrow['case_id']!=case_id or evrow['source_id']!=source_id:raise RuntimeError('provenance case/source mismatch')
  obj=self.db.one('SELECT * FROM content_object_423 WHERE content_id=?',(content_id,))
  if not obj or self.content423._hash(dict(obj))!=obj.get('record_hash'):raise RuntimeError('content integrity check failed')
  obs=self.db.one('SELECT * FROM content_observation_423 WHERE event_id=? AND content_id=? AND case_id=? AND source_id=?',(event_id,content_id,case_id,source_id))
  if not obs or (obs.get('record_hash') and self.content423._hash(dict(obs))!=obs.get('record_hash')):raise RuntimeError('content observation integrity check failed')
  return {'source_record_hash':srcrow['record_hash'],'event_record_hash':evrow['record_hash'],'content_record_hash':obj['record_hash'],'observation_record_hash':obs.get('record_hash','')}
 def _entity_row(self,eid):
  r=self.db.one('SELECT * FROM resolution_entities_115 WHERE resolution_entity_id=?',(eid,))
  if not r:raise KeyError('resolution entity not found')
  return dict(r)
 def _aliases(self,eid):return [dict(r) for r in self.db.all('SELECT * FROM resolution_aliases_115 WHERE resolution_entity_id=? ORDER BY created_at,alias_id',(eid,))]
 def _anchors(self,eid):return [dict(r) for r in self.db.all('SELECT * FROM resolution_anchors_115 WHERE resolution_entity_id=? ORDER BY created_at,anchor_id',(eid,))]
 def _add_alias(self,eid,value,kind,actor,source_ref):
  val=_clean(value,500)
  if len(self.base115.normalize_text(val))<2:return
  norm=self.base115.normalize_text(val)
  if not self.db.one('SELECT 1 FROM resolution_aliases_115 WHERE resolution_entity_id=? AND normalized_alias=?',(eid,norm)):self.base115.add_alias(eid,val,kind,actor,source_ref)
 def _add_anchor(self,eid,typ,value,actor,reliability,source_ref):
  val=_clean(value,1000)
  if not val or typ not in self.base115.ANCHOR_TYPES:return
  norm=self.base115.normalize_anchor(typ,val)
  if not norm:return
  digest=hashlib.sha256(f'{typ}:{norm}'.encode()).hexdigest()
  if not self.db.one('SELECT 1 FROM resolution_anchors_115 WHERE resolution_entity_id=? AND anchor_type=? AND value_hash=?',(eid,typ,digest)):self.base115.add_anchor(eid,typ,val,actor,_clamp(reliability),source_ref)
 def _ensure_entity(self,*,ident,case_id,source_entity_id,entity_type,display_name,aliases=(),anchors=(),attributes=None):
  row=self.db.one('SELECT resolution_entity_id FROM resolution_entities_115 WHERE case_id=? AND source_entity_id=?',(case_id,source_entity_id))
  created=False
  if row:eid=row['resolution_entity_id']
  else:
   out=self.entity371.register_candidate(case_id=case_id,entity_type=entity_type,display_name=display_name,identity=ident,source_entity_id=source_entity_id,attributes=attributes or {},aliases=list(aliases),anchors=list(anchors));eid=out['entity']['resolution_entity_id'];created=True
  actor=str(ident['username'])
  for a in aliases:self._add_alias(eid,a,'phase19_alias',actor,'phase19:'+source_entity_id)
  for a in anchors:self._add_anchor(eid,a['type'],a['value'],actor,a.get('reliability',.7),a.get('source_ref') or 'phase19:'+source_entity_id)
  return eid,created
 def _bind(self,*,ident,case_id,source_kind,source_object_id,eid,source_id='',event_id='',content_id='',source_ref='',reliability=.7,provenance=None):
  existing=self.db.one('SELECT * FROM phase19_entity_binding_437 WHERE case_id=? AND source_kind=? AND source_object_id=?',(case_id,source_kind,source_object_id))
  if existing:
   d=dict(existing)
   if self._rh(d)!=d['record_hash']:raise RuntimeError('entity binding integrity check failed')
   if d['resolution_entity_id']!=eid:raise RuntimeError('source object is already bound to another resolution entity')
   return d,False
  r={'binding_id':'eb437_'+secrets.token_hex(10),'case_id':case_id,'source_kind':source_kind,'source_object_id':source_object_id,'resolution_entity_id':eid,'source_id':str(source_id or ''),'event_id':str(event_id or ''),'content_id':str(content_id or ''),'source_ref':str(source_ref or ''),'reliability':_clamp(reliability),'provenance_json':_canon(provenance or {}),'created_by':str(ident['username']),'created_at':_now()};r['record_hash']=self._rh(r);self.db.execute('INSERT INTO phase19_entity_binding_437 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',tuple(r.values()));return r,True
 def _sync_organizations(self,ident,case_id,include_fixtures):
  added=entities=0
  for sub in self.organization433.list_subjects(case_id):
   aliases=list(sub.get('aliases') or []);anchors=[]
   if sub.get('website'):
    anchors.append({'type':'url','value':sub['website'],'reliability':.45,'source_ref':'analyst:organization433:'+sub['subject_id']});dom=_domain(sub['website'])
    if dom:anchors.append({'type':'domain','value':dom,'reliability':.45,'source_ref':'analyst:organization433:'+sub['subject_id']})
   eid,new=self._ensure_entity(ident=ident,case_id=case_id,source_entity_id='phase19:organization433:'+sub['subject_id'],entity_type='organisation',display_name=sub['display_name'],aliases=aliases,anchors=anchors,attributes={'phase19_origin':'organization433','organization_type':sub.get('organization_type',''),'jurisdiction':sub.get('jurisdiction','')});entities+=int(new)
   _,bnew=self._bind(ident=ident,case_id=case_id,source_kind='organization_subject',source_object_id=sub['subject_id'],eid=eid,source_ref='analyst:organization433',reliability=.45,provenance={'analyst_defined_subject':True});added+=int(bnew)
   detail=self.organization433.subject_detail(case_id,sub['subject_id'])
   for o in detail['observations']:
    if o.get('test_fixture') and not include_fixtures:continue
    raw=self.db.one('SELECT * FROM organization_observation_433 WHERE observation_id=?',(o['observation_id'],))
    if not raw or self.organization433._rh(dict(raw))!=raw.get('record_hash'):raise RuntimeError('organization observation integrity check failed')
    pv=self._verify_provenance(case_id,o['source_id'],o['event_id'],o['content_id']);src_ref='source:'+o['source_id'];self._add_alias(eid,o.get('observed_name') or sub['display_name'],'source_observed',str(ident['username']),src_ref)
    attrs=o.get('attributes') or {}
    if attrs.get('legal_name'):self._add_alias(eid,attrs['legal_name'],'legal_name',str(ident['username']),src_ref)
    if attrs.get('website'):
     self._add_anchor(eid,'url',attrs['website'],str(ident['username']),.78,src_ref);dom=_domain(attrs['website'])
     if dom:self._add_anchor(eid,'domain',dom,str(ident['username']),.78,src_ref)
    if attrs.get('address'):self._add_anchor(eid,'location',attrs['address'],str(ident['username']),.52,src_ref)
    for item in o.get('identifiers') or []:
     value='|'.join([_clean(item.get('type'),80).casefold(),_clean(item.get('jurisdiction'),100).casefold(),_clean(item.get('issuer'),160).casefold(),_clean(item.get('value'),300)])
     self._add_anchor(eid,'external_id',value,str(ident['username']),.95,src_ref)
    _,bnew=self._bind(ident=ident,case_id=case_id,source_kind='organization_observation',source_object_id=o['observation_id'],eid=eid,source_id=o['source_id'],event_id=o['event_id'],content_id=o['content_id'],source_ref=src_ref,reliability=.9,provenance={**pv,'subject_id':sub['subject_id'],'source_claim_only':True});added+=int(bnew)
  return added,entities
 def _sync_social(self,ident,case_id,include_fixtures):
  added=entities=0
  for o in self.social432.case_items(case_id,include_fixtures=include_fixtures):
   key=_clean(o.get('account_id') or o.get('account_handle'),300)
   if not key:continue
   raw=self.db.one('SELECT * FROM social_observation_432 WHERE observation_id=?',(o['observation_id'],))
   if not raw or self.social432._rh(dict(raw))!=raw.get('record_hash'):raise RuntimeError('social observation integrity check failed')
   pv=self._verify_provenance(case_id,o['source_id'],o['event_id'],o['content_id']);src_ref='source:'+o['source_id'];platform=_clean(o.get('platform'),80).casefold();source_entity_id='phase19:social432:'+o['source_id']+':'+platform+':'+hashlib.sha256(key.casefold().encode()).hexdigest()[:20];anchors=[]
   if o.get('account_handle'):anchors.append({'type':'username','value':platform+'|'+o['account_handle'],'reliability':.82,'source_ref':src_ref})
   if o.get('account_id'):anchors.append({'type':'external_id','value':platform+'|account|'+o['account_id'],'reliability':.94,'source_ref':src_ref})
   if o.get('object_type') in {'profile','account'} and o.get('canonical_url'):anchors.append({'type':'url','value':o['canonical_url'],'reliability':.8,'source_ref':src_ref})
   eid,new=self._ensure_entity(ident=ident,case_id=case_id,source_entity_id=source_entity_id,entity_type='account',display_name=o.get('account_handle') or o.get('account_id'),aliases=[o.get('account_handle')] if o.get('account_handle') else [],anchors=anchors,attributes={'phase19_origin':'social432','platform':platform});entities+=int(new)
   _,bnew=self._bind(ident=ident,case_id=case_id,source_kind='social_observation',source_object_id=o['observation_id'],eid=eid,source_id=o['source_id'],event_id=o['event_id'],content_id=o['content_id'],source_ref=src_ref,reliability=.85,provenance={**pv,'platform':platform,'public_only':True,'test_fixture':bool(o.get('test_fixture'))});added+=int(bnew)
  return added,entities
 def _sync_news(self,ident,case_id,min_confidence):
  added=entities=0
  for ex in self.news430.case_extractions(case_id):
   rawex=self.db.one('SELECT * FROM news_extraction_430 WHERE extraction_id=?',(ex['extraction_id'],))
   if not rawex or self.news430._rh(dict(rawex))!=rawex.get('record_hash'):raise RuntimeError('news extraction integrity check failed')
   itemrow=self.db.one('SELECT * FROM news_item_429 WHERE news_item_id=?',(ex['news_item_id'],))
   if not itemrow or self.news429._rh(dict(itemrow))!=itemrow.get('record_hash'):raise RuntimeError('news item integrity check failed')
   item=dict(itemrow);pv=self._verify_provenance(case_id,item['source_id'],item['event_id'],item['content_id']);src_ref='source:'+item['source_id']
   for idx,m in enumerate(ex.get('entities') or []):
    conf=float(m.get('confidence') or 0);kind=_clean(m.get('kind'),80).casefold();etype=SUPPORTED_NEWS_KINDS.get(kind)
    if conf<float(min_confidence) or not etype:continue
    label=_clean(m.get('label'),500)
    if len(self.base115.normalize_text(label))<2:continue
    anchors=[];rel=min(.78,max(.35,conf*.8))
    if etype in {'email','phone','domain'}:anchors.append({'type':etype,'value':label,'reliability':rel,'source_ref':src_ref})
    elif etype=='account':anchors.append({'type':'username','value':label,'reliability':rel,'source_ref':src_ref})
    source_entity_id='phase19:news430:'+ex['extraction_id']+':'+str(idx);eid,new=self._ensure_entity(ident=ident,case_id=case_id,source_entity_id=source_entity_id,entity_type=etype,display_name=label,aliases=[],anchors=anchors,attributes={'phase19_origin':'news430','machine_observation':True,'extractor':ex['extractor'],'confidence':conf});entities+=int(new)
    _,bnew=self._bind(ident=ident,case_id=case_id,source_kind='news_entity_mention',source_object_id=ex['extraction_id']+':'+str(idx),eid=eid,source_id=item['source_id'],event_id=item['event_id'],content_id=item['content_id'],source_ref=src_ref,reliability=rel,provenance={**pv,'news_item_id':ex['news_item_id'],'extraction_id':ex['extraction_id'],'source_span':m.get('source_span',''),'machine_confidence':conf,'machine_observation_not_fact':True});added+=int(bnew)
  return added,entities
 def _entity_sources(self,eid):
  rows=self.db.all('SELECT DISTINCT source_kind,source_id,source_ref FROM phase19_entity_binding_437 WHERE resolution_entity_id=?',(eid,));return {(r['source_kind'],r['source_id'] or r['source_ref']) for r in rows}
 def _prefilter(self,left,right,min_name):
  if left['entity_type']!=right['entity_type']:return False
  if self._entity_sources(left['resolution_entity_id'])==self._entity_sources(right['resolution_entity_id']):return False
  if left['normalized_name']==right['normalized_name']:return True
  if SequenceMatcher(None,left['normalized_name'],right['normalized_name']).ratio()>=float(min_name):return True
  la={r['normalized_alias'] for r in self._aliases(left['resolution_entity_id'])};ra={r['normalized_alias'] for r in self._aliases(right['resolution_entity_id'])}
  if la&ra:return True
  lh={(r['anchor_type'],r['value_hash']) for r in self._anchors(left['resolution_entity_id'])};rh={(r['anchor_type'],r['value_hash']) for r in self._anchors(right['resolution_entity_id'])}
  return bool(lh&rh)
 def sync_case(self,*,identity,case_id,include_fixtures=False,min_news_confidence=.60,min_name_similarity=.84,max_entities=500,max_pairs=2000):
  ident=self._authorize(identity,case_id);case_id=str(case_id or '').strip()
  if not case_id:raise ValueError('case_id required')
  if not .5<=float(min_news_confidence)<=1:raise ValueError('min_news_confidence must be between 0.5 and 1.0')
  if not .7<=float(min_name_similarity)<=1:raise ValueError('min_name_similarity must be between 0.7 and 1.0')
  preflight=self._preflight();bindings=created=0
  for fn in (self._sync_organizations,self._sync_social):
   b,e=fn(ident,case_id,bool(include_fixtures));bindings+=b;created+=e
  b,e=self._sync_news(ident,case_id,float(min_news_confidence));bindings+=b;created+=e
  ids=[r['resolution_entity_id'] for r in self.db.all('SELECT DISTINCT resolution_entity_id FROM phase19_entity_binding_437 WHERE case_id=? ORDER BY resolution_entity_id',(case_id,))]
  if len(ids)>int(max_entities):raise ValueError('entity set exceeds max_entities; narrow the case scope before resolution')
  ents=[self._entity_row(x) for x in ids];pairs=[];classes={}
  for i,left in enumerate(ents):
   for right in ents[i+1:]:
    if not self._prefilter(left,right,float(min_name_similarity)):continue
    if len(pairs)>=int(max_pairs):raise ValueError('candidate pair set exceeds max_pairs; narrow the case scope before resolution')
    a_id,b_id=sorted([left['resolution_entity_id'],right['resolution_entity_id']]);existing=self.db.one('SELECT comparison_id,state FROM resolution_comparisons_115 WHERE case_id=? AND left_entity_id=? AND right_entity_id=?',(case_id,a_id,b_id))
    if existing and existing['state'] in {'approved_same','approved_distinct','rejected'}:cmp=self.base115.comparison(existing['comparison_id'])
    else:cmp=self.entity371.analyze_internal(case_id=case_id,left_entity_id=left['resolution_entity_id'],right_entity_id=right['resolution_entity_id'],actor=str(ident['username']))
    pairs.append(cmp['comparison_id']);classes[cmp['classification']]=classes.get(cmp['classification'],0)+1
  review=sum(v for k,v in classes.items() if k in REVIEW_CLASSES and k!='likely_distinct');distinct=int(classes.get('likely_distinct',0));run_id='er437_'+secrets.token_hex(10);result={'build':BUILD,'case_id':case_id,'bindings_added':bindings,'new_resolution_entities':created,'entities_considered':len(ents),'pairs_compared':len(pairs),'classification_counts':classes,'review_candidates':review,'likely_distinct':distinct,'comparison_ids':pairs,'preflight':preflight,'score_is_probability':False,'automatic_identity_confirmation':False,'automatic_merge':False,'destructive_merge':False,'independent_human_review_required':True,'surface_onion_content_correlation_is_identity_evidence':False,'network_execution':False}
  row={'run_id':run_id,'case_id':case_id,'bindings_synced':bindings,'entities_considered':len(ents),'pairs_compared':len(pairs),'review_candidates':review,'likely_distinct':distinct,'result_json':_canon(result),'created_by':str(ident['username']),'created_at':_now()};row['record_hash']=self._rh(row);self.db.execute('INSERT INTO phase19_resolution_run_437 VALUES(?,?,?,?,?,?,?,?,?,?,?)',tuple(row.values()));self.audit.log('cross_source_entity_resolution_run_437','case',case_id,case_id,{'run_id':run_id,'entities':len(ents),'pairs':len(pairs),'review_candidates':review,'automatic_merge':False});return {**row,'result':result}
 def bindings(self,case_id):
  out=[]
  for r in self.db.all('SELECT * FROM phase19_entity_binding_437 WHERE case_id=? ORDER BY created_at,binding_id',(str(case_id),)):
   d=dict(r);d['provenance']=json.loads(d['provenance_json']);out.append(d)
  return out
 def review_queue(self,case_id):
  bound={r['resolution_entity_id'] for r in self.db.all('SELECT DISTINCT resolution_entity_id FROM phase19_entity_binding_437 WHERE case_id=?',(str(case_id),))};out=[]
  for r in self.db.all("SELECT comparison_id FROM resolution_comparisons_115 WHERE case_id=? AND state='needs_review' ORDER BY total_score DESC,created_at",(str(case_id),)):
   cmp=self.base115.comparison(r['comparison_id'])
   if cmp['left_entity_id'] in bound and cmp['right_entity_id'] in bound:out.append(self.packet(case_id,cmp['comparison_id']))
  return out
 def packet(self,case_id,comparison_id):
  cmp=self.base115.comparison(comparison_id)
  if cmp['case_id']!=str(case_id):raise KeyError('comparison not found in case')
  left=self._entity_row(cmp['left_entity_id']);right=self._entity_row(cmp['right_entity_id']);lb=[b for b in self.bindings(case_id) if b['resolution_entity_id']==left['resolution_entity_id']];rb=[b for b in self.bindings(case_id) if b['resolution_entity_id']==right['resolution_entity_id']]
  content_ids={b['content_id'] for b in lb+rb if b['content_id']};context=[]
  if content_ids:
   marks=','.join('?' for _ in content_ids);rows=self.db.all("SELECT * FROM surface_onion_candidate_436 WHERE case_id=? AND (surface_content_id IN ("+marks+") OR onion_content_id IN ("+marks+")) ORDER BY score DESC",(str(case_id),*content_ids,*content_ids))
   for r in rows:
    d=dict(r);d['signals']=json.loads(d['signals_json']);d['context_only']=True;d['identity_evidence']=False;context.append(d)
  return {'build':BUILD,'comparison':cmp,'left':{**left,'aliases':self._aliases(left['resolution_entity_id']),'anchors':self._anchors(left['resolution_entity_id']),'bindings':lb},'right':{**right,'aliases':self._aliases(right['resolution_entity_id']),'anchors':self._anchors(right['resolution_entity_id']),'bindings':rb},'surface_onion_context':context,'score_is_probability':False,'content_correlation_is_identity_evidence':False,'human_review_required':True,'automatic_merge':False}
 def propose_same_entity(self,*,identity,case_id,comparison_id,canonical_entity_id):
  ident=self._authorize(identity,case_id,'research.run',comparison_id);self.packet(case_id,comparison_id);return self.entity371.propose_same_entity(case_id=case_id,comparison_id=comparison_id,canonical_entity_id=canonical_entity_id,identity=ident)
 def review_same_entity(self,*,identity,case_id,proposal_id,approve,reason):
  ident=self._authorize(identity,case_id,'dossier.review',proposal_id);return self.entity371.review_same_entity(case_id=case_id,proposal_id=proposal_id,identity=ident,approve=bool(approve),reason=str(reason))
 def latest(self,case_id):
  r=self.db.one('SELECT * FROM phase19_resolution_run_437 WHERE case_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1',(str(case_id),))
  if not r:return None
  d=dict(r);d['result']=json.loads(d['result_json']);return d
 def case_report(self,case_id):
  bindings=self.bindings(case_id);entities={b['resolution_entity_id'] for b in bindings};comparisons=self.db.one("SELECT COUNT(*) n FROM resolution_comparisons_115 WHERE case_id=?",(str(case_id),))['n'];links=self.db.one("SELECT COUNT(*) n FROM resolution_links_115 WHERE case_id=? AND active=1",(str(case_id),))['n'];pending=self.db.one("SELECT COUNT(*) n FROM resolution_merge_proposals_115 WHERE case_id=? AND state='pending'",(str(case_id),))['n'];chain=self.base115.verify_event_chain(str(case_id))
  return {'build':BUILD,'case_id':str(case_id),'bindings':len(bindings),'resolution_entities':len(entities),'comparisons':int(comparisons),'review_queue':len(self.review_queue(case_id)),'approved_non_destructive_links':int(links),'pending_proposals':int(pending),'resolution_event_chain_valid':bool(chain['valid']),'integrity_valid':self.verify_integrity()['valid'],'automatic_merge':False,'destructive_merge':False,'score_is_probability':False,'case_scoped':True}
 def _fixture_source(self,kind):
  cfg={'registry':('src421_fixture_er437_registry','registry','https://build437-registry.example.invalid'),'ngo':('src421_fixture_er437_ngo','ngo','https://build437-ngo.example.invalid')}[kind];sid,stype,base=cfg
  with self.db.transaction(immediate=True):
   try:src=self.registry421.get(sid)
   except KeyError:
    caps=['organization_records','entity_resolution_fixture'];coverage={'fixture_only':True,'network_execution_forbidden':True};r={'source_id':sid,'name':'Build 437 '+kind+' fixture','source_type':stype,'access_mode':'public','base_url':base,'capabilities_json':_canon(caps),'coverage_json':_canon(coverage),'terms_url':'','license_note':'Trusted Build 437 synthetic fixture; no network retrieval.','enabled':1,'created_by':'system:build437_fixture','created_at':_now()};r['record_hash']=self.registry421._record_hash(r);self.db.execute('INSERT OR IGNORE INTO acquisition_source_421 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',tuple(r.values()));src=self.registry421.get(sid)
   if not bool((src.get('coverage') or {}).get('fixture_only')):raise RuntimeError('reserved Build 437 fixture source has unexpected configuration')
   return src
 def run_case_selftest(self,*,identity,case_id):
  ident=self._authorize(identity,case_id);case_id=str(case_id);token=secrets.token_hex(5);website='https://entity-'+token+'.example.invalid';shared_id='fixture_registry|de|fixture issuer|ER-'+token
  subjects=[]
  for kind in ('registry','ngo'):
   src=self._fixture_source(kind);sub=self.organization433.create_subject(identity=ident,case_id=case_id,display_name='Synthetic Resolution Entity '+token,organization_type='association',jurisdiction='DE',status='active',website=website,aliases=['SRE '+token]);raw=('Build 437 '+kind+' record '+token).encode();digest=hashlib.sha256(raw).hexdigest();ev=self.events422.record(identity=ident,case_id=case_id,source_id=src['source_id'],target=src['base_url']+'/record/'+token,method='manual_import',status='retrieved',content_sha256=digest,media_type='text/plain',bytes_count=len(raw),provenance={'build':'437.0','fixture_only':True},usage={'public_only':True,'network_execution':False});content=self.content423.ingest(identity=ident,event_id=ev['event_id'],content=raw,media_type='text/plain',metadata={'build437_fixture':True});obs=self.organization433.record_observation(identity=ident,case_id=case_id,subject_id=sub['subject_id'],source_id=src['source_id'],event_id=ev['event_id'],content_id=content['content_id'],observed_name=sub['display_name'],attributes={'legal_name':sub['display_name'],'organization_type':'association','jurisdiction':'DE','website':website},identifiers=[{'type':'fixture_registry','value':'ER-'+token,'jurisdiction':'DE','issuer':'Fixture Issuer'}],metadata={'build437_fixture':True},test_fixture=True);subjects.append((sub,obs))
  run=self.sync_case(identity=ident,case_id=case_id,include_fixtures=True,min_name_similarity=.8);ids=[]
  for sub,_ in subjects:
   b=self.db.one("SELECT resolution_entity_id FROM phase19_entity_binding_437 WHERE case_id=? AND source_kind='organization_subject' AND source_object_id=?",(case_id,sub['subject_id']));ids.append(b['resolution_entity_id'])
  a,b=sorted(ids);cmp=self.db.one('SELECT comparison_id,classification,state FROM resolution_comparisons_115 WHERE case_id=? AND left_entity_id=? AND right_entity_id=?',(case_id,a,b));packet=self.packet(case_id,cmp['comparison_id']) if cmp else None;links=self.db.one('SELECT COUNT(*) n FROM resolution_links_115 WHERE case_id=?',(case_id,))['n'];checks={'sync_completed':run['result']['pairs_compared']>=1,'two_distinct_candidates_retained':len(set(ids))==2,'review_candidate_created':bool(cmp and cmp['classification'] in {'strong_review_candidate','possible_review_candidate'}),'same_external_identifier_visible':bool(packet and any(x['anchor_type']=='external_id' for x in packet['left']['anchors']) and any(x['anchor_type']=='external_id' for x in packet['right']['anchors'])),'no_automatic_link':int(links)==0,'human_review_required':bool(packet and packet['human_review_required']),'score_not_probability':bool(packet and packet['score_is_probability'] is False),'network_execution_absent':run['result']['network_execution'] is False,'integrity_valid':self.verify_integrity()['valid']}
  return {'build':BUILD,'case_id':case_id,'result':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'run':run,'comparison_packet':packet,'note':'Two independent public-source organization records remain separate candidates until explicit human review; no destructive merge occurs.'}
 def verify_integrity(self):
  bad=[]
  for table,key in [('phase19_entity_binding_437','binding_id'),('phase19_resolution_run_437','run_id')]:
   for r in self.db.all('SELECT * FROM '+table):
    d=dict(r)
    if self._rh(d)!=d['record_hash']:bad.append({key:d[key],'table':table,'reason':'record_hash_mismatch'})
  return {'build':BUILD,'valid':not bad,'violations':bad}
 def status(self):
  b=self.db.one('SELECT COUNT(*) n FROM phase19_entity_binding_437')['n'];r=self.db.one('SELECT COUNT(*) n FROM phase19_resolution_run_437')['n'];return {'build':BUILD,'policy':POLICY_ID,'bindings':int(b),'runs':int(r),'integrity_valid':self.verify_integrity()['valid'],'cross_source_entity_resolution':True,'uses_canonical_resolution_ledger_115':True,'uses_evidence_weighted_review_371':True,'news_machine_mentions_candidate_only':True,'surface_onion_content_correlation_is_identity_evidence':False,'score_is_probability':False,'automatic_identity_confirmation':False,'automatic_merge':False,'destructive_merge':False,'independent_human_review_required':True,'network_execution':False,'case_specific_selftest':True,'production_release_ready':False}
