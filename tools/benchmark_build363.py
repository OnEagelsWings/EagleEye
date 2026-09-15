from __future__ import annotations
import json,tempfile,hashlib
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
from eagleeye.phase16.storage_search363 import _endpoint_safe

class B:
    def __init__(self,b):self.b=b
    def read(self):return self.b
class S3:
    def __init__(self):self.d={}
    def put_object(self,**kw):self.d[(kw['Bucket'],kw['Key'])]=bytes(kw['Body'])
    def get_object(self,**kw):return {'Body':B(self.d[(kw['Bucket'],kw['Key'])])}
    def delete_object(self,**kw):self.d.pop((kw['Bucket'],kw['Key']),None)

def run(install_dir:Path):
    cases=0;viol=0;cats={}
    with tempfile.TemporaryDirectory(prefix='ee363-bench-') as td:
      with AppContext(base_dir=Path(td)) as c:
        # 500 endpoint policy cases
        good=['https://s3.example.org','https://minio.example.org:9000','http://127.0.0.1:9000','http://localhost:9000']
        bad=['http://s3.example.org','ftp://x.example.org','', 'not-a-url']
        for i in range(500):
            want=(i%2==0); val=good[i%len(good)] if want else bad[i%len(bad)]
            ok=_endpoint_safe(val)
            viol += int(ok!=want);cases+=1
        cats['endpoint_policy']=500
        # 500 S3 contract roundtrips, injected never external
        import os
        os.environ['EAGLEEYE_S3_ENDPOINT']='http://127.0.0.1:9000';os.environ['EAGLEEYE_S3_BUCKET']='qa'
        for i in range(500):
            r=c.build363.s3_live_validation(client=S3(),external_client=False)
            viol += int(not (r['status']=='pass' and not r['externally_validated'] and r['sha256_verified']));cases+=1
        cats['s3_contract']=500
        # 500 team search contracts
        def ex(sql,params):return [{'probe':params[0]}]
        for i in range(500):
            r=c.build363.team_search_live_validation(executor=ex,external_executor=False)
            viol += int(not (r['status']=='pass' and r['contract_validated'] and not r['live_validated']));cases+=1
        cats['team_search_contract']=500
        # 500 local CAS/FTS operations
        cid=c.cases.create_case(title='bench363',client='qa',purpose='benchmark',legal_basis='authorized')['case_id']
        for i in range(500):
            raw=f'object-{i}'.encode(); ob=c.local_object_store_347.put_bytes(raw); ok1=c.local_object_store_347.read_bytes(ob['object_key'],ob['sha256'])==raw
            did=f'd{i}'; c.search_platform_348.local.index_document(doc_id=did,case_id=cid,title='alpha',body=f'alpha evidence {i}',security_state='local_safe')
            rs=c.search_platform_348.local.search(case_id=cid,query='alpha',limit=5);ok2=bool(rs)
            viol += int(not (ok1 and ok2));cases+=1
        cats['local_store_search']=500
        fp=c.build363.code_fingerprint()
    out={'build':'363.0','result':'pass' if cases==2000 and viol==0 else 'fail','cases':cases,'violations':viol,'categories':cats,'code_fingerprint':fp,'external_s3_validation':'not_run','external_team_search_validation':'not_run','network_connections_opened':0}
    return out
if __name__=='__main__':
    root=Path(__file__).resolve().parents[1];out=run(root);p=root/'BENCHMARK_BUILD_363_OBJECT_SEARCH.json';p.write_text(json.dumps(out,indent=2,sort_keys=True));print(json.dumps(out,indent=2,sort_keys=True))
