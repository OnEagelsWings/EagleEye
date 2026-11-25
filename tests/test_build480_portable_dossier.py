"""Restored formal dossier artifacts must not depend on the old workspace."""
import hashlib,shutil
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
from eagleeye.bootstrap.recovery479 import create_backup,restore_backup
from test_build449_integrated import test_four_eyes_chain_evidence_claim_dossier_and_export as seed_dossier

def test_formal_dossier_remains_readable_after_old_workspace_is_removed(tmp_path):
    original=tmp_path/'original';archive=tmp_path/'backup.zip';restored=tmp_path/'restored'
    seed_dossier(original)
    create_backup(original,archive);receipt=restore_backup(archive,restored)
    assert receipt['archived_bytes_verified_before_session_reset']
    shutil.rmtree(original)
    with AppContext(base_dir=restored) as ctx:
        row=ctx.db.one('SELECT case_id,record_hash FROM dossier_export_447')
        exports=ctx.evidence_claims_dossier_447.exports(row['case_id'])
        assert len(exports)==1 and exports[0]['record_hash']==row['record_hash']
        output=exports[0]
        package=Path(output['paths']['case_package'])
        assert restored in package.parents and package.is_file()
        assert hashlib.sha256(package.read_bytes()).hexdigest()==output['package_hash']
        for kind in ('json','docx','pdf','manifest'):
            path=Path(output['paths'][kind])
            assert restored in path.parents and hashlib.sha256(path.read_bytes()).hexdigest()==output['hashes'][path.name]
        assert ctx.human_review_449.verify_integrity()['valid']
        assert ctx.evidence_claims_dossier_447.verify_integrity()['valid']
