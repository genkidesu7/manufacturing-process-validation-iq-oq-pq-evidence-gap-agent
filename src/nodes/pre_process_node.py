"""AgentCore Platform v1.0"""

# Node contract (agents_layer_design.md §1):
#  - Extend FunctionNode; implement execute(state) -> dict[str, Any]
#  - Return ONLY the fields this node changes (never full state)
#  - Return AgentStatus.<X>.value strings for status assignments [A1]
#  - Read input_context via state.get("input_context", {}) — read-only [C1]
#  - Never import from mediator/, api/, or other agents

from __future__ import annotations

import json
from typing import Any

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.services.events import emitter
from shared.services.events.types import EventType
from shared.utils.audit_logger import emit_trace_event

_REQUIRED_PACKAGE_KEYS = (
    "protocol",
    "test_records",
    "acceptance_criteria",
    "deviation_log",
    "signatures",
)


def _parse_protocol_steps(package: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract structured protocol steps from the submitted evidence package."""
    protocol = package.get("protocol") or {}
    raw_steps = protocol.get("steps", []) if isinstance(protocol, dict) else []
    steps: list[dict[str, Any]] = []
    for i, raw in enumerate(raw_steps, start=1):
        if not isinstance(raw, dict):
            continue
        steps.append(
            {
                "step_id": raw.get("step_id", f"STEP-{i}"),
                "description": raw.get("description", ""),
                "acceptance_criteria": raw.get("acceptance_criteria"),
                "required_signature_roles": raw.get("required_signature_roles", []),
            }
        )
    return steps


class PreProcessNode(FunctionNode):
    """Protocol Ingest — parse and validate the submitted IQ/OQ/PQ evidence package."""

    # S-1: explicit by design, not inherited implicitly.
    # Raise to VERIFIED_EXTERNAL/INTERNAL only if this node performs a
    # privileged operation.
    required_trust_level = TrustLevel.ANONYMOUS

    def _extra_security_gate_input(self, state: dict[str, Any]) -> dict[str, Any]:
        """S-2 domain extension: reject a package with zero parsed protocol steps.

        Runs after the default PII scan. Contract: must return state; may set
        status=ERROR + error_log to reject (must not raise for this check —
        raising is reserved for structural/security violations, not "no
        steps parsed", which is a normal validation outcome surfaced to the
        caller via error_log).
        """
        user_input = state.get("user_input", "")
        try:
            package = json.loads(user_input) if user_input else {}
        except (json.JSONDecodeError, TypeError):
            package = {}
        protocol_steps = _parse_protocol_steps(package) if isinstance(package, dict) else []
        if not protocol_steps:
            state = dict(state)
            state["status"] = AgentStatus.ERROR.value
            state["error_log"] = state.get("error_log", []) + [
                "PreProcessNode: evidence package has zero parseable protocol steps"
            ]
        return state

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        emitter().emit_event(
            event_type=EventType.PROGRESS_UPDATE,
            message="Parsing and validating the IQ/OQ/PQ evidence package...",
            metadata={"stage": "pre_process"},
        )
        user_input = state.get("user_input", "")
        input_context = state.get("input_context", {})  # read-only [C1]

        if not user_input or not user_input.strip():
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["PreProcessNode: user_input is empty or missing"],
            }

        try:
            package = json.loads(user_input)
        except (json.JSONDecodeError, TypeError) as exc:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": [f"PreProcessNode: user_input is not valid JSON ({exc})"],
            }

        if not isinstance(package, dict):
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["PreProcessNode: evidence package must be a JSON object"],
            }

        missing_keys = [key for key in _REQUIRED_PACKAGE_KEYS if key not in package]
        protocol_steps = _parse_protocol_steps(package)

        if not protocol_steps:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["PreProcessNode: no protocol steps could be parsed from the evidence package"],
            }

        emit_trace_event(
            "protocol_ingested",
            {"protocol_step_count": len(protocol_steps), "missing_package_keys": missing_keys},
            state,
        )

        return {
            "validated_input": user_input.strip(),
            "protocol_steps": protocol_steps,
            "enriched_context": {
                "source": "mfg-c2-140",
                "channel": input_context.get("channel", "unknown"),
                "missing_package_keys": missing_keys,
            },
            "status": AgentStatus.SUCCESS.value,
        }
