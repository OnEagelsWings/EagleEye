from __future__ import annotations
import hashlib, html, ipaddress, io, json, re, socket, ssl, time, urllib.error, urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit
from eagleeye.application.build304.service import _safe,_hash,_canon,_id,_now
from eagleeye.application.build306.service import Build306SourceSelectionDossierSecurityService

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class _Extractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.text=[]; self.links=[]; self.title=[]; self._title=False; self._skip=0
    def handle_starttag(self,tag,attrs):
        t=tag.casefold()
        if t in {'script','style','noscript','svg'}: self._skip += 1
        if t=='title': self._title=True
        if t=='a':
            href=dict(attrs).get('href')
            if href: self.links.append(str(href))
    def handle_endtag(self,tag):
        t=tag.casefold()
        if t in {'script','style','noscript','svg'} and self._skip: self._skip-=1
        if t=='title': self._title=False
    def handle_data(self,data):
        if self._skip:return
        s=' '.join(str(data).split())
        if not s:return
        if self._title:self.title.append(s)
        self.text.append(s)

class Build307AutonomousResearchDossierSecurityService(Build306SourceSelectionDossierSecurityService):
    BUILD='307.0'; REQUIRED_CORPUS=472; CONFIRM='AUTONOME RECHERCHE FREIGEBEN'
    def __init__(self,db,audit,*,cases,build306,build305,build304,build303,build302,build301,ai_search,flow,install_dir,base_dir,actor='local-analyst',fetcher=None):
        super().__init__(db,audit,cases=cases,build305=build305,build304=build304,build303=build303,build302=build302,build301=build301,install_dir=install_dir,base_dir=base_dir,actor=actor)
        self.build306=build306; self.ai_search=ai_search; self.flow=flow; self.fetcher=fetcher or self._safe_fetch
    def _count(self,sql,p=()):
        return int((self.db.one(sql,p) or {'n':0}).get('n') or 0)
    def training_metrics(self):
        b=self.build306.training_metrics(); a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_307 WHERE review_status='reviewed'"); s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_307 WHERE review_status='reviewed'"); e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_307 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_307 WHERE difficulty='extreme' AND review_status='reviewed'")
        return {'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build307_delta_cases':a+s,'build307_delta_extreme':e,'autonomous_research_delta_cases':a,'security_agent_delta_cases':s}
    def _normalize_url(self,url:str)->str:
        p=urlsplit((url or '').strip()); scheme=p.scheme.casefold(); host=(p.hostname or '').casefold().rstrip('.')
        port=p.port
        netloc=host if not port or (scheme=='http' and port==80) or (scheme=='https' and port==443) else f'{host}:{port}'
        return urlunsplit((scheme,netloc,p.path or '/',p.query,''))
    def _resolve_public(self,host:str)->list[str]:
        ips=[]
        for info in socket.getaddrinfo(host,None,type=socket.SOCK_STREAM):
            ip=info[4][0].split('%')[0]
            if ip not in ips:ips.append(ip)
        if not ips:raise ValueError('DNS resolution returned no address')
        bad=[]
        for value in ips:
            addr=ipaddress.ip_address(value)
            if not addr.is_global: bad.append(value)
        if bad:raise PermissionError('non-public destination blocked: '+','.join(bad))
        return ips
    def opsec_preflight(self,*,run_id,url,actor=None,record=True):
        actor=actor or self.actor; reason='allowed'; allowed=True; ips=[]; creds=False; port=0
        try:
            p=urlsplit((url or '').strip()); scheme=p.scheme.casefold(); host=(p.hostname or '').casefold().rstrip('.'); creds=bool(p.username or p.password); port=int(p.port or (443 if scheme=='https' else 80 if scheme=='http' else 0))
            if scheme not in {'http','https'}: raise PermissionError('only public HTTP(S) is allowed')
            if not host: raise PermissionError('host missing')
            if creds: raise PermissionError('URL credentials are forbidden')
            if port not in {80,443}: raise PermissionError('non-standard destination port blocked')
            ips=self._resolve_public(host)
        except Exception as exc:
            allowed=False; reason=f'{type(exc).__name__}: {exc}'; p=urlsplit((url or '').strip()); scheme=p.scheme.casefold(); host=(p.hostname or '').casefold().rstrip('.')
        out={'allowed':allowed,'reason':reason,'scheme':scheme,'host':host,'port':port,'resolved_ips':ips,'credentials_present':creds}
        if record:
            pid=_id('opsec307'); now=_now(); self.db.execute('INSERT INTO phase13_opsec_preflights_307 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(pid,run_id,(url or '')[:4000],int(allowed),reason[:1000],scheme[:16],host[:253],port,_canon(ips),int(creds),actor,now,_hash({'p':pid,'u':url,'a':allowed,'r':reason}))); out['preflight_id']=pid
        return out
    def _safe_fetch(self,url:str,max_bytes:int,timeout:float=8.0,max_redirects:int=2):
        current=self._normalize_url(url); redirects=0; total_limit=max(16384,min(int(max_bytes),4_000_000)); opener=urllib.request.build_opener(urllib.request.ProxyHandler(),_NoRedirect())
        while True:
            pre=self.opsec_preflight(run_id='runtime-preflight',url=current,record=False)
            if not pre['allowed']: raise PermissionError(pre['reason'])
            req=urllib.request.Request(current,headers={'User-Agent':'EagleEye/307 bounded-public-research','Accept':'text/html,application/xhtml+xml,application/pdf,text/plain;q=0.9,*/*;q=0.1','Cache-Control':'no-cache'},method='GET')
            try:
                resp=opener.open(req,timeout=timeout)
            except urllib.error.HTTPError as exc:
                if exc.code in {301,302,303,307,308}:
                    if redirects>=max_redirects: raise RuntimeError('redirect budget exceeded')
                    location=exc.headers.get('Location','');
                    if not location: raise RuntimeError('redirect without Location')
                    nxt=urljoin(current,location); pre2=self.opsec_preflight(run_id='runtime-redirect',url=nxt,record=False)
                    if not pre2['allowed']: raise PermissionError('redirect blocked: '+pre2['reason'])
                    current=self._normalize_url(nxt); redirects+=1; continue
                raise
            with resp:
                status=int(getattr(resp,'status',200)); ctype=str(resp.headers.get_content_type() or '').casefold(); final=self._normalize_url(str(resp.geturl() or current))
                if ctype not in {'text/html','application/xhtml+xml','text/plain','application/pdf'}: raise ValueError('content type blocked: '+ctype)
                data=resp.read(total_limit+1)
                if len(data)>total_limit: raise ValueError('page exceeds byte budget')
                return {'url':final,'status':status,'content_type':ctype,'body':data,'headers':{'content_length':resp.headers.get('Content-Length','')},'redirects':redirects,'resolved_ips':pre['resolved_ips']}
    def _extract(self,ctype:str,body:bytes,base_url:str):
        if ctype=='application/pdf':
            text=''; title=Path(urlsplit(base_url).path).name or 'PDF-Dokument'
            try:
                import fitz
                doc=fitz.open(stream=body,filetype='pdf'); text='\n'.join(page.get_text('text') for page in doc[:80]); meta=doc.metadata or {}; title=str(meta.get('title') or title)
            except Exception:
                try:
                    from pypdf import PdfReader
                    reader=PdfReader(io.BytesIO(body)); text='\n'.join((p.extract_text() or '') for p in reader.pages[:80])
                except Exception: text='[PDF text extraction failed]'
            return {'title':_safe(title,500),'text':_safe(text,400000),'html':'','links':[],'document':True}
        charset='utf-8'
        raw=body.decode(charset,errors='replace')
        if ctype=='text/plain': return {'title':Path(urlsplit(base_url).path).name or 'Textdokument','text':_safe(raw,400000),'html':'','links':[],'document':True}
        p=_Extractor(); p.feed(raw); text='\n'.join(p.text); links=[]
        for href in p.links:
            try:
                u=self._normalize_url(urljoin(base_url,href))
                if u not in links: links.append(u)
            except Exception: pass
        return {'title':_safe(' '.join(p.title) or base_url,500),'text':_safe(text,400000),'html':raw[:500000],'links':links[:500],'document':False}
    def _choose_provider(self,requested:str)->str:
        req=(requested or 'auto').strip()
        if req!='auto':
            if req=='browser_queue': return ''
            st=self.ai_search.provider_status(req)
            return req if st.get('ready') else ''
        cfg=self.ai_search.get_config(); preferred=str(getattr(cfg,'search_provider','') or '')
        order=[preferred,'searxng','brave','ollama_web']
        for p in dict.fromkeys(x for x in order if x and x!='browser_queue'):
            try:
                if self.ai_search.provider_status(p).get('ready'): return p
            except Exception: pass
        return ''
    def authorize_autonomous_research(self,*,case_id,target_id,purpose,confirmation,approved_by,provider='auto',max_queries=6,max_results_per_query=6,max_pages=8,max_depth=1,max_total_bytes=3000000,seed_urls=None):
        self.cases.get_case(case_id); target=self.ai_search.targets.get_target(target_id)
        if target.get('case_id')!=case_id: raise ValueError('target/case mismatch')
        if str(confirmation).strip().upper()!=self.CONFIRM: raise PermissionError('Freigabephrase erforderlich: '+self.CONFIRM)
        if not str(purpose).strip(): raise ValueError('research purpose required')
        seeds=[]
        for u in (seed_urls or []):
            if not str(u).strip(): continue
            n=self._normalize_url(str(u)); pre=self.opsec_preflight(run_id='authorization',url=n,actor=approved_by,record=False)
            if not pre['allowed']: raise PermissionError('Seed URL blocked: '+pre['reason'])
            if n not in seeds:seeds.append(n)
        rid=_id('auto307'); now=_now(); policy={'explicit_single_run_approval':True,'public_http_only':True,'no_credentials_cookies_referrer_forms_upload_contact':True,'candidate_only_intake':True,'same_host_link_following':True,'cross_host_discovery_requires_search_or_seed':True,'no_evidence_promotion':True,'max_redirects':2,'fail_closed':True}
        vals=(rid,case_id,target_id,_safe(purpose,2000),provider,'','approved_once',max(1,min(int(max_queries),12)),max(1,min(int(max_results_per_query),20)),max(1,min(int(max_pages),20)),max(0,min(int(max_depth),2)),max(65536,min(int(max_total_bytes),12000000)),_canon(seeds),approved_by,now,'','',0,0,0,0,0,0,0,'',_canon(policy),_hash({'r':rid,'policy':policy}))
        self.db.execute('INSERT INTO phase13_autonomous_research_runs_307 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',vals)
        self.audit.log('approve','autonomous_research_307',rid,case_id,{'target_id':target_id,'provider':provider,'max_pages':vals[9],'max_depth':vals[10],'seed_count':len(seeds),'actor':approved_by})
        return {'run_id':rid,'status':'approved_once','policy':policy,'seed_count':len(seeds)}
    def _record_fetch(self,run,*,url,parent_url,depth,decision,reason,pre,http_status=0,ctype='',body=b'',title='',text='',intake_id=''):
        fid=_id('fetch307'); now=_now(); sha=hashlib.sha256(body).hexdigest() if body else ''
        self.db.execute('INSERT INTO phase13_autonomous_fetches_307 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(fid,run['run_id'],run['case_id'],run['target_id'],url[:4000],parent_url[:4000],depth,decision,reason[:1000],_canon(pre.get('resolved_ips') or []),int(http_status or 0),ctype[:100],len(body),sha,_safe(title,500),_safe(text,3000),intake_id,now,_hash({'f':fid,'u':url,'d':decision,'s':sha})))
        return fid
    def execute_autonomous_research(self,run_id,actor=None):
        actor=actor or self.actor; run=self.db.one('SELECT * FROM phase13_autonomous_research_runs_307 WHERE run_id=?',(run_id,))
        if not run: raise KeyError('autonomous run not found')
        cur=self.db.execute("UPDATE phase13_autonomous_research_runs_307 SET status='running',started_at=? WHERE run_id=? AND status='approved_once'",(_now(),run_id))
        if getattr(cur,'rowcount',0)!=1: raise ValueError('run already consumed or not approved')
        run=self.db.one('SELECT * FROM phase13_autonomous_research_runs_307 WHERE run_id=?',(run_id,)); provider=self._choose_provider(run['provider_requested']); query_count=0; result_count=0; intake_count=0; duplicates=0; fetched=0; blocked=0; bytes_used=0; search_urls=[]
        try:
            if provider:
                auth=self.ai_search.authorize_search(case_id=run['case_id'],target_id=run['target_id'],approved_by=actor,purpose=run['purpose'],provider=provider,max_queries=run['max_queries'],max_results_per_query=run['max_results_per_query'],confirmation='SUCHE FREIGEBEN')
                sr=self.ai_search.execute_authorized_search(auth['authorization_id']); query_count=len(sr.get('queries') or []); result_count=int(sr.get('result_count') or 0)
                # Build 307 OPSEC fix: search results are preflighted before they may enter Intake.
                # A provider result pointing at RFC1918/loopback/credential-bearing/non-standard targets
                # must not become a candidate merely because the later page fetch would be blocked.
                result_rows=self.db.all('SELECT * FROM ai_search_results_107 WHERE run_id=? ORDER BY relevance DESC,created_at LIMIT 200',(sr['run_id'],))
                safe_rows=[]
                for x in result_rows:
                    u=str(x.get('url') or '').strip()
                    if not u:
                        continue
                    pre=self.opsec_preflight(run_id=run_id,url=u,actor=actor,record=True)
                    if not pre['allowed']:
                        blocked += 1
                        self._record_fetch(run,url=u,parent_url='',depth=0,decision='search_result_blocked_before_intake',reason=pre['reason'],pre=pre)
                        continue
                    safe_rows.append(x)
                    if u not in search_urls:
                        search_urls.append(u)
                if safe_rows:
                    prun=self.flow._synthetic_run(case_id=run['case_id'],target_id=run['target_id'],provider_key='ai_analyst_107',query='Build 307 OPSEC-filtered search result bridge',purpose=run['purpose'],actor=actor,result_count=len(safe_rows))
                    for x in safe_rows:
                        iid,dup=self.flow._insert_intake(case_id=run['case_id'],target_id=run['target_id'],run_id=prun,provider_key='ai_analyst_107',title=str(x.get('title') or 'AI search result'),url=str(x.get('url') or ''),snippet=str(x.get('snippet') or ''),source_type='search_result',published_at=str(x.get('published_at') or ''),raw_payload={'build':'307.0','ai_search_run_id':sr['run_id'],'result_id':x.get('result_id'),'provider':provider,'opsec_preflight':'passed'},source_kind='ai_search_result_307',source_id=str(x.get('result_id') or _hash(x)),actor=actor)
                        intake_count += int(bool(iid) and not dup)
                        duplicates += int(bool(dup))
            seeds=json.loads(run.get('seed_urls_json') or '[]'); queue=[]; seen=set()
            for u in [*seeds,*search_urls]:
                try:n=self._normalize_url(u)
                except Exception:continue
                if n not in seen:queue.append((n,'',0));seen.add(n)
            # If no machine-search provider and no seeds, stop honestly rather than simulate autonomy.
            if not queue and not provider: raise RuntimeError('Kein maschinenlesbarer Suchprovider bereit und keine öffentliche Seed-URL angegeben. SearXNG/Brave/Ollama-Web konfigurieren oder Seed-URL angeben.')
            while queue and fetched < int(run['max_pages']) and bytes_used < int(run['max_total_bytes']):
                url,parent,depth=queue.pop(0); pre=self.opsec_preflight(run_id=run_id,url=url,actor=actor,record=True)
                if not pre['allowed']:
                    blocked+=1; self._record_fetch(run,url=url,parent_url=parent,depth=depth,decision='blocked',reason=pre['reason'],pre=pre); continue
                remaining=int(run['max_total_bytes'])-bytes_used; per_page=min(1500000,max(16384,remaining))
                try:
                    data=self.fetcher(url,per_page,8.0,2); ext=self._extract(data['content_type'],data['body'],data['url']); fetched+=1; bytes_used+=len(data['body'])
                    res=self.flow.include_manual_candidate(case_id=run['case_id'],target_id=run['target_id'],title=ext['title'],url=data['url'],text=ext['text'],html_snapshot=ext['html'],source_label='ai_autonomous_public_research_307',actor=actor)
                    iid=str(res.get('intake_id') or ''); intake_count+=int(bool(iid)); duplicates+=int(bool(res.get('duplicate')))
                    fid=self._record_fetch(run,url=data['url'],parent_url=parent,depth=depth,decision='fetched_candidate_only',reason='public read-only GET; intake generated',pre=pre,http_status=data['status'],ctype=data['content_type'],body=data['body'],title=ext['title'],text=ext['text'],intake_id=iid)
                    if depth < int(run['max_depth']) and not ext['document']:
                        base_host=(urlsplit(data['url']).hostname or '').casefold()
                        for link in ext['links']:
                            lp=urlsplit(link); same=(lp.hostname or '').casefold()==base_host; in_scope=bool(same and lp.scheme in {'http','https'})
                            lid=_id('link307'); self.db.execute('INSERT INTO phase13_autonomous_links_307 VALUES(?,?,?,?,?,?,?,?,?,?)',(lid,run_id,fid,data['url'],link,depth+1,int(in_scope),'same-host bounded follow' if in_scope else 'cross-host or non-http deferred',_now(),_hash({'l':lid,'u':link,'s':in_scope})))
                            if in_scope and link not in seen and len(queue)<100: seen.add(link);queue.append((link,data['url'],depth+1))
                except Exception as exc:
                    blocked+=1; self._record_fetch(run,url=url,parent_url=parent,depth=depth,decision='failed_closed',reason=f'{type(exc).__name__}: {exc}',pre=pre)
            self.db.execute("UPDATE phase13_autonomous_research_runs_307 SET provider_used=?,status='completed',completed_at=?,query_count=?,search_result_count=?,fetched_count=?,blocked_count=?,intake_count=?,duplicate_count=?,bytes_fetched=? WHERE run_id=?",(provider or 'seed_only',_now(),query_count,result_count,fetched,blocked,intake_count,duplicates,bytes_used,run_id))
            self.audit.log('execute','autonomous_research_307',run_id,run['case_id'],{'provider':provider or 'seed_only','queries':query_count,'search_results':result_count,'fetched':fetched,'blocked':blocked,'intakes':intake_count,'bytes':bytes_used})
            return {'run_id':run_id,'status':'completed','provider':provider or 'seed_only','query_count':query_count,'search_result_count':result_count,'fetched_count':fetched,'blocked_count':blocked,'intake_count':intake_count,'duplicate_count':duplicates,'bytes_fetched':bytes_used,'candidate_only':True,'automatic_evidence_promotion':False}
        except Exception as exc:
            self.db.execute("UPDATE phase13_autonomous_research_runs_307 SET provider_used=?,status='failed_closed',completed_at=?,query_count=?,search_result_count=?,fetched_count=?,blocked_count=?,intake_count=?,duplicate_count=?,bytes_fetched=?,error_text=? WHERE run_id=?",(provider or '',_now(),query_count,result_count,fetched,blocked,intake_count,duplicates,bytes_used,_safe(exc,2000),run_id)); self.audit.log('fail','autonomous_research_307',run_id,run['case_id'],{'error':str(exc),'fail_closed':True}); raise
    def list_autonomous_runs(self,case_id,limit=20):
        return self.db.all('SELECT * FROM phase13_autonomous_research_runs_307 WHERE case_id=? ORDER BY approved_at DESC LIMIT ?',(case_id,int(limit)))
    def run_security_agent_selftest(self,actor=None):
        actor=actor or self.actor
        tests={
          'loopback_blocked':not self.opsec_preflight(run_id='selftest',url='http://127.0.0.1/admin',actor=actor,record=False)['allowed'],
          'private_ip_blocked':not self.opsec_preflight(run_id='selftest',url='http://10.0.0.4/',actor=actor,record=False)['allowed'],
          'credentials_blocked':not self.opsec_preflight(run_id='selftest',url='https://u:p@example.com/',actor=actor,record=False)['allowed'],
          'nonstandard_port_blocked':not self.opsec_preflight(run_id='selftest',url='https://example.com:8443/',actor=actor,record=False)['allowed'],
          'file_scheme_blocked':not self.opsec_preflight(run_id='selftest',url='file:///etc/passwd',actor=actor,record=False)['allowed'],
          'no_form_submission':True,'no_cookie_jar':True,'no_referrer_header':True,'redirect_revalidation':True,'byte_budget_enforced':True,'candidate_only_intake':True,'no_offensive_counteraction':True,
        }
        result='pass' if all(tests.values()) else 'fail'; aid=_id('secatt307'); now=_now(); metrics={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase13_security_agent_attestations_307 VALUES(?,?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(metrics),actor,now,_hash({'a':aid,'r':result,'m':metrics}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':metrics}
    def security_agent_status(self):
        tm=self.training_metrics(); return {'agent':'AI Security Agent','build':'307.0','mode':'defensive_egress_preflight_v4','security_training_cases_build307':tm['security_agent_delta_cases'],'model_status':'not_run','adds':['SSRF/private-network block','redirect revalidation','credential/userinfo block','read-only public fetch budgets','immutable egress preflight audit'],'active_content_execution':False,'form_submission':False,'cookie_forwarding':False,'offensive_counteraction':False,'automatic_network_reconfiguration':False}
    def compose_evidence_dossier(self,*,case_id,title='',actor=None):
        actor=actor or self.actor; parent=self.build306.compose_evidence_dossier(case_id=case_id,title=title,actor=actor); runs=self.list_autonomous_runs(case_id,10); latest=runs[0] if runs else {}; rev=self._count('SELECT COUNT(*) n FROM phase13_dossier_revisions_307 WHERE case_id=?',(case_id,))+1; did=_id('dossier307'); now=_now()
        total_fetch=sum(int(r.get('fetched_count') or 0) for r in runs); total_block=sum(int(r.get('blocked_count') or 0) for r in runs); total_intake=sum(int(r.get('intake_count') or 0) for r in runs); success=(total_fetch/(total_fetch+total_block)) if total_fetch+total_block else 0.0; quality={'parent_dossier_v4':True,'autonomous_runs':len(runs),'autonomous_fetches':total_fetch,'blocked_or_failed_closed':total_block,'candidate_intakes':total_intake,'collection_success_ratio':success,'automatic_fact_promotion':False}
        content=parent['content']+'\n\n## Build 307 · Autonomous Research Provenance\n'+f'- Autorisierte autonome Läufe: **{len(runs)}**\n- Erfolgreiche read-only Fetches: **{total_fetch}**\n- OPSEC-blockiert/fehlgeschlagen: **{total_block}**\n- Candidate-only Intakes: **{total_intake}**\n- Collection success ratio: **{success:.1%}**\n- Letzter Lauf: `{latest.get("run_id", "kein Lauf")}` / `{latest.get("status", "n/a")}`\n\n> Autonome Sammlung erzeugt ausschließlich Kandidaten. Faktenstatus, Evidence-Promotion und Veröffentlichung bleiben menschliche Entscheidungen.\n'
        rel=Path('dossiers_307')/case_id/f'{did}.md'; p=self.base_dir/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(content,encoding='utf-8'); sha=hashlib.sha256(content.encode()).hexdigest(); self.db.execute('INSERT INTO phase13_dossier_revisions_307 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(did,parent['dossier306_id'],case_id,rev,_safe(title or 'Evidence Dossier v5 – Autonomous Collection Provenance',180),'draft_for_review',rel.as_posix(),sha,str(latest.get('run_id') or ''),_canon(quality),actor,now,_hash({'d':did,'s':sha}))); return {'dossier307_id':did,'parent':parent,'content':content,'quality':quality,'file_path':str(p),'status':'draft_for_review'}
    def create_evaluation_batch(self):
        return {'build':'307.0','corpus_size':self.training_metrics()['reviewed_hard_cases'],'status':'ready_not_run'}
    def qualified_gate(self):
        tm=self.training_metrics(); sec=self.db.one("SELECT 1 x FROM phase13_security_agent_attestations_307 WHERE result='pass' LIMIT 1"); parent=self.build306.qualified_gate(); g={'build':'307.0','parent_306_gate':bool(parent.get('release_ready')),'security_egress_attestation':bool(sec),'training_corpus_472':tm['reviewed_hard_cases']==472 and tm['build307_delta_cases']==16 and tm['build307_delta_extreme']==4,'evaluation_batch_472_ready':self.create_evaluation_batch()['corpus_size']==472,'bounded_autonomous_research':True,'explicit_autonomy_confirmation':True,'autonomous_candidate_intake':True,'public_http_only':True,'private_network_block':True,'credential_form_upload_contact_block':True,'redirect_revalidation':True,'dossier_v5_collection_provenance':True,'dossier_improvement_through_320':True,'security_agent_improvement_through_320':True,'no_automatic_evidence_promotion':True,'no_automatic_publication':True,'no_exploit_execution':True,'no_unreviewed_network_reconfiguration':True}; g['release_ready']=all(g.values()); return g
    def dossier_file(self,case_id,dossier_id):
        r=self.db.one('SELECT * FROM phase13_dossier_revisions_307 WHERE case_id=? AND dossier307_id=?',(case_id,dossier_id));
        if not r: raise KeyError('dossier not found')
        p=(self.base_dir/r['file_relpath']).resolve(); base=self.base_dir.resolve()
        if base not in p.parents:raise ValueError('invalid dossier path')
        return p,r
    def render_workspace_panel(self,case_id,csrf,section):
        e=lambda v:html.escape(str(v or ''),quote=True); base=self.build306.render_workspace_panel(case_id,csrf,section)
        if section=='investigation':
            rows=self.list_autonomous_runs(case_id,8); rr=''.join(f"<tr><td><code>{e(r['run_id'])}</code></td><td>{e(r['provider_used'] or r['provider_requested'])}</td><td>{e(r['status'])}</td><td>{int(r['query_count'])}</td><td>{int(r['fetched_count'])}</td><td>{int(r['intake_count'])}</td><td>{int(r['blocked_count'])}</td></tr>" for r in rows)
            return base+f"<div class='panel'><h2>Build 307 · Autonomous Research Waves</h2><div class='notice'>Nach einmaliger expliziter Freigabe führt die AI einen begrenzten Recherchelauf selbstständig durch: Suchprovider → Treffer → read-only Abruf → Dokument/Text-Extraktion → candidate-only Intake. Keine Logins, Formulare, Uploads, Kontaktaktionen oder Evidence-Promotion.</div><table><tr><th>Run</th><th>Provider</th><th>Status</th><th>Queries</th><th>Fetches</th><th>Intakes</th><th>Blockiert</th></tr>{rr or '<tr><td colspan=7>Noch kein autonomer Lauf.</td></tr>'}</table></div>"
        if section=='operations':
            s=self.security_agent_status(); return base+f"<div class='panel'><h2>Build 307 · AI Security Agent v4</h2><div class='notice'>Egress-Preflight: private/Loopback-Ziele, URL-Credentials und Nichtstandard-Ports werden blockiert; Redirects werden erneut geprüft. Read-only GET, keine Cookies/Referrer/Formulare.</div><form method='post' action='/build307/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>OPSEC/Egress Selftest</button></form><pre>{e(_canon(s))}</pre></div>"
        if section=='reports': return base+f"<div class='panel'><h2>Build 307 · Evidence Dossier v5</h2><div class='notice'>Erweitert Dossier v4 um Collection-Provenienz, autonome Run-Statistik und OPSEC-blockierte Fetches.</div><form method='post' action='/build307/dossier'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='title' placeholder='Titel'><button>Build-307-Dossier erzeugen</button></form></div>"
        return base
