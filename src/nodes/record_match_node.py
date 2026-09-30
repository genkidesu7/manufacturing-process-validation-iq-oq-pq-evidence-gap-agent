"""AgentCore Platform v1.0"""

# Inner domain-workflow node (src/graph/domain_workflow_graph.py topology).
# Node contract: extend FunctionNode; implement execute(state) -> dict[str, Any] only.

from __future__ import annotations

from typing import Any

import asyncio
import json

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.services.events import emitter
from shared.services.events.types import EventType
from shared.utils.audit_logger import emit_trace_event

from src.services.record_match_service import RecordMatchService


def _extract_protocol_steps(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Return protocol_steps, decoding it from the inner graph's user_input if needed.

    Inner-graph caveat (sdk-expertise): the inner graph's initial_state only
    contains user_input — no other outer state field (including protocol_steps)
    is carried over automatically by BaseGraph.invoke(). The outer
    EvidenceReconciliationGraphNode.extract_input() JSON-encodes protocol_steps
    into the string passed as user_input specifically to bridge this gap. This
    node (the inner graph's entry point) is responsible for decoding it back
    out and re-exposing it as state["protocol_steps"] for downstream inner
    nodes, which read it directly from state.
    """
    protocol_steps: list[dict[str, Any]] | None = state.get("protocol_steps")
    if protocol_steps:
        return protocol_steps
    raw = state.get("validated_input", state.get("user_input", ""))
    try:
        decoded = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return []
    if isinstance(decoded, dict):
        return decoded.get("protocol_steps", []) or []
    return []


class RecordMatchNode(FunctionNode):
    """Record Match — RAG-match executed test records to protocol steps."""

    # S-1: explicit by design. No privileged operation here.
    required_trust_level = TrustLevel.ANONYMOUS

    def __init__(self) -> None:
        super().__init__()
        self._service = RecordMatchService()

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        emitter().emit_event(
            event_type=EventType.PROGRESS_UPDATE,
            message="Matching executed test records to protocol steps...",
            metadata={"stage": "record_match"},
        )
        protocol_steps = _extract_protocol_steps(state)

        if not protocol_steps:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["RecordMatchNode: protocol_steps is empty or missing"],
            }

        matched_records = asyncio.run(self._service.match_records(protocol_steps))

        emit_trace_event(
            "records_matched",
            {"protocol_step_count": len(protocol_steps), "matched_record_count": len(matched_records)},
            state,
        )

        return {
            "protocol_steps": protocol_steps,
            "matched_records": matched_records,
            "status": AgentStatus.SUCCESS.value,
        }
