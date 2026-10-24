"""Actual read-only public metadata pilot; never substitutes mocked responses."""
from __future__ import annotations
import argparse,hashlib,json,tempfile,sys,shutil
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from eagleeye.application.collectors469 import collect,_fetch_fixed_json
from eagleeye.application.entity_registry461 import EntityRegistry461
from eagleeye.interfaces.web.app480 import create_workspace_app480
from eagleeye.interfaces.web.findings478 import notes_db,notes_for_case,BASE_COLUMNS,INSERT_FINDING_SQL,finding_hash
from eagleeye.interfaces.web.report479 import report_body,source_states
from eagleeye.bootstrap.recovery479 import create_backup,restore_backup

QUERIES=[('dns','example.com'),('rdap_com','example.com'),('crossref','10.1038/195899a0')]

def actual_capture(provider,indicator):
    original={}
    def real_fetch(url):
        payload=_fetch_fixed_json(url);original.update(payload);return payload
    packet=collect(provider,indicator,fetcher=real_fetch)
    if provider=='dns' and (original.get('Status')!=0 or not original.get('Answer')):raise ValueError('DNS answer missing')
    if provider=='rdap_com' and str(original.get('ldhName','')).casefold()!=indicator:raise ValueError('RDAP name mismatch')
    if provider=='crossref' and str(original.get('message',{}).get('DOI','')).casefold()!=indicator.casefold():raise ValueError('Crossref DOI mismatch')
    return packet

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='checkpoint480-live-public.json')
    args=parser.parse_args()
    proof={'captured_at_utc':datetime.now(timezone.utc).isoformat(),'mocked_network':False,
        'synthetic_identity_accounts':True,'human_independent_review':False,'llm_evaluated':False,
        'production_release_ready':False,'sources':[],'technical_existing_dossier_chain':'N/A'}
    packets=[]
    for provider,indicator in QUERIES:
        try:
            packet=actual_capture(provider,indicator);packets.append(packet)
            proof['sources'].append({'provider':provider,'indicator':indicator,'status':'PASS',
                'url':packet['source_url'],'snapshot_sha256':hashlib.sha256(packet['raw']).hexdigest(),'bytes':len(packet['raw'])})
        except Exception as exc:
            proof['sources'].append({'provider':provider,'indicator':indicator,'status':'FAIL','reason':type(exc).__name__})
    error=None
    if packets:
        try:
            with tempfile.TemporaryDirectory(prefix='eagleeye-live480-') as temporary:
                root=Path(temporary)/'original';app=create_workspace_app480(base_dir=root);ctx=app.state.context
                cid='';documents=[]
                try:
                    admin=ctx.team_identity_359.create_initial_admin(username='publicqa',display_name='Public metadata test',password='Distinct!Public-Pilot_8294')
                    reviewer=ctx.team_governance_359.create_user(identity=admin,username='reviewqa',display_name='Scripted second test account',global_role='reviewer',password='Distinct!Review-Pilot_8294')
                    case=ctx.team_governance_359.create_case(identity=admin,title='Actual public metadata pilot',client='Technical QA',purpose='Evaluate public example-domain and publication metadata with original snapshots',legal_basis='public_data')
                    cid=case['case_id']
                    ctx.team_governance_359.assign_case_role(identity=admin,case_id=cid,username=reviewer['username'],case_role='reviewer')
                    for index,packet in enumerate(packets):
                        doc=ctx.document_intelligence_458.import_bytes(identity=admin,case_id=cid,filename=packet['filename'],raw=packet['raw'],title=packet['title'],source_url=packet['source_url'])
                        documents.append(doc['document_id'])
                        anchor=ctx.document_intelligence_458.anchors(identity=admin,document_id=doc['document_id'])['anchors'][0]
                        anchor=ctx.document_intelligence_458._anchor(anchor['anchor_id'])
                        doc=ctx.document_intelligence_458._document(doc['document_id'])
                        row=dict(finding_id='live480-'+str(index),case_id=cid,document_id=doc['document_id'],anchor_id=anchor['anchor_id'],
                            title='Actual public snapshot '+packet['provider'],interpretation='A live public provider returned this bounded metadata snapshot. It does not establish identity, ownership, or current real-world truth.',
                            source_excerpt=anchor['text_excerpt'],document_sha256=doc['document_sha256'],source_url=packet['source_url'],
                            created_by=admin['username'],created_at=packet['captured_at_utc'],review_state='unreviewed',review_reason='',reviewed_by='',
                            kind='observation',anchor_hash=anchor['record_hash'],legacy_imported=0)
                        row['record_hash']=finding_hash(row)
                        with notes_db(app) as db:db.execute(INSERT_FINDING_SQL,tuple(row[k] for k in BASE_COLUMNS+('record_hash',)))
                        host=urlsplit(packet['source_url']).netloc
                        source=ctx.build421.register_source(identity=admin,name='Actual public '+packet['provider'],source_type='website',access_mode='public',
                            base_url='https://'+host+'/',capabilities=['public_pages'],coverage={'actual_network':True,'provider':packet['provider']})
                        event=ctx.acquisition_events_422.record(identity=admin,case_id=cid,source_id=source['source_id'],target=packet['source_url'],
                            method='api',status='retrieved',content_sha256=hashlib.sha256(packet['raw']).hexdigest(),media_type='text/plain',bytes_count=len(packet['raw']),
                            provenance={'actual_network':True,'captured_at_utc':packet['captured_at_utc'],'mocked':False},
                            usage={'public_only':True,'technical_test':True,'human_review':False})
                        ctx.content_store_423.ingest(identity=admin,event_id=event['event_id'],content=packet['raw'],media_type='text/plain',metadata={'actual_public_snapshot':True})
                    notes=notes_for_case(app,cid)
                    assert all(s=='snapshot_match' for s in source_states(app,admin,cid,notes).values())
                    working=report_body(app,admin,case,notes);assert len(notes)==len(packets)
                    proof['working_report']={'status':'PASS','notes':len(notes),'sha256':hashlib.sha256(working.encode()).hexdigest(),'review_state':'unreviewed'}
                    with EntityRegistry461(root/'entity_registry_462.sqlite3') as registry:
                        first=registry.create_entity(case_id=cid,kind='document',label='Actual public provider capture')
                        second=registry.create_entity(case_id=cid,kind='document',label='Bounded metadata observation')
                        registry.create_relation(case_id=cid,source_id=first['id'],target_id=second['id'],predicate='recorded_as',
                            source_refs=['document:'+documents[0]],state='hypothesis')
                        assert registry.graph(cid)['relations'][0]['state']=='hypothesis'
                    proof['graph_hypothesis_preserved']=True
                    sync=ctx.evidence_claims_dossier_447.sync_case_evidence(identity=admin,case_id=cid)
                    evidence=ctx.evidence_claims_dossier_447.case_evidence(cid)[0]
                    def complete(kind,object_id,decision,confirmation):
                        request=ctx.build449.request_review_449(identity=admin,object_type=kind,object_id=object_id,
                            note='Scripted technical role-separation test; NOT independent human approval.',assigned_to=reviewer['username'])
                        ctx.build449.claim_review_449(identity=reviewer,review_id=request['review_id'])
                        ctx.build449.complete_review_449(identity=reviewer,review_id=request['review_id'],decision=decision,
                            note='Technical test only. Actual public payload, but no human independence or substantive truth certification.',confirmation=confirmation)
                        return request
                    request=ctx.build449.request_review_449(identity=admin,object_type='evidence',object_id=evidence['evidence_id'],
                        note='Scripted role-separation check with actual public bytes.',assigned_to=reviewer['username'])
                    denied=False
                    try:ctx.build449.claim_review_449(identity=admin,review_id=request['review_id'])
                    except PermissionError:denied=True
                    assert denied
                    ctx.build449.claim_review_449(identity=reviewer,review_id=request['review_id'])
                    ctx.build449.complete_review_449(identity=reviewer,review_id=request['review_id'],decision='accepted',
                        note='Scripted technical test of provenance plumbing, not independent human approval.',confirmation='REVIEW EVIDENCE 447')
                    claim=ctx.evidence_claims_dossier_447.propose_claim(identity=admin,case_id=cid,
                        statement='The technical test acquired a public provider snapshot; no identity or ownership inference is made.',
                        support_evidence_ids=[evidence['evidence_id']],uncertainty_note='Scripted test; source content and substantive interpretation require independent human evaluation.')
                    complete('claim',claim['claim_id'],'accepted_for_dossier','REVIEW CLAIM 447')
                    dossier=ctx.evidence_claims_dossier_447.build_dossier(identity=admin,case_id=cid,title='TECHNICAL TEST – Actual Public Snapshot')
                    complete('dossier',dossier['revision_id'],'approved_for_export','APPROVE DOSSIER 447')
                    approval=complete('dossier_export',dossier['revision_id'],'approve','APPROVE DOSSIER EXPORT 449')
                    exported=ctx.build449.execute_approved_export_449(identity=admin,review_id=approval['review_id'],confirmation='EXPORT DOSSIER 447')
                    assert ctx.human_review_449.verify_integrity()['valid']
                    for kind in ('docx','pdf','case_package'):assert Path(exported['export']['paths'][kind]).is_file()
                    proof['technical_existing_dossier_chain']={'status':'PASS','evidence':len(sync['evidence_ids']),
                        'same_account_review_blocked':denied,'separate_scripted_accounts':True,'human_approval':False,
                        'package_hash':exported['export']['package_hash'],'review_integrity_valid':True}
                finally:ctx.close()
                archive=Path(temporary)/'pilot-backup.zip';target=Path(temporary)/'restored'
                create_backup(root,archive);receipt=restore_backup(archive,target)
                shutil.rmtree(root)  # Prove no restored component can fall back to the old workspace.
                restored=create_workspace_app480(base_dir=target)
                try:
                    context=restored.state.context;user=context.team_identity_359.public_user('publicqa')
                    restored_notes=notes_for_case(restored,cid)
                    assert len(restored_notes)==len(packets)
                    assert all(s=='snapshot_match' for s in source_states(restored,user,cid,restored_notes).values())
                    assert context.human_review_449.verify_integrity()['valid']
                    restored_exports=context.evidence_claims_dossier_447.exports(cid)
                    assert len(restored_exports)==1
                    output=restored_exports[0]
                    assert hashlib.sha256(Path(output['paths']['case_package']).read_bytes()).hexdigest()==output['package_hash']
                    for kind in ('json','docx','pdf','manifest'):
                        path=Path(output['paths'][kind]);assert path.is_file() and target in path.parents
                        assert hashlib.sha256(path.read_bytes()).hexdigest()==output['hashes'][path.name]
                    with EntityRegistry461(target/'entity_registry_462.sqlite3') as registry:assert len(registry.graph(cid)['relations'])==1
                    proof['actual_public_case_restore']={'status':'PASS','notes':len(restored_notes),'verified_files':receipt['verified_files'],
                        'graph_and_dossier_history_retained':True,'original_snapshots_match':True}
                finally:context.close()
        except Exception as exc:
            error=exc;proof['integration_error']=type(exc).__name__+': '+str(exc)[:400]
    proof['result']='PASS' if len(packets)==len(QUERIES) and not error else 'FAIL'
    Path(args.output).write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(proof,ensure_ascii=False))
    if error:raise error
    return 0 if proof['result']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
