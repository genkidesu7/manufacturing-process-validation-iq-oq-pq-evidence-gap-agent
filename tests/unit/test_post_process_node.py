from framework.schemas.agent_status import AgentStatus

from src.nodes.post_process_node import DISCLAIMER, PostProcessNode


def _base_state(**overrides):
    state = {
        "draft_brief": "Draft brief body.",
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


class TestPostProcessNode:
    def setup_method(self):
        self.node = PostProcessNode()

    def test_dom12_appends_disclaimer(self):
        state = _base_state(draft_brief="Some brief text.")
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS.value
        assert DISCLAIMER.strip() in result["formatted_output"]
        assert "Some brief text." in result["formatted_output"]

    def test_dom12_strips_raw_source_refs(self):
        state = _base_state(draft_brief="See mock://test-records/IQ-01 for evidence.")
        result = self.node.execute(state)
        assert "mock://test-records/IQ-01" not in result["formatted_output"]
        assert "[SOURCE_REF_REDACTED]" in result["formatted_output"]

    def test_errors_when_no_draft_brief_available(self):
        state = _base_state(draft_brief="", result=None)
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.ERROR.value

    def test_tc10_extra_security_gate_output_reappends_missing_disclaimer(self):
        """TC-10: domain S-3 extension is non-trivial — backstops a defect that
        dropped the disclaimer from formatted_output."""
        result = {"formatted_output": "Brief with no disclaimer somehow."}
        gated = self.node._extra_security_gate_output(result)
        assert DISCLAIMER.strip() in gated["formatted_output"]

    def test_extra_security_gate_output_is_noop_when_disclaimer_present(self):
        text = "Brief text." + DISCLAIMER
        result = {"formatted_output": text}
        gated = self.node._extra_security_gate_output(result)
        assert gated["formatted_output"] == text

    def test_full_call_via_dunder_call(self):
        state = _base_state(draft_brief="Body text.")
        result = self.node(state)
        assert result["status"] == AgentStatus.SUCCESS.value
        assert DISCLAIMER.strip() in result["formatted_output"]
        assert "PostProcessNode" in result["node_history"]
