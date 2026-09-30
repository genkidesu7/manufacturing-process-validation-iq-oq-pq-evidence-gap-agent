import json

from framework.schemas.agent_status import AgentStatus

from src.nodes.pre_process_node import PreProcessNode


def _base_state(**overrides):
    state = {
        "user_input": "",
        "input_context": {},
        "caller_trust_level": "ANONYMOUS",
        "correlation_id": "c1",
        "session_id": "s1",
        "thread_id": "t1",
        "trace_id": "tr1",
        "node_history": [],
        "error_log": [],
    }
    state.update(overrides)
    return state


VALID_PACKAGE = {
    "protocol": {
        "steps": [
            {
                "step_id": "IQ-01",
                "description": "Install pump",
                "acceptance_criteria": "Pump installed per spec",
                "required_signature_roles": ["engineer"],
            }
        ]
    },
    "test_records": [],
    "acceptance_criteria": [],
    "deviation_log": [],
    "signatures": [],
}


class TestPreProcessNode:
    def setup_method(self):
        self.node = PreProcessNode()

    def test_dom04_parses_valid_package_into_protocol_steps(self):
        state = _base_state(user_input=json.dumps(VALID_PACKAGE))
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS.value
        assert result["protocol_steps"] == [
            {
                "step_id": "IQ-01",
                "description": "Install pump",
                "acceptance_criteria": "Pump installed per spec",
                "required_signature_roles": ["engineer"],
            }
        ]
        assert result["validated_input"] == json.dumps(VALID_PACKAGE)

    def test_dom05_rejects_empty_input(self):
        state = _base_state(user_input="")
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.ERROR.value
        assert result["error_log"]

    def test_dom05_rejects_non_json_input(self):
        state = _base_state(user_input="not json{{{")
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.ERROR.value
        assert "not valid JSON" in result["error_log"][0]

    def test_dom05_rejects_non_object_json(self):
        state = _base_state(user_input=json.dumps([1, 2, 3]))
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.ERROR.value
        assert "JSON object" in result["error_log"][0]

    def test_dom05_rejects_zero_step_package(self):
        empty_package = {**VALID_PACKAGE, "protocol": {"steps": []}}
        state = _base_state(user_input=json.dumps(empty_package))
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.ERROR.value

    def test_tc02_security_violation_status_on_invalid_input(self):
        """TC-02: invalid input surfaces as an ERROR status (SecurityViolationError-equivalent
        rejection path), not a silent success."""
        state = _base_state(user_input="{}")
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.ERROR.value

    def test_dom06_extra_security_gate_input_rejects_zero_steps(self):
        state = _base_state(user_input=json.dumps({"protocol": {"steps": []}}))
        gated_state = self.node._extra_security_gate_input(state)
        assert gated_state["status"] == AgentStatus.ERROR.value
        assert gated_state is not None  # must return state, never None

    def test_extra_security_gate_input_passes_through_valid_package(self):
        state = _base_state(user_input=json.dumps(VALID_PACKAGE))
        gated_state = self.node._extra_security_gate_input(state)
        assert gated_state.get("status") != AgentStatus.ERROR.value

    def test_full_call_via_dunder_call_sets_node_history(self):
        """Exercises __call__() (S-1/S-2/S-3/S-4 pipeline), not just execute()."""
        state = _base_state(user_input=json.dumps(VALID_PACKAGE))
        result = self.node(state)
        assert result["status"] == AgentStatus.SUCCESS.value
        assert "PreProcessNode" in result["node_history"]
