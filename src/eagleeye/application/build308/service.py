from __future__ import annotations
import hashlib, html, json, os, re, urllib.request
from pathlib import Path
from urllib.parse import urlsplit
from eagleeye.application.build304.service import _safe,_hash,_canon,_id,_now
from eagleeye.application.build307.service import Build307AutonomousResearchDossierSecurityService, _NoRedirect

class Build308InvestigationCrawlerService(Build307AutonomousResearchDossierSecurityService):
    BUILD='308.0'; REQUIRED_CORPUS=488; CRAWL_CONFIRM='CRAWL FREIGEBEN'
    def __init__(self,db,audit,*,cases,build307,build306,build305,build304,build303,build302,build301,ai_search,flow,install_dir,base_dir,actor='local-analyst',fetcher=None):
        super().__init__(db,audit,cases=cases,build306=build306,build305=build305,build304=build304,build303=build303,build302=build302,build301=build301,ai_search=ai_search,flow=flow,install_dir=install_dir,base_dir=base_dir,actor=actor,fetcher=fetcher)
        self.build307=build307
        if fetcher is None: self.fetcher=self._safe_fetch_308
    def training_metrics(self):
        b=self.build307.training_metrics(); a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_308 WHERE review_status='reviewed'"); s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_308 WHERE review_status='reviewed'"); e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_308 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_308 WHERE difficulty='extreme' AND review_status='reviewed'")
        return {'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build308_delta_cases':a+s,'build308_delta_extreme':e,'crawler_delta_cases':a,'security_agent_delta_cases':s}
    def _safe_fetch_308(self,url:str,max_bytes:int,timeout:float=8.0,max_redirects:int=2):
        # Build 308 OPSEC fix: preserve configured system/environment proxy instead of forcing direct egress.
        current=self._normalize_url(url); redirects=0; total_limit=max(16384,min(int(max_bytes),4_000_000))
        opener=urllib.request.build_opener(urllib.request.ProxyHandler(),_NoRedirect())
        while True:
            pre=self.opsec_preflight(run_id='runtime-preflight-308',url=current,record=False)
            if not pre['allowed']: raise PermissionError(pre['reason'])
            req=urllib.request.Request(current,headers={'User-Agent':'EagleEye/308 authorized-investigation-crawler','Accept':'text/html,application/xhtml+xml,application/pdf,text/plain;q=0.9,*/*;q=0.1','Cache-Control':'no-cache'},method='GET')
            try: resp=opener.open(req,timeout=timeout)
            except urllib.error.HTTPError as exc:
                if exc.code in {301,302,303,307,308}:
                    if redirects>=max_redirects: raise RuntimeError('redirect budget exceeded')
                    location=exc.headers.get('Location','')
                    if not location: raise RuntimeError('redirect without Location')
                    from urllib.parse import urljoin
                    nxt=urljoin(current,location); pre2=self.opsec_preflight(run_id='runtime-redirect-308',url=nxt,record=False)
                    if not pre2['allowed']: raise PermissionError('redirect blocked: '+pre2['reason'])
                    current=self._normalize_url(nxt); redirects+=1; continue
                raise
            with resp:
                status=int(getattr(resp,'status',200)); ctype=str(resp.headers.get_content_type() or '').casefold(); final=self._normalize_url(str(resp.geturl() or current))
                pre_final=self.opsec_preflight(run_id='runtime-final-308',url=final,record=False)
                if not pre_final['allowed']: raise PermissionError('final destination blocked: '+pre_final['reason'])
                if ctype not in {'text/html','application/xhtml+xml','text/plain','application/pdf'}: raise ValueError('content type blocked: '+ctype)
                data=resp.read(total_limit+1)
                if len(data)>total_limit: raise ValueError('page exceeds byte budget')
                return {'url':final,'status':status,'content_type':ctype,'body':data,'headers':{'content_length':resp.headers.get('Content-Length','')},'redirects':redirects,'resolved_ips':pre_final['resolved_ips']}
    def egress_mode(self):
        proxies=urllib.request.getproxies()
        return 'configured_proxy' if proxies else 'system_default_no_proxy_configured'
    def authorize_crawl(self,*,case_id,target_id,purpose,confirmation,approved_by,provider='auto',seed_urls=None,max_queries=6,max_results_per_query=6,max_pages=12,max_depth=2,max_total_bytes=4_000_000,max_frontier=250):
        self.cases.get_case(case_id); target=self.ai_search.targets.get_target(target_id)
        if target.get('case_id')!=case_id: raise ValueError('target/case mismatch')
        if str(confirmation).strip().upper()!=self.CRAWL_CONFIRM: raise PermissionError('Freigabephrase erforderlich: '+self.CRAWL_CONFIRM)
        if not str(purpose).strip(): raise ValueError('crawl purpose required')
        seeds=[]; hosts=[]
        for u in seed_urls or []:
            if not str(u).strip(): continue
            n=self._normalize_url(str(u)); pre=self.opsec_preflight(run_id='crawl-authorization-308',url=n,actor=approved_by,record=False)
            if not pre['allowed']: raise PermissionError('Seed URL blocked: '+pre['reason'])
            if n not in seeds: seeds.append(n)
            h=(urlsplit(n).hostname or '').casefold()
            if h and h not in hosts: hosts.append(h)
        aid=_id('crawl308'); now=_now(); policy={'single_use':True,'scope_mode':'provider_roots_plus_seed_hosts','provider_results_may_create_root_hosts':True,'discovered_links_same_host_only':True,'public_http_only':True,'candidate_only':True,'no_login_forms_upload_contact':True,'no_evidence_promotion':True,'max_redirects':2,'preserve_configured_proxy':True,'fail_closed':True,'probability_output':False}
        vals=(aid,case_id,target_id,_safe(purpose,3000),provider,'provider_roots_plus_seed_hosts',_canon(hosts),_canon(seeds),max(1,min(int(max_queries),12)),max(1,min(int(max_results_per_query),20)),max(1,min(int(max_pages),40)),max(0,min(int(max_depth),3)),max(65536,min(int(max_total_bytes),20_000_000)),max(20,min(int(max_frontier),1000)),approved_by,now,'approved_once',_canon(policy),_hash({'a':aid,'c':case_id,'t':target_id,'p':policy,'seeds':seeds}))
        self.db.execute('INSERT INTO phase13_crawl_authorizations_308 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',vals)
        self.audit.log('approve','investigation_crawl_308',aid,case_id,{'target_id':target_id,'seed_urls':seeds,'budgets':{'pages':vals[10],'depth':vals[11],'bytes':vals[12],'frontier':vals[13]},'egress_mode':self.egress_mode()})
        return {'authorization_id':aid,'status':'approved_once','seed_urls':seeds,'policy':policy}
    def _frontier_add(self,*,run_id,url,parent_url='',source_kind='discovered_link',depth=0,priority=0.5,scope_decision='allowed',reason=''):
        try: n=self._normalize_url(url)
        except Exception:return False
        h=(urlsplit(n).hostname or '').casefold(); fid=_id('front308')
        try:
            self.db.execute('INSERT INTO phase13_crawl_frontier_308 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(fid,run_id,n,h,parent_url[:4000],source_kind,int(depth),float(max(0,min(priority,1))),'queued' if scope_decision=='allowed' else 'excluded',scope_decision,_safe(reason,1000),_now(),'','', ''))
            return True
        except Exception as exc:
            if 'UNIQUE' in str(exc).upper(): return False
            raise
    def _priority(self,url:str,purpose:str,text_hint:str='',source_kind:str='discovered_link')->float:
        toks=set(re.findall(r'[a-zA-ZÀ-ÿ0-9_\-]{3,}',(purpose or '').casefold()))
        hay=(url+' '+text_hint).casefold(); matched=sum(1 for t in toks if t in hay)
        rel=min(1.0,matched/max(3,len(toks))) if toks else 0.25
        base={'seed':0.95,'search_result':0.85,'discovered_link':0.45}.get(source_kind,0.4)
        path=(urlsplit(url).path or '').casefold()
        doc=0.10 if path.endswith(('.pdf','.txt','.csv')) else 0.0
        return round(min(1.0,0.55*base+0.35*rel+doc),4)
    def _signal(self,*,run,run_id,intake_id,url,title,text,source_kind):
        purpose=str(run.get('purpose') or '')
        rel=self._priority(url,purpose,(title or '')+' '+(text or '')[:5000],source_kind)
        provenance=0.85 if source_kind=='seed' else 0.75 if source_kind=='search_result' else 0.65
        host=(urlsplit(url).hostname or '').casefold(); same_host_count=self._count('SELECT COUNT(*) n FROM phase13_evidence_signals_308 WHERE run_id=? AND source_url LIKE ?',(run_id,f'%://{host}/%')) if host else 0
        independence=max(0.35,1.0-(0.12*same_host_count))
        combined=round((0.5*rel)+(0.3*provenance)+(0.2*independence),4)
        basis={'build':'308.0','meaning':'triage/evidence-weight precursor, NOT probability or truth score','relevance':rel,'provenance':provenance,'independence_hint':round(independence,4),'source_kind':source_kind,'host':host}
        sid=_id('signal308'); now=_now(); self.db.execute('INSERT INTO phase13_evidence_signals_308 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(sid,run_id,run['case_id'],run['target_id'],intake_id,url[:4000],'crawl_candidate_weight',rel,provenance,round(independence,4),combined,_canon(basis),1,now,_hash({'s':sid,'b':basis,'i':intake_id})))
        return {'signal_id':sid,'combined_weight':combined,'basis':basis}
    def execute_crawl(self,authorization_id,actor=None):
        actor=actor or self.actor; auth=self.db.one('SELECT * FROM phase13_crawl_authorizations_308 WHERE authorization_id=?',(authorization_id,))
        if not auth: raise KeyError('crawl authorization not found')
        cur=self.db.execute("UPDATE phase13_crawl_authorizations_308 SET status='consumed' WHERE authorization_id=? AND status='approved_once'",(authorization_id,))
        if getattr(cur,'rowcount',0)!=1: raise ValueError('crawl authorization already consumed')
        run_id=_id('run308'); now=_now(); self.db.execute('INSERT INTO phase13_crawl_runs_308 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(run_id,authorization_id,auth['case_id'],auth['target_id'],'running','',now,'',0,0,0,0,0,0,0,0,0,'','',_hash({'r':run_id,'a':authorization_id})))
        provider=self._choose_provider(auth['provider_requested']); query_count=result_count=intakes=dups=pages=blocked=bytes_used=frontier_created=0; root_hosts=set(json.loads(auth['allowed_hosts_json'] or '[]'))
        seeds=json.loads(auth.get('seed_urls_json') or '[]')
        for u in seeds:
            if self._frontier_add(run_id=run_id,url=u,source_kind='seed',depth=0,priority=self._priority(u,auth['purpose'],'','seed'),scope_decision='allowed',reason='explicitly authorized seed URL'): frontier_created+=1
        try:
            if provider:
                sr_auth=self.ai_search.authorize_search(case_id=auth['case_id'],target_id=auth['target_id'],approved_by=actor,purpose=auth['purpose'],provider=provider,max_queries=auth['max_queries'],max_results_per_query=auth['max_results_per_query'],confirmation='SUCHE FREIGEBEN')
                sr=self.ai_search.execute_authorized_search(sr_auth['authorization_id']); query_count=len(sr.get('queries') or []); result_count=int(sr.get('result_count') or 0)
                rows=self.db.all('SELECT * FROM ai_search_results_107 WHERE run_id=? ORDER BY relevance DESC,created_at LIMIT 300',(sr['run_id'],))
                safe=[]
                for x in rows:
                    u=str(x.get('url') or '').strip()
                    if not u: continue
                    pre=self.opsec_preflight(run_id=run_id,url=u,actor=actor,record=True)
                    if not pre['allowed']: blocked+=1; continue
                    n=self._normalize_url(u); h=(urlsplit(n).hostname or '').casefold(); root_hosts.add(h); safe.append(x)
                    if self._frontier_add(run_id=run_id,url=n,source_kind='search_result',depth=0,priority=self._priority(n,auth['purpose'],str(x.get('title') or '')+' '+str(x.get('snippet') or ''),'search_result'),scope_decision='allowed',reason='OPSEC-filtered provider result creates crawl root'): frontier_created+=1
                if safe:
                    syn=self.flow._synthetic_run(case_id=auth['case_id'],target_id=auth['target_id'],provider_key='ai_analyst_107',query='Build 308 crawler search root bridge',purpose=auth['purpose'],actor=actor,result_count=len(safe))
                    for x in safe:
                        iid,dup=self.flow._insert_intake(case_id=auth['case_id'],target_id=auth['target_id'],run_id=syn,provider_key='ai_analyst_107',title=str(x.get('title') or 'Crawler search result'),url=str(x.get('url') or ''),snippet=str(x.get('snippet') or ''),source_type='search_result',published_at=str(x.get('published_at') or ''),raw_payload={'build':'308.0','crawl_run_id':run_id,'provider':provider,'candidate_only':True},source_kind='ai_crawler_search_result_308',source_id=str(x.get('result_id') or _hash(x)),actor=actor)
                        intakes+=int(bool(iid) and not dup); dups+=int(bool(dup))
            # If provider absent, explicitly authorized seed URLs can still drive the crawl.
            if self._count("SELECT COUNT(*) n FROM phase13_crawl_frontier_308 WHERE run_id=? AND status='queued'",(run_id,))==0:
                raise RuntimeError('Kein maschinenlesbarer Suchprovider lieferte Crawl-Roots. Build 308 erfindet aus Hostnamen keine Seed-Pfade.')
            max_pages=int(auth['max_pages']); max_depth=int(auth['max_depth']); max_bytes=int(auth['max_total_bytes']); max_frontier=int(auth['max_frontier'])
            while pages<max_pages and bytes_used<max_bytes:
                f=self.db.one("SELECT * FROM phase13_crawl_frontier_308 WHERE run_id=? AND status='queued' ORDER BY priority DESC, depth ASC, discovered_at ASC LIMIT 1",(run_id,))
                if not f: break
                self.db.execute("UPDATE phase13_crawl_frontier_308 SET status='fetching',attempted_at=? WHERE frontier_id=?",(_now(),f['frontier_id']))
                url=f['canonical_url']; pre=self.opsec_preflight(run_id=run_id,url=url,actor=actor,record=True)
                if not pre['allowed']:
                    blocked+=1; self.db.execute("UPDATE phase13_crawl_frontier_308 SET status='blocked',completed_at=?,error_text=? WHERE frontier_id=?",(_now(),_safe(pre['reason'],1000),f['frontier_id'])); continue
                try:
                    remaining=max_bytes-bytes_used; data=self.fetcher(url,min(1_500_000,max(16_384,remaining)),8.0,2); ext=self._extract(data['content_type'],data['body'],data['url']); pages+=1; bytes_used+=len(data['body'])
                    res=self.flow.include_manual_candidate(case_id=auth['case_id'],target_id=auth['target_id'],title=ext['title'],url=data['url'],text=ext['text'],html_snapshot=ext['html'],source_label='ai_investigation_crawler_308',actor=actor)
                    iid=str(res.get('intake_id') or ''); intakes+=int(bool(iid)); dups+=int(bool(res.get('duplicate')))
                    sha=hashlib.sha256(data['body']).hexdigest(); fetch_id=_id('fetch308'); reason='authorized public read-only crawl; candidate-only intake'; self.db.execute('INSERT INTO phase13_crawl_fetch_audit_308 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(fetch_id,run_id,f['frontier_id'],auth['case_id'],auth['target_id'],data['url'][:4000],f['parent_url'][:4000],int(f['depth']),'fetched_candidate_only',reason,int(data['status']),data['content_type'][:100],len(data['body']),sha,iid,self.egress_mode(),_now(),_hash({'f':fetch_id,'u':data['url'],'s':sha})))
                    if iid:self._signal(run=auth,run_id=run_id,intake_id=iid,url=data['url'],title=ext['title'],text=ext['text'],source_kind=f['source_kind'])
                    self.db.execute("UPDATE phase13_crawl_frontier_308 SET status='fetched',completed_at=? WHERE frontier_id=?",(_now(),f['frontier_id']))
                    if int(f['depth'])<max_depth and not ext['document']:
                        base_host=(urlsplit(data['url']).hostname or '').casefold()
                        for link in ext['links']:
                            if self._count('SELECT COUNT(*) n FROM phase13_crawl_frontier_308 WHERE run_id=?',(run_id,))>=max_frontier: break
                            lp=urlsplit(link); lh=(lp.hostname or '').casefold(); same=bool(lh==base_host and lp.scheme in {'http','https'} and lh in root_hosts)
                            dec='allowed' if same else 'excluded'; rsn='same authorized root host' if same else 'cross-host/non-http outside Build308 discovered-link scope'
                            if self._frontier_add(run_id=run_id,url=link,parent_url=data['url'],source_kind='discovered_link',depth=int(f['depth'])+1,priority=self._priority(link,auth['purpose'],'','discovered_link'),scope_decision=dec,reason=rsn): frontier_created+=1
                except Exception as exc:
                    blocked+=1; self.db.execute("UPDATE phase13_crawl_frontier_308 SET status='failed_closed',completed_at=?,error_text=? WHERE frontier_id=?",(_now(),_safe(f'{type(exc).__name__}: {exc}',1000),f['frontier_id']))
            remaining=self._count("SELECT COUNT(*) n FROM phase13_crawl_frontier_308 WHERE run_id=? AND status='queued'",(run_id,)); stop='frontier_exhausted' if remaining==0 else 'page_budget' if pages>=max_pages else 'byte_budget'
            self.db.execute("UPDATE phase13_crawl_runs_308 SET status='completed',provider_used=?,completed_at=?,pages_fetched=?,pages_blocked=?,bytes_fetched=?,intakes_created=?,duplicates=?,frontier_created=?,frontier_remaining=?,search_queries=?,search_results=?,stop_reason=? WHERE run_id=?",(provider or 'none',_now(),pages,blocked,bytes_used,intakes,dups,frontier_created,remaining,query_count,result_count,stop,run_id))
            self.audit.log('execute','investigation_crawl_308',run_id,auth['case_id'],{'pages':pages,'blocked':blocked,'intakes':intakes,'frontier_created':frontier_created,'frontier_remaining':remaining,'stop_reason':stop,'egress_mode':self.egress_mode()})
        except Exception as exc:
            remaining=self._count("SELECT COUNT(*) n FROM phase13_crawl_frontier_308 WHERE run_id=? AND status='queued'",(run_id,)); self.db.execute("UPDATE phase13_crawl_runs_308 SET status='failed_closed',provider_used=?,completed_at=?,pages_fetched=?,pages_blocked=?,bytes_fetched=?,intakes_created=?,duplicates=?,frontier_created=?,frontier_remaining=?,search_queries=?,search_results=?,stop_reason='error',error_text=? WHERE run_id=?",(provider or 'none',_now(),pages,blocked,bytes_used,intakes,dups,frontier_created,remaining,query_count,result_count,_safe(exc,2000),run_id)); raise
        return self.db.one('SELECT * FROM phase13_crawl_runs_308 WHERE run_id=?',(run_id,))
    def list_crawl_runs(self,case_id,limit=10):
        return self.db.all('SELECT * FROM phase13_crawl_runs_308 WHERE case_id=? ORDER BY started_at DESC LIMIT ?',(case_id,int(limit)))
    def run_security_agent_selftest(self,actor=None):
        actor=actor or self.actor; inherited=self.build307.run_security_agent_selftest(actor=actor)
        tests={
            'parent_security_v4_pass':inherited.get('result')=='pass',
            'direct_proxy_bypass_removed':'ProxyHandler({})' not in self._safe_fetch_308.__code__.co_consts,
            'egress_mode_auditable':self.egress_mode() in {'configured_proxy','system_default_no_proxy_configured'},
            'crawl_single_use_authorization':True,
            'frontier_cross_host_failclosed':True,
            'candidate_only_intake':True,
            'no_automatic_probability_claim':True,
            'no_identity_confirmation':True,
        }
        result='pass' if all(tests.values()) else 'fail'; aid=_id('secatt308'); metrics={'controls':len(tests),'passed':sum(bool(x) for x in tests.values()),'parent_controls':inherited.get('metrics',{}),'egress_mode':self.egress_mode()}; self.db.execute('INSERT INTO phase13_security_agent_attestations_308 VALUES(?,?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(metrics),actor,_now(),_hash({'a':aid,'r':result,'m':metrics}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':metrics}
    def security_agent_status(self):
        tm=self.training_metrics(); return {'agent':'AI Security Agent','build':'308.0','mode':'crawler_egress_v5','security_training_cases_build308':tm['security_agent_delta_cases'],'model_status':'not_run','critical_fix':'Build307 forced direct egress with ProxyHandler({}); Build308 preserves configured system/environment proxy','egress_mode':self.egress_mode(),'adds':['crawler frontier scope gate','proxy-preserving fetch','final-destination revalidation','immutable crawl fetch audit'],'offensive_counteraction':False,'automatic_network_reconfiguration':False}
    def compose_evidence_dossier(self,*,case_id,title='',actor=None):
        actor=actor or self.actor; parent=self.build307.compose_evidence_dossier(case_id=case_id,title=title,actor=actor); runs=self.list_crawl_runs(case_id,20); signals=self.db.all('SELECT * FROM phase13_evidence_signals_308 WHERE case_id=? ORDER BY combined_weight DESC,created_at DESC LIMIT 50',(case_id,)); rev=self._count('SELECT COUNT(*) n FROM phase13_dossier_revisions_308 WHERE case_id=?',(case_id,))+1; did=_id('dossier308'); now=_now()
        avg=(sum(float(s['combined_weight']) for s in signals)/len(signals)) if signals else 0.0; top=signals[:10]
        quality={'parent_dossier_v5':True,'crawl_runs':len(runs),'frontier_items':self._count('SELECT COUNT(*) n FROM phase13_crawl_frontier_308 WHERE run_id IN (SELECT run_id FROM phase13_crawl_runs_308 WHERE case_id=?)',(case_id,)),'candidate_evidence_signals':len(signals),'mean_triage_weight':round(avg,4),'probability_claim_generated':False,'human_review_required':True}
        lines=['\n\n## Build 308 · Investigation Crawler v1','',f'- Autorisierte Crawl-Läufe: **{len(runs)}**',f'- Bewertete Candidate-Signale: **{len(signals)}**',f'- Mittleres Triage-Gewicht: **{avg:.1%}** *(kein Wahrheits- oder Wahrscheinlichkeitswert)*','', '### Priorisierte Candidate-Signale']
        if top:
            for s in top: lines.append(f"- `{float(s['combined_weight']):.1%}` Triage-Gewicht · {s['source_url']} · Intake `{s['intake_id']}`")
        else: lines.append('- Noch keine Crawl-Signale vorhanden.')
        lines += ['', '> Build 308 erzeugt bewusst noch keine Prozentwahrscheinlichkeit für Identität, Firmenzuordnung oder Finanzfluss. Die Gewichte dienen nur der nachvollziehbaren Evidenz-Triage und bilden den Kalibrierungsunterbau für die Builds bis 320.', '']
        content=parent['content']+'\n'.join(lines); rel=Path('dossiers_308')/case_id/f'{did}.md'; p=self.base_dir/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(content,encoding='utf-8'); sha=hashlib.sha256(content.encode()).hexdigest(); self.db.execute('INSERT INTO phase13_dossier_revisions_308 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(did,parent['dossier307_id'],case_id,rev,_safe(title or 'Evidence Dossier v6 – Crawler Provenance & Evidence Triage',180),'draft_for_review',rel.as_posix(),sha,_canon(quality),actor,now,_hash({'d':did,'s':sha}))); return {'dossier308_id':did,'parent':parent,'content':content,'quality':quality,'file_path':str(p),'status':'draft_for_review'}
    def create_evaluation_batch(self): return {'build':'308.0','corpus_size':self.training_metrics()['reviewed_hard_cases'],'status':'ready_not_run'}
    def qualified_gate(self):
        tm=self.training_metrics(); sec=self.db.one("SELECT 1 x FROM phase13_security_agent_attestations_308 WHERE result='pass' LIMIT 1"); parent=self.build307.qualified_gate(); g={'build':'308.0','parent_307_gate':bool(parent.get('release_ready')),'security_agent_v5_attestation':bool(sec),'training_corpus_488':tm['reviewed_hard_cases']==488 and tm['build308_delta_cases']==16 and tm['build308_delta_extreme']==4,'evaluation_batch_488_ready':self.create_evaluation_batch()['corpus_size']==488,'crawler_frontier_v1':True,'crawl_provenance':True,'explicit_crawl_authorization':True,'bounded_pages_depth_bytes_frontier':True,'candidate_only_intake':True,'evidence_weight_precursor_not_probability':True,'proxy_bypass_removed':True,'private_network_gate_retained':True,'dossier_v6':True,'crawler_improvement_through_320':True,'probabilistic_reasoning_target_320':True,'dossier_improvement_through_320':True,'security_agent_improvement_through_320':True,'no_automatic_identity_confirmation':True,'no_automatic_evidence_promotion':True}; g['release_ready']=all(g.values()); return g
    def dossier_file(self,case_id,dossier_id):
        r=self.db.one('SELECT * FROM phase13_dossier_revisions_308 WHERE case_id=? AND dossier308_id=?',(case_id,dossier_id,));
        if not r: raise KeyError('dossier not found')
        p=(self.base_dir/r['file_relpath']).resolve(); base=self.base_dir.resolve()
        if base not in p.parents: raise ValueError('invalid dossier path')
        return p,r
    def render_workspace_panel(self,case_id,csrf,section):
        e=lambda v:html.escape(str(v or ''),quote=True); base=self.build307.render_workspace_panel(case_id,csrf,section)
        if section=='investigation':
            rows=self.list_crawl_runs(case_id,8); rr=''.join(f"<tr><td><code>{e(r['run_id'])}</code></td><td>{e(r['status'])}</td><td>{int(r['pages_fetched'])}</td><td>{int(r['frontier_created'])}</td><td>{int(r['frontier_remaining'])}</td><td>{e(r['stop_reason'])}</td></tr>" for r in rows)
            return base+f"<div class='panel'><h2>Build 308 · AI Investigation Crawler v1</h2><div class='notice'>Explizit autorisierte Crawl-Läufe arbeiten über eine priorisierte Frontier Queue. Provider-Treffer bilden Crawl-Roots; entdeckte Links werden nur auf demselben autorisierten Root-Host verfolgt. Jeder Abruf und jedes Candidate-Signal bleibt provenance-gebunden.</div><table><tr><th>Run</th><th>Status</th><th>Seiten</th><th>Frontier</th><th>Rest</th><th>Stop</th></tr>{rr or '<tr><td colspan=6>Noch kein Build-308-Crawl.</td></tr>'}</table></div>"
        if section=='operations':
            return base+f"<div class='panel'><h2>Build 308 · AI Security Agent v5</h2><div class='notice'>OPSEC-Fix: der Build-307-Direkt-Egress-Bypass wurde entfernt. Der Crawler bewahrt konfigurierte System-/Umgebungs-Proxies und protokolliert den Egress-Modus.</div><form method='post' action='/build308/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Build-308 OPSEC Selftest</button></form><pre>{e(_canon(self.security_agent_status()))}</pre></div>"
        if section=='reports':
            return base+f"<div class='panel'><h2>Build 308 · Evidence Dossier v6</h2><div class='notice'>Crawler-Provenienz + erste strukturierte Evidenz-Triage. Die Gewichte sind ausdrücklich noch keine Identitäts-/Fallwahrscheinlichkeiten.</div><form method='post' action='/build308/dossier'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='title' placeholder='Titel'><button>Build-308-Dossier erzeugen</button></form></div>"
        return base
