"""AgentCore Platform v1.0"""

# Inner domain-workflow node (src/graph/domain_workflow_graph.py topology).
# Node contract: extend FunctionNode; implement execute(state) -> dict[str, Any] only.

from __future__ import annotations

from typing import Any

import asyncio

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel
from shared.services.events import emitter
from shared.services.events.types import EventType
from shared.utils.audit_logger import emit_trace_event

from src.services.mock_data import stub_brief_draft
from src.services.mock_mode import mock_mode_enabled
from src.services.service import build_brief_messages, call_llm


class BriefDraftNode(FunctionNode):
    """Brief Draft — generate the structured, provenance-linked reviewer brief."""

    # S-1: explicit by design. No privileged operation here.
    required_trust_level = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        mock_mode = mock_mode_enabled()
        emitter().emit_event(
            event_type=EventType.PROGRESS_UPDATE,
            message="Drafting reviewer-ready gap and remediation brief...",
            metadata={"stage": "brief_draft", "mock_mode": mock_mode},
        )
        evidence_matrix = state.get("evidence_matrix", [])
        annotated_gap_list = state.get("annotated_gap_list", [])

        if mock_mode:
            draft_brief = asyncio.run(stub_brief_draft(evidence_matrix, annotated_gap_list))
        else:
            # Mock mode is checked BEFORE credential resolution
            # (.claude/rules/implementation_rule.md Rule 2): a real deployment
            # with no Azure OpenAI secrets fails fast here via require().
            ctx = InvocationContext.from_state(state)
            draft_brief = call_llm(build_brief_messages(evidence_matrix, annotated_gap_list), ctx.secrets)

        emit_trace_event(
            "brief_drafted",
            {"evidence_matrix_row_count": len(evidence_matrix), "gap_count": len(annotated_gap_list)},
            state,
        )

        return {
            "draft_brief": draft_brief,
            "status": AgentStatus.SUCCESS.value,
        }
