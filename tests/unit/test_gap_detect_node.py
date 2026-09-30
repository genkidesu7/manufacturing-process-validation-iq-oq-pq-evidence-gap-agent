from framework.schemas.agent_status import AgentStatus

from src.nodes.gap_detect_node import GapDetectNode


def _base_state(**overrides):
    state = {
        "evidence_matrix": [],
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


class TestGapDetectNode:
    def setup_method(self):
        self.node = GapDetectNode()

    def test_dom09_classifies_unexecuted(self):
        state = _base_state(
            evidence_matrix=[
                {"step_id": "S1", "evidence_refs": [], "signature_status": "unsigned", "acceptance_criteria_met": False}
            ]
        )
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS.value
        assert result["gap_list"][0]["gap_type"] == "unexecuted"

    def test_dom09_classifies_unsigned(self):
        state = _base_state(
            evidence_matrix=[
                {
                    "step_id": "S2",
                    "evidence_refs": ["ref1"],
                    "signature_status": "unsigned",
                    "acceptance_criteria_met": True,
                }
            ]
        )
        result = self.node.execute(state)
        assert result["gap_list"][0]["gap_type"] == "unsigned"

    def test_dom09_classifies_missing_criteria(self):
        state = _base_state(
            evidence_matrix=[
                {
                    "step_id": "S3",
                    "evidence_refs": ["ref1"],
                    "signature_status": "signed",
                    "acceptance_criteria_met": "unknown",
                }
            ]
        )
        result = self.node.execute(state)
        assert result["gap_list"][0]["gap_type"] == "missing_criteria"

    def test_dom09_classifies_contradictory(self):
        state = _base_state(
            evidence_matrix=[
                {
                    "step_id": "S4",
                    "evidence_refs": ["ref1"],
                    "signature_status": "signed",
                    "acceptance_criteria_met": False,
                }
            ]
        )
        result = self.node.execute(state)
        assert result["gap_list"][0]["gap_type"] == "contradictory"

    def test_no_gap_row_omitted_when_step_fully_compliant(self):
        state = _base_state(
            evidence_matrix=[
                {
                    "step_id": "S5",
                    "evidence_refs": ["ref1"],
                    "signature_status": "signed",
                    "acceptance_criteria_met": True,
                }
            ]
        )
        result = self.node.execute(state)
        assert result["gap_list"] == []

    def test_errors_when_evidence_matrix_missing(self):
        state = _base_state(evidence_matrix=[])
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.ERROR.value
