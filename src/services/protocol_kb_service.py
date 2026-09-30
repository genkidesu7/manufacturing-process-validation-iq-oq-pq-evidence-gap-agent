"""AgentCore Platform v1.0"""

# Service layer: protocol/acceptance-criteria KB lookups and evidence-matrix
# row construction.
# Only the LLM call is real in this deployment (see src/services/service.py);
# this connector is served from src/services/mock_data.py stubs and never
# touches a credential.

from __future__ import annotations

from typing import Any

from src.services.mock_data import stub_evidence_matrix_row


class ProtocolKbService:
    """Builds evidence-matrix rows for each protocol step."""

    async def build_evidence_matrix(
        self,
        protocol_steps: list[dict[str, Any]],
        matched_records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Build the requirement-to-evidence traceability matrix from the stub data source."""
        return [await stub_evidence_matrix_row(step, matched_records) for step in protocol_steps]
