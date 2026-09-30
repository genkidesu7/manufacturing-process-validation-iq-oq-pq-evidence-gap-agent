"""AgentCore Platform v1.0"""

# Service layer: RAG-style matching of executed test records to
# protocol steps.
# Only the LLM call is real in this deployment (see src/services/service.py);
# this connector is served from src/services/mock_data.py stubs and never
# touches a credential.

from __future__ import annotations

from typing import Any

from src.services.mock_data import stub_matched_records


class RecordMatchService:
    """Matches executed test records to protocol steps."""

    async def match_records(self, protocol_steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return one matched-record entry per protocol step from the stub data source."""
        return await stub_matched_records(protocol_steps)
