from __future__ import annotations
import json,tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.final_acceptance400 import CONFIRM_RUN,CONFIRM_REVIEW
ROOT=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory() as d:
    with AppContext(base_dir=Path(d),actor='acceptance400') as c:
        a=c.team_identity_359.create_initial_admin(username='accept400',display_name='Phase17 Acceptance',password='Build400-Acceptance-Z9!');a={**a,'session_id':'acc'}
        run=c.build400.run_phase17_acceptance(identity=a,confirmation=CONFIRM_RUN)
        run=c.build400.review_phase17_acceptance(run_id=run['run_id'],identity=a,disposition='accept_internal_phase17',rationale='Internal Phase 17 acceptance passed; external/live production evidence remains pending.',confirmation=CONFIRM_REVIEW)
        checks={
          '19_predecessor_stages_pass':run['passed_steps']==19 and run['total_steps']==19,
          'internal_phase17_complete':run['internal_acceptance'],
          'phase18_entry_ready':run['phase18_entry_ready'],
          'professional_pilot_preserved':run['professional_pilot_ready'],
          'human_review_recorded':bool(run['review']),
          'hash_chain_valid':c.build400.verify_phase17_acceptance(run['run_id'])['valid'],
          'external_holdout_not_faked':not run['external_holdout_qualified'],
          'external_soak_not_faked':not run['external_soak_qualified'],
          'production_not_released':not run['production_release_ready'],
          'real_model_holdout_blocker_visible':'build398_real_model_human_holdout_pending' in run['blockers'],
          'real_72h_soak_blocker_visible':'build399_real_72h_windows_firefox_soak_pending' in run['blockers'],
          'independent_operational_qualification_visible':'independent_build379_operational_qualification_pending' in run['blockers'],
          'real_connector_validation_visible':'real_connector_chain_validation_pending' in run['blockers'],
          'dossier_review_blocker_visible':'external_dossier_domain_review_pending' in run['blockers'],
          'tor_e2e_blocker_visible':'tor_onion_end_to_end_pending' in run['blockers'],
          'version_coherent':c.build400.version_status()['coherent'],
          'schema_integrity':c.build400.schema_metrics()['within_phase17_gate'],
          'predecessor_receipt':c.build400.historical_build399_receipt()['valid'],
        }
        result='pass' if all(checks.values()) else 'fail';fp=c.build400.code_fingerprint()
        acc={'build':'400.0','code_fingerprint':fp,'result':result,'checks':checks,'passed':sum(checks.values()),'total':len(checks)}
        final={'build':'400.0','code_fingerprint':fp,'internal_phase17_complete':bool(run['internal_acceptance']),'phase18_entry_ready':bool(run['phase18_entry_ready']),'professional_pilot_ready':bool(run['professional_pilot_ready']),'external_holdout_qualified':bool(run['external_holdout_qualified']),'external_72h_soak_qualified':bool(run['external_soak_qualified']),'broad_live_research_ready':False,'production_release_ready':False,'blockers':run['blockers'],'truthful_note':'Phase 17 is internally complete and may enter Phase 18 engineering. This is not a broad live-research or production release.'}
ROOT.joinpath('ACCEPTANCE_RESULTS_BUILD_400_0.json').write_text(json.dumps(acc,indent=2),encoding='utf-8');ROOT.joinpath('PHASE17_FINAL_ACCEPTANCE_BUILD_400.json').write_text(json.dumps(final,indent=2),encoding='utf-8');print(json.dumps(acc,indent=2));print(json.dumps(final,indent=2))
