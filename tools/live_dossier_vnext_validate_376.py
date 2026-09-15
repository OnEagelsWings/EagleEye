from __future__ import annotations
import argparse, json, tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',default='LIVE_VALIDATION_BUILD_376_DOSSIER_VNEXT.json');args=ap.parse_args()
    root=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as td, AppContext(base_dir=td,actor='validate376') as c:
        a=c.team_identity_359.create_initial_admin(username='v376',display_name='V376',password='Valid-376-Password!');ident={**a,'session_id':'v376'}
        case=c.build376.team_create_case(identity=ident,title='Validation 376',client='QA',purpose='local dossier validation',legal_basis='public_data');cid=case['case_id']
        s=c.crawler_frontier_352.register_source(display_name='Validation Source',seed_urls=['https://example.org/v376'],terms_ref='public terms',max_depth=0,max_pages=1,requests_per_minute=5,max_response_bytes=100000)
        if s['review_status']=='pending_review':s=c.crawler_frontier_352.review_source(s['source_id'],decision='approve_read_only',rationale='local fixture source',reviewer='v376')
        c.build376.configure_case_workflow(case_id=cid,identity=ident,source_budgets={s['source_id']:10},case_request_budget=20,max_active_crawls=2,confirmation='WORKFLOW')
        packet=c.build376.dossier_packet(case_id=cid,identity=ident)
        checks={'coverage_register':packet['source_coverage']['expected_sources']==1,'gap_without_auto_crawl':packet['research_gap_count']==1 and packet['automatic_crawl_from_gap'] is False,'absence_semantics':packet['negative_evidence']['absence_is_nonexistence'] is False,'direct_network_authority':packet['direct_network_authority'] is False}
        out={'build':'376.0','code_fingerprint':c.build376.code_fingerprint(),'local_dossier_vnext_validation':'pass' if all(checks.values()) else 'fail','checks':checks,'external_network_used':False,'external_dossier_validation':'not_run','external_negative_evidence_validation':'not_run','truthful_note':'Local deterministic validation only; no external network or professional analyst validation performed.'}
    (root/args.output).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
