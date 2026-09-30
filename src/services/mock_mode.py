"""AgentCore Platform v1.0"""

# Shared mock-mode resolution helper.
#
# Per .claude/rules/implementation_rule.md Rule 1: the scaffold's deploy-stg
# CI job sets STG_MOCK_MODE=true as a CI-script-only variable — it is never
# exported to the uvicorn process the job boots. Local dev / tests use the
# canonical USE_MOCK. Every service/node gating real-vs-mock behavior MUST
# resolve mock mode through this single helper — never re-implement env var
# resolution locally (a future rename only needs one edit here).

from __future__ import annotations

import os

_TRUTHY = {"1", "true", "yes", "on"}


def mock_mode_enabled() -> bool:
    """Return True if mock mode is enabled via USE_MOCK or STG_MOCK_MODE.

    USE_MOCK is the canonical flag (what tests and local dev set).
    STG_MOCK_MODE is the alias the deploy-stg CI job actually sets.
    Either being set to a truthy string enables mock mode.
    """
    use_mock = os.environ.get("USE_MOCK", "")
    stg_mock_mode = os.environ.get("STG_MOCK_MODE", "")
    return use_mock.strip().lower() in _TRUTHY or stg_mock_mode.strip().lower() in _TRUTHY
