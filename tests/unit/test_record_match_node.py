import json


from framework.schemas.agent_status import AgentStatus

from src.nodes.record_match_node import RecordMatchNode

PROTOCOL_STEPS = [{"step_id": "IQ-01", "description": "Install pump"}]


def _base_state(**overrides):
    state = {
        "user_input": "",
        "protocol_steps": [],
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


class TestRecordMatchNode:
    def setup_method(self):
        self.node = RecordMatchNode()

    def test_dom07_succeeds_in_mock_mode_with_no_secret_bound(self, monkeypatch):
        """Regression test (.claude/rules/test_rule.md Rule 2): mock mode must
        not depend on a secret being resolvable. No bound_secrets() context at
        all — current_secrets() falls back to NullProvider."""
        monkeypatch.setenv("USE_MOCK", "true")
        monkeypatch.delenv("STG_MOCK_MODE", raising=False)
        state = _base_state(protocol_steps=PROTOCOL_STEPS)
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS.value
        assert len(result["matched_records"]) == 1
        assert result["matched_records"][0]["step_id"] == "IQ-01"

    def test_errors_when_protocol_steps_missing(self, monkeypatch):
        monkeypatch.setenv("USE_MOCK", "true")
        state = _base_state(protocol_steps=[])
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.ERROR.value

    def test_decodes_protocol_steps_from_user_input_when_absent_from_state(self, monkeypatch):
        """Inner-graph caveat: protocol_steps is bridged via the JSON-encoded
        user_input the outer GraphNode.extract_input() produces."""
        monkeypatch.setenv("USE_MOCK", "true")
        state = _base_state(
            protocol_steps=[],
            user_input=json.dumps({"protocol_steps": PROTOCOL_STEPS}),
        )
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS.value
        assert result["protocol_steps"] == PROTOCOL_STEPS

    def test_tc04_connector_is_stub_backed_and_needs_no_credential_outside_mock_mode(self, monkeypatch):
        """Only the LLM call is real; the record-match connector serves stub data and
        must not demand a credential (no VECTOR_DB_API_KEY) with every mock alias cleared."""
        monkeypatch.delenv("USE_MOCK", raising=False)
        monkeypatch.delenv("STG_MOCK_MODE", raising=False)
        state = _base_state(protocol_steps=PROTOCOL_STEPS)
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS.value
        assert result["matched_records"]
