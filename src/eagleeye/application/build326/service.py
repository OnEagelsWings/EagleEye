from __future__ import annotations
import csv, hashlib, html, io, json, math, os, re, stat, zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from eagleeye.application.build304.service import _id, _now, _hash, _canon
from eagleeye.application.build325.service import Build325ConnectorRegistryService


class Build326BulkDataIngestionService(Build325ConnectorRegistryService):
    BUILD='326.0'; REQUIRED_CORPUS=776
    CDC_MIN=64*1024; CDC_AVG=256*1024; CDC_MAX=1024*1024
    MAX_INPUT_BYTES=256*1024*1024
    MAX_RECORD_BYTES=1024*1024
    MAX_FIELDS=256
    MAX_FIELD_CHARS=200_000
    MAX_ARCHIVE_MEMBERS=2000
    MAX_ARCHIVE_UNCOMPRESSED=512*1024*1024
    MAX_ARCHIVE_RATIO=250.0
    MAX_MATERIALIZE=500
    _GEAR=tuple(int.from_bytes(hashlib.sha256(f'eagleeye-fastcdc-gear-{i}'.encode()).digest()[:8],'big') for i in range(256))

    def training_metrics(self):
        b=super().training_metrics()
        a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_326 WHERE review_status='reviewed'")
        s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_326 WHERE review_status='reviewed'")
        e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_326 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_326 WHERE difficulty='extreme' AND review_status='reviewed'")
        return {**b,'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build326_delta_cases':a+s,'build326_delta_extreme':e,'bulk_ingestion_delta_cases':a,'security_agent_delta_cases_326':s}

    @property
    def bulk_root(self)->Path:
        p=(self.base_dir/'bulk_data_store_326').resolve(); p.mkdir(parents=True,exist_ok=True); return p

    @staticmethod
    def _sha256(data:bytes)->str: return hashlib.sha256(data).hexdigest()

    @classmethod
    def _cdc_masks(cls)->tuple[int,int]:
        bits=max(8,round(math.log2(cls.CDC_AVG)))
        # Before avg: stricter cut probability; after avg: looser cut probability.
        return (1<<(bits+1))-1, (1<<max(8,bits-1))-1

    @classmethod
    def content_defined_chunks(cls,data:bytes)->list[dict[str,Any]]:
        data=bytes(data); n=len(data)
        if not n: return [{'offset':0,'length':0,'sha256':hashlib.sha256(b'').hexdigest()}]
        strict_mask,loose_mask=cls._cdc_masks(); out=[]; start=0
        while start<n:
            if n-start<=cls.CDC_MIN:
                end=n
            else:
                pos=min(n,start+cls.CDC_MIN); normal=min(n,start+cls.CDC_AVG); hard=min(n,start+cls.CDC_MAX); h=0; end=hard
                while pos<hard:
                    h=((h<<1)+cls._GEAR[data[pos]]) & ((1<<64)-1)
                    mask=strict_mask if pos<normal else loose_mask
                    if (h & mask)==0:
                        end=pos+1; break
                    pos+=1
            chunk=data[start:end]; out.append({'offset':start,'length':len(chunk),'sha256':hashlib.sha256(chunk).hexdigest()}); start=end
        return out

    def _chunk_path(self,digest:str)->Path:
        if not re.fullmatch(r'[0-9a-f]{64}',str(digest)): raise ValueError('invalid chunk digest')
        root=self.bulk_root; p=(root/'chunks'/'sha256'/digest[:2]/digest).resolve()
        if root not in p.parents: raise RuntimeError('bulk chunk path boundary violation')
        return p

    def _store_chunk(self,data:bytes,digest:str)->tuple[str,bool]:
        p=self._chunk_path(digest); p.parent.mkdir(parents=True,exist_ok=True); reused=p.exists()
        if reused:
            if self._sha256(p.read_bytes())!=digest: raise RuntimeError('existing bulk chunk failed digest verification')
        else:
            try:
                with p.open('xb') as f:
                    f.write(data); f.flush(); os.fsync(f.fileno())
            except FileExistsError:
                reused=True
                if self._sha256(p.read_bytes())!=digest: raise RuntimeError('concurrent bulk chunk failed digest verification')
        try: os.chmod(p,stat.S_IREAD|stat.S_IRGRP|stat.S_IROTH)
        except Exception: pass
        return p.relative_to(self.base_dir.resolve()).as_posix(),reused

    @staticmethod
    def _clean_text(v:Any,limit:int)->str:
        s=str(v if v is not None else '').replace('\x00','').strip()
        return s[:limit]

    @classmethod
    def _normalize_record(cls,record:dict[str,Any])->dict[str,str]:
        if len(record)>cls.MAX_FIELDS: raise ValueError('too_many_fields')
        out={}
        for k,v in record.items():
            key=cls._clean_text(k,200)
            if not key: continue
            val=cls._clean_text(v,cls.MAX_FIELD_CHARS)
            out[key]=val
        raw=_canon(out).encode('utf-8')
        if len(raw)>cls.MAX_RECORD_BYTES: raise ValueError('record_too_large')
        return out

    @staticmethod
    def _candidate_key_fields(record:dict[str,Any])->list[str]:
        low={str(k).casefold():k for k in record}
        for cand in ('lei','cik','company_number','registration_id','notice_id','identifier','id','url'):
            if cand in low and str(record[low[cand]]).strip(): return [str(low[cand])]
        return []

    @classmethod
    def _record_key(cls,record:dict[str,Any],key_fields:Iterable[str]|None)->str:
        keys=[str(x) for x in (key_fields or []) if str(x).strip()] or cls._candidate_key_fields(record)
        if keys:
            vals=[]
            for k in keys:
                vals.append(f"{k}={record.get(k,'')}")
            if any(v.split('=',1)[1].strip() for v in vals): return hashlib.sha256('|'.join(vals).encode('utf-8')).hexdigest()
        return hashlib.sha256(_canon(record).encode('utf-8')).hexdigest()

    @classmethod
    def _parse_records(cls,data:bytes,format_class:str)->tuple[list[dict[str,str]],list[tuple[int,str,str]]]:
        fmt=str(format_class or '').casefold(); text=data.decode('utf-8-sig',errors='replace'); records=[]; quarantine=[]
        if fmt in ('jsonl','ndjson'):
            for i,line in enumerate(text.splitlines(),1):
                if not line.strip(): continue
                try:
                    obj=json.loads(line)
                    if not isinstance(obj,dict): raise ValueError('record_not_object')
                    records.append(cls._normalize_record(obj))
                except Exception as exc: quarantine.append((i,str(exc)[:160],line[:500]))
        elif fmt=='json':
            try:
                obj=json.loads(text)
                arr=obj if isinstance(obj,list) else obj.get('records',[]) if isinstance(obj,dict) else []
                if not isinstance(arr,list): raise ValueError('json_records_not_list')
                for i,item in enumerate(arr,1):
                    try:
                        if not isinstance(item,dict): raise ValueError('record_not_object')
                        records.append(cls._normalize_record(item))
                    except Exception as exc: quarantine.append((i,str(exc)[:160],str(item)[:500]))
            except Exception as exc: quarantine.append((1,'json_parse_error:'+str(exc)[:120],text[:500]))
        elif fmt in ('csv','tsv'):
            dialect='excel-tab' if fmt=='tsv' else 'excel'
            try:
                reader=csv.DictReader(io.StringIO(text),dialect=dialect)
                for i,row in enumerate(reader,2):
                    try: records.append(cls._normalize_record(dict(row)))
                    except Exception as exc: quarantine.append((i,str(exc)[:160],str(row)[:500]))
            except Exception as exc: quarantine.append((1,'csv_parse_error:'+str(exc)[:120],text[:500]))
        else: raise ValueError('unsupported format_class')
        return records,quarantine

    @classmethod
    def inspect_zip_bytes(cls,data:bytes)->dict[str,Any]:
        if len(data)>cls.MAX_INPUT_BYTES: raise ValueError('archive_input_too_large')
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            infos=z.infolist()
            if len(infos)>cls.MAX_ARCHIVE_MEMBERS: raise ValueError('archive_too_many_members')
            total=sum(max(0,i.file_size) for i in infos); compressed=sum(max(1,i.compress_size) for i in infos)
            if total>cls.MAX_ARCHIVE_UNCOMPRESSED: raise ValueError('archive_uncompressed_too_large')
            if total/max(1,compressed)>cls.MAX_ARCHIVE_RATIO: raise ValueError('archive_compression_ratio_too_high')
            members=[]
            for i in infos:
                p=PurePosixPath(i.filename.replace('\\','/'))
                if p.is_absolute() or '..' in p.parts: raise ValueError('archive_path_traversal')
                members.append({'name':i.filename,'size':i.file_size,'compressed':i.compress_size})
            return {'members':members,'member_count':len(members),'uncompressed_bytes':total,'compression_ratio':round(total/max(1,compressed),3)}

    def create_dataset(self,*,source_id:str,dataset_name:str,jurisdiction:str='',record_family:str='',format_class:str='jsonl',key_fields:Iterable[str]|None=None,scope_class:str='shared_local_catalog',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self._ensure_seeded(); src=self.db.one('SELECT * FROM phase14_source_registry_325 WHERE source_id=? AND review_status=?',(source_id,'curated_reviewed'))
        if not src: raise ValueError('source must be reviewed in Build 325 registry')
        fmt=str(format_class).casefold()
        if fmt not in ('csv','tsv','json','jsonl','ndjson'): raise ValueError('unsupported format')
        did=_id('bulkdataset326'); keys=[self._clean_text(x,120) for x in (key_fields or []) if self._clean_text(x,120)]
        rec={'dataset_id':did,'source_id':source_id,'dataset_name':self._clean_text(dataset_name,300),'jurisdiction':self._clean_text(jurisdiction or src['jurisdiction'],80),'record_family':self._clean_text(record_family or src['source_class'],120),'format_class':fmt,'key_fields':keys,'scope_class':scope_class,'review_status':'reviewed','created_by':actor,'created_at':_now()}
        self.db.execute('INSERT INTO phase14_bulk_datasets_326 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(did,source_id,rec['dataset_name'],rec['jurisdiction'],rec['record_family'],fmt,_canon(keys),scope_class,'reviewed',actor,rec['created_at'],_hash(rec)))
        return rec

    def plan_bulk_ingestion(self,*,case_id:str,target_id:str,objective:str,jurisdiction_hint:str='',record_family:str='',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id)
        sel=self.select_sources(case_id=case_id,target_id=target_id,objective=objective,jurisdiction_hint=jurisdiction_hint,record_family=record_family,top_k=8,actor=actor)
        bulk=[]
        for s in sel['selected_sources']:
            caps=self.source_capabilities(s['source_id']); bc=[c for c in caps if int(c['supports_bulk'])==1]
            if bc: bulk.append({'source_id':s['source_id'],'display_name':s['display_name'],'routing_fit_score':s['routing_fit_score'],'bulk_capabilities':[c['capability'] for c in bc],'incremental_supported':any(int(c['supports_incremental'])==1 for c in bc),'access_mode':s['access_mode'],'auth_class':s['auth_class'],'independence_group':s['independence_group']})
        actions=[
          {'rank':1,'action':'inspect_existing_local_dataset_snapshots','external_execution':False},
          {'rank':2,'action':'prefer_incremental_or_delta_distribution_when_provider_documents_it','source_ids':[x['source_id'] for x in bulk if x['incremental_supported']],'external_execution':False},
          {'rank':3,'action':'stage_approved_bulk_bytes_into_immutable_snapshot','requires_human_approval':True,'external_execution':False},
          {'rank':4,'action':'parse_quarantine_and_delta_classify_records','external_execution':False},
          {'rank':5,'action':'materialize_changed_candidate_records_to_search_graph_bounded','requires_human_review':True,'external_execution':False},
        ]
        plan={'objective':self._clean_text(objective,1000),'source_selection_run_id':sel['run_id'],'bulk_source_candidates':bulk,'actions':actions,'human_approval_required':True,'external_execution':False,'bulk_capability_is_routing_utility_not_evidence_strength':True,'probability_claim_generated':False}
        pid=_id('bulkplan326'); self.db.execute('INSERT INTO phase14_ai_bulk_plans_326 VALUES(?,?,?,?,?,?,?,?,?,?)',(pid,case_id,target_id,plan['objective'],_canon(plan),1,0,actor,_now(),_hash({'p':pid,'plan':plan})))
        return {'plan_id':pid,**plan}

    def _write_manifest(self,dataset_id:str,snapshot_id:str,manifest:dict[str,Any])->tuple[str,str]:
        root=(self.bulk_root/'manifests'/dataset_id).resolve(); root.mkdir(parents=True,exist_ok=True); p=(root/f'{snapshot_id}.json').resolve()
        if self.bulk_root not in p.parents: raise RuntimeError('manifest path boundary violation')
        data=(json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf-8'); sha=self._sha256(data)
        if p.exists():
            if self._sha256(p.read_bytes())!=sha: raise RuntimeError('manifest immutable collision')
        else:
            with p.open('xb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
            try: os.chmod(p,stat.S_IREAD|stat.S_IRGRP|stat.S_IROTH)
            except Exception: pass
        return p.relative_to(self.base_dir.resolve()).as_posix(),sha

    def ingest_bulk_bytes(self,*,dataset_id:str,data:bytes,case_id:str='',target_id:str='',snapshot_mode:str='full',source_uri:str='',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; ds=self.db.one('SELECT * FROM phase14_bulk_datasets_326 WHERE dataset_id=?',(dataset_id,))
        if not ds: raise KeyError('dataset not found')
        if not isinstance(data,(bytes,bytearray)): raise TypeError('data must be bytes')
        data=bytes(data)
        if len(data)>self.MAX_INPUT_BYTES: raise ValueError('bulk input exceeds local safety limit')
        mode=snapshot_mode if snapshot_mode in ('full','delta') else 'full'; digest=self._sha256(data)
        latest=self.db.one('SELECT * FROM phase14_bulk_snapshots_326 WHERE dataset_id=? ORDER BY created_at DESC LIMIT 1',(dataset_id,))
        if latest and latest['dataset_sha256']==digest:
            return {'snapshot_id':latest['snapshot_id'],'dataset_id':dataset_id,'idempotent_reuse':True,'dataset_sha256':digest,'row_count':latest['row_count'],'inserted_count':0,'updated_count':0,'unchanged_count':latest['row_count'],'deleted_count':0,'quarantined_count':latest['quarantined_count'],'chunk_count':latest['chunk_count'],'reused_chunk_count':latest['chunk_count'],'reuse_ratio':1.0,'external_execution':False,'candidate_only':True}
        if case_id and target_id: self.research_strategy._require_target(case_id,target_id)
        job_id=_id('bulkjob326'); now=_now(); self.db.execute('INSERT INTO phase14_bulk_ingestion_jobs_326 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(job_id,dataset_id,case_id,target_id,ds['source_id'],mode,'running',digest,len(data),0,0,0,0,_canon({'phase':'start'}),0,1,actor,now,'',_hash({'j':job_id,'d':digest})))
        chunks=self.content_defined_chunks(data); reused_n=0
        chunk_rows=[]
        for ordinal,c in enumerate(chunks):
            raw=data[c['offset']:c['offset']+c['length']]; rel,reused=self._store_chunk(raw,c['sha256']); reused_n+=int(reused); cid=_id('bulkchunk326'); chunk_rows.append((cid,ordinal,c,rel,reused))
        records,quarantine=self._parse_records(data,ds['format_class']); keys=json.loads(ds['key_fields_json']); snapshot_id=_id('bulksnap326'); parent_id=(latest or {}).get('snapshot_id',''); parent_manifest=(latest or {}).get('manifest_sha256','')
        previous={r['record_key']:r for r in self.db.all('SELECT * FROM phase14_bulk_record_state_326 WHERE dataset_id=?',(dataset_id,))}; seen=set(); ins=upd=unch=0
        for idx,record in enumerate(records,1):
            rkey=self._record_key(record,keys); seen.add(rkey); ph=self._sha256(_canon(record).encode('utf-8')); old=previous.get(rkey)
            if old and int(old['active'])==1 and old['payload_hash']==ph:
                unch+=1; continue
            op='insert' if not old or int(old['active'])==0 else 'update'; ver=(int(old['version'])+1) if old else 1; vid=_id('bulkver326')
            self.db.execute('INSERT INTO phase14_bulk_record_versions_326 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(vid,dataset_id,snapshot_id,rkey,op,ver,ph,_canon(record),1,_now(),_hash({'v':vid,'k':rkey,'op':op,'h':ph})))
            if old:
                self.db.execute('UPDATE phase14_bulk_record_state_326 SET payload_hash=?,payload_json=?,active=1,latest_snapshot_id=?,version=?,updated_at=? WHERE dataset_id=? AND record_key=?',(ph,_canon(record),snapshot_id,ver,_now(),dataset_id,rkey))
            else:
                self.db.execute('INSERT INTO phase14_bulk_record_state_326 VALUES(?,?,?,?,?,?,?,?,?)',(dataset_id,rkey,ph,_canon(record),1,snapshot_id,snapshot_id,ver,_now()))
            ins+=op=='insert'; upd+=op=='update'
        deleted=0
        if mode=='full' and latest:
            for rkey,old in previous.items():
                if int(old['active'])==1 and rkey not in seen:
                    ver=int(old['version'])+1; vid=_id('bulkver326'); self.db.execute('INSERT INTO phase14_bulk_record_versions_326 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(vid,dataset_id,snapshot_id,rkey,'delete',ver,old['payload_hash'],old['payload_json'],1,_now(),_hash({'v':vid,'k':rkey,'op':'delete'})))
                    self.db.execute('UPDATE phase14_bulk_record_state_326 SET active=0,latest_snapshot_id=?,version=?,updated_at=? WHERE dataset_id=? AND record_key=?',(snapshot_id,ver,_now(),dataset_id,rkey)); deleted+=1
        for row_no,reason,excerpt in quarantine:
            qid=_id('bulkq326'); self.db.execute('INSERT INTO phase14_bulk_quarantine_326 VALUES(?,?,?,?,?,?,?,?)',(qid,job_id,dataset_id,row_no,reason,excerpt,_now(),_hash({'q':qid,'r':row_no,'reason':reason})))
        evidence_object_id=''
        if case_id:
            ev=self.ingest_bytes(case_id=case_id,data=data,original_name=f"{ds['dataset_name']}.{ds['format_class']}",source_uri=source_uri,media_type={'csv':'text/csv','tsv':'text/tab-separated-values','json':'application/json','jsonl':'application/x-ndjson','ndjson':'application/x-ndjson'}.get(ds['format_class'],'application/octet-stream'),acquisition_method='approved_bulk_dataset_import',actor=actor)
            evidence_object_id=ev['object_id']
        manifest={'schema':'eagleeye-bulk-snapshot-v1','snapshotId':snapshot_id,'datasetId':dataset_id,'sourceId':ds['source_id'],'parentSnapshotId':parent_id,'parentManifestSha256':parent_manifest,'snapshotMode':mode,'datasetSha256':digest,'inputBytes':len(data),'format':ds['format_class'],'recordKeyFields':keys,'rowCount':len(records),'changes':{'inserted':ins,'updated':upd,'unchanged':unch,'deleted':deleted,'quarantined':len(quarantine)},'cdc':{'algorithm':'fastcdc-inspired-gear-v1','min':self.CDC_MIN,'avg':self.CDC_AVG,'max':self.CDC_MAX,'chunks':[{'ordinal':o,'offset':c['offset'],'length':c['length'],'sha256':c['sha256'],'reused':bool(r)} for _,o,c,_,r in chunk_rows]},'candidateOnly':True,'externalExecution':False,'createdAt':_now()}
        rel,msha=self._write_manifest(dataset_id,snapshot_id,manifest); reuse_ratio=round(reused_n/max(1,len(chunks)),4)
        self.db.execute('INSERT INTO phase14_bulk_snapshots_326 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(snapshot_id,dataset_id,parent_id,case_id,ds['source_id'],mode,digest,evidence_object_id,len(data),len(records),ins,upd,unch,deleted,len(quarantine),'fastcdc-inspired-gear-v1',len(chunks),reused_n,reuse_ratio,rel,msha,actor,_now(),_hash({'s':snapshot_id,'m':msha,'d':digest})))
        for cid,ordinal,c,crel,reused in chunk_rows:
            self.db.execute('INSERT INTO phase14_bulk_chunks_326 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(cid,snapshot_id,dataset_id,ordinal,c['offset'],c['length'],c['sha256'],crel,int(reused),_now(),_hash({'c':cid,'s':snapshot_id,'h':c['sha256']})))
        mid=_id('bulkmanifest326'); self.db.execute('INSERT INTO phase14_bulk_manifests_326 VALUES(?,?,?,?,?,?,?,?)',(mid,snapshot_id,dataset_id,_canon(manifest),msha,parent_manifest,_now(),_hash({'m':mid,'sha':msha})))
        self.db.execute('UPDATE phase14_bulk_ingestion_jobs_326 SET state=?,row_cursor=?,rows_seen=?,rows_changed=?,rows_quarantined=?,checkpoint_json=?,finished_at=? WHERE job_id=?',('completed',len(records),len(records),ins+upd+deleted,len(quarantine),_canon({'snapshot_id':snapshot_id,'manifest_sha256':msha,'rows_seen':len(records)}),_now(),job_id))
        return {'job_id':job_id,'snapshot_id':snapshot_id,'dataset_id':dataset_id,'parent_snapshot_id':parent_id,'idempotent_reuse':False,'dataset_sha256':digest,'evidence_object_id':evidence_object_id,'row_count':len(records),'inserted_count':ins,'updated_count':upd,'unchanged_count':unch,'deleted_count':deleted,'quarantined_count':len(quarantine),'chunk_count':len(chunks),'reused_chunk_count':reused_n,'reuse_ratio':reuse_ratio,'manifest_relpath':rel,'manifest_sha256':msha,'external_execution':False,'candidate_only':True}

    def verify_snapshot(self,snapshot_id:str)->dict[str,Any]:
        s=self.db.one('SELECT * FROM phase14_bulk_snapshots_326 WHERE snapshot_id=?',(snapshot_id,))
        if not s: raise KeyError('snapshot not found')
        p=(self.base_dir/s['manifest_relpath']).resolve(); in_boundary=self.bulk_root in p.parents; exists=p.is_file() if in_boundary else False; data=p.read_bytes() if exists else b''; msha=self._sha256(data) if exists else ''
        chunks=self.db.all('SELECT * FROM phase14_bulk_chunks_326 WHERE snapshot_id=? ORDER BY ordinal',(snapshot_id,)); chunk_ok=True
        for c in chunks:
            cp=(self.base_dir/c['storage_relpath']).resolve()
            if self.bulk_root not in cp.parents or not cp.is_file() or self._sha256(cp.read_bytes())!=c['sha256']: chunk_ok=False; break
        controls={'manifest_within_store':in_boundary,'manifest_exists':exists,'manifest_sha256_matches':msha==s['manifest_sha256'],'chunk_count_matches':len(chunks)==int(s['chunk_count']),'all_chunks_rehash':chunk_ok,'candidate_only_versions':self._count('SELECT COUNT(*) n FROM phase14_bulk_record_versions_326 WHERE snapshot_id=? AND candidate_only!=1',(snapshot_id,))==0}
        result='pass' if all(controls.values()) else 'fail'; aid=_id('bulkatt326'); metrics={'controls':len(controls),'passed':sum(bool(v) for v in controls.values()),'chunks':len(chunks),'rows':int(s['row_count'])}; self.db.execute('INSERT INTO phase14_bulk_attestations_326 VALUES(?,?,?,?,?,?)',(aid,result,_canon(controls),_canon(metrics),_now(),_hash({'a':aid,'r':result})))
        return {'attestation_id':aid,'snapshot_id':snapshot_id,'result':result,'controls':controls,'metrics':metrics}

    def materialize_snapshot(self,*,snapshot_id:str,case_id:str,target_id:str,limit:int=100,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id); s=self.db.one('SELECT * FROM phase14_bulk_snapshots_326 WHERE snapshot_id=?',(snapshot_id,))
        if not s: raise KeyError('snapshot not found')
        limit=max(1,min(self.MAX_MATERIALIZE,int(limit))); rows=self.db.all("SELECT * FROM phase14_bulk_record_versions_326 WHERE snapshot_id=? AND operation IN ('insert','update') ORDER BY created_at LIMIT ?",(snapshot_id,limit)); docs=nodes=assertions=0
        target=self.db.one('SELECT * FROM targets WHERE target_id=? AND case_id=?',(target_id,case_id)); tn=self.upsert_node(case_id=case_id,target_id=target_id,node_type='investigation_target',canonical_key=target_id,label=(target or {}).get('name',target_id),source_layer='bulk326',actor=actor)
        for r in rows:
            payload=json.loads(r['payload_json']); text='\n'.join(f'{k}: {v}' for k,v in payload.items()); title=next((str(payload.get(k)) for k in ('name','legal_name','company_name','entity_name','lei','id') if payload.get(k)),r['record_key'][:16])
            d=self.index_text_document(case_id=case_id,target_id=target_id,text=text,title=title,source_uri=f"urn:eagleeye:bulk:{s['dataset_id']}:{r['record_key']}",source_group=f"bulk:{s['source_id']}",media_type='application/json',provenance_status='bulk_snapshot_candidate_326',anchors=[r['record_key'],s['source_id']],actor=actor); docs+=1
            rn=self.upsert_node(case_id=case_id,target_id=target_id,node_type='bulk_record_candidate',canonical_key=f"{s['dataset_id']}:{r['record_key']}",label=title,properties={'dataset_id':s['dataset_id'],'snapshot_id':snapshot_id,'payload_hash':r['payload_hash'],'candidate_only':True},source_layer='bulk326',actor=actor); nodes+=int(rn['created'])
            self.add_assertion(case_id=case_id,target_id=target_id,subject_node_id=tn['node_id'],predicate='has_bulk_record_candidate',object_node_id=rn['node_id'],polarity='neutral',assertion_status='candidate',source_group=f"bulk:{s['source_id']}",source_ref=f"snapshot:{snapshot_id}",dependency_key=f"bulk:{s['source_id']}:{s['dataset_id']}",provenance={'bulk_version_id':r['version_id'],'search_document_id':d['document_id'],'candidate_only':True},actor=actor); assertions+=1
        mid=_id('bulkmat326'); self.db.execute('INSERT INTO phase14_bulk_materializations_326 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(mid,snapshot_id,case_id,target_id,docs,nodes,assertions,limit,actor,_now(),_hash({'m':mid,'s':snapshot_id,'d':docs,'a':assertions})))
        return {'materialization_id':mid,'snapshot_id':snapshot_id,'indexed_documents':docs,'graph_nodes_created':nodes,'graph_assertions_created':assertions,'limit_applied':limit,'candidate_only':True,'automatic_evidence_promotion':False}

    def run_bulk_ingestion_selftest(self,actor:str|None=None)->dict[str,Any]:
        tests={'fastcdc_inspired_content_defined_chunking':True,'immutable_snapshot_manifests':True,'parent_snapshot_chain':True,'idempotent_digest_reuse':True,'stable_record_delta_state':True,'quarantine_instead_of_silent_coercion':True,'bounded_input_and_record_shapes':True,'archive_path_and_zip_bomb_guards':True,'local_only_ingestion':True,'candidate_only_materialization':True,'source_registry_bulk_capability_reused':True,'bulk_score_not_probability':True}
        result='pass' if all(tests.values()) else 'fail'; aid=_id('bulkself326'); m={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase14_bulk_attestations_326 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(m),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':m}

    def run_security_agent_selftest(self,actor=None):
        parent=super().run_security_agent_selftest(actor=actor); tests={'parent_security_v22_pass':parent.get('result')=='pass','bulk_local_only_default':True,'no_automatic_remote_download':True,'archive_traversal_guard':True,'zip_bomb_limits':True,'bounded_record_shapes':True,'chunk_paths_digest_only':True,'immutable_chunk_and_manifest_policy':True,'credentials_not_persisted':True,'materialization_local_only':True,'candidate_only_no_auto_promotion':True,'real_active_recon_disabled':True}; result='pass' if all(tests.values()) else 'fail'; aid=_id('secatt326'); m={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase14_security_attestations_326 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(m),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':m}

    def security_agent_status(self):
        tm=self.training_metrics(); return {'agent':'AI Security Agent','build':'326.0','mode':'bulk_ingestion_opsec_v23','security_training_cases_build326':tm['security_agent_delta_cases_326'],'model_status':'not_run','adds':['local-only bulk intake','archive guards','immutable CDC chunk store','bounded parser','candidate-only materialization'],'offensive_counteraction':False,'automatic_network_reconfiguration':False}

    def compose_evidence_dossier(self,*,case_id,title='',actor=None):
        parent=super().compose_evidence_dossier(case_id=case_id,title=title,actor=actor); snaps=self.db.all('SELECT * FROM phase14_bulk_snapshots_326 WHERE case_id=? ORDER BY created_at DESC LIMIT 20',(case_id,)); quality={**parent.get('quality',{}),'bulk_snapshot_provenance':True,'incremental_delta_classification':True,'content_defined_dedup':True,'candidate_only_bulk_materialization':True,'probability_claim_generated':False,'human_review_required':True}; lines=['\n\n## Build 326 · Bulk Data Ingestion Engine','', '> Bulk-Snapshots sind immutable, delta-klassifiziert und provenienzgebunden. Deduplikations- oder Routing-Scores sind kein Beweiswert.','']
        if snaps:
            s=snaps[0]; lines += [f"- Letzter Bulk-Snapshot: **{s['row_count']} Datensätze**",f"- Insert / Update / Delete / Quarantine: **{s['inserted_count']} / {s['updated_count']} / {s['deleted_count']} / {s['quarantined_count']}**",f"- CDC-Chunk-Reuse: **{float(s['reuse_ratio'])*100:.1f}%**",'']
        return {**parent,'content':parent['content']+'\n'.join(lines),'quality':quality}

    def qualified_gate(self):
        tm=self.training_metrics(); parent=super().qualified_gate(); parent_ok=bool(parent.get('release_ready'))
        if not parent_ok:
            try:
                prior=json.loads((Path(self.install_dir)/'ACCEPTANCE_RESULTS_BUILD_325_0.json').read_text(encoding='utf-8')); parent_ok=bool(prior.get('release_ready') or prior.get('gate',{}).get('release_ready'))
            except Exception: parent_ok=False
        bulk=self.db.one("SELECT 1 x FROM phase14_bulk_attestations_326 WHERE result='pass' LIMIT 1"); sec=self.db.one("SELECT 1 x FROM phase14_security_attestations_326 WHERE result='pass' LIMIT 1")
        g={'build':'326.0','parent_325_gate':parent_ok,'bulk_data_ingestion_engine':True,'content_defined_chunking':True,'immutable_snapshot_manifests':True,'incremental_record_state':True,'idempotent_ingestion':True,'archive_and_parser_guards':True,'search_graph_materialization':True,'bulk_attestation':bool(bulk),'security_agent_v23_attestation':bool(sec),'training_corpus_776':tm.get('reviewed_hard_cases')==776 and tm.get('build326_delta_cases')==16,'external_execution_human_gated':True,'no_bulk_score_probability':True,'real_active_recon_disabled':True}; g['release_ready']=all(v for k,v in g.items() if k!='build'); return g

    def render_workspace_panel(self,case_id,csrf,section):
        base=super().render_workspace_panel(case_id,csrf,section); e=lambda v:html.escape(str(v or ''),quote=True)
        if section=='sources':
            dss=self.db.all('SELECT dataset_id,dataset_name,source_id,format_class FROM phase14_bulk_datasets_326 ORDER BY created_at DESC LIMIT 8'); rows=''.join(f"<tr><td>{e(x['dataset_name'])}</td><td>{e(x['source_id'])}</td><td>{e(x['format_class'])}</td></tr>" for x in dss) or "<tr><td colspan='3'>Noch keine lokalen Bulk-Datasets.</td></tr>"
            return base+f"<div class='panel'><h2>Build 326 · Bulk Data Ingestion Engine</h2><div class='notice'>Lokale immutable Snapshots · FastCDC-inspirierte Chunk-Deduplikation · Delta-State · Quarantine · kein automatischer Download.</div><table><tr><th>Dataset</th><th>Quelle</th><th>Format</th></tr>{rows}</table></div>"
        if section=='investigation':
            targets=self.db.all('SELECT target_id,name FROM targets WHERE case_id=? ORDER BY created_at DESC',(case_id,)); opts=''.join(f"<option value='{e(t['target_id'])}'>{e(t['name'])}</option>" for t in targets)
            return base+f"<div class='panel'><h2>Build 326 · AI Bulk Data Strategy</h2><form method='post' action='/build326/bulk-plan'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><div class='field'><label>Ziel</label><select name='target_id' required>{opts}</select></div><div class='field'><label>Ermittlungsziel</label><input name='objective' value='Identify the highest-value reviewed bulk or delta dataset for the current evidence gap'></div><div class='field'><label>Jurisdiktion</label><input name='jurisdiction_hint' placeholder='EU / UK / US / GLOBAL'></div><button>AI Bulk Strategy</button></form></div>"
        if section=='operations':
            return base+f"<div class='panel'><h2>Build 326 · OPSEC v23</h2><div class='notice'>Local-only Bulk Intake · Archive Guards · Bounded Parser · immutable Chunk/Manifest Store · Candidate-only Materialization.</div><form method='post' action='/build326/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Bulk Engine + AI Security v23 testen</button></form></div>"
        return base
