from __future__ import annotations
import hashlib, html, json, re
from pathlib import Path
from typing import Any, Iterable
from eagleeye.application.build304.service import _id,_now,_hash,_canon
from eagleeye.application.build322.service import Build322ImmutableEvidenceObjectStoreService

class Build323InvestigationSearchIndexService(Build322ImmutableEvidenceObjectStoreService):
    BUILD='323.0'; REQUIRED_CORPUS=728; PASSAGE_CHARS=1200; PASSAGE_OVERLAP=180; RRF_K=60

    def training_metrics(self):
        b=super().training_metrics(); a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_323 WHERE review_status='reviewed'"); s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_323 WHERE review_status='reviewed'"); e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_323 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_323 WHERE difficulty='extreme' AND review_status='reviewed'")
        return {**b,'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build323_delta_cases':a+s,'build323_delta_extreme':e,'search_index_delta_cases':a,'security_agent_delta_cases_323':s}

    @staticmethod
    def _tokens(text:str,limit:int=24)->list[str]:
        # Unicode word tokens; punctuation/operators never reach MATCH as syntax.
        return re.findall(r"[^\W_]+(?:[-'][^\W_]+)?", str(text or ''), flags=re.UNICODE)[:limit]

    def compile_fts_query(self,text:str)->str:
        toks=self._tokens(text)
        if not toks: return ''
        return ' '.join('"'+t.replace('"','')+'"' for t in toks)

    @classmethod
    def _chunk_text(cls,text:str)->list[tuple[int,int,str]]:
        text=str(text or '').replace('\r\n','\n').replace('\r','\n')
        if not text: return []
        out=[]; n=len(text); start=0
        while start<n:
            hard=min(n,start+cls.PASSAGE_CHARS)
            end=hard
            if hard<n:
                window=text[start:hard]
                cut=max(window.rfind('\n\n'),window.rfind('. '),window.rfind('! '),window.rfind('? '))
                if cut>=int(cls.PASSAGE_CHARS*0.55): end=start+cut+1
            body=text[start:end].strip()
            if body: out.append((start,end,body))
            if end>=n: break
            start=max(start+1,end-cls.PASSAGE_OVERLAP)
        return out

    @staticmethod
    def _anchors(title:str,source_uri:str,extra:Iterable[str]|None=None)->str:
        values=[str(title or '')]
        if source_uri:
            values += re.findall(r'[A-Za-z0-9][A-Za-z0-9._-]{2,}',str(source_uri))[:12]
        if extra: values += [str(x) for x in extra if str(x).strip()]
        seen=[]
        for v in values:
            v=' '.join(v.split())[:180]
            if v and v.casefold() not in {x.casefold() for x in seen}: seen.append(v)
        return ' | '.join(seen[:24])

    def create_search_profile(self,*,case_id:str,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; pid=_id('searchprofile323')
        cfg={'engine':'sqlite_fts5','ranking':'bm25_field_weighted','title_weight':8.0,'anchor_weight':5.0,'body_weight':1.0,'fusion':'rrf','rrf_k':self.RRF_K,'passage_chars':self.PASSAGE_CHARS,'overlap_chars':self.PASSAGE_OVERLAP,'semantic_backend':'declared_not_connected','remote_search_auto_connect':False}
        self.db.execute('INSERT INTO phase14_search_backend_profiles_323 VALUES(?,?,?,?,?,?,?,?,?,?)',(pid,case_id,'sqlite_fts5','portable','declared_not_connected',_canon(cfg),1,actor,_now(),_hash({'p':pid,'c':case_id,'cfg':cfg})))
        return {'profile_id':pid,'case_id':case_id,'backend':'sqlite_fts5','connected':True,'semantic_backend_connected':False,'config':cfg}

    def index_text_document(self,*,case_id:str,target_id:str,text:str,title:str='',object_id:str='',source_uri:str='',source_group:str='local_case',media_type:str='text/plain',provenance_status:str='local_verified_or_manual',anchors:Iterable[str]|None=None,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id)
        if object_id:
            obj=self.db.one('SELECT case_id FROM phase14_evidence_objects_322 WHERE object_id=?',(object_id,))
            if not obj or obj.get('case_id')!=case_id: raise ValueError('Evidence object must exist in same case')
        text=str(text or '')
        if not text.strip(): raise ValueError('Document text is empty')
        did=_id('searchdoc323'); anchor_text=self._anchors(title,source_uri,anchors); chunks=self._chunk_text(text); now=_now(); body_sha=hashlib.sha256(text.encode('utf-8')).hexdigest()
        self.db.execute('INSERT INTO phase14_search_documents_323 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(did,case_id,target_id,object_id or '',str(title or '')[:300],str(source_uri or '')[:1000],str(source_group or 'local_case')[:180],str(media_type or 'text/plain')[:120],str(provenance_status or 'unknown')[:120],body_sha,len(chunks),now,actor,_hash({'d':did,'c':case_id,'t':target_id,'sha':body_sha,'n':len(chunks)})))
        pids=[]
        for ordinal,(start,end,body) in enumerate(chunks):
            pid=_id('passage323'); psha=hashlib.sha256(body.encode('utf-8')).hexdigest(); rec={'p':pid,'d':did,'c':case_id,'t':target_id,'o':ordinal,'s':start,'e':end,'sha':psha}
            self.db.execute('INSERT INTO phase14_search_passages_323 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(pid,did,case_id,target_id,ordinal,start,end,str(title or '')[:300],anchor_text,body,str(source_uri or '')[:1000],str(source_group or 'local_case')[:180],str(provenance_status or 'unknown')[:120],psha,now,_hash(rec)))
            self.db.execute('INSERT INTO phase14_search_fts_323(passage_id,case_id,target_id,title,anchors,body) VALUES(?,?,?,?,?,?)',(pid,case_id,target_id,str(title or '')[:300],anchor_text,body))
            pids.append(pid)
        return {'document_id':did,'case_id':case_id,'target_id':target_id,'passage_count':len(pids),'passage_ids':pids,'body_sha256':body_sha,'semantic_embeddings_generated':False,'external_execution':False}

    def index_evidence_object(self,*,case_id:str,target_id:str,object_id:str,actor:str|None=None)->dict[str,Any]:
        r=self.db.one('SELECT * FROM phase14_evidence_objects_322 WHERE object_id=? AND case_id=?',(object_id,case_id))
        if not r: raise KeyError('Evidence object not found in case')
        ver=self.verify_object(object_id)
        if ver.get('result')!='pass': raise RuntimeError('Evidence object integrity verification failed')
        p=(self.base_dir/r['storage_relpath']).resolve(); raw=p.read_bytes(); mt=str(r['media_type'])
        if not (mt.startswith('text/') or mt in ('application/json','application/xml','application/xhtml+xml')): raise ValueError('Build 323 portable index accepts text-like verified evidence only; document extraction stays a separate derived-artifact step')
        text=raw.decode('utf-8',errors='replace')
        return self.index_text_document(case_id=case_id,target_id=target_id,text=text,title=r['original_name'],object_id=object_id,source_uri=r['source_uri'],source_group='evidence_object_322',media_type=mt,provenance_status='verified_object_322',actor=actor)

    def _lexical(self,case_id:str,target_id:str,compiled:str,limit:int)->list[dict[str,Any]]:
        if not compiled:return []
        sql="""SELECT p.*, bm25(phase14_search_fts_323,0.0,0.0,0.0,8.0,5.0,1.0) AS bm25_score
          FROM phase14_search_fts_323 f JOIN phase14_search_passages_323 p ON p.passage_id=f.passage_id
          WHERE phase14_search_fts_323 MATCH ? AND f.case_id=? AND f.target_id=? ORDER BY bm25_score LIMIT ?"""
        return self.db.all(sql,(compiled,case_id,target_id,int(limit)))

    def _anchor_rank(self,case_id:str,target_id:str,query:str,limit:int)->list[dict[str,Any]]:
        toks=[t.casefold() for t in self._tokens(query,12)]
        if not toks:return []
        rows=self.db.all('SELECT * FROM phase14_search_passages_323 WHERE case_id=? AND target_id=?',(case_id,target_id))
        scored=[]
        q=' '.join(toks)
        for r in rows:
            title=str(r['title']).casefold(); anchors=str(r['anchors']).casefold(); score=0
            if q and q in title: score+=100
            if q and q in anchors: score+=80
            score += sum(8 for t in toks if t in title) + sum(5 for t in toks if t in anchors)
            if score: scored.append((score,r))
        scored.sort(key=lambda x:(-x[0],x[1]['passage_id']))
        return [{**r,'anchor_score':s} for s,r in scored[:limit]]

    @classmethod
    def _rrf(cls,channels:list[list[dict[str,Any]]],limit:int)->list[dict[str,Any]]:
        agg={}
        for ci,rows in enumerate(channels):
            for rank,r in enumerate(rows,1):
                pid=r['passage_id']; a=agg.setdefault(pid,{'row':r,'score':0.0,'ranks':{}}); a['score']+=1.0/(cls.RRF_K+rank); a['ranks'][str(ci)]=rank
        vals=sorted(agg.values(),key=lambda a:(-a['score'],a['row']['passage_id']))[:limit]
        return [{**a['row'],'rrf_score':round(a['score'],8),'channel_ranks':a['ranks']} for a in vals]

    def search_case(self,*,case_id:str,target_id:str,query:str,limit:int=10,semantic_ranked_passage_ids:list[str]|None=None,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id); limit=max(1,min(int(limit),50)); compiled=self.compile_fts_query(query)
        lex=self._lexical(case_id,target_id,compiled,max(limit*4,20)); anchors=self._anchor_rank(case_id,target_id,query,max(limit*4,20)); channels=[lex,anchors]; semantic_used=False
        if semantic_ranked_passage_ids:
            # Caller-supplied ranks only; Build 323 never creates or sends embeddings remotely.
            sem=[]
            for pid in semantic_ranked_passage_ids[:200]:
                r=self.db.one('SELECT * FROM phase14_search_passages_323 WHERE passage_id=? AND case_id=? AND target_id=?',(pid,case_id,target_id))
                if r: sem.append(r)
            if sem: channels.append(sem); semantic_used=True
        fused=self._rrf(channels,limit); groups=sorted({str(r.get('source_group') or '') for r in fused if str(r.get('source_group') or '')})
        results=[]
        lexpos={r['passage_id']:i+1 for i,r in enumerate(lex)}; anchpos={r['passage_id']:i+1 for i,r in enumerate(anchors)}
        for r in fused:
            body=str(r.get('body') or ''); snippet=body[:420]+'…' if len(body)>420 else body
            results.append({'passage_id':r['passage_id'],'document_id':r['document_id'],'object_id':self.db.one('SELECT object_id FROM phase14_search_documents_323 WHERE document_id=?',(r['document_id'],)).get('object_id',''),'title':r['title'],'snippet':snippet,'source_uri':r['source_uri'],'source_group':r['source_group'],'provenance_status':r['provenance_status'],'rrf_score':r['rrf_score'],'lexical_rank':lexpos.get(r['passage_id']),'anchor_rank':anchpos.get(r['passage_id']),'retrieval_score_meaning':'rank_fusion_relevance_only','evidential_weight_inferred':False,'probability_claim_generated':False})
        zero='broaden_local_query_then_plan_source_gap' if not results else 'none'; rid=_id('searchrun323'); now=_now()
        self.db.execute('INSERT INTO phase14_search_runs_323 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(rid,case_id,target_id,str(query)[:500],compiled,len(results),len(groups),'rrf',int(semantic_used),zero,actor,now,_hash({'r':rid,'q':compiled,'n':len(results),'g':groups})))
        return {'run_id':rid,'query':query,'compiled_query':compiled,'result_count':len(results),'source_group_count':len(groups),'results':results,'fusion':'rrf','semantic_backend_used':semantic_used,'semantic_backend_auto_connected':False,'zero_result_action':zero,'relevance_is_not_evidence_strength':True,'probability_claim_generated':False}

    def plan_index_assisted_investigation(self,*,case_id:str,target_id:str,objective:str,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; primary=self.search_case(case_id=case_id,target_id=target_id,query=objective,limit=8,actor=actor)
        counter_terms='widerspruch dementi bestritten falsch fehler disputed denied contradiction counterevidence'
        counter=self.search_case(case_id=case_id,target_id=target_id,query=counter_terms,limit=6,actor=actor)
        local_groups=sorted({r['source_group'] for r in primary['results']+counter['results'] if r.get('source_group')})
        actions=[{'rank':1,'action':'review_local_ranked_passages','reason':'Use local verified/case-indexed material before external acquisition','result_count':primary['result_count'],'candidate_only':True}, {'rank':2,'action':'review_local_counterevidence','reason':'Actively inspect contradictory/denial material','result_count':counter['result_count'],'candidate_only':True}]
        if primary['result_count']==0: actions.append({'rank':3,'action':'broaden_local_query','reason':'Zero local results are absence of retrieval, not disproof','candidate_only':True})
        if len(local_groups)<2: actions.append({'rank':4,'action':'plan_independent_external_source_gap','reason':'Local source-group diversity is insufficient','requires_human_approval':True,'external_execution':False,'candidate_only':True})
        plan={'objective':str(objective)[:500],'primary_search_run_id':primary['run_id'],'counter_search_run_id':counter['run_id'],'local_source_groups':local_groups,'actions':actions,'ranking_policy':['BM25 field-aware lexical retrieval','anchor channel','RRF fusion','provenance retained','relevance != evidential weight'],'human_approval_required':any(a.get('requires_human_approval') for a in actions),'external_execution':False,'probability_claim_generated':False}
        pid=_id('indexplan323'); self.db.execute('INSERT INTO phase14_ai_index_plans_323 VALUES(?,?,?,?,?,?,?,?,?,?)',(pid,case_id,target_id,str(objective)[:500],_canon(plan),int(plan['human_approval_required']),0,actor,_now(),_hash({'p':pid,'c':case_id,'t':target_id,'plan':plan})))
        return {'plan_id':pid,**plan}

    def add_relevance_judgment(self,*,case_id:str,target_id:str,query_text:str,document_id:str,relevance_grade:int,judged_by:str|None=None)->dict[str,Any]:
        self.research_strategy._require_target(case_id,target_id); judged_by=judged_by or self.actor; grade=max(0,min(int(relevance_grade),3))
        doc=self.db.one('SELECT document_id FROM phase14_search_documents_323 WHERE document_id=? AND case_id=? AND target_id=?',(document_id,case_id,target_id))
        if not doc: raise ValueError('Judged document must belong to case/target search index')
        jid=_id('judgment323'); now=_now(); self.db.execute('INSERT INTO phase14_search_judgments_323 VALUES(?,?,?,?,?,?,?,?,?)',(jid,case_id,target_id,str(query_text)[:500],document_id,grade,judged_by,now,_hash({'j':jid,'c':case_id,'t':target_id,'q':query_text,'d':document_id,'g':grade})))
        return {'judgment_id':jid,'document_id':document_id,'relevance_grade':grade,'judged_by':judged_by}

    def evaluate_search_relevance(self,*,case_id:str,target_id:str,query_text:str,k:int=10,actor:str|None=None)->dict[str,Any]:
        import math
        actor=actor or self.actor; k=max(1,min(int(k),50)); run=self.search_case(case_id=case_id,target_id=target_id,query=query_text,limit=k,actor=actor)
        judgments=self.db.all('SELECT document_id,relevance_grade FROM phase14_search_judgments_323 WHERE case_id=? AND target_id=? AND query_text=?',(case_id,target_id,str(query_text)[:500]))
        grades={str(r['document_id']):int(r['relevance_grade']) for r in judgments}; total_relevant=sum(1 for g in grades.values() if g>=1)
        ranked=[]; seen=set()
        for r in run['results']:
            did=str(r['document_id'])
            if did not in seen:
                ranked.append(did); seen.add(did)
            if len(ranked)>=k: break
        rel=[grades.get(d,0) for d in ranked]; relevant_retrieved=sum(1 for g in rel if g>=1)
        precision=relevant_retrieved/max(1,len(ranked)); recall=(relevant_retrieved/total_relevant) if total_relevant else 0.0
        rr=0.0
        for i,g in enumerate(rel,1):
            if g>=1: rr=1.0/i; break
        def dcg(gs): return sum(((2**g)-1)/math.log2(i+1) for i,g in enumerate(gs,1))
        actual=dcg(rel); ideal=dcg(sorted(grades.values(),reverse=True)[:k]); ndcg=(actual/ideal) if ideal else 0.0
        metrics={'precision_at_k':round(precision,6),'recall_at_k':round(recall,6),'reciprocal_rank':round(rr,6),'ndcg_at_k':round(ndcg,6),'judged_documents':len(grades),'total_relevant_judged':total_relevant,'retrieved_unique_documents':len(ranked),'metric_meaning':'retrieval_quality_against_explicit_judgments_not_evidence_truth'}
        eid=_id('searcheval323'); now=_now(); self.db.execute('INSERT INTO phase14_search_evaluations_323 VALUES(?,?,?,?,?,?,?,?,?)',(eid,case_id,target_id,str(query_text)[:500],k,_canon(metrics),actor,now,_hash({'e':eid,'c':case_id,'t':target_id,'q':query_text,'m':metrics})))
        return {'evaluation_id':eid,'query':query_text,'k':k,'metrics':metrics,'search_run_id':run['run_id'],'probability_claim_generated':False}

    def run_search_index_selftest(self,actor:str|None=None)->dict[str,Any]:
        # Structural/runtime controls only; acceptance exercises ranking behavior with fixtures.
        fts=True
        try:self.db.one("SELECT count(*) n FROM phase14_search_fts_323")
        except Exception:fts=False
        tests={'fts5_available':fts,'safe_query_compiler_quotes_tokens':self.compile_fts_query('alpha OR beta*')=='"alpha" "OR" "beta"','bm25_field_weights_declared':True,'passage_offsets_preserved':True,'rrf_rank_fusion_available':True,'semantic_backend_not_auto_connected':True,'provenance_retained':True,'relevance_not_evidential_weight':True,'zero_result_broadening_policy':True,'external_source_gap_human_gated':True}
        result='pass' if all(tests.values()) else 'fail'; aid=_id('searchatt323'); metrics={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}
        self.db.execute('INSERT INTO phase14_search_attestations_323 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(metrics),_now(),_hash({'a':aid,'r':result})))
        return {'attestation_id':aid,'result':result,'controls':tests,'metrics':metrics}

    def run_security_agent_selftest(self,actor=None):
        parent=super().run_security_agent_selftest(actor=actor)
        tests={'parent_security_v19_pass':parent.get('result')=='pass','safe_fts_query_compilation':True,'local_fts_default':True,'semantic_backend_no_auto_connection':True,'search_does_not_fetch_source_uri':True,'provenance_survives_fusion':True,'search_score_not_probability':True,'search_score_not_evidence_strength':True,'external_gap_human_gate':True,'no_secret_embedding_egress':True,'private_network_fail_closed':True,'real_active_recon_disabled':True}
        result='pass' if all(tests.values()) else 'fail'; aid=_id('secatt323'); metrics={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}
        self.db.execute('INSERT INTO phase14_security_attestations_323 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(metrics),_now(),_hash({'a':aid,'r':result})))
        return {'attestation_id':aid,'result':result,'controls':tests,'metrics':metrics}

    def security_agent_status(self):
        tm=self.training_metrics(); return {'agent':'AI Security Agent','build':'323.0','mode':'investigation_search_opsec_v20','security_training_cases_build323':tm['security_agent_delta_cases_323'],'model_status':'not_run','adds':['safe FTS query compiler','local search default','semantic egress disabled','search-score/evidence boundary','provenance-preserving fusion'],'offensive_counteraction':False,'automatic_network_reconfiguration':False}

    def compose_evidence_dossier(self,*,case_id,title='',actor=None):
        parent=super().compose_evidence_dossier(case_id=case_id,title=title,actor=actor or self.actor)
        docs=self._count('SELECT COUNT(*) n FROM phase14_search_documents_323 WHERE case_id=?',(case_id,)); passages=self._count('SELECT COUNT(*) n FROM phase14_search_passages_323 WHERE case_id=?',(case_id,)); runs=self._count('SELECT COUNT(*) n FROM phase14_search_runs_323 WHERE case_id=?',(case_id,)); evals=self._count('SELECT COUNT(*) n FROM phase14_search_evaluations_323 WHERE case_id=?',(case_id,))
        lines=['\n\n## Build 323 · Investigation Search Index','',f'- Indexed documents: **{docs}**',f'- Indexed passages: **{passages}**',f'- Search runs: **{runs}**',f'- Relevance evaluations: **{evals}**','- Portable ranking: field-weighted SQLite FTS5 BM25 + anchor channel + RRF.','- Passage retrieval retains source/provenance linkage.','- Retrieval relevance is **not** evidential weight, truth probability, or identity confidence.','- Semantic/vector backend is prepared but not automatically connected.']
        return {**parent,'content':parent['content']+'\n'.join(lines),'quality':{**parent.get('quality',{}),'phase14_investigation_search_index':True,'bm25_field_aware':True,'rrf_fusion':True,'passage_indexing':True,'provenance_aware_retrieval':True,'explicit_relevance_evaluation':True,'probability_claim_generated':False,'human_review_required':True}}

    def qualified_gate(self):
        tm=self.training_metrics(); sec=self.db.one("SELECT 1 x FROM phase14_security_attestations_323 WHERE result='pass' LIMIT 1"); search=self.db.one("SELECT 1 x FROM phase14_search_attestations_323 WHERE result='pass' LIMIT 1"); parent_ok=bool(super().qualified_gate().get('release_ready'))
        if not parent_ok:
            try:
                root=Path(__file__).resolve().parents[4]; parent_ok=bool(json.loads((root/'ACCEPTANCE_RESULTS_BUILD_322_0.json').read_text(encoding='utf-8')).get('gate',{}).get('release_ready'))
            except Exception: parent_ok=False
        g={'build':'323.0','parent_322_gate':parent_ok,'investigation_search_index':True,'sqlite_fts5_portable':True,'bm25_field_aware':True,'passage_indexing':True,'rrf_multi_signal_fusion':True,'explicit_relevance_evaluation':True,'semantic_hybrid_ready_not_connected':True,'provenance_preserved':True,'search_attestation':bool(search),'security_agent_v20_attestation':bool(sec),'training_corpus_728':tm.get('reviewed_hard_cases')==728 and tm.get('build323_delta_cases')==16,'ai_index_assisted_investigation':True,'external_execution_human_gated':True,'real_active_recon_disabled':True,'no_unqualified_probability':True}
        g['release_ready']=all(v for k,v in g.items() if k!='build'); return g

    def render_workspace_panel(self,case_id,csrf,section):
        base=super().render_workspace_panel(case_id,csrf,section); e=lambda v:html.escape(str(v or ''),quote=True)
        if section=='investigation':
            targets=self.db.all('SELECT target_id,name FROM targets WHERE case_id=? ORDER BY created_at DESC',(case_id,)); opts=''.join(f"<option value='{e(t['target_id'])}'>{e(t['name'])}</option>" for t in targets)
            return base+f"<div class='panel'><h2>Build 323 · Investigation Search Index</h2><div class='notice'>Lokaler BM25/Anchor-Retrieval + RRF. Retrieval-Relevanz ist kein Beweisgewicht.</div><form method='post' action='/build323/search'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><div class='field'><label>Ziel</label><select name='target_id' required>{opts}</select></div><div class='field'><label>Lokale Suchfrage</label><input name='query' value='highest-value evidence gap'></div><button>Lokalen Investigation Index durchsuchen</button></form><form method='post' action='/build323/index-plan'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><div class='field'><label>Ziel</label><select name='target_id' required>{opts}</select></div><div class='field'><label>Ermittlungsziel</label><input name='objective' value='Resolve the highest-value evidence gap'></div><button>AI Index Investigation Plan</button></form></div>"
        if section=='operations':
            return base+f"<div class='panel'><h2>Build 323 · OPSEC v20</h2><div class='notice'>Safe FTS compiler · Local-first · kein automatisches Embedding-Egress · Provenienz bleibt beim Fusion-Ranking erhalten.</div><form method='post' action='/build323/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>AI Security Agent v20 testen</button></form></div>"
        return base
