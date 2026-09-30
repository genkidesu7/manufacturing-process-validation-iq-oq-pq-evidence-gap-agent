# Standalone /invoke caller-auth boundary: INVOKE_AUTH_TOKEN -> VERIFIED_EXTERNAL,
# STG_INTERNAL_RUNNER_TOKEN -> INTERNAL, never the other way round.

import pytest
from fastapi import HTTPException

from framework.schemas.trust_level import TrustLevel


@pytest.fixture
def resolve():
    from src.api.server import _resolve_standalone_trust

    return _resolve_standalone_trust


def test_no_tokens_configured_stays_anonymous(resolve):
    assert resolve(TrustLevel.ANONYMOUS, "", None, None) is TrustLevel.ANONYMOUS


def test_external_bearer_never_promotes_to_internal(resolve):
    assert resolve(TrustLevel.ANONYMOUS, "Bearer external", "external", "runner") is TrustLevel.VERIFIED_EXTERNAL


def test_runner_bearer_promotes_to_internal(resolve):
    assert resolve(TrustLevel.ANONYMOUS, "Bearer runner", "external", "runner") is TrustLevel.INTERNAL


def test_wrong_or_missing_bearer_is_rejected_when_auth_is_enabled(resolve):
    for header in ("", "Bearer wrong", "Bearer é"):
        with pytest.raises(HTTPException) as exc:
            resolve(TrustLevel.ANONYMOUS, header, "external", None)
        assert exc.value.status_code == 401


def test_middleware_established_trust_is_never_changed(resolve):
    assert resolve(TrustLevel.INTERNAL, "", "external", "runner") is TrustLevel.INTERNAL
