"""Current-build regression: live provider access needs a case-approved query."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from eagleeye.application.collection.service import ProviderCollection120Service
from eagleeye.infrastructure.providers import ProviderAuthorizationError


def _service():
    service = object.__new__(ProviderCollection120Service)
    service._validate_case_target = Mock()
    service._validate_search_approval = Mock()
    service._adapters = {
        "public_test": SimpleNamespace(
            definition=SimpleNamespace(
                enabled=True, supports_live=True, supports_replay=True
            )
        )
    }
    return service


@pytest.mark.parametrize(
    "intent_id,query_id",
    [("", ""), ("intent-1", ""), ("", "query-1")],
)
def test_live_provider_requires_both_case_search_approvals(intent_id, query_id):
    service = _service()
    with pytest.raises(ProviderAuthorizationError, match="approved case search"):
        service.execute(
            case_id="case-1",
            provider_key="public_test",
            query="public archive records",
            purpose="Check publicly available archive records",
            approved_by="reviewer-1",
            confirmation=service.APPROVAL_PHRASE,
            mode="live",
            search_intent_id=intent_id,
            search_query_id=query_id,
        )
    service._validate_search_approval.assert_not_called()


@pytest.mark.parametrize(
    "overrides",
    [
        {"case_id": "other-case"},
        {"intent_id": "other-intent"},
        {"intent_state": "draft"},
        {"query_state": "draft"},
        {"provider": "other-provider"},
        {"query_text": "different public search"},
    ],
)
def test_live_approval_rejects_wrong_case_scope_or_unapproved_query(overrides):
    service = _service()
    row = {
        "case_id": "case-1",
        "intent_id": "intent-1",
        "intent_state": "approved",
        "query_state": "approved",
        "provider": "public_test",
        "query_text": "public archive records",
        "target_id": None,
    }
    row.update(overrides)
    service.db = SimpleNamespace(one=Mock(return_value=row))
    with pytest.raises(ProviderAuthorizationError):
        ProviderCollection120Service._validate_search_approval(
            service,
            case_id="case-1",
            provider_key="public_test",
            query="public archive records",
            search_intent_id="intent-1",
            search_query_id="query-1",
        )
    service.db.one.assert_called_once()


def test_live_approval_accepts_only_matching_approved_query():
    service = _service()
    service.db = SimpleNamespace(one=Mock(return_value={
        "case_id": "case-1",
        "intent_id": "intent-1",
        "intent_state": "approved",
        "query_state": "approved",
        "provider": "public_test",
        "query_text": "public archive records",
        "target_id": None,
    }))
    ProviderCollection120Service._validate_search_approval(
        service,
        case_id="case-1",
        provider_key="public_test",
        query="public archive records",
        search_intent_id="intent-1",
        search_query_id="query-1",
    )


@pytest.mark.parametrize("approved_target,execution_target", [
    ("target-A", "target-B"),
    ("target-A", ""),
    (None, "target-A"),
])
def test_live_approval_rejects_target_scope_mismatch(approved_target, execution_target):
    service = _service()
    service.db = SimpleNamespace(one=Mock(return_value={
        "case_id": "case-1", "intent_id": "intent-1",
        "intent_state": "approved", "query_state": "approved",
        "provider": "public_test", "query_text": "public archive records",
        "target_id": approved_target,
    }))
    with pytest.raises(ProviderAuthorizationError, match="search target differs"):
        ProviderCollection120Service._validate_search_approval(
            service, case_id="case-1", provider_key="public_test",
            query="public archive records", search_intent_id="intent-1",
            search_query_id="query-1", target_id=execution_target,
        )


def test_live_run_rechecks_approval_before_candidate_intake():
    """Revocation after the last response must not create unreviewed candidates."""
    from eagleeye.infrastructure.providers import (
        NormalizedProviderItem, ProviderHttpRequest, ProviderTransportResponse,
    )

    service = _service()
    service.clock = lambda: 1731000000.0
    service.db = SimpleNamespace(execute=Mock())
    service.audit = SimpleNamespace(log=Mock())
    service._event = Mock()
    service._execute_request = Mock(return_value=(
        ProviderTransportResponse(
            requested_url="https://example.org/record",
            status_code=200, final_url="https://example.org/record",
            body=b"{}", headers={}, elapsed_ms=5,
        ), 1,
    ))
    service._record_fixture = Mock(return_value="fixture-1")
    service._store_intake = Mock(return_value=(["candidate-1"], 0))
    service._record_run_failure = Mock()
    service._record_run_success = Mock()
    service._adapters = {
        "public_test": SimpleNamespace(
            definition=SimpleNamespace(
                enabled=True, supports_live=True, supports_replay=True,
            ),
            validate_request=Mock(),
            build_requests=Mock(return_value=(
                ProviderHttpRequest("https://example.org/record"),
            )),
            normalize=Mock(return_value=[]),
        )
    }
    calls = 0

    def revoke_on_final_check(**_kwargs):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise ProviderAuthorizationError("approval revoked")

    service._validate_search_approval = revoke_on_final_check
    with pytest.raises(ProviderAuthorizationError, match="approval revoked"):
        service.execute(
            case_id="case-1", provider_key="public_test",
            query="public archive records",
            purpose="Check publicly available archive records",
            approved_by="reviewer-1",
            confirmation=service.APPROVAL_PHRASE, mode="live",
            search_intent_id="intent-1", search_query_id="query-1",
            record_replay=True,
        )
    assert calls == 3
    service._record_fixture.assert_not_called()
    service._store_intake.assert_not_called()
    assert any(
        "status='failed'" in call.args[0]
        for call in service.db.execute.call_args_list
    )


def test_live_revocation_after_fixture_blocks_candidate_intake():
    """A late revocation must not promote normalized data into intake."""
    from eagleeye.infrastructure.providers import ProviderHttpRequest, ProviderTransportResponse

    service = _service()
    service.clock = lambda: 1731000000.0
    service.db = SimpleNamespace(execute=Mock())
    service.audit = SimpleNamespace(log=Mock())
    service._event = Mock()
    response = ProviderTransportResponse(
        requested_url="https://example.org/record", status_code=200,
        final_url="https://example.org/record", body=b"{}", headers={}, elapsed_ms=5,
    )
    service._execute_request = Mock(return_value=(response, 1))
    service._record_fixture = Mock(return_value="fixture-1")
    service._store_intake = Mock(return_value=(["candidate-1"], 0))
    service._record_run_failure = Mock()
    service._adapters = {"public_test": SimpleNamespace(
        definition=SimpleNamespace(enabled=True, supports_live=True, supports_replay=True),
        validate_request=Mock(),
        build_requests=Mock(return_value=(ProviderHttpRequest("https://example.org/record"),)),
        normalize=Mock(return_value=[]),
    )}
    calls = 0

    def revoke_before_intake(**_kwargs):
        nonlocal calls
        calls += 1
        if calls == 5:
            raise ProviderAuthorizationError("approval revoked before intake")

    service._validate_search_approval = revoke_before_intake
    with pytest.raises(ProviderAuthorizationError, match="approval revoked before intake"):
        service.execute(
            case_id="case-1", provider_key="public_test", query="public archive records",
            purpose="Check publicly available archive records", approved_by="reviewer-1",
            confirmation=service.APPROVAL_PHRASE, mode="live",
            search_intent_id="intent-1", search_query_id="query-1", record_replay=True,
        )
    assert calls == 5
    service._record_fixture.assert_called_once()
    service._store_intake.assert_not_called()
    service._record_run_failure.assert_not_called()


@pytest.mark.parametrize("altered_query", [
    "PUBLIC archive records",
    "public  archive records",
    "public archive records ",
    "public archive records OR unrelated",
])
def test_live_approval_query_changes_are_not_silently_accepted(altered_query):
    """Case-sensitive operators and spacing must match the approved query."""
    service = _service()
    service.db = SimpleNamespace(one=Mock(return_value={
        "case_id": "case-1", "intent_id": "intent-1",
        "intent_state": "approved", "query_state": "approved",
        "provider": "public_test", "query_text": "public archive records",
        "target_id": None,
    }))
    if altered_query == "public archive records ":
        # Harmless outer form whitespace is deliberately tolerated.
        ProviderCollection120Service._validate_search_approval(
            service, case_id="case-1", provider_key="public_test",
            query=altered_query, search_intent_id="intent-1",
            search_query_id="query-1",
        )
    else:
        with pytest.raises(ProviderAuthorizationError, match="differs from approved"):
            ProviderCollection120Service._validate_search_approval(
                service, case_id="case-1", provider_key="public_test",
                query=altered_query, search_intent_id="intent-1",
                search_query_id="query-1",
            )
