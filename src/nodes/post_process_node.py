"""AgentCore Platform v1.0"""

from __future__ import annotations

import re
from typing import Any

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.services.events import emitter
from shared.services.events.types import EventType
from shared.utils.audit_logger import emit_trace_event

# Mandatory disclaimer (mitigates proposal Risk #1: a gap brief being misread
# as an approval/certification decision). Code-enforced, not optional LLM prose.
DISCLAIMER = (
    "\n\n---\nADVISORY OUTPUT ONLY: This evidence matrix and gap brief is advisory "
    "and does not constitute a release, certification, or production-change approval. "
    "A qualified QA/validation reviewer must review and approve before any such "
    "decision is made."
)

# Confidential-content patterns that must never survive into the final output —
# raw source excerpts / record summaries beyond the aggregated brief text.
_RAW_RECORD_EXCERPT_PATTERN = re.compile(r"mock://test-records/\S+")


def _strip_confidential_content(text: str) -> str:
    """Strip raw record source references that should not leak into the final brief."""
    return _RAW_RECORD_EXCERPT_PATTERN.sub("[SOURCE_REF_REDACTED]", text)


class PostProcessNode(FunctionNode):
    """Output Validate (S-3) — strip confidential content, enforce the reviewer disclaimer."""

    # S-1: explicit by design, not inherited implicitly.
    # Raise to VERIFIED_EXTERNAL/INTERNAL only if this node performs a
    # privileged operation.
    required_trust_level = TrustLevel.ANONYMOUS

    def _extra_security_gate_output(self, result: dict[str, Any]) -> dict[str, Any]:
        """S-3 domain extension: re-append the disclaimer if execute() ever dropped it.

        Runs after the default credential scan. Contract: must return result.
        This is a defense-in-depth backstop — execute() already appends the
        disclaimer — so the disclaimer can never silently go missing even if
        a future change to execute() has a defect.
        """
        output = result.get("formatted_output")
        if isinstance(output, str) and output and DISCLAIMER.strip() not in output:
            result["formatted_output"] = output + DISCLAIMER
        return result

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        emitter().emit_event(
            event_type=EventType.PROGRESS_UPDATE,
            message="Validating output and appending reviewer disclaimer...",
            metadata={"stage": "post_process"},
        )
        draft_brief = state.get("draft_brief") or state.get("result") or ""

        if not draft_brief:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["PostProcessNode: no draft brief available to finalize"],
            }

        sanitized = _strip_confidential_content(draft_brief)
        formatted_output = sanitized + DISCLAIMER

        emit_trace_event(
            "output_validated",
            {"output_length": len(formatted_output)},
            state,
        )

        return {
            "formatted_output": formatted_output,
            "status": AgentStatus.SUCCESS.value,
        }
