from __future__ import annotations
import pytest
from eagleeye.crawler.engine import RobotsRules
from test_build394_integrated import ctx, admin, case, setup, side_counts
from test_build396_integrated import prepare_active
from eagleeye_pro.phase17.argumentative_analyst397 import CONFIRM_REVIEW


def base(c,a,cid):
    cl,h1,h2,ws,plan,*_=setup(c,a,cid); prepare_active(c,a,cid,cl,h1,h2,plan); return cl,h1,h2,plan

def test_version_schema_status(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build397.version_status()=={'runtime_build':'397.0','schema_version':'397.0','package_version':'397.0.0','coherent':True}
        assert c.build397.schema_metrics()['within_phase17_gate']
        s=c.argumentative_analyst_397.status(); assert s['precise_evidence_citations'] and s['explicit_stop_decisions'] and not s['truth_probability']

def test_robots_pdf_wildcard_end_anchor_fixed():
    r=RobotsRules('User-agent: *\nDisallow: /*.pdf$\n')
    assert not r.allowed('/report.pdf')
    assert r.allowed('/report.pdf?download=1')

def test_robots_multi_user_agent_group_fixed():
    r=RobotsRules('User-agent: ExampleBot\nUser-agent: EagleEye-GovernedCrawler\nDisallow: /private/\n')
    assert not r.allowed('/private/a') and r.allowed('/public/a')

def test_robots_longest_rule_allow_wins_tie():
    r=RobotsRules('User-agent: *\nDisallow: /private/\nAllow: /private/public/\n')
    assert r.allowed('/private/public/a') and not r.allowed('/private/secret')

def test_robots_fail_closed_state():
    r=RobotsRules.fail_closed('robots_http_503'); assert not r.allowed('/') and not r.allowed('/anything') and r.fail_closed_state

def test_claim_assessment_has_precise_citations(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*_=base(c,a,cid)
        out=c.build397.assess_argumentation(case_id=cid,target_type='claim',target_id=cl['claim_id'],identity=a)
        assert out['citations'] and all(x['candidate_id'] and x['object_sha256'] and x['parse_run_id'] for x in out['citations'])
        assert out['support_groups']>=1 and out['contradiction_groups']>=1 and out['stop_decision']=='continue_discriminating_research'

def test_hypothesis_assessment_preserves_argument_direction(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,h1,*_=base(c,a,cid)
        out=c.build397.assess_argumentation(case_id=cid,target_type='hypothesis',target_id=h1['hypothesis_id'],identity=a)
        assert out['target_type']=='hypothesis' and out['citations'] and out['probability_assigned'] is False

def test_assessment_integrity(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*_=base(c,a,cid)
        out=c.build397.assess_argumentation(case_id=cid,target_type='claim',target_id=cl['claim_id'],identity=a)
        assert c.argumentative_analyst_397.verify_assessment(case_id=cid,assessment_id=out['assessment_id'])['valid']

def test_recommendation_requires_review(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*_=base(c,a,cid); x=c.build397.assess_argumentation(case_id=cid,target_type='claim',target_id=cl['claim_id'],identity=a)
        r=c.build397.propose_analyst_recommendation(case_id=cid,assessment_id=x['assessment_id'],identity=a,recommendation_type='additional_discriminating_research',proposal={'question':'Resolve dated source conflict.'},rationale='Counterevidence remains independently sourced and material.')
        assert r['status']=='proposal_needs_review' and not r['execution_authority']
        with pytest.raises(PermissionError): c.build397.review_analyst_recommendation(case_id=cid,recommendation_id=r['recommendation_id'],identity=a,disposition='approve_for_manual_revision',rationale='review',confirmation='YES')

def test_review_does_not_mutate_upstream(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*_=base(c,a,cid); before=side_counts(c)
        x=c.build397.assess_argumentation(case_id=cid,target_type='claim',target_id=cl['claim_id'],identity=a)
        r=c.build397.propose_analyst_recommendation(case_id=cid,assessment_id=x['assessment_id'],identity=a,recommendation_type='claim_revision',proposal={'proposition':'Narrow wording for review.'},rationale='A narrower wording should be manually reviewed against the citations.')
        rr=c.build397.review_analyst_recommendation(case_id=cid,recommendation_id=r['recommendation_id'],identity=a,disposition='approve_for_manual_revision',rationale='Approved only for manual versioned revision; no automatic mutation.',confirmation=CONFIRM_REVIEW)
        assert rr['status']=='reviewed_for_manual_revision' and before==side_counts(c)

def test_tampered_candidate_breaks_assessment_verification(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*_=base(c,a,cid); x=c.build397.assess_argumentation(case_id=cid,target_type='claim',target_id=cl['claim_id'],identity=a); cand=x['citations'][0]['candidate_id']
        c.db.execute("UPDATE evidence_candidate_389 SET record_hash='tampered' WHERE candidate_id=?",(cand,))
        assert not c.argumentative_analyst_397.verify_assessment(case_id=cid,assessment_id=x['assessment_id'])['valid']

def test_no_execution_side_effects(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*_=base(c,a,cid); before=side_counts(c); c.build397.assess_argumentation(case_id=cid,target_type='claim',target_id=cl['claim_id'],identity=a); assert before==side_counts(c)

def test_phase_status(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build397.phase17_status(); assert s['build']=='397.0' and s['phase17_builds_completed']==17 and s['robots_parser_hardened'] and not s['execution_authority']
