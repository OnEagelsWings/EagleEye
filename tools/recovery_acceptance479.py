"""Prove backup/restore with the installed isolated interpreter and real canonical stores."""
import argparse,json,os,subprocess,tempfile
from pathlib import Path
SEED="""
import hashlib,json,sys
from pathlib import Path
from eagleeye.interfaces.web.app479 import create_workspace_app479
from eagleeye.interfaces.web.findings478 import BASE_COLUMNS,INSERT_FINDING_SQL,finding_hash,notes_db,notes_for_case
root=Path(sys.argv[1]);mode=sys.argv[2];app=create_workspace_app479(base_dir=root);ctx=app.state.context
try:
    if mode=='seed':ctx.team_identity_359.create_initial_admin(username='restoreqa',display_name='Restore QA',password='Separate!Restore-Test-892')
    issued=ctx.team_identity_359.authenticate(username='restoreqa',password='Separate!Restore-Test-892',client_fingerprint='native-restore')
    identity=ctx.team_identity_359.validate_session(issued.token,client_fingerprint='native-restore',touch=False)
    if mode=='seed':
        case=ctx.team_governance_359.create_case(identity=identity,title='Native recovery proof',client='QA',purpose='Public synthetic recovery test',legal_basis='public_data')
        cid=case['case_id']
        doc=ctx.document_intelligence_458.import_bytes(identity=identity,case_id=cid,filename='source.txt',raw=b'Original source survives offline restoration.',title='Recovery source',source_url='https://example.org/source')
        anchor=ctx.document_intelligence_458.anchors(identity=identity,document_id=doc['document_id'])['anchors'][0]
        row=dict(finding_id='native-restore-note',case_id=cid,document_id=doc['document_id'],anchor_id=anchor['anchor_id'],title='Original source observation',interpretation='This is a human working note, not a confirmed fact.',source_excerpt=anchor['text_excerpt'],document_sha256=doc['document_sha256'],source_url=doc['source_url'],created_by=identity['username'],created_at='2026-10-24T00:00:00+00:00',review_state='unreviewed',review_reason='',reviewed_by='',kind='observation',anchor_hash=anchor['record_hash'],legacy_imported=0)
        row['record_hash']=finding_hash(row)
        with notes_db(app) as db:db.execute(INSERT_FINDING_SQL,tuple(row[k] for k in BASE_COLUMNS+('record_hash',)))
        print(json.dumps({'case_id':cid,'old_session_id':issued.session_id}))
    else:
        from eagleeye.interfaces.web.report479 import source_states
        saved=json.loads(sys.argv[3]);cid=saved['case_id'];notes=notes_for_case(app,cid)
        assert len(notes)==1 and notes[0]['finding_id']=='native-restore-note'
        assert source_states(app,identity,cid,notes)['native-restore-note']=='snapshot_match'
        old=ctx.db.one('SELECT revoked,revoked_reason FROM phase15_team_sessions WHERE session_id=?',(saved['old_session_id'],))
        assert old['revoked'] and old['revoked_reason']=='workspace_restore'
        assert ctx.team_identity_359.verify_access_chain()['ok']
        print(json.dumps({'case_opened':True,'note_preserved':True,'source_snapshot_match':True,'old_session_revoked':True,'access_chain_valid':True}))
finally:ctx.close()
"""
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runtime-python',required=True);parser.add_argument('--output',default='recovery-acceptance479.json')
    args=parser.parse_args();python=str(Path(args.runtime_python).absolute())
    def run(arguments):
        result=subprocess.run([python,'-I',*arguments],capture_output=True,text=True,timeout=120,check=False)
        if result.returncode:raise RuntimeError(result.stderr[-4000:])
        return json.loads(result.stdout.strip().splitlines()[-1])
    with tempfile.TemporaryDirectory(prefix='eagleeye-native-recovery-') as directory:
        root=Path(directory);original=root/'original';restored=root/'restored';archive=root/'backup.zip'
        saved=run(['-c',SEED,str(original),'seed'])
        env={**os.environ,'EAGLEEYE_DATA_DIR':str(original),'EAGLEEYE_SETTINGS_DIR':str(root/'settings')}
        def cli(*arguments):
            result=subprocess.run([python,'-I','-m','eagleeye.bootstrap.recovery479','--install-root',str(Path.cwd()),*arguments],
                env=env,capture_output=True,text=True,timeout=120,check=True)
            return json.loads(result.stdout)
        backup=cli('--backup','--archive',str(archive))
        receipt=cli('--restore','--archive',str(archive),'--target',str(restored))
        checked=run(['-c',SEED,str(restored),'verify',json.dumps(saved)])
        proof={'installed_interpreter':True,'isolated_mode':True,'backup_files':backup['files'],
            'restore_verified_files':receipt['verified_files'],'archived_bytes_verified_before_session_reset':receipt['archived_bytes_verified_before_session_reset'],
            **checked,'production_release_ready':False}
        Path(args.output).write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8');print(json.dumps(proof))
    return 0
if __name__=='__main__':raise SystemExit(main())
