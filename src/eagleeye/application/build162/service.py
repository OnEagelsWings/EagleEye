from __future__ import annotations
import hashlib, json, time
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from urllib.parse import urlencode, urlparse
from eagleeye_pro.core.database import dumps, new_id, now_ts

def _canon(v:Any)->str: return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v:Any)->str: return hashlib.sha256(_canon(v).encode()).hexdigest()
def _utc(v:str|None):
    if not v:return None
    d=datetime.fromisoformat(v.replace('Z','+00:00')); return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

class Build162SocialMediaCollectionService:
    BUILD='162.0'; MISSION='Official-API, public-only social media collection'
    SOURCES={
      'bluesky_public':{'host':'public.api.bsky.app','base':'https://public.api.bsky.app/xrpc/','auth':False,'operations':{
        'search_profiles':('app.bsky.actor.searchActors','q','actors'),
        'get_profile':('app.bsky.actor.getProfile','actor',None),
        'author_feed':('app.bsky.feed.getAuthorFeed','actor','feed'),
        'search_posts':('app.bsky.feed.searchPosts','q','posts')}},
      'mastodon_public':{'host_mode':'instance','auth':False,'operations':{
        'search':('/api/v2/search','q',None),
        'account_statuses':('/api/v1/accounts/{account_id}/statuses',None,None),
        'public_timeline':('/api/v1/timelines/public',None,None)}},
      'youtube_data':{'host':'www.googleapis.com','base':'https://www.googleapis.com/youtube/v3/','auth':True,'operations':{
        'search':('search','q','items'), 'comment_threads':('commentThreads','videoId','items'),
        'channels':('channels','id','items')}},
      'reddit_data':{'host':'oauth.reddit.com','base':'https://oauth.reddit.com/','auth':True,'operations':{
        'search_posts':('search','q','data.children'), 'user_about':('user/{username}/about',None,'data'),
        'user_submitted':('user/{username}/submitted',None,'data.children')}}
    }
    def __init__(self,db:Any,audit:Any,*,acceptance:Any,observability:Any|None=None,actor:str='system'):
        self.db=db; self.audit=audit; self.acceptance=acceptance; self.observability=observability; self.actor=actor
    def authorize(self,case_id:str,source_id:str,*,purpose:str,scope:Mapping[str,Any],approved_by:str,confirmation:str,expires_at:str|None=None)->dict[str,Any]:
        if source_id not in self.SOURCES: raise KeyError('unknown social source')
        if confirmation!=f'SOCIAL 162 {case_id} {source_id} AUTHORISIEREN': raise PermissionError('explicit investigator authorization required')
        if not purpose.strip(): raise ValueError('purpose required')
        max_items=int(scope.get('max_items',100)); max_pages=int(scope.get('max_pages',5))
        if not 1<=max_items<=1000 or not 1<=max_pages<=20: raise ValueError('collection scope exceeds limits')
        safe={**dict(scope),'max_items':max_items,'max_pages':max_pages,'public_only':True,'no_interaction':True,'no_private_access':True}
        aid=new_id('socialauth162'); payload={'authorization_id':aid,'case_id':case_id,'source_id':source_id,'purpose':purpose,'scope':safe,'approved_by':approved_by,'expires_at':expires_at}
        self.db.execute('INSERT INTO social_collection_authorizations_162 VALUES(?,?,?,?,?,?,?,?,?,?)',(aid,case_id,source_id,purpose,dumps(safe),approved_by,now_ts(),expires_at,'active',_hash(payload)))
        self.audit.log('social_collection_authorized_162','social_authorization',aid,case_id,{'source_id':source_id,'purpose':purpose,'scope':safe})
        return payload
    def _authorization(self,case_id:str,source_id:str)->dict[str,Any]:
        r=self.db.one("SELECT * FROM social_collection_authorizations_162 WHERE case_id=? AND source_id=? AND status='active' ORDER BY approved_at DESC LIMIT 1",(case_id,source_id))
        if not r: raise PermissionError('active social collection authorization required')
        if r['expires_at'] and _utc(r['expires_at'])<=datetime.now(timezone.utc): raise PermissionError('social collection authorization expired')
        d=dict(r); d['scope']=json.loads(d['scope_json']); return d
    def _readiness(self,source_id:str)->dict[str,Any]:
        try:r=self.acceptance.readiness(source_id)
        except Exception:return {'readiness':'not_ready','findings':['connector_acceptance_missing']}
        return r
    def collect(self,case_id:str,source_id:str,operation:str,query:Mapping[str,Any],*,confirmation:str,transport:Callable[...,Mapping[str,Any]]|None=None)->dict[str,Any]:
        auth=self._authorization(case_id,source_id); spec=self.SOURCES[source_id]
        if operation not in spec['operations']: raise ValueError('unsupported source operation')
        if confirmation!=f'SOCIAL 162 {case_id} {source_id} SAMMELN': raise PermissionError('explicit collection approval required')
        ready=self._readiness(source_id)
        # Public Bluesky may run after a successful sandbox probe; credentialed sources require production readiness.
        allowed=ready.get('readiness')=='production_ready' or (source_id=='bluesky_public' and ready.get('readiness') in {'sandbox_ready','production_ready'})
        if not allowed: raise PermissionError('source is not operationally accepted')
        run_id=new_id('socialrun162'); started=now_ts(); cursor=str(query.get('cursor') or query.get('pageToken') or query.get('after') or '') or None
        self.db.execute('INSERT INTO social_collection_runs_162 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(run_id,case_id,source_id,operation,dumps(query),'running','',started,None,cursor,None,0,'{}','{}','{}',_hash({'run_id':run_id,'started':started})))
        try:
            url,headers=self._request(source_id,operation,query,auth['scope'])
            response=self._transport(url,headers,transport); status=int(response['status']); body=response['body']; rh=dict(response.get('headers') or {})
            if not 200<=status<300: raise RuntimeError(f'HTTP {status}')
            data=json.loads(body.decode() if isinstance(body,(bytes,bytearray)) else body)
            items,next_cursor=self._extract(source_id,operation,data)
            cap=min(auth['scope']['max_items'],len(items)); stored=0
            for item in items[:cap]: stored+=self._store_record(run_id,case_id,source_id,operation,item,url)
            rate={k:v for k,v in rh.items() if 'rate' in k.lower() or k.lower()=='retry-after'}
            prov={'request_host':urlparse(url).hostname,'request_url_sha256':hashlib.sha256(url.encode()).hexdigest(),'http_status':status,'body_sha256':hashlib.sha256(body if isinstance(body,bytes) else str(body).encode()).hexdigest(),'public_only':True,'analyst_authorization_id':auth['authorization_id']}
            outcome='SUCCESS' if stored or not items else 'NO_RESULT'; finished=now_ts()
            self.db.execute('UPDATE social_collection_runs_162 SET status=?,outcome=?,finished_at=?,cursor_out=?,item_count=?,rate_limit_json=?,provenance_json=?,payload_sha256=? WHERE run_id=?',('succeeded',outcome,finished,next_cursor,stored,dumps(rate),dumps(prov),_hash({'run_id':run_id,'outcome':outcome,'count':stored,'provenance':prov}),run_id))
            if next_cursor:self._save_cursor(run_id,source_id,next_cursor)
            self._event(run_id,case_id,source_id,'collection_completed',{'operation':operation,'stored':stored,'next_cursor':bool(next_cursor)})
            return {'run_id':run_id,'status':'succeeded','outcome':outcome,'stored':stored,'next_cursor':next_cursor,'review_required':True,'automatic_identity_confirmation':False}
        except Exception as exc:
            self.db.execute('UPDATE social_collection_runs_162 SET status=?,outcome=?,finished_at=?,error_json=? WHERE run_id=?',('failed','SOURCE_UNAVAILABLE',now_ts(),dumps({'type':type(exc).__name__,'message':str(exc)[:300]}),run_id))
            self._event(run_id,case_id,source_id,'collection_failed',{'type':type(exc).__name__,'message':str(exc)[:200]})
            raise
    def _request(self,source_id:str,operation:str,query:Mapping[str,Any],scope:Mapping[str,Any])->tuple[str,dict[str,str]]:
        spec=self.SOURCES[source_id]; endpoint,key,_=spec['operations'][operation]; params={k:str(v) for k,v in query.items() if v is not None and k not in {'instance','account_id','username'}}
        limit=min(int(params.get('limit') or params.get('maxResults') or 50),min(int(scope['max_items']),100));
        if source_id=='youtube_data': params.setdefault('part','snippet'); params['maxResults']=str(min(limit,50))
        elif source_id in {'bluesky_public','mastodon_public'}: params['limit']=str(min(limit,100))
        headers={'Accept':'application/json','User-Agent':'EagleEye-PersonOSINT/162 public-only social collection'}
        if source_id=='mastodon_public':
            instance=str(query.get('instance','')).lower().strip();
            if not instance or '/' in instance or ':' in instance: raise ValueError('valid Mastodon instance hostname required')
            endpoint=endpoint.format(account_id=str(query.get('account_id',''))); url=f'https://{instance}{endpoint}'
        else:
            endpoint=endpoint.format(username=str(query.get('username',''))); url=spec['base']+endpoint
        # Credentials are fetched only inside the local vault and never persisted in provenance.
        if spec.get('auth'):
            h,p=self.acceptance._auth(source_id); headers.update(h); params.update({k:v for k,v in p.items() if k not in {'q','search','per-page'}})
        return url+('?' + urlencode(params) if params else ''),headers
    def _transport(self,url:str,headers:Mapping[str,str],transport):
        if transport:return transport(url=url,headers=dict(headers),timeout=20,max_bytes=4_000_000)
        import urllib.request
        with urllib.request.urlopen(urllib.request.Request(url,headers=dict(headers)),timeout=20) as r:return {'status':r.status,'headers':dict(r.headers.items()),'body':r.read(4_000_000)}
    def _extract(self,source_id:str,operation:str,data:Any)->tuple[list[dict[str,Any]],str|None]:
        if source_id=='bluesky_public':
            key=self.SOURCES[source_id]['operations'][operation][2]; items=[data] if key is None else list(data.get(key,[])); return items,data.get('cursor')
        if source_id=='mastodon_public':
            if isinstance(data,list):return data,None
            items=[]
            for k in ('accounts','statuses','hashtags'): items.extend([{**x,'_mastodon_type':k[:-1]} for x in data.get(k,[])])
            return items,None
        if source_id=='youtube_data': return list(data.get('items',[])),data.get('nextPageToken')
        node=data
        for p in (self.SOURCES[source_id]['operations'][operation][2] or '').split('.'):
            if p: node=node.get(p,{}) if isinstance(node,dict) else []
        return ([node] if isinstance(node,dict) else list(node or [])), data.get('data',{}).get('after') if isinstance(data,dict) else None
    def _store_record(self,run_id,case_id,source_id,operation,item,url)->int:
        raw=dict(item); rid_value=raw.get('uri') or raw.get('id') or raw.get('name')
        if isinstance(rid_value,dict): rid_value=rid_value.get('videoId') or rid_value.get('channelId') or rid_value.get('playlistId')
        rid=str(rid_value or raw.get('did') or raw.get('data',{}).get('name') or '') or None
        author=raw.get('author') if isinstance(raw.get('author'),dict) else raw.get('account') if isinstance(raw.get('account'),dict) else {}
        text=str(raw.get('text') or raw.get('content') or raw.get('description') or raw.get('snippet',{}).get('description') or raw.get('record',{}).get('text') or '')
        published=raw.get('createdAt') or raw.get('created_at') or raw.get('publishedAt') or raw.get('snippet',{}).get('publishedAt')
        uri=str(raw.get('uri') or raw.get('url') or '') or None
        normalized={'source_id':source_id,'operation':operation,'source_record_id':rid,'author_id':author.get('did') or author.get('id') or author.get('name'),'author_handle':author.get('handle') or author.get('acct') or author.get('name'),'published_at':published,'text':text,'uri':uri,'raw':raw}
        ch=_hash(normalized); rec=new_id('socialrec162'); prov={'run_id':run_id,'source_id':source_id,'request_url_sha256':hashlib.sha256(url.encode()).hexdigest(),'collected_at':now_ts(),'public_only':True}
        cur=self.db.execute('INSERT OR IGNORE INTO social_records_162 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(rec,run_id,case_id,source_id,operation,rid,uri,normalized['author_id'],normalized['author_handle'],published,text,dumps(raw),dumps(prov),ch,'needs_review',now_ts()))
        return 1 if getattr(cur,'rowcount',0)>0 else 0
    def _save_cursor(self,run_id,source_id,cursor):
        pid=new_id('page162'); self.db.execute('INSERT INTO social_pagination_162 VALUES(?,?,?,?,?,?,?)',(pid,run_id,source_id,str(cursor),None,now_ts(),_hash({'run_id':run_id,'cursor':cursor})))
    def _event(self,run_id,case_id,source_id,event_type,details):
        eid=new_id('socialevt162'); self.db.execute('INSERT INTO social_collection_events_162 VALUES(?,?,?,?,?,?,?,?)',(eid,run_id,case_id,source_id,event_type,dumps(details),now_ts(),_hash({'event_id':eid,'details':details})))
    def records(self,case_id:str,*,source_id:str|None=None)->list[dict[str,Any]]:
        q='SELECT * FROM social_records_162 WHERE case_id=?'; args=[case_id]
        if source_id:q+=' AND source_id=?';args.append(source_id)
        q+=' ORDER BY created_at DESC'; return [dict(r) for r in self.db.all(q,tuple(args))]
