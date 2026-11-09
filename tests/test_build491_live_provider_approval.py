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
    }))
    ProviderCollection120Service._validate_search_approval(
        service,
        case_id="case-1",
        provider_key="public_test",
        query="public archive records",
        search_intent_id="intent-1",
        search_query_id="query-1",
    )
