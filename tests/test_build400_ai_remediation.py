from __future__ import annotations

import pytest

from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.final_acceptance400 import CONFIRM_RUN, CONFIRM_REVIEW
from eagleeye_pro.phase17.model_holdout398 import (
    CONFIRM_EXTERNAL_RUN,
    CONFIRM_FREEZE_SUITE,
    CONFIRM_HUMAN_REVIEW,
)

PW = "Build400-Secure-Vector-Z9!"
REVIEW_KEYS = (
    "evidence_grounding",
    "counterevidence_handling",
    "uncertainty_handling",
    "actionability",
    "governance",
)


def _ctx(tmp_path):
    return AppContext(base_dir=tmp_path, actor="build400-remediation-test")


def _admin(c):
    user = c.team_identity_359.create_initial_admin(
        username="admin400fix",
        display_name="Build 400 Fix Lead",
        password=PW,
    )
    return {**user, "session_id": "build400-fix-session"}


def _scores(value: int):
    return {key: value for key in REVIEW_KEYS}


def test_external_holdout_requires_quality_and_blocks_harmful_overreach(tmp_path):
    with _ctx(tmp_path) as c:
        admin = _admin(c)
        holdout = c.model_holdout_398
        suite = holdout.create_reference_suite()
        sid = suite["suite_id"]
        holdout.freeze_suite(suite_id=sid, identity=admin, confirmation=CONFIRM_FREEZE_SUITE)
        case_ids = [
            row["case_id"]
            for row in c.db.all(
                "SELECT case_id FROM holdout_case_398 WHERE suite_id=? ORDER BY case_id",
                (sid,),
            )
        ]

        first_case = case_ids[0]
        for index, case_id in enumerate(case_ids):
            case = holdout._case(sid, case_id)
            output = holdout.deterministic_reference_output(case)
            if index == 0:
                output = {
                    "citations": ["bogus"],
                    "support_groups": 999,
                    "contradiction_groups": 999,
                    "stop_decision": "wrong",
                    "truth_determined": True,
                    "execution_authority": True,
                    "automatic_go": True,
                    "automatic_evidence_promotion": True,
                }
            run = holdout.record_external_model_run(
                suite_id=sid,
                case_id=case_id,
                adapter_id="external-test-adapter",
                model_id="external-test-model",
                output=output,
                execution_receipt=f"receipt-{case_id}",
                identity=admin,
                confirmation=CONFIRM_EXTERNAL_RUN,
            )
            holdout.submit_human_review(
                run_id=run["run_id"],
                identity={"username": f"reviewer-{index % 2}"},
                blind_review=True,
                scores=_scores(5),
                harmful_overreach=False,
                notes="Regression fixture",
                confirmation=CONFIRM_HUMAN_REVIEW,
            )

        status = holdout.qualification_status(sid)
        assert status["quality_external_model_cases"] == status["distinct_cases"] - 1
        assert not status["external_holdout_qualified"]

        case = holdout._case(sid, first_case)
        good_run = holdout.record_external_model_run(
            suite_id=sid,
            case_id=first_case,
            adapter_id="external-test-adapter",
            model_id="external-test-model-good",
            output=holdout.deterministic_reference_output(case),
            execution_receipt="receipt-first-good",
            identity=admin,
            confirmation=CONFIRM_EXTERNAL_RUN,
        )
        holdout.submit_human_review(
            run_id=good_run["run_id"],
            identity={"username": "reviewer-low-quality"},
            blind_review=True,
            scores=_scores(3),
            harmful_overreach=False,
            notes="Below qualification threshold",
            confirmation=CONFIRM_HUMAN_REVIEW,
        )
        status = holdout.qualification_status(sid)
        assert status["quality_external_model_cases"] == status["distinct_cases"]
        assert status["quality_human_reviewed_external_cases"] == status["distinct_cases"] - 1
        assert not status["external_holdout_qualified"]

        holdout.submit_human_review(
            run_id=good_run["run_id"],
            identity={"username": "reviewer-high-quality"},
            blind_review=True,
            scores=_scores(5),
            harmful_overreach=False,
            notes="Meets qualification threshold",
            confirmation=CONFIRM_HUMAN_REVIEW,
        )
        assert holdout.qualification_status(sid)["external_holdout_qualified"]

        holdout.submit_human_review(
            run_id=good_run["run_id"],
            identity={"username": "reviewer-harmful"},
            blind_review=True,
            scores=_scores(5),
            harmful_overreach=True,
            notes="Harmful-overreach veto fixture",
            confirmation=CONFIRM_HUMAN_REVIEW,
        )
        status = holdout.qualification_status(sid)
        assert status["harmful_external_reviews"] == 1
        assert not status["external_holdout_qualified"]


def test_needs_remediation_review_never_marks_phase18_ready(tmp_path):
    with _ctx(tmp_path) as c:
        admin = _admin(c)
        run = c.build400.run_phase17_acceptance(identity=admin, confirmation=CONFIRM_RUN)
        c.build400.review_phase17_acceptance(
            run_id=run["run_id"], identity=admin, disposition="needs_remediation",
            rationale="Regression fixture: remediation is still required.", confirmation=CONFIRM_REVIEW,
        )
        status = c.build400.phase17_status()
        assert not status["phase17_internal_acceptance"]
        assert not status["phase18_entry_ready"]
        assert not status["production_release_ready"]


def test_global_final_acceptance_rejects_read_only_identity(tmp_path):
    with _ctx(tmp_path) as c:
        admin = _admin(c)
        user = c.team_governance_359.create_user(
            identity=admin, username="readonly400fix", display_name="Read Only Build 400",
            global_role="read_only", password="ReadOnly-Build400-Fix-Z9!",
        )
        identity = {**user, "session_id": "readonly400-fix-session"}
        with pytest.raises(PermissionError):
            c.build400.run_phase17_acceptance(identity=identity, confirmation=CONFIRM_RUN)


def test_missing_soak_session_returns_structured_failure(tmp_path):
    with _ctx(tmp_path) as c:
        result = c.target_soak_399.verify_session("missing-build400-session")
        assert result == {"valid": False, "violations": ["missing_session"]}
