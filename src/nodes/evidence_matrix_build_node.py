"""AgentCore Platform v1.0"""

# Inner domain-workflow node (src/graph/domain_workflow_graph.py topology).
# Node contract: extend FunctionNode; implement execute(state) -> dict[str, Any] only.

from __future__ import annotations

from typing import Any

import asyncio

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.services.events import emitter
from shared.services.events.types import EventType
from shared.utils.audit_logger import emit_trace_event

from src.services.protocol_kb_service import ProtocolKbService


class EvidenceMatrixBuildNode(FunctionNode):
    """Evidence Matrix Build — construct the requirement-to-evidence traceability matrix."""

    # S-1: explicit by design. No privileged operation here.
    required_trust_level = TrustLevel.ANONYMOUS

    def __init__(self) -> None:
        super().__init__()
        self._service = ProtocolKbService()

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        emitter().emit_event(
            event_type=EventType.PROGRESS_UPDATE,
            message="Building requirement-to-evidence traceability matrix...",
            metadata={"stage": "evidence_matrix_build"},
        )
        protocol_steps = state.get("protocol_steps", [])
        matched_records = state.get("matched_records", [])

        if not protocol_steps:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["EvidenceMatrixBuildNode: protocol_steps is empty or missing"],
            }

        evidence_matrix = asyncio.run(self._service.build_evidence_matrix(protocol_steps, matched_records))

        emit_trace_event(
            "evidence_matrix_built",
            {"row_count": len(evidence_matrix)},
            state,
        )

        return {
            "evidence_matrix": evidence_matrix,
            "status": AgentStatus.SUCCESS.value,
        }
