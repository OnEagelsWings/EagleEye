from __future__ import annotations
import hashlib, html, json, re, time, uuid
from pathlib import Path
from typing import Any


def _now(): return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
def _id(p): return f'{p}_{uuid.uuid4().hex[:12]}'
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v): return hashlib.sha256(_canon(v).encode()).hexdigest()
def _norm(v): return re.sub(r'\s+',' ',re.sub(r'[^\wÀ-ÿ&.-]+',' ',str(v or '').casefold())).strip()
def _safe_host(v):
    x=str(v or '').casefold().strip().strip('.')
    return x if re.fullmatch(r'[a-z0-9.-]{3,253}',x) else ''

EMAIL_RE=re.compile(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b',re.I)
PHONE_RE=re.compile(r'(?<!\w)(?:\+?\d{1,3}[\s()/.-])(?:[\d\s()/.-]{6,}\d)(?!\w)')
ALLOWED_TYPES={'public_source','public_organization','public_body','public_document_family'}
SENSITIVE_DOC={'special_category','high_impact_sensitive','controlled_personal_record'}

class Build274CrossCaseKnowledgeService:
    BUILD='274.0'
    def __init__(self,db:Any,audit:Any,*,documents273:Any,source271:Any,collection270:Any,research263:Any,targets:Any,temporal265:Any,compatibility:Any,training:Any,actor:str='local-analyst'):
        self.db=db;self.audit=audit;self.documents273=documents273;self.source271=source271;self.collection270=collection270
        self.research263=research263;self.targets=targets;self.temporal265=temporal265;self.compatibility=compatibility;self.training=training;self.actor=actor

    def _run(self,case_id,run_id):
        r=self.db.one('SELECT * FROM ai_research_runs_263 WHERE case_id=? AND run_id=?',(case_id,run_id))
        if not r:raise KeyError('research run not found')
        return r

    def _profile_country(self,case_id,parent_run_id):
        run=self._run(case_id,parent_run_id);tid=run.get('target_id') or ''
        if tid:
            p=self.documents273.latest_profile(tid)
            if p:return p.get('country_code') or 'UN'
        row=self.db.one('SELECT country_code FROM document_candidates_273 WHERE case_id=? AND parent_run_id=? AND country_code<>\'\' ORDER BY rowid DESC LIMIT 1',(case_id,parent_run_id))
        return (row or {'country_code':'UN'})['country_code'] or 'UN'

    def _reject_sensitive_global_payload(self,knowledge_type,display_label,attributes):
        if knowledge_type not in ALLOWED_TYPES:raise PermissionError('only public source/organization/body/document-family objects may enter global knowledge')
        # Hashes/fingerprints are deliberately excluded from PII pattern scanning: long numeric
        # substrings inside a cryptographic hash are not phone numbers.
        values=[str(display_label)]
        for k,v in dict(attributes or {}).items():
            if 'hash' in str(k).casefold() or 'fingerprint' in str(k).casefold():continue
            if isinstance(v,(list,tuple,set)):values.extend(str(x) for x in v)
            elif isinstance(v,(str,int,float)):values.append(str(v))
        blob='\n'.join(values)
        if EMAIL_RE.search(blob) or PHONE_RE.search(blob) or re.search(r'(?i)\b(target_[a-z0-9]+|CPF\s*[:#-]?|\bRG\s*[:#-]?)',blob):
            raise PermissionError('case-private or sensitive identifier cannot enter global knowledge')

    def publish_public_object(self,*,knowledge_type,public_key,display_label,jurisdiction='UN',source_class='',attributes=None):
        attributes=dict(attributes or {})
        self._reject_sensitive_global_payload(knowledge_type,display_label,attributes)
        key=_norm(public_key)
        if not key:raise ValueError('public key required')
        row=self.db.one('SELECT * FROM global_public_objects_274 WHERE knowledge_type=? AND public_key=?',(knowledge_type,key))
        if row:return row,False
        kid=_id('gpub274');payload={'type':knowledge_type,'key':key,'label':display_label,'jurisdiction':jurisdiction,'source_class':source_class,'attributes':attributes}
        self.db.execute('INSERT INTO global_public_objects_274 VALUES(?,?,?,?,?,?,?,?,?,?)',
            (kid,knowledge_type,key,str(display_label)[:300],jurisdiction or 'UN',source_class or '',_canon(attributes),'public_candidate',_now(),_hash(payload)))
        alias=_norm(display_label)
        if alias:
            self.db.execute('INSERT OR IGNORE INTO global_public_aliases_274 VALUES(?,?,?,?,?,?,?)',
                (_id('galias274'),kid,str(display_label)[:300],alias,'public_alias',_now(),_hash({'k':kid,'a':alias})))
        return self.db.one('SELECT * FROM global_public_objects_274 WHERE knowledge_id=?',(kid,)),True

    def _observe(self,*,obj,case_id,parent_run_id,local_object_type,local_ref,jurisdiction='UN',evidence_refs=None,relevance='observed_public_context'):
        lrh=_hash(str(local_ref));eh=sorted({_hash(str(x)) for x in (evidence_refs or []) if str(x)})
        oid=_id('gobs274');payload={'k':obj['knowledge_id'],'case':case_id,'run':parent_run_id,'type':local_object_type,'ref':lrh,'evidence':eh}
        self.db.execute('INSERT OR IGNORE INTO global_public_observations_274 VALUES(?,?,?,?,?,?,?,?,?,?,?)',
            (oid,obj['knowledge_id'],case_id,parent_run_id,local_object_type,lrh,jurisdiction or 'UN',_canon(eh),'public_observation',_now(),_hash(payload)))
        lid=_id('klink274')
        self.db.execute('INSERT OR IGNORE INTO case_public_knowledge_links_274 VALUES(?,?,?,?,?,?,?,?,?,?,?)',
            (lid,case_id,parent_run_id,obj['knowledge_id'],local_object_type,lrh,relevance,_canon(eh),'case_public_link',_now(),_hash({'k':obj['knowledge_id'],'r':lrh,'rel':relevance})))

    def _source_objects(self,case_id,parent_run_id,jurisdiction):
        out=[];new=0
        rows=self.db.all('SELECT * FROM source_nodes_271 WHERE case_id=? AND run_id=? ORDER BY host,source_id',(case_id,parent_run_id))
        for r in rows:
            host=_safe_host(r.get('host'))
            if not host:continue
            obj,created=self.publish_public_object(knowledge_type='public_source',public_key='source:'+host,display_label=host,jurisdiction=jurisdiction,source_class=r.get('source_class') or '',attributes={'host':host,'source_class':r.get('source_class') or ''})
            self._observe(obj=obj,case_id=case_id,parent_run_id=parent_run_id,local_object_type='source_node',local_ref=r['source_id'],jurisdiction=jurisdiction,evidence_refs=[r.get('evidence_ref')])
            out.append(obj);new+=int(created)
        # Country catalog entries become public source context only when they are auto-query-allowed.
        if jurisdiction and jurisdiction!='UN':
            for r in self.db.all('SELECT * FROM country_source_catalog_273 WHERE country_code IN (?,\'*\') AND auto_query_allowed=1 ORDER BY country_code,source_id',(jurisdiction,)):
                host=_safe_host(r.get('base_domain'))
                if not host:continue
                obj,created=self.publish_public_object(knowledge_type='public_source',public_key='source:'+host,display_label=r['source_name'],jurisdiction=jurisdiction,source_class=r['source_class'],attributes={'host':host,'source_class':r['source_class'],'catalog_source_id':r['source_id'],'access_mode':'public_web'})
                self._observe(obj=obj,case_id=case_id,parent_run_id=parent_run_id,local_object_type='source_catalog',local_ref=r['source_id'],jurisdiction=jurisdiction,evidence_refs=[])
                out.append(obj);new+=int(created)
        return out,new

    def _organization_objects(self,case_id,parent_run_id):
        out=[];new=0
        runs=self.source271._family_runs(case_id,parent_run_id)
        for rid in runs:
            rows=self.db.all("SELECT * FROM network_nodes_266 WHERE case_id=? AND run_id=? AND node_type IN ('organization','public_body') ORDER BY node_id",(case_id,rid))
            for r in rows:
                ktype='public_body' if r['node_type']=='public_body' else 'public_organization'
                # Exact canonical key only. No fuzzy cross-case entity resolution.
                pkey=f"{ktype}:{r['canonical_key']}"
                refs=[]
                for e in self.db.all('SELECT evidence_refs_json FROM network_edges_266 WHERE case_id=? AND run_id=? AND (source_node_id=? OR target_node_id=?)',(case_id,rid,r['node_id'],r['node_id'])):
                    try:refs.extend(json.loads(e['evidence_refs_json']))
                    except Exception:pass
                obj,created=self.publish_public_object(knowledge_type=ktype,public_key=pkey,display_label=r['label'],jurisdiction='UN',source_class='network_public_entity',attributes={'canonical_key':r['canonical_key'],'node_type':r['node_type']})
                self._observe(obj=obj,case_id=case_id,parent_run_id=parent_run_id,local_object_type='network_node',local_ref=r['node_id'],evidence_refs=refs,relevance='public_network_context')
                out.append(obj);new+=int(created)
        return out,new

    def _document_objects(self,case_id,parent_run_id,jurisdiction):
        out=[];new=0
        rows=self.db.all('''SELECT f.* FROM document_families_273 f JOIN (
            SELECT family_key,MAX(revision_no) rev FROM document_families_273 WHERE case_id=? AND parent_run_id=? GROUP BY family_key
            ) x ON x.family_key=f.family_key AND x.rev=f.revision_no WHERE f.case_id=? AND f.parent_run_id=? ORDER BY f.family_key''',(case_id,parent_run_id,case_id,parent_run_id))
        for f in rows:
            try:ids=json.loads(f['member_document_ids_json'])
            except Exception:ids=[]
            if not ids:continue
            docs=[]
            for did in ids:
                r=self.db.one('SELECT * FROM document_candidates_273 WHERE document_id=?',(did,))
                if r:docs.append(r)
            if not docs:continue
            if any(d['sensitivity_class'] in SENSITIVE_DOC or d['access_mode'] not in {'public_web','local_vault'} for d in docs):continue
            # Global object deliberately stores only a family hash + non-sensitive type/language/source-host metadata, never person text.
            fhash=_hash(f['family_key'])
            obj,created=self.publish_public_object(knowledge_type='public_document_family',public_key='docfam:'+fhash,display_label='Public document family '+fhash[:12],jurisdiction=jurisdiction,source_class=f['document_type'],attributes={'family_hash':fhash,'document_type':f['document_type'],'source_hosts':json.loads(f['source_hosts_json']),'languages':json.loads(f['language_set_json'])})
            self._observe(obj=obj,case_id=case_id,parent_run_id=parent_run_id,local_object_type='document_family',local_ref=f['family_id'],jurisdiction=jurisdiction,evidence_refs=json.loads(f['evidence_refs_json']),relevance='public_document_family')
            out.append(obj);new+=int(created)
        return out,new

    def reuse_context(self,*,case_id,target_id='',country_code='UN'):
        country=(country_code or 'UN').upper()
        sources=[]
        rows=self.db.all('''SELECT o.knowledge_id,o.display_label,o.attributes_json,o.source_class,
            MAX(CASE WHEN ob.local_object_type='source_node' THEN 1 ELSE 0 END) evidence_observed
            FROM global_public_objects_274 o JOIN global_public_observations_274 ob ON ob.knowledge_id=o.knowledge_id
            WHERE o.knowledge_type='public_source' AND ob.case_id<>? AND (ob.jurisdiction=? OR ?='UN')
            GROUP BY o.knowledge_id,o.display_label,o.attributes_json,o.source_class
            ORDER BY evidence_observed DESC,o.display_label LIMIT 12''',(case_id,country,country))
        for r in rows:
            try:a=json.loads(r['attributes_json'])
            except Exception:a={}
            host=_safe_host(a.get('host'))
            if host:sources.append({'knowledge_id':r['knowledge_id'],'source_name':r['display_label'],'host':host,'source_class':r['source_class']})
        orgs=[]
        if target_id:
            t=self.targets.get_target(target_id)
            companies={_norm(x) for x in t.get('companies_json',[]) if _norm(x)}
            if companies:
                for r in self.db.all("SELECT * FROM global_public_objects_274 WHERE knowledge_type='public_organization' ORDER BY display_label"):
                    if _norm(r['display_label']) in companies and self.db.one('SELECT 1 x FROM global_public_observations_274 WHERE knowledge_id=? AND case_id<>? LIMIT 1',(r['knowledge_id'],case_id)):
                        orgs.append({'knowledge_id':r['knowledge_id'],'label':r['display_label'],'reuse_mode':'public_org_context_only'})
        return {'public_sources':sources,'public_organizations':orgs,'person_cross_case_merge':False,'private_case_data_exported':False}

    def create_person_document_run(self,*,case_id,user_request,target_id='',country_code='',birth_place='',actor=None):
        out=self.documents273.create_person_document_run(case_id=case_id,user_request=user_request,target_id=target_id,country_code=country_code,birth_place=birth_place,actor=actor or self.actor)
        profile=self.documents273.latest_profile(out['target_id']);country=(profile or {}).get('country_code') or out.get('country_code') or 'UN'
        ctx=self.reuse_context(case_id=case_id,target_id=out['target_id'],country_code=country)
        existing={r['query_text'].casefold() for r in self.db.all('SELECT query_text FROM ai_research_queries_263 WHERE run_id=?',(out['run_id'],))}
        target=self.targets.get_target(out['target_id']);added=[]
        for src in ctx['public_sources'][:3]:
            q=f'site:{src["host"]} "{target["name"]}"'
            if q.casefold() in existing:continue
            qid=_id('xq274');urls=self.research263._urls(q);payload={'q':q,'source':src['knowledge_id'],'public_only':True}
            self.db.execute('INSERT INTO ai_research_queries_263 VALUES(?,?,?,?,?,?,?,?,?,?)',
                (qid,out['run_id'],case_id,q,'Cross-case public source reuse; verify relevance independently',src['source_class'] or 'cross_case_public_source',_canon(urls),'planned',_now(),_hash(payload)))
            added.append(qid);existing.add(q.casefold())
        for org in ctx['public_organizations'][:2]:
            q=f'"{target["name"]}" "{org["label"]}"'
            if q.casefold() in existing:continue
            qid=_id('xq274');urls=self.research263._urls(q)
            self.db.execute('INSERT INTO ai_research_queries_263 VALUES(?,?,?,?,?,?,?,?,?,?)',
                (qid,out['run_id'],case_id,q,'Public organization context reuse; does not confirm person identity','cross_case_public_org_context',_canon(urls),'planned',_now(),_hash({'q':q,'org':org['knowledge_id']})))
            added.append(qid);existing.add(q.casefold())
        out['cross_case_reuse_274']={**ctx,'added_query_ids':added,'requires_ok_for_external_execution':bool(added)}
        return out

    def audit_case_isolation(self,*,case_id,parent_run_id):
        blob='\n'.join((r['display_label']+' '+r['attributes_json']) for r in self.db.all('SELECT display_label,attributes_json FROM global_public_objects_274'))
        gperson=(self.db.one("SELECT COUNT(*) n FROM global_public_objects_274 WHERE knowledge_type NOT IN ('public_source','public_organization','public_body','public_document_family')") or {'n':0})['n']
        forbidden=(self.db.one("SELECT COUNT(*) n FROM case_public_knowledge_links_274 WHERE local_object_type NOT IN ('source_node','network_node','document_family','source_catalog')") or {'n':0})['n']
        emails=len(EMAIL_RE.findall(blob));phones=len(PHONE_RE.findall(blob));target_hits=0;username_hits=0
        for t in self.targets.list_targets(case_id):
            if t['target_id'] and t['target_id'] in blob:target_hits+=1
            for u in t.get('usernames_json',[]):
                if len(str(u))>=4 and str(u).casefold() in blob.casefold():username_hits+=1
            for e in t.get('emails_json',[]):
                if e and str(e).casefold() in blob.casefold():emails+=1
        result='pass' if not any((gperson,forbidden,emails,phones,target_hits,username_hits)) else 'fail'
        notes=[]
        if result=='pass':notes.append('global layer contains only approved public object types and no current-case target identifiers')
        else:notes.append('case/private leakage indicator detected; global reuse must be treated as blocked until remediated')
        aid=_id('caseiso274');payload={'gperson':gperson,'forbidden':forbidden,'emails':emails,'phones':phones,'targets':target_hits,'users':username_hits,'result':result}
        self.db.execute('INSERT INTO case_isolation_audits_274 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (aid,case_id,parent_run_id,gperson,forbidden,emails,phones,target_hits,username_hits,result,_canon(notes),_now(),_hash(payload)))
        return {'audit_id':aid,'result':result,'global_person_object_count':gperson,'forbidden_local_link_count':forbidden,'email_pattern_count':emails,'phone_pattern_count':phones,'raw_target_id_pattern_count':target_hits,'raw_username_pattern_count':username_hits,'notes':notes}

    def verify_browser_hardening(self,*,case_id,run_id,high_risk=False):
        probe=None;notes=[]
        try:
            probe=self.temporal265.create_opsec_context(case_id=case_id,run_id=run_id,mode='build274_hardening_probe')
            profile=Path(probe['profile_path']);userjs=profile/'user.js';txt=userjs.read_text(encoding='utf-8') if userjs.exists() else ''
            checks={
                'profile_present':int(profile.exists() and userjs.exists()),
                'private_browsing':int('browser.privatebrowsing.autostart", true' in txt),
                'referrer_disabled':int('network.http.sendRefererHeader", 0' in txt),
                'webrtc_disabled':int('media.peerconnection.enabled", false' in txt),
                'dns_prefetch_disabled':int('network.dns.disablePrefetch", true' in txt),
                'speculative_connections_disabled':int('network.http.speculative-parallel-limit", 0' in txt and 'browser.urlbar.speculativeConnect.enabled", false' in txt and 'network.prefetch-next", false' in txt),
                'resist_fingerprinting':int('privacy.resistFingerprinting", true' in txt),
                'telemetry_disabled':int('toolkit.telemetry.enabled", false' in txt and 'datareporting.healthreport.uploadEnabled", false' in txt),
                'clear_on_shutdown':int(all(x in txt for x in ('privacy.clearOnShutdown.cookies", true','privacy.clearOnShutdown.cache", true','privacy.clearOnShutdown.history", true'))),
            }
            rel=str(profile.relative_to(Path(self.db.path).parent));cnt=(self.db.one('SELECT COUNT(*) n FROM opsec_sessions_265 WHERE ephemeral_profile_relpath=?',(rel,)) or {'n':0})['n']
            checks['profile_unique']=int(cnt==1)
            residue=int(any(p.is_file() and p.name.casefold() in {'cookies.sqlite','places.sqlite','history.sqlite'} for p in profile.rglob('*')))
            required=all(checks.values()) and not residue
            result='pass' if required else ('blocked' if high_risk else 'warning')
            if not required:notes.append('one or more browser hardening controls are absent or residue is present')
            if result=='pass':notes.append('ephemeral Firefox configuration satisfies Build274 local hardening profile; this is not a network-anonymity proof')
            aid=_id('bhard274');payload={**checks,'residue':residue,'result':result}
            self.db.execute('INSERT INTO browser_hardening_audits_274 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (aid,case_id,run_id,checks['profile_present'],checks['profile_unique'],checks['private_browsing'],checks['referrer_disabled'],checks['webrtc_disabled'],checks['dns_prefetch_disabled'],checks['speculative_connections_disabled'],checks['resist_fingerprinting'],checks['telemetry_disabled'],checks['clear_on_shutdown'],residue,result,_canon(notes),_now(),_hash(payload)))
            return {'audit_id':aid,'result':result,**{k:bool(v) for k,v in checks.items()},'residue_present':bool(residue),'network_anonymity_verified':False,'notes':notes}
        finally:
            if probe:
                try:self.temporal265.cleanup_context(probe['session_id'],notes='Build274 browser hardening probe cleanup')
                except Exception:pass

    def analyze_family(self,*,case_id,parent_run_id,actor=None):
        actor=actor or self.actor;self._run(case_id,parent_run_id);jur=self._profile_country(case_id,parent_run_id)
        src,snew=self._source_objects(case_id,parent_run_id,jur);org,onew=self._organization_objects(case_id,parent_run_id);docs,dnew=self._document_objects(case_id,parent_run_id,jur)
        current_ids={o['knowledge_id'] for o in src+org+docs}
        reused=0
        for kid in current_ids:
            n=(self.db.one('SELECT COUNT(DISTINCT case_id) n FROM global_public_observations_274 WHERE knowledge_id=?',(kid,)) or {'n':0})['n']
            reused+=int(n>1)
        iso=self.audit_case_isolation(case_id=case_id,parent_run_id=parent_run_id)
        hard=self.verify_browser_hardening(case_id=case_id,run_id=parent_run_id,high_risk=False)
        run=self._run(case_id,parent_run_id);reuse=self.reuse_context(case_id=case_id,target_id=run.get('target_id') or '',country_code=jur)
        suggestions=[]
        for s in reuse['public_sources'][:8]:suggestions.append({'kind':'public_source','host':s['host'],'source_name':s['source_name'],'knowledge_id':s['knowledge_id']})
        for o in reuse['public_organizations'][:5]:suggestions.append({'kind':'public_organization','label':o['label'],'knowledge_id':o['knowledge_id'],'person_identity_confirmed':False})
        last=self.db.one('SELECT MAX(revision_no) n FROM cross_case_knowledge_briefs_274 WHERE case_id=? AND parent_run_id=?',(case_id,parent_run_id));rev=int((last or {'n':0})['n'] or 0)+1
        counts={'public_source':len({x['knowledge_id'] for x in src}),'public_organization':len({x['knowledge_id'] for x in org if x['knowledge_type']=='public_organization'}),'public_body':len({x['knowledge_id'] for x in org if x['knowledge_type']=='public_body'}),'public_document_family':len({x['knowledge_id'] for x in docs})}
        summary=(f"Cross-case public knowledge: {counts['public_source']} public sources, {counts['public_organization']} organizations, {counts['public_body']} public bodies and {counts['public_document_family']} non-sensitive document families. "
                 f"{reused} current public objects have observations in another case. Persons and private target identifiers remain case-local and are never merged globally.")
        bid=_id('xbrief274');payload={'counts':counts,'reused':reused,'new':snew+onew+dnew,'suggestions':suggestions,'privacy':iso['result']}
        self.db.execute('INSERT INTO cross_case_knowledge_briefs_274 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (bid,case_id,parent_run_id,rev,counts['public_source'],counts['public_organization'],counts['public_body'],counts['public_document_family'],reused,snew+onew+dnew,_canon(suggestions),int(iso['result']=='pass'),summary,'analysis_basis',actor,_now(),_hash(payload)))
        self._event(case_id,'cross_case_public_knowledge','research_run',parent_run_id,actor,{'brief_id':bid,'reused':reused,'privacy':iso['result']})
        return {'brief_id':bid,'revision_no':rev,**counts,'reused_from_other_cases_count':reused,'new_global_object_count':snew+onew+dnew,'reuse_suggestions':suggestions,'privacy_guard':iso,'browser_hardening':hard,'summary':summary,'person_cross_case_merge':False}

    def augment_collection_plan(self,*,case_id,plan_id,brief_id):
        plan=self.collection270.plan(plan_id);b=self.db.one('SELECT * FROM cross_case_knowledge_briefs_274 WHERE brief_id=?',(brief_id,))
        if not b or b['case_id']!=case_id or plan['case_id']!=case_id:raise ValueError('plan/brief mismatch')
        suggestions=json.loads(b['reuse_suggestions_json']);existing={t['query_text'].casefold() for t in plan['tasks']};run=self._run(case_id,plan['parent_run_id']);target=self.targets.get_target(run['target_id']) if run.get('target_id') else None
        added=[]
        if target:
            for s in [x for x in suggestions if x.get('kind')=='public_source'][:2]:
                q=f'site:{s["host"]} "{target["name"]}"'
                if q.casefold() in existing:continue
                tid=_id('ctask274');payload={'q':q,'brief':brief_id,'public_only':True}
                self.db.execute('INSERT INTO collection_tasks_270 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (tid,plan_id,'xcasegap274_'+brief_id,case_id,plan['parent_run_id'],q,'Cross-case public-source reuse: independently verify relevance','cross_case_public_source',16,6,1,'planned',_now(),_hash(payload)))
                added.append(tid);existing.add(q.casefold())
        return {'plan_id':plan_id,'added_task_ids':added,'requires_new_ok':True,'automatic_execution':False,'person_cross_case_merge':False}

    def execute_initial_run(self,*,case_id,run_id,confirmation,approved_by=None,provider='',max_queries=8,max_results_per_query=8,proxy_mode='direct',proxy_label='',opsec_mode='standard'):
        if opsec_mode=='high_risk':
            h=self.verify_browser_hardening(case_id=case_id,run_id=run_id,high_risk=True)
            if h['result']=='blocked':raise RuntimeError('Build274 browser hardening preflight blocked high-risk run')
        out=self.documents273.execute_initial_run(case_id=case_id,run_id=run_id,confirmation=confirmation,approved_by=approved_by or self.actor,provider=provider,max_queries=max_queries,max_results_per_query=max_results_per_query,proxy_mode=proxy_mode,proxy_label=proxy_label,opsec_mode=opsec_mode)
        out['cross_case_knowledge_274']=self.analyze_family(case_id=case_id,parent_run_id=run_id,actor=approved_by or self.actor)
        return out

    def approve_and_execute_wave(self,*,case_id,plan_id,confirmation,approved_by=None,provider='browser_queue',opsec_mode='standard',task_budget=None,result_budget=8):
        plan=self.collection270.plan(plan_id)
        if opsec_mode=='high_risk':
            h=self.verify_browser_hardening(case_id=case_id,run_id=plan['parent_run_id'],high_risk=True)
            if h['result']=='blocked':raise RuntimeError('Build274 browser hardening preflight blocked high-risk wave')
        out=self.documents273.approve_and_execute_wave(case_id=case_id,plan_id=plan_id,confirmation=confirmation,approved_by=approved_by or self.actor,provider=provider,opsec_mode=opsec_mode,task_budget=task_budget,result_budget=result_budget)
        brief=self.analyze_family(case_id=case_id,parent_run_id=plan['parent_run_id'],actor=approved_by or self.actor);aug=self.augment_collection_plan(case_id=case_id,plan_id=plan_id,brief_id=brief['brief_id'])
        out['cross_case_knowledge_274']=brief;out['cross_case_task_ids']=aug['added_task_ids'];out['requires_new_ok_for_next_wave']=True
        return out

    def review_brief(self,*,case_id,brief_id,decision,rationale,reviewer=None):
        b=self.db.one('SELECT * FROM cross_case_knowledge_briefs_274 WHERE brief_id=?',(brief_id,))
        if not b or b['case_id']!=case_id:raise KeyError('brief')
        reviewer=reviewer or self.actor
        if reviewer==b['created_by']:raise ValueError('independent reviewer required')
        if decision not in {'retain_analysis','needs_more_evidence','challenge_analysis','reject_analysis'}:raise ValueError('invalid decision')
        rid=_id('xrev274');self.db.execute('INSERT INTO cross_case_knowledge_reviews_274 VALUES(?,?,?,?,?,?,?,?)',(rid,brief_id,case_id,decision,rationale,reviewer,_now(),_hash({'d':decision,'r':rationale})))
        return {'review_id':rid,'decision':decision}

    def stage_training_candidate(self,*,case_id,brief_id,actor=None):
        b=self.db.one('SELECT * FROM cross_case_knowledge_briefs_274 WHERE brief_id=? AND case_id=?',(brief_id,case_id));rv=self.db.one('SELECT * FROM cross_case_knowledge_reviews_274 WHERE brief_id=?',(brief_id,))
        if not b or not rv or rv['decision']!='retain_analysis' or not b['privacy_guard_passed']:raise PermissionError('independently retained privacy-clean cross-case brief required')
        return self.training.add_example(case_id=case_id,instruction='Reuse only public cross-case source, organization, public-body and non-sensitive document-family knowledge. Never globalize or merge persons, target identifiers, emails, usernames, addresses or sensitive records.',response=_canon({'public_sources':b['public_source_count'],'public_organizations':b['public_organization_count'],'public_bodies':b['public_body_count'],'public_document_families':b['public_document_family_count'],'reused_from_other_cases':b['reused_from_other_cases_count'],'person_cross_case_merge':False}),context={'build':'274.0','public_only':True,'case_private_persons':True,'human_review_required':True},evidence_refs=[],language='de',source_type='build274_reviewed_cross_case_public_knowledge',source_ref=brief_id,created_by=actor or self.actor,confirmation=f'TRAINING EXAMPLE 228 {case_id} ANLEGEN')

    def ai_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM ai_cross_case_benchmarks_274 WHERE review_status='reviewed'") or {'n':0})['n'];fam=(self.db.one('SELECT COUNT(DISTINCT task_family) n FROM ai_cross_case_benchmarks_274') or {'n':0})['n']
        return {'reviewed_benchmarks':n,'task_families':fam,'public_cross_case_reuse':True,'person_cross_case_merge':False,'document_hash_reuse':True,'ai_research_context_reuse':True,'automatic_model_activation':False,'automatic_adapter_activation':False}
    def opsec_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM opsec_controls_274 WHERE review_status='verified'") or {'n':0})['n']
        return {'verified_controls':n,'global_person_objects_allowed':0,'case_private_identifier_export':0,'browser_hardening_verification':1,'gateway_fail_closed_preserved':1,'automatic_ip_rotation':0,'disposable_email_generation':0}
    def qualified_gate(self):
        caps=self.compatibility.capabilities();a=self.ai_metrics();o=self.opsec_metrics()
        g={'build':'274.0','main_goal':bool(self.db.one("SELECT name FROM sqlite_master WHERE name='global_public_objects_274'")),'ai_delta':a['reviewed_benchmarks']>=64 and a['task_families']>=25,'opsec_delta':o['verified_controls']>=60 and o['global_person_objects_allowed']==0,'capability_regression':'country_aware_person_document_research_273' in caps and 'document_corpus_intelligence_273' in caps,'parent_build_gate':self.documents273.qualified_gate()['release_ready']}
        g['release_ready']=all(g[k] for k in ('main_goal','ai_delta','opsec_delta','capability_regression','parent_build_gate'));return g

    def render_workspace_panel(self,*,case_id,csrf):
        e=lambda v:html.escape(str(v or ''),quote=True)
        briefs=self.db.all('SELECT * FROM cross_case_knowledge_briefs_274 WHERE case_id=? ORDER BY created_at DESC LIMIT 12',(case_id,))
        rows=''.join(f"<tr><td><code>{e(b['parent_run_id'])}</code></td><td>{e(b['revision_no'])}</td><td>{e(b['public_source_count'])}</td><td>{e(b['public_organization_count']+b['public_body_count'])}</td><td>{e(b['public_document_family_count'])}</td><td>{e(b['reused_from_other_cases_count'])}</td><td>{e(b['summary'])}</td></tr>" for b in briefs)
        audits=self.db.all('SELECT * FROM case_isolation_audits_274 WHERE case_id=? ORDER BY created_at DESC LIMIT 12',(case_id,))
        arows=''.join(f"<tr><td>{e(a['parent_run_id'])}</td><td>{e(a['result'])}</td><td>{e(a['global_person_object_count'])}</td><td>{e(a['email_pattern_count'])}</td><td>{e(a['raw_target_id_pattern_count'])}</td></tr>" for a in audits)
        return f"""<section class='card'><h2>Cross-Case Knowledge Layer · Build 274</h2>
        <p><b>Case-local evidence → public-only knowledge objects → exact-key reuse → AI research context → case-bound verification.</b></p>
        <p>Global erlaubt: öffentliche Quellen, Organisationen/Behörden und nicht-sensitive Dokumentfamilien. Personen, Zielprofile, E-Mails, Usernames, Adressen und sensible Akten bleiben strikt im jeweiligen Fall.</p>
        <form method='post' action='/build274/analyze'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='parent_run_id' placeholder='Parent Research Run ID' required><button>Public Knowledge + Isolation Audit aktualisieren</button></form>
        <h3>Cross-Case Briefs</h3><table><tr><th>Run</th><th>Rev.</th><th>Sources</th><th>Orgs/Bodies</th><th>Doc Families</th><th>Cross-Case Reuse</th><th>Summary</th></tr>{rows or '<tr><td colspan="7">Noch kein Cross-Case Brief.</td></tr>'}</table>
        <details><summary><b>Brief unabhängig reviewen</b></summary><form method='post' action='/build274/review'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='brief_id' placeholder='Brief ID' required><select name='decision'><option>retain_analysis</option><option>needs_more_evidence</option><option>challenge_analysis</option><option>reject_analysis</option></select><textarea name='rationale' required placeholder='Review-Begründung'></textarea><button>Review speichern</button></form></details>
        <h3>Case-Isolation Audit</h3><table><tr><th>Run</th><th>Result</th><th>Global Persons</th><th>Email Leaks</th><th>Target-ID Leaks</th></tr>{arows or '<tr><td colspan="5">Noch kein Isolation Audit.</td></tr>'}</table>
        <p>Browser-Hardening wird zusätzlich mit einem frischen ephemeren Firefox-Profil verifiziert. Die Prüfung ist eine lokale Konfigurationsprüfung und keine Anonymitätsgarantie.</p>
        <pre>{e(_canon(self.qualified_gate()))}</pre></section>"""

    def _event(self,cid,etype,otype,oid,actor,payload):
        prev=self.db.one('SELECT event_hash FROM build274_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(cid,));ph=prev['event_hash'] if prev else 'GENESIS';eid=_id('evt274');now=_now();data={'event_id':eid,'case_id':cid,'event_type':etype,'object_type':otype,'object_id':oid,'actor':actor,'payload':payload,'previous_hash':ph,'created_at':now}
        self.db.execute('INSERT INTO build274_events VALUES(?,?,?,?,?,?,?,?,?,?)',(eid,cid,etype,otype,oid,actor,_canon(payload),ph,_hash(data),now))
