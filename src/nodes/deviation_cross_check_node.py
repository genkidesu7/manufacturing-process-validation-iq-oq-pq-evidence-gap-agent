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

from src.services.deviation_log_service import DeviationLogService


class DeviationCrossCheckNode(FunctionNode):
    """Deviation Cross-Check — annotate gaps against the open deviation log."""

    # S-1: explicit by design. No privileged operation here.
    required_trust_level = TrustLevel.ANONYMOUS

    def __init__(self) -> None:
        super().__init__()
        self._service = DeviationLogService()

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        emitter().emit_event(
            event_type=EventType.PROGRESS_UPDATE,
            message="Cross-checking gaps against the deviation log...",
            metadata={"stage": "deviation_cross_check"},
        )
        gap_list = state.get("gap_list", [])

        annotated_gap_list = [
            {**gap, **asyncio.run(self._service.lookup_deviation(gap.get("step_id", "")))} for gap in gap_list
        ]

        emit_trace_event(
            "deviations_cross_checked",
            {"gap_count": len(gap_list)},
            state,
        )

        return {
            "annotated_gap_list": annotated_gap_list,
            "status": AgentStatus.SUCCESS.value,
        }
