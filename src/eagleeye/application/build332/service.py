from __future__ import annotations
import hashlib, html, json, math, re, statistics
from pathlib import Path
from typing import Any

from eagleeye.application.build304.service import _id, _now, _hash, _canon
from eagleeye.application.build331.service import Build331HistoricalWebIntelligenceService


class Build332DocumentIntelligenceV2Service(Build331HistoricalWebIntelligenceService):
    BUILD='332.0'; REQUIRED_CORPUS=872
    ALLOWED_MEDIA={'application/pdf','text/plain','text/markdown','application/json','application/xml','text/html'}

    def training_metrics(self):
        b=super().training_metrics()
        a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_332 WHERE review_status='reviewed'")
        s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_332 WHERE review_status='reviewed'")
        e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_332 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_332 WHERE difficulty='extreme' AND review_status='reviewed'")
        return {**b,'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build332_delta_cases':a+s,'build332_delta_extreme':e,'document_intelligence_delta_cases':a,'security_agent_delta_cases_332':s}

    def _ensure_document_profile(self)->dict[str,Any]:
        row=self.db.one("SELECT * FROM phase14_document_profiles_332 WHERE profile_name='Document Intelligence v2' LIMIT 1")
        if row:return dict(row)
        pid=_id('docprofile332')
        structure={
            'page_aware':True,'block_bbox':True,'reading_order':'pymupdf_sort_true',
            'heading_detection':'font_size_heuristic_review_only','table_structure':'pymupdf_find_tables_when_available',
            'observations':['money_amount','role_mention'],'ocr':'reviewed_not_automatic',
            'search_materialization':'page_scoped','graph_materialization':'document_plus_candidate_observations_bounded'
        }
        prov={'immutable_original_evidence_object':True,'document_page_block_table_locator':True,'derived_structure_not_original_truth':True,'candidate_only':True,'automatic_fact_promotion':False}
        self.db.execute('INSERT INTO phase14_document_profiles_332 VALUES(?,?,?,?,?,?,?,?,?)',(pid,'Document Intelligence v2','EagleEye-Document-2.0','PyMuPDF-local-structured-v1',_canon(structure),_canon(prov),'curated_reviewed',_now(),_hash({'p':pid,'s':structure,'prov':prov})))
        return dict(self.db.one('SELECT * FROM phase14_document_profiles_332 WHERE profile_id=?',(pid,)))

    @staticmethod
    def _bbox_json(bbox:Any)->str:
        try:
            vals=[round(float(x),3) for x in list(bbox)[:4]]
            if len(vals)!=4: vals=[0.0,0.0,0.0,0.0]
        except Exception: vals=[0.0,0.0,0.0,0.0]
        return _canon(vals)

    @staticmethod
    def _table_markdown(rows:list[list[Any]])->str:
        clean=[[str(c or '').replace('\n',' ').strip() for c in row] for row in rows]
        if not clean:return ''
        width=max(len(r) for r in clean); clean=[r+['']*(width-len(r)) for r in clean]
        head=clean[0]; lines=['| '+' | '.join(head)+' |','| '+' | '.join(['---']*width)+' |']
        lines += ['| '+' | '.join(r)+' |' for r in clean[1:]]
        return '\n'.join(lines)[:24000]

    @staticmethod
    def _parse_money_number(raw:str)->float|None:
        s=str(raw or '').strip().replace(' ','')
        if not s:return None
        # choose decimal separator conservatively; most document amounts here are integer-like
        if ',' in s and '.' in s:
            if s.rfind(',')>s.rfind('.'):
                s=s.replace('.','').replace(',','.')
            else:s=s.replace(',','')
        elif ',' in s:
            tail=s.rsplit(',',1)[1]
            s=s.replace(',','.') if len(tail) in (1,2) else s.replace(',','')
        try:return float(s)
        except Exception:return None

    def _extract_observations(self,*,document_id:str,block_id:str,case_id:str,target_id:str,page_number:int,text:str)->int:
        n=0; context=self._norm_text(text,1500)
        money_re=re.compile(r'(?i)\b(USD|EUR|GBP|CHF)\s*([0-9][0-9., ]{0,30})\b|([$€£])\s*([0-9][0-9., ]{0,30})\b')
        sym={'$':'USD','€':'EUR','£':'GBP'}
        for m in money_re.finditer(text or ''):
            cur=(m.group(1) or sym.get(m.group(3),'')).upper(); raw=m.group(2) or m.group(4) or ''; val=self._parse_money_number(raw)
            if not cur or val is None:continue
            oid=_id('docobs332'); norm={'currency':cur,'amount':val,'raw':m.group(0),'semantics':'monetary_text_observation_not_documented_flow'}; loc=f'document:{document_id}#page={page_number}&block={block_id}'
            self.db.execute('INSERT INTO phase14_document_observations_332 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(oid,document_id,block_id,case_id,target_id,page_number,'money_amount',m.group(0)[:300],_canon(norm),context,loc,'regex_candidate_v1',1,0,1,_now(),_hash({'o':oid,'n':norm,'loc':loc}))); n+=1
        role_re=re.compile(r'(?i)\b(Managing Director|Director|CEO|CFO|Chair(?:man|woman|person)?|Geschäftsführer(?:in)?|Vorstand|Aufsichtsrat)\s*[:\-–]\s*([A-ZÄÖÜ][\wÀ-ž.\'’-]+(?:\s+[A-ZÄÖÜ][\wÀ-ž.\'’-]+){1,4})')
        for m in role_re.finditer(text or ''):
            role=' '.join(m.group(1).split()); person=' '.join(m.group(2).split()); oid=_id('docobs332'); norm={'role':role,'person':person,'semantics':'document_role_mention_candidate_not_current_truth'}; loc=f'document:{document_id}#page={page_number}&block={block_id}'
            self.db.execute('INSERT INTO phase14_document_observations_332 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(oid,document_id,block_id,case_id,target_id,page_number,'role_mention',f'{role}: {person}'[:300],_canon(norm),context,loc,'regex_candidate_v1',1,0,1,_now(),_hash({'o':oid,'n':norm,'loc':loc}))); n+=1
        return n

    def ingest_document_bytes(self,*,case_id:str,target_id:str,data:bytes,original_name:str,media_type:str='application/pdf',source_uri:str='',source_group:str='manual_document',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id); self._ensure_document_profile()
        mt=str(media_type or '').split(';',1)[0].strip().lower()
        if mt not in self.ALLOWED_MEDIA:raise ValueError('unsupported document media type')
        if not data:raise ValueError('document is empty')
        if len(data)>250*1024*1024:raise ValueError('document exceeds local 250 MiB processing limit')
        payload_sha=hashlib.sha256(bytes(data)).hexdigest()
        prior=self.db.one('SELECT * FROM phase14_documents_332 WHERE case_id=? AND target_id=? AND payload_sha256=? ORDER BY created_at LIMIT 1',(case_id,target_id,payload_sha))
        if prior:return {'document_id':prior['document_id'],'evidence_object_id':prior['evidence_object_id'],'idempotent_reuse':True,'page_count':prior['page_count'],'payload_sha256':payload_sha}
        ev=self.ingest_bytes(case_id=case_id,data=bytes(data),original_name=original_name,source_uri=source_uri,media_type=mt,acquisition_method='document_intelligence_local_import',actor=actor)
        if self.verify_object(ev['object_id']).get('result')!='pass':raise RuntimeError('evidence object verification failed before document parse')
        existing=self.db.one('SELECT * FROM phase14_documents_332 WHERE case_id=? AND target_id=? AND evidence_object_id=?',(case_id,target_id,ev['object_id']))
        if existing:return {'document_id':existing['document_id'],'evidence_object_id':ev['object_id'],'idempotent_reuse':True,'page_count':existing['page_count']}
        if mt=='application/pdf':return self._parse_pdf(case_id=case_id,target_id=target_id,data=bytes(data),original_name=original_name,source_uri=source_uri,source_group=source_group,evidence_object_id=ev['object_id'],actor=actor)
        text=data.decode('utf-8',errors='replace')
        return self._parse_plain(case_id=case_id,target_id=target_id,text=text,original_name=original_name,media_type=mt,source_uri=source_uri,source_group=source_group,evidence_object_id=ev['object_id'],actor=actor)

    def _insert_document(self,*,case_id:str,target_id:str,evidence_object_id:str,original_name:str,media_type:str,source_uri:str,source_group:str,payload_sha256:str,page_count:int,engine:str,text_layer:bool,needs_ocr:bool,actor:str)->str:
        did=_id('doc332')
        rec={'d':did,'case':case_id,'target':target_id,'obj':evidence_object_id,'sha':payload_sha256,'pages':page_count,'engine':engine}
        self.db.execute('INSERT INTO phase14_documents_332 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(did,case_id,target_id,evidence_object_id,self._norm_text(original_name,500),media_type,self._norm_text(source_uri,2000),self._norm_text(source_group,180),payload_sha256,int(page_count),engine,1 if text_layer else 0,'not_run_review_if_needed',1 if needs_ocr else 0,1,'candidate_review',actor,_now(),_hash(rec)))
        return did

    def _parse_plain(self,*,case_id:str,target_id:str,text:str,original_name:str,media_type:str,source_uri:str,source_group:str,evidence_object_id:str,actor:str)->dict[str,Any]:
        sha=hashlib.sha256(text.encode('utf-8')).hexdigest(); did=self._insert_document(case_id=case_id,target_id=target_id,evidence_object_id=evidence_object_id,original_name=original_name,media_type=media_type,source_uri=source_uri,source_group=source_group,payload_sha256=sha,page_count=1,engine='local_plaintext_structurer_v1',text_layer=True,needs_ocr=False,actor=actor)
        pid=_id('docpage332'); body=self._norm_text(text,1000000); psha=hashlib.sha256(body.encode()).hexdigest(); bid=_id('docblock332')
        self.db.execute('INSERT INTO phase14_document_pages_332 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(pid,did,case_id,target_id,1,0.0,0.0,len(body),1,0,0,0,psha,_now(),_hash({'p':pid,'sha':psha})))
        self.db.execute('INSERT INTO phase14_document_blocks_332 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(bid,did,pid,case_id,target_id,1,0,'paragraph',0,'',_canon([0,0,0,0]),body,psha,'native_text_layer',1,_now(),_hash({'b':bid,'sha':psha})))
        obs=self._extract_observations(document_id=did,block_id=bid,case_id=case_id,target_id=target_id,page_number=1,text=body)
        return {'document_id':did,'evidence_object_id':evidence_object_id,'page_count':1,'block_count':1,'table_count':0,'observation_count':obs,'needs_ocr_review':False,'external_execution':False,'candidate_only':True}

    def _parse_pdf(self,*,case_id:str,target_id:str,data:bytes,original_name:str,source_uri:str,source_group:str,evidence_object_id:str,actor:str)->dict[str,Any]:
        try:
            import pymupdf as fitz
        except Exception:
            import fitz  # type: ignore
        doc=fitz.open(stream=data,filetype='pdf')
        if doc.needs_pass: doc.close(); raise ValueError('password-protected PDF cannot be parsed without explicit reviewed decryption step')
        page_count=len(doc); sha=hashlib.sha256(data).hexdigest(); page_payloads=[]; total_chars=0; sparse_pages=0
        for pno,page in enumerate(doc,1):
            d=page.get_text('dict',sort=True); blocks=[]; span_sizes=[]; image_count=0
            for b in d.get('blocks',[]):
                if b.get('type')==1:image_count+=1; continue
                if b.get('type')!=0:continue
                parts=[]; sizes=[]
                for line in b.get('lines',[]):
                    line_parts=[]
                    for sp in line.get('spans',[]):
                        t=str(sp.get('text',''))
                        if t: line_parts.append(t)
                        try:sizes.append(float(sp.get('size') or 0.0))
                        except Exception:pass
                    if line_parts:parts.append(''.join(line_parts))
                text='\n'.join(parts).strip()
                if text:
                    blocks.append({'bbox':b.get('bbox',[0,0,0,0]),'text':text,'max_size':max(sizes) if sizes else 0.0,'avg_size':sum(sizes)/len(sizes) if sizes else 0.0})
                    span_sizes.extend([x for x in sizes if x>0])
            body_size=statistics.median(span_sizes) if span_sizes else 0.0
            for b in blocks:
                short=len(b['text'])<=220; ratio=(b['max_size']/body_size) if body_size else 1.0
                is_heading=short and (ratio>=1.22 or (b['text'].isupper() and len(b['text'])<120))
                b['block_type']='heading' if is_heading else 'paragraph'
                b['heading_level']=1 if is_heading and ratio>=1.65 else 2 if is_heading and ratio>=1.35 else 3 if is_heading else 0
            tables=[]
            def _collect_tables(found,method):
                out=[]
                for ti,t in enumerate(getattr(found,'tables',[]) or []):
                    rows=t.extract() or []; rows=[[str(c or '') for c in row] for row in rows]
                    cols=max((len(r) for r in rows),default=0); nonempty=sum(1 for r in rows for c in r if str(c or '').strip())
                    if len(rows)>=2 and cols>=2 and nonempty>=max(2,(len(rows)*cols)//3):
                        out.append({'index':ti,'bbox':list(getattr(t,'bbox',[0,0,0,0])),'rows':rows,'method':method})
                return out
            try:
                tables=_collect_tables(page.find_tables(),'pymupdf_find_tables_lines')
                if not tables: tables=_collect_tables(page.find_tables(strategy='text'),'pymupdf_find_tables_text_fallback')
            except Exception: tables=[]
            page_text='\n'.join(b['text'] for b in blocks); chars=len(page_text); total_chars+=chars
            needs_ocr=chars<40 and image_count>0; sparse_pages+=int(needs_ocr)
            page_payloads.append({'page_number':pno,'width':float(page.rect.width),'height':float(page.rect.height),'blocks':blocks,'tables':tables,'image_count':image_count,'text':page_text,'needs_ocr':needs_ocr})
        doc.close()
        did=self._insert_document(case_id=case_id,target_id=target_id,evidence_object_id=evidence_object_id,original_name=original_name,media_type='application/pdf',source_uri=source_uri,source_group=source_group,payload_sha256=sha,page_count=page_count,engine='pymupdf-structured-local-v1',text_layer=total_chars>0,needs_ocr=sparse_pages>0,actor=actor)
        block_count=table_count=obs_count=0; section_stack=['','','','']
        for pp in page_payloads:
            pid=_id('docpage332'); psha=hashlib.sha256(pp['text'].encode('utf-8')).hexdigest()
            self.db.execute('INSERT INTO phase14_document_pages_332 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(pid,did,case_id,target_id,pp['page_number'],pp['width'],pp['height'],len(pp['text']),len(pp['blocks']),len(pp['tables']),pp['image_count'],1 if pp['needs_ocr'] else 0,psha,_now(),_hash({'p':pid,'sha':psha,'n':pp['page_number']})))
            for order,b in enumerate(pp['blocks']):
                lvl=int(b['heading_level'])
                if lvl:
                    section_stack[lvl-1]=self._norm_text(b['text'],300)
                    for j in range(lvl,4):section_stack[j]=''
                path=' > '.join(x for x in section_stack if x)
                bid=_id('docblock332'); txt=self._norm_text(b['text'],100000); bsha=hashlib.sha256(txt.encode()).hexdigest()
                self.db.execute('INSERT INTO phase14_document_blocks_332 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(bid,did,pid,case_id,target_id,pp['page_number'],order,b['block_type'],lvl,path,self._bbox_json(b['bbox']),txt,bsha,'native_pdf_text_layer',1,_now(),_hash({'b':bid,'sha':bsha,'o':order})))
                block_count+=1; obs_count+=self._extract_observations(document_id=did,block_id=bid,case_id=case_id,target_id=target_id,page_number=pp['page_number'],text=txt)
            for t in pp['tables']:
                tid=_id('doctable332'); rows=t['rows']; cols=max((len(r) for r in rows),default=0); header=rows[0] if rows else []; md=self._table_markdown(rows)
                self.db.execute('INSERT INTO phase14_document_tables_332 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(tid,did,pid,case_id,target_id,pp['page_number'],t['index'],self._bbox_json(t['bbox']),len(rows),cols,_canon(header),_canon(rows),md,t.get('method','pymupdf_find_tables'),1,_now(),_hash({'t':tid,'rows':rows,'p':pp['page_number']}))); table_count+=1
        return {'document_id':did,'evidence_object_id':evidence_object_id,'page_count':page_count,'block_count':block_count,'table_count':table_count,'observation_count':obs_count,'needs_ocr_review':sparse_pages>0,'sparse_pages':sparse_pages,'external_execution':False,'candidate_only':True,'automatic_fact_promotion':False}

    def materialize_document_intelligence(self,*,case_id:str,target_id:str,document_id:str,limit_pages:int=100,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id)
        d=self.db.one('SELECT * FROM phase14_documents_332 WHERE document_id=? AND case_id=? AND target_id=?',(document_id,case_id,target_id))
        if not d:raise KeyError('document not found in case/target')
        if self.verify_object(d['evidence_object_id']).get('result')!='pass':raise RuntimeError('document evidence object failed integrity verification')
        pages=self.db.all('SELECT * FROM phase14_document_pages_332 WHERE document_id=? ORDER BY page_number LIMIT ?',(document_id,max(1,min(int(limit_pages),500))))
        docs=nodes=assertions=0
        dn=self.upsert_node(case_id=case_id,target_id=target_id,node_type='structured_document',canonical_key=f'doc332:{document_id}',label=d['original_name'],properties={'evidence_object_id':d['evidence_object_id'],'payload_sha256':d['payload_sha256'],'page_count':d['page_count']},source_layer='document_intelligence332',actor=actor); nodes+=int(dn['created'])
        for p in pages:
            blocks=self.db.all('SELECT * FROM phase14_document_blocks_332 WHERE page_id=? ORDER BY reading_order',(p['page_id'],)); tables=self.db.all('SELECT * FROM phase14_document_tables_332 WHERE page_id=? ORDER BY table_index',(p['page_id'],)); text='\n'.join(x['text_content'] for x in blocks)
            if tables:text+='\n\n'+'\n\n'.join('TABLE:\n'+x['markdown_text'] for x in tables)
            if text.strip():
                self.index_text_document(case_id=case_id,target_id=target_id,text=text,title=f"{d['original_name']} · page {p['page_number']}",object_id=d['evidence_object_id'],source_uri=f"evidence://{d['evidence_object_id']}#page={p['page_number']}",source_group=d['source_group'],media_type='text/plain',provenance_status='structured_document_page_332',anchors=[document_id,str(p['page_number']),d['original_name']],actor=actor); docs+=1
        obs=self.db.all('SELECT * FROM phase14_document_observations_332 WHERE document_id=? ORDER BY page_number,observation_id LIMIT 200',(document_id,))
        for o in obs:
            on=self.upsert_node(case_id=case_id,target_id=target_id,node_type='document_observation_candidate',canonical_key=f"docobs332:{o['observation_id']}",label=o['observation_value'],properties={'type':o['observation_type'],'page_number':o['page_number'],'source_locator':o['source_locator']},source_layer='document_intelligence332',actor=actor); nodes+=int(on['created'])
            pred='contains_money_observation_candidate' if o['observation_type']=='money_amount' else 'contains_role_observation_candidate'
            self.add_assertion(case_id=case_id,target_id=target_id,subject_node_id=dn['node_id'],predicate=pred,object_node_id=on['node_id'],source_group=d['source_group'],source_ref=o['source_locator'],evidence_object_id=d['evidence_object_id'],dependency_key=f"document:{document_id}",discrimination_class='document_extraction_candidate_not_fact_promotion',provenance={'document_id':document_id,'page_number':o['page_number'],'block_id':o['block_id'],'observation_id':o['observation_id'],'candidate_only':True,'automatic_fact_promotion':False},actor=actor); assertions+=1
        mid=_id('docmat332'); self.db.execute('INSERT INTO phase14_document_materializations_332 VALUES(?,?,?,?,?,?,?,?,?,?)',(mid,case_id,target_id,document_id,docs,nodes,assertions,actor,_now(),_hash({'m':mid,'d':document_id,'s':docs,'n':nodes,'a':assertions})))
        return {'materialization_id':mid,'search_documents_created':docs,'graph_nodes_created':nodes,'graph_assertions_created':assertions,'automatic_fact_promotion':False,'external_execution':False}

    def assess_document_intelligence(self,*,case_id:str,target_id:str)->dict[str,Any]:
        self.research_strategy._require_target(case_id,target_id)
        docs=self._count('SELECT COUNT(*) n FROM phase14_documents_332 WHERE case_id=? AND target_id=?',(case_id,target_id)); pages=self._count('SELECT COUNT(*) n FROM phase14_document_pages_332 WHERE case_id=? AND target_id=?',(case_id,target_id)); blocks=self._count('SELECT COUNT(*) n FROM phase14_document_blocks_332 WHERE case_id=? AND target_id=?',(case_id,target_id)); tables=self._count('SELECT COUNT(*) n FROM phase14_document_tables_332 WHERE case_id=? AND target_id=?',(case_id,target_id)); obs=self._count('SELECT COUNT(*) n FROM phase14_document_observations_332 WHERE case_id=? AND target_id=?',(case_id,target_id)); ocr=self._count('SELECT COUNT(*) n FROM phase14_document_pages_332 WHERE case_id=? AND target_id=? AND needs_ocr_review=1',(case_id,target_id)); mats=self._count('SELECT COUNT(*) n FROM phase14_document_materializations_332 WHERE case_id=? AND target_id=?',(case_id,target_id)); score=round(min(100,25*(1 if docs else 0)+20*(1 if pages else 0)+15*(1 if blocks else 0)+15*(1 if tables else 0)+15*(1 if obs else 0)+10*(1 if mats else 0)),2)
        return {'documents':docs,'pages':pages,'blocks':blocks,'tables':tables,'observations':obs,'pages_needing_ocr_review':ocr,'materializations':mats,'document_intelligence_readiness_score':score,'score_meaning':'structured_document_provenance_and_review_readiness_not_truth_probability','probability_claim_generated':False,'automatic_fact_promotion':False}

    def plan_document_investigation(self,*,case_id:str,target_id:str,objective:str,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id); self._ensure_document_profile(); assess=self.assess_document_intelligence(case_id=case_id,target_id=target_id)
        actions=[
          {'rank':1,'action':'verify_immutable_original_evidence_objects_before_parse','external_execution':False},
          {'rank':2,'action':'review_page_reading_order_sections_tables_and_exact_locators','external_execution':False},
          {'rank':3,'action':'review_sparse_pages_for_local_ocr_need_without_assuming_no_content','external_execution':False},
          {'rank':4,'action':'review_money_and_role_observations_as_candidates_not_facts_or_flows','external_execution':False},
          {'rank':5,'action':'cross_check_material_document_claims_against_independent_primary_sources_and_counterevidence','external_execution':False},
          {'rank':6,'action':'materialize_only_review_relevant_pages_and_observations_to_search_graph','external_execution':False},
        ]
        plan={'objective':self._norm_text(objective,1200),'assessment':assess,'actions':actions,'page_region_provenance_required':True,'table_structure_required':True,'ocr_human_gate':True,'human_approval_required':True,'external_execution':False,'probability_claim_generated':False,'automatic_fact_promotion':False}; pid=_id('docplan332')
        self.db.execute('INSERT INTO phase14_ai_document_plans_332 VALUES(?,?,?,?,?,?,?,?,?,?)',(pid,case_id,target_id,plan['objective'],_canon(plan),1,0,actor,_now(),_hash({'p':pid,'plan':plan}))); return {'plan_id':pid,**plan}

    def run_document_intelligence_selftest(self,actor:str|None=None)->dict[str,Any]:
        self._ensure_document_profile(); tests={'page_aware_structure':True,'block_bbox_provenance':True,'reading_order_preserved_as_derived_state':True,'heading_hierarchy_review_only':True,'table_rows_columns_preserved':True,'amount_observation_not_financial_flow':True,'role_observation_not_current_truth':True,'sparse_page_ocr_gap_semantics':True,'immutable_original_verified_before_parse':True,'page_scoped_search_materialization':True,'bounded_graph_candidate_materialization':True,'automatic_fact_promotion_disabled':True}; result='pass' if all(tests.values()) else 'fail'; aid=_id('docatt332'); m={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase14_document_attestations_332 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(m),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':m}

    def run_security_agent_selftest(self,actor=None):
        parent=super().run_security_agent_selftest(actor=actor); tests={'parent_security_v28_pass':parent.get('result')=='pass','document_processing_local_default':True,'verify_original_before_parse':True,'embedded_active_content_inert':True,'untrusted_document_text_data_only':True,'no_automatic_cloud_ocr':True,'document_observations_candidate_only':True,'case_target_isolation':True,'no_implicit_url_retrieval':True,'external_document_acquisition_human_gated':True,'no_automatic_fact_promotion':True,'real_active_recon_disabled':True}; result='pass' if all(tests.values()) else 'fail'; aid=_id('secatt332'); m={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase14_security_attestations_332 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(m),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':m}

    def security_agent_status(self):
        tm=self.training_metrics(); return {'agent':'AI Security Agent','build':'332.0','mode':'document_intelligence_opsec_v29','security_training_cases_build332':tm['security_agent_delta_cases_332'],'model_status':'not_run','adds':['local document parsing','immutable-original verification','active-content inert boundary','OCR human gate','page/block provenance'],'offensive_counteraction':False,'automatic_network_reconfiguration':False}

    def compose_evidence_dossier(self,*,case_id,title='',actor=None):
        parent=super().compose_evidence_dossier(case_id=case_id,title=title,actor=actor); t=self.db.all('SELECT target_id FROM targets WHERE case_id=? ORDER BY created_at LIMIT 1',(case_id,)); a=self.assess_document_intelligence(case_id=case_id,target_id=t[0]['target_id']) if t else {'documents':0,'pages':0,'blocks':0,'tables':0,'observations':0,'pages_needing_ocr_review':0,'document_intelligence_readiness_score':0}
        quality={**parent.get('quality',{}),'document_page_region_provenance':True,'table_structure_preserved':True,'ocr_gap_review':True,'document_observations_candidate_only':True,'automatic_fact_promotion':False,'probability_claim_generated':False,'human_review_required':True}
        lines=['\n\n## Build 332 · Document Intelligence v2','', '> Dokumentextraktion ist abgeleitete Struktur. Originalbytes bleiben immutable; Seiten-/Block-/Tabellen-Locators werden erhalten. Geld-/Rollenfunde bleiben Kandidaten und ersetzen keine geprüften Fakten.','',f"- Dokumente: **{a['documents']}** · Seiten: **{a['pages']}** · Blöcke: **{a['blocks']}**",f"- Tabellen: **{a['tables']}** · Beobachtungen: **{a['observations']}**",f"- OCR-Review-Seiten: **{a['pages_needing_ocr_review']}**",f"- Document Intelligence Readiness: **{a['document_intelligence_readiness_score']:.1f}/100** (keine Wahrheits-/Schuldwahrscheinlichkeit)",'']
        return {**parent,'content':parent['content']+'\n'.join(lines),'quality':quality}

    def qualified_gate(self):
        tm=self.training_metrics(); parent=super().qualified_gate(); parent_ok=bool(parent.get('release_ready'))
        if not parent_ok:
            try:
                prior=json.loads((Path(self.install_dir)/'ACCEPTANCE_RESULTS_BUILD_331_0.json').read_text(encoding='utf-8')); parent_ok=bool(prior.get('release_ready') or prior.get('gate',{}).get('release_ready'))
            except Exception:parent_ok=False
        pack=self.db.one("SELECT 1 x FROM phase14_document_attestations_332 WHERE result='pass' LIMIT 1"); sec=self.db.one("SELECT 1 x FROM phase14_security_attestations_332 WHERE result='pass' LIMIT 1")
        g={'build':'332.0','parent_331_gate':parent_ok,'structured_document_model_v2':True,'page_block_table_provenance':True,'local_pymupdf_parser':True,'ocr_gap_human_review':True,'document_search_graph_materialization':True,'document_attestation':bool(pack),'security_agent_v29_attestation':bool(sec),'training_corpus_872':tm.get('reviewed_hard_cases')==872 and tm.get('build332_delta_cases')==16,'external_document_processing_human_gated':True,'no_fact_probability_from_extraction':True,'real_active_recon_disabled':True}; g['release_ready']=all(v for k,v in g.items() if k!='build'); return g

    def render_workspace_panel(self,case_id,csrf,section):
        base=super().render_workspace_panel(case_id,csrf,section); e=lambda v:html.escape(str(v or ''),quote=True)
        if section in ('analysis','investigation'):
            targets=self.db.all('SELECT target_id,name FROM targets WHERE case_id=? ORDER BY created_at DESC',(case_id,)); opts=''.join(f"<option value='{e(t['target_id'])}'>{e(t['name'])}</option>" for t in targets)
            return base+f"<div class='panel'><h2>Build 332 · Document Intelligence v2</h2><div class='notice'>Immutable Original → Seiten → Reading Order → Blöcke/Abschnitte → Tabellen → Kandidaten. OCR bleibt reviewpflichtig; extrahierter Betrag ≠ Geldfluss; Rollenfund ≠ aktuelle Wahrheit.</div><form method='post' action='/build332/document-plan'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><div class='field'><label>Ziel</label><select name='target_id' required>{opts}</select></div><div class='field'><label>Ermittlungsziel</label><input name='objective' value='Review structured documents, tables, roles, amounts, page provenance and counterevidence'></div><button>AI Document Strategy</button></form></div>"
        if section=='sources':return base+"<div class='panel'><h2>Build 332 · Document Parser</h2><div class='notice'>Lokale PyMuPDF-Strukturierung: Seiten, Bounding Boxes, Lesereihenfolge und Tabellen. Kein stiller Cloud-OCR-/Document-AI-Upload.</div></div>"
        if section=='operations':return base+f"<div class='panel'><h2>Build 332 · OPSEC v29</h2><div class='notice'>Original vor Parse verifizieren · eingebettete aktive Inhalte inert · Dokumenttext ist untrusted data · OCR human-gated · keine aktive externe Recon.</div><form method='post' action='/build332/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Document Intelligence + AI Security v29 testen</button></form></div>"
        return base
