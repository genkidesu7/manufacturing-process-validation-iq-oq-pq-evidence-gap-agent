"""AgentCore Platform v1.0"""

# Service layer: deviation-log lookups for cross-checking detected gaps.
# Only the LLM call is real in this deployment (see src/services/service.py);
# this connector is served from src/services/mock_data.py stubs and never
# touches a credential.

from __future__ import annotations

from typing import Any

from src.services.mock_data import stub_deviation_lookup


class DeviationLogService:
    """Looks up open deviation-log entries related to a protocol step."""

    async def lookup_deviation(self, step_id: str) -> dict[str, Any]:
        """Return {deviation_ref, known_deviation} for the given step_id from the stub data source."""
        return await stub_deviation_lookup(step_id)
