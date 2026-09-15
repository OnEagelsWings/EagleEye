from __future__ import annotations
import hashlib, json, re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse
from eagleeye_pro.core.database import dumps, new_id, now_ts

_SECRET_KEYS={'password','token','secret','api_key','authorization','cookie','session'}
_HANDLE_RE=re.compile(r'[^a-z0-9._-]+')

def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v:Any)->str:return hashlib.sha256(_canon(v).encode()).hexdigest()
def _safe(v:Any)->Any:
    if isinstance(v,Mapping):
        return {str(k):('[REDACTED]' if str(k).lower() in _SECRET_KEYS else _safe(x)) for k,x in v.items()}
    if isinstance(v,list):return [_safe(x) for x in v]
    return v

def _norm_handle(v:str|None)->str:
    x=(v or '').strip().lower().lstrip('@')
    return _HANDLE_RE.sub('',x)

def _tokens(v:str|None)->set[str]:
    return {x for x in re.split(r'[^\w]+',(v or '').casefold()) if len(x)>1}

class Build163SocialCorrelationService:
    BUILD='163.0'
    MISSION='Review-first media, account, alias and interaction correlation'
    ALLOWED_INTERACTIONS={'authored','replied_to','mentioned','reposted','liked','commented_on','linked_to','same_media'}
    def __init__(self,db:Any,audit:Any,*,collection:Any,multilingual:Any|None=None,temporal:Any|None=None,observability:Any|None=None,actor:str='system'):
        self.db=db;self.audit=audit;self.collection=collection;self.multilingual=multilingual;self.temporal=temporal;self.observability=observability;self.actor=actor

    def ingest_case(self,case_id:str,*,confirmation:str)->dict[str,Any]:
        if confirmation!=f'KORRELATION 163 {case_id} IMPORTIEREN':raise PermissionError('explicit correlation import approval required')
        rows=self.db.all('SELECT * FROM social_records_162 WHERE case_id=? ORDER BY created_at',(case_id,))
        accounts=media=interactions=0
        for row in rows:
            raw=json.loads(row['raw_json']); source=row['source_id']; record_id=row['record_id']
            acct=self._extract_account(source,raw,row)
            account_id=None
            if acct: account_id=self._upsert_account(case_id,source,acct,row);accounts+=1
            for m in self._extract_media(source,raw,row): media+=self._store_media(case_id,source,record_id,m,row)
            for edge in self._extract_interactions(source,raw,row,account_id): interactions+=self._store_interaction(case_id,source,edge,row)
        out={'case_id':case_id,'records_scanned':len(rows),'accounts_observed':accounts,'media_stored':media,'interactions_stored':interactions,'review_required':True,'automatic_identity_confirmation':False}
        self._event(case_id,'case_ingested',None,out)
        return out

    def _extract_account(self,source:str,raw:Mapping[str,Any],row:Mapping[str,Any])->dict[str,Any]|None:
        if source=='bluesky_public':
            a=raw.get('author') if isinstance(raw.get('author'),dict) else raw
            pid=a.get('did');handle=a.get('handle');name=a.get('displayName')
            uri=f'https://bsky.app/profile/{handle or pid}' if (handle or pid) else None
        elif source=='mastodon_public':
            a=raw.get('account') if isinstance(raw.get('account'),dict) else raw
            pid=a.get('id');handle=a.get('acct') or a.get('username');name=a.get('display_name');uri=a.get('url')
        elif source=='youtube_data':
            sn=raw.get('snippet',{}) if isinstance(raw.get('snippet'),dict) else {}
            pid=sn.get('channelId') or raw.get('id');handle=sn.get('customUrl') or sn.get('channelTitle');name=sn.get('title') or sn.get('channelTitle');uri=f'https://www.youtube.com/channel/{pid}' if pid else None
        elif source=='reddit_data':
            d=raw.get('data',raw);pid=d.get('name') or d.get('author_fullname');handle=d.get('name') or d.get('author');name=d.get('subreddit_name_prefixed') or handle;uri=f'https://www.reddit.com/user/{handle}' if handle else None
        else:return None
        if not(pid or handle):return None
        return {'platform_account_id':str(pid or handle),'handle':str(handle or ''),'display_name':str(name or ''),'profile_uri':uri,'raw':dict(a if 'a' in locals() else raw)}

    def _upsert_account(self,case_id,source,acct,row)->str:
        existing=self.db.one('SELECT account_id FROM social_accounts_163 WHERE case_id=? AND source_id=? AND platform_account_id=?',(case_id,source,acct['platform_account_id']))
        aliases=sorted({_norm_handle(acct.get('handle')),*(x.casefold() for x in _tokens(acct.get('display_name'))) }- {''})
        prov={'record_id':row['record_id'],'run_id':row['run_id'],'public_only':True,'source_id':source}
        if existing:
            self.db.execute('UPDATE social_accounts_163 SET handle=?,display_name=?,profile_uri=?,profile_json=?,normalized_handle=?,alias_keys_json=?,last_observed_at=?,provenance_json=?,content_sha256=? WHERE account_id=?',(acct.get('handle'),acct.get('display_name'),acct.get('profile_uri'),dumps(_safe(acct['raw'])),_norm_handle(acct.get('handle')),dumps(aliases),now_ts(),dumps(prov),_hash(acct),existing['account_id']))
            return existing['account_id']
        aid=new_id('socialacct163')
        self.db.execute('INSERT INTO social_accounts_163 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(aid,case_id,source,acct['platform_account_id'],acct.get('handle'),acct.get('display_name'),acct.get('profile_uri'),dumps(_safe(acct['raw'])),_norm_handle(acct.get('handle')),dumps(aliases),now_ts(),now_ts(),dumps(prov),_hash(acct),'needs_review'))
        return aid

    def _extract_media(self,source,raw,row)->list[dict[str,Any]]:
        found=[]
        def add(uri,kind='image',meta=None):
            if not uri:return
            p=urlparse(str(uri));
            if p.scheme!='https':return
            found.append({'uri':str(uri),'media_type':kind,'metadata':_safe(meta or {})})
        if source=='bluesky_public':
            emb=raw.get('embed') or raw.get('record',{}).get('embed') or {}
            for im in emb.get('images',[]) if isinstance(emb,dict) else []: add(im.get('fullsize') or im.get('thumb'),'image',{'alt':im.get('alt')})
            if isinstance(emb,dict) and emb.get('playlist'): add(emb.get('playlist'),'video')
        elif source=='mastodon_public':
            for m in raw.get('media_attachments',[]) or []:add(m.get('url') or m.get('preview_url'),m.get('type','media'),{'description':m.get('description')})
        elif source=='youtube_data':
            thumbs=(raw.get('snippet',{}).get('thumbnails') or {})
            for size,m in thumbs.items():add(m.get('url'),'thumbnail',{'size':size,'width':m.get('width'),'height':m.get('height')})
        elif source=='reddit_data':
            d=raw.get('data',raw);add(d.get('url_overridden_by_dest') if str(d.get('post_hint','')).startswith('image') else None,'image')
        return found

    def _store_media(self,case_id,source,record_id,m,row)->int:
        key=_hash({'uri':m['uri'],'type':m['media_type']});mid=new_id('socialmedia163');prov={'record_id':record_id,'run_id':row['run_id'],'public_only':True}
        cur=self.db.execute('INSERT OR IGNORE INTO social_media_163 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(mid,case_id,source,record_id,m['media_type'],m['uri'],key[:32],dumps(m['metadata']),dumps(prov),now_ts(),'needs_review',key))
        return 1 if getattr(cur,'rowcount',0)>0 else 0

    def _extract_interactions(self,source,raw,row,account_id)->list[dict[str,Any]]:
        edges=[]
        rid=row['record_id']
        if account_id:edges.append({'type':'authored','actor':account_id,'target_account':None,'source_record':rid,'target_record':None,'confidence':1.0,'evidence_class':'direct_public_api'})
        if source=='bluesky_public':
            reply=raw.get('record',{}).get('reply') or raw.get('reply') or {}
            parent=(reply.get('parent') or {}).get('uri') if isinstance(reply,dict) else None
            if parent:edges.append({'type':'replied_to','actor':account_id,'source_record':rid,'target_record':parent,'confidence':1.0,'evidence_class':'direct_public_api'})
            reason=raw.get('reason') or {}
            if reason.get('$type','').endswith('reasonRepost'):edges.append({'type':'reposted','actor':None,'source_record':rid,'target_record':raw.get('uri'),'confidence':1.0,'evidence_class':'direct_public_api'})
        elif source=='mastodon_public' and raw.get('in_reply_to_id'):
            edges.append({'type':'replied_to','actor':account_id,'source_record':rid,'target_record':str(raw.get('in_reply_to_id')),'confidence':1.0,'evidence_class':'direct_public_api'})
        elif source=='youtube_data':
            sn=raw.get('snippet',{}); top=sn.get('topLevelComment',{}).get('id') if isinstance(sn,dict) else None
            if top:edges.append({'type':'commented_on','actor':account_id,'source_record':rid,'target_record':str(sn.get('videoId') or top),'confidence':1.0,'evidence_class':'direct_public_api'})
        elif source=='reddit_data':
            d=raw.get('data',raw)
            if d.get('parent_id'):edges.append({'type':'replied_to','actor':account_id,'source_record':rid,'target_record':str(d['parent_id']),'confidence':1.0,'evidence_class':'direct_public_api'})
        return edges

    def _store_interaction(self,case_id,source,e,row)->int:
        if e['type'] not in self.ALLOWED_INTERACTIONS:return 0
        iid=new_id('socialedge163'); prov={'record_id':row['record_id'],'run_id':row['run_id'],'public_only':True}
        vals=(iid,case_id,source,e['type'],e.get('actor'),e.get('target_account'),e.get('source_record'),e.get('target_record'),now_ts(),float(e.get('confidence',0.5)),e.get('evidence_class','inferred'),dumps(prov),'needs_review',_hash({'case_id':case_id,'source':source,'edge':e}))
        cur=self.db.execute('INSERT OR IGNORE INTO social_interactions_163 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',vals)
        return 1 if getattr(cur,'rowcount',0)>0 else 0

    def propose_clusters(self,case_id:str,*,confirmation:str,created_by:str|None=None)->list[dict[str,Any]]:
        if confirmation!=f'PROFILE 163 {case_id} KORRELIEREN':raise PermissionError('explicit profile correlation approval required')
        rows=[dict(r) for r in self.db.all('SELECT * FROM social_accounts_163 WHERE case_id=?',(case_id,))]
        groups=[];used=set()
        for i,a in enumerate(rows):
            if a['account_id'] in used:continue
            members=[a];signals=[];contr=[]
            for b in rows[i+1:]:
                if b['account_id'] in used or a['source_id']==b['source_id']:continue
                score,sig,con=self._account_similarity(a,b)
                if score>=0.55:members.append(b);signals.extend(sig);contr.extend(con);used.add(b['account_id'])
            if len(members)<2:continue
            used.add(a['account_id']);score=min(0.99,0.45+0.12*len(set(signals)));risk=max(0.0,score-0.12*len(set(contr)))
            band='high' if risk>=.8 else 'medium' if risk>=.6 else 'low';cid=new_id('socialcluster163')
            payload={'cluster_id':cid,'case_id':case_id,'members':[x['account_id'] for x in members],'signals':sorted(set(signals)),'contradictions':sorted(set(contr)),'score':round(score,4),'risk_adjusted_score':round(risk,4),'confidence_band':band}
            self.db.execute('INSERT INTO social_identity_clusters_163 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(cid,case_id,members[0].get('display_name') or members[0].get('handle'),dumps(payload['members']),dumps(payload['signals']),dumps(payload['contradictions']),payload['score'],payload['risk_adjusted_score'],band,'needs_review',created_by or self.actor,now_ts(),_hash(payload)))
            groups.append({**payload,'review_status':'needs_review','automatic_identity_confirmation':False})
        self._event(case_id,'clusters_proposed',None,{'count':len(groups)})
        return groups

    def _account_similarity(self,a,b):
        signals=[];contr=[];score=0.0
        ah,bh=a.get('normalized_handle') or '',b.get('normalized_handle') or ''
        if ah and bh:
            if ah==bh:score+=.45;signals.append('same_normalized_handle')
            elif ah.split('.')[0]==bh.split('.')[0]:score+=.3;signals.append('same_handle_stem')
        an,bn=_tokens(a.get('display_name')),_tokens(b.get('display_name'))
        if an and bn:
            jac=len(an&bn)/len(an|bn)
            if jac>=.8:score+=.3;signals.append('display_name_token_match')
            elif jac==0:contr.append('display_name_conflict')
        aa=set(json.loads(a.get('alias_keys_json') or '[]'));ba=set(json.loads(b.get('alias_keys_json') or '[]'))
        if aa&ba:score+=.2;signals.append('shared_alias_key')
        # Platform separation is a useful signal, but never proof.
        if a['source_id']!=b['source_id']:score+=.05;signals.append('cross_platform_observation')
        return min(score,1.0),signals,contr

    def rank_key_persons(self,case_id:str,*,confirmation:str)->list[dict[str,Any]]:
        if confirmation!=f'SCHLUESSELPERSONEN 163 {case_id} BERECHNEN':raise PermissionError('explicit key-person analysis approval required')
        accounts=[dict(r) for r in self.db.all('SELECT * FROM social_accounts_163 WHERE case_id=?',(case_id,))]
        edges=[dict(r) for r in self.db.all('SELECT * FROM social_interactions_163 WHERE case_id=?',(case_id,))]
        degree=Counter();types=defaultdict(set);sources=defaultdict(set)
        for e in edges:
            for aid in (e.get('actor_account_id'),e.get('target_account_id')):
                if aid:degree[aid]+=1;types[aid].add(e['interaction_type']);sources[aid].add(e['source_id'])
        ranked=[]
        for a in accounts:
            aid=a['account_id']; score=min(1.0,0.15*degree[aid]+0.12*len(types[aid])+0.08*len(sources[aid]))
            factors={'observed_interactions':degree[aid],'interaction_types':sorted(types[aid]),'source_count':len(sources[aid]),'public_data_only':True}
            limitations=['centrality_is_not_culpability','missing_private_or_unavailable_data','platform_api_bias','analyst_review_required']
            ranked.append({'account_id':aid,'handle':a.get('handle'),'source_id':a['source_id'],'score':round(score,4),'factors':factors,'limitations':limitations})
        ranked.sort(key=lambda x:(-x['score'],x['account_id']))
        self.db.execute('DELETE FROM social_key_person_scores_163 WHERE case_id=?',(case_id,))
        for pos,x in enumerate(ranked,1):
            sid=new_id('keyscore163');x['rank_position']=pos
            self.db.execute('INSERT INTO social_key_person_scores_163 VALUES(?,?,?,?,?,?,?,?,?)',(sid,case_id,x['account_id'],x['score'],pos,dumps(x['factors']),dumps(x['limitations']),now_ts(),_hash(x)))
        self._event(case_id,'key_persons_ranked',None,{'count':len(ranked)})
        return ranked

    def review_cluster(self,cluster_id:str,*,decision:str,reviewer:str,note:str='')->dict[str,Any]:
        allowed={'accepted','rejected','needs_more_evidence'}
        if decision not in allowed:raise ValueError('invalid cluster review decision')
        row=self.db.one('SELECT * FROM social_identity_clusters_163 WHERE cluster_id=?',(cluster_id,))
        if not row:raise KeyError('cluster not found')
        self.db.execute('UPDATE social_identity_clusters_163 SET review_status=? WHERE cluster_id=?',(decision,cluster_id))
        self._event(row['case_id'],'cluster_reviewed',cluster_id,{'decision':decision,'reviewer':reviewer,'note':note[:500]})
        return {'cluster_id':cluster_id,'decision':decision,'reviewer':reviewer,'automatic_identity_confirmation':False}

    def case_summary(self,case_id:str)->dict[str,Any]:
        def c(table):return int(self.db.one(f'SELECT COUNT(*) n FROM {table} WHERE case_id=?',(case_id,))['n'])
        return {'case_id':case_id,'accounts':c('social_accounts_163'),'media':c('social_media_163'),'interactions':c('social_interactions_163'),'clusters':c('social_identity_clusters_163'),'review_required':True,'automatic_identity_confirmation':False,'opsec':{'public_only':True,'no_private_access':True,'no_interaction':True,'secrets_redacted':True}}

    def _event(self,case_id,event_type,entity_id,details):
        eid=new_id('socialcorrevt163');safe=_safe(details)
        self.db.execute('INSERT INTO social_correlation_events_163 VALUES(?,?,?,?,?,?,?)',(eid,case_id,event_type,entity_id,dumps(safe),now_ts(),_hash({'event_id':eid,'details':safe})))
        try:self.audit.log(f'social_{event_type}_163','social_correlation',entity_id or case_id,case_id,safe)
        except Exception:pass
