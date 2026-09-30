# PB-6: Invoke Execution Order Verification
# Verifies BaseNode.__call__() enforces: S-1 trust gate -> S-4 node_start ->
# S-2 _security_gate_input() -> execute() -> S-3 _security_gate_output() ->
# S-4 node_complete, for every concrete node under src/nodes/.
#
# MFG-C2-140 adaptation: several nodes in this agent call external services
# gated by mock_mode_enabled() (.claude/rules/implementation_rule.md Rule 2) —
# with no USE_MOCK/STG_MOCK_MODE set and no secret provider bound, those nodes
# correctly raise (MissingSecret) rather than silently
# proceeding, which is the intended behavior outside mock mode, not a PB-6
# violation. This test therefore runs with USE_MOCK=true and node-appropriate
# minimal state so every node's execute() succeeds and the full
# S-1 -> S-4 -> S-2 -> execute -> S-3 -> S-4 chain can be observed end-to-end.

import importlib
import inspect
import json
import pkgutil

import pytest

# Per-node minimal state overrides so execute() can reach a SUCCESS path.
# PB-6 verifies *invoke order*, not business-logic correctness — these are the
# smallest inputs that let each node's execute() complete without raising.
_NODE_STATE_OVERRIDES: dict[str, dict] = {
    "PreProcessNode": {
        "user_input": json.dumps(
            {
                "protocol": {"steps": [{"step_id": "IQ-01", "description": "Install pump"}]},
                "test_records": [],
                "acceptance_criteria": [],
                "deviation_log": [],
                "signatures": [],
            }
        )
    },
    "RecordMatchNode": {"protocol_steps": [{"step_id": "IQ-01", "description": "Install pump"}]},
    "EvidenceMatrixBuildNode": {
        "protocol_steps": [{"step_id": "IQ-01", "description": "Install pump", "acceptance_criteria": "spec"}],
        "matched_records": [{"step_id": "IQ-01", "source_ref": "mock://test-records/IQ-01"}],
    },
    "GapDetectNode": {
        "evidence_matrix": [
            {
                "step_id": "IQ-01",
                "evidence_refs": ["mock://test-records/IQ-01"],
                "signature_status": "signed",
                "acceptance_criteria_met": True,
            }
        ]
    },
    "DeviationCrossCheckNode": {"gap_list": []},
    "BriefDraftNode": {"evidence_matrix": [], "annotated_gap_list": []},
    "PostProcessNode": {"draft_brief": "Draft brief body."},
}


def _discover_node_classes() -> list[type]:
    """Import every module under src/nodes/ and collect concrete BaseNode subclasses."""
    from framework.nodes.base_node import BaseNode

    try:
        pkg = importlib.import_module("src.nodes")
    except ImportError:
        return []

    discovered = []
    for _, modname, _ in pkgutil.walk_packages(pkg.__path__, prefix="src.nodes."):
        module = importlib.import_module(modname)
        for attr in vars(module).values():
            if (
                isinstance(attr, type)
                and issubclass(attr, BaseNode)
                and attr is not BaseNode
                and attr.__module__ == modname
                and not inspect.isabstract(attr)
            ):
                discovered.append(attr)
    return discovered


class TestInvokeOrder:
    """PB-6: __call__ must run S-1 -> node_start -> S-2 -> execute() -> S-3 -> node_complete."""

    def test_call_order_for_every_node(self, monkeypatch):
        node_classes = _discover_node_classes()
        if not node_classes:
            pytest.skip("no concrete BaseNode subclasses found under src/nodes/")

        monkeypatch.setenv("USE_MOCK", "true")
        monkeypatch.delenv("STG_MOCK_MODE", raising=False)

        import framework.nodes.base_node as base_node_module

        failures: list[str] = []
        for node_cls in node_classes:
            order: list[str] = []
            monkeypatch.setattr(
                base_node_module,
                "emit_trace_event",
                lambda event_type, _payload, _state, _o=order: _o.append(f"event:{event_type}"),
            )

            for method_name, label in (
                ("_security_gate_input", "security_gate_input"),
                ("execute", "execute"),
                ("_security_gate_output", "security_gate_output"),
            ):
                original = getattr(node_cls, method_name)

                def spy(self, arg, _o=order, _label=label, _orig=original):
                    _o.append(_label)
                    return _orig(self, arg)

                monkeypatch.setattr(node_cls, method_name, spy)

            instance = node_cls()
            state = {
                "caller_trust_level": node_cls.required_trust_level.value,
                "correlation_id": "pb6-invoke-order-test",
                "session_id": "pb6-session",
                "thread_id": "pb6-thread",
                "trace_id": "pb6-trace",
            }
            state.update(_NODE_STATE_OVERRIDES.get(node_cls.__name__, {}))
            instance(state)

            expected = [
                "event:node_start",
                "security_gate_input",
                "execute",
                "security_gate_output",
                "event:node_complete",
            ]
            if order != expected:
                failures.append(
                    f"{node_cls.__name__}: invoke order violation.\n" f"expected: {expected}\nactual:   {order}"
                )

        assert not failures, "\n\n".join(failures)
