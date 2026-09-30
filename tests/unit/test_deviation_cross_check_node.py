from framework.schemas.agent_status import AgentStatus

from src.nodes.deviation_cross_check_node import DeviationCrossCheckNode


def _base_state(**overrides):
    state = {
        "gap_list": [],
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


class TestDeviationCrossCheckNode:
    def setup_method(self):
        self.node = DeviationCrossCheckNode()

    def test_dom10_succeeds_in_mock_mode_with_no_secret_bound(self, monkeypatch):
        monkeypatch.setenv("USE_MOCK", "true")
        monkeypatch.delenv("STG_MOCK_MODE", raising=False)
        gap_list = [{"step_id": "S1", "gap_type": "unexecuted", "description": "x"}]
        state = _base_state(gap_list=gap_list)
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS.value
        assert len(result["annotated_gap_list"]) == 1
        annotated = result["annotated_gap_list"][0]
        assert "deviation_ref" in annotated
        assert "known_deviation" in annotated
        # original gap fields preserved
        assert annotated["step_id"] == "S1"
        assert annotated["gap_type"] == "unexecuted"

    def test_empty_gap_list_returns_empty_annotated_list(self, monkeypatch):
        monkeypatch.setenv("USE_MOCK", "true")
        state = _base_state(gap_list=[])
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS.value
        assert result["annotated_gap_list"] == []
