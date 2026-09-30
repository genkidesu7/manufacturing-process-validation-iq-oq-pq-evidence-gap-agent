"""AgentCore Platform v1.0"""

# Inner domain-workflow node (src/graph/domain_workflow_graph.py topology).
# Node contract: extend FunctionNode; implement execute(state) -> dict[str, Any] only.
#
# Pure logic over evidence_matrix — no external service call, so no mock-mode
# gating is required here.

from __future__ import annotations

from typing import Any

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.services.events import emitter
from shared.services.events.types import EventType
from shared.utils.audit_logger import emit_trace_event


def _classify_gap(row: dict[str, Any]) -> str | None:
    """Return a gap_type for an evidence-matrix row, or None if no gap."""
    signature_status = row.get("signature_status")
    acceptance_criteria_met = row.get("acceptance_criteria_met")

    if not row.get("evidence_refs"):
        return "unexecuted"
    if signature_status != "signed":
        return "unsigned"
    if acceptance_criteria_met == "unknown":
        return "missing_criteria"
    if acceptance_criteria_met is False:
        return "contradictory"
    return None


class GapDetectNode(FunctionNode):
    """Gap Detect — flag unexecuted, unsigned, missing-criteria, or contradictory steps."""

    # S-1: explicit by design. No privileged operation here.
    required_trust_level = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        emitter().emit_event(
            event_type=EventType.PROGRESS_UPDATE,
            message="Detecting unexecuted, unsigned and contradictory steps...",
            metadata={"stage": "gap_detect"},
        )
        evidence_matrix = state.get("evidence_matrix", [])

        if not evidence_matrix:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["GapDetectNode: evidence_matrix is empty or missing"],
            }

        gap_list: list[dict[str, Any]] = []
        for row in evidence_matrix:
            gap_type = _classify_gap(row)
            if gap_type is not None:
                gap_list.append(
                    {
                        "step_id": row.get("step_id", ""),
                        "gap_type": gap_type,
                        "description": f"Step {row.get('step_id', '')} flagged as {gap_type}.",
                    }
                )

        emit_trace_event(
            "gaps_detected",
            {"evidence_matrix_row_count": len(evidence_matrix), "gap_count": len(gap_list)},
            state,
        )

        return {
            "gap_list": gap_list,
            "status": AgentStatus.SUCCESS.value,
        }
