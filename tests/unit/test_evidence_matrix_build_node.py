from framework.schemas.agent_status import AgentStatus

from src.nodes.evidence_matrix_build_node import EvidenceMatrixBuildNode


def _base_state(**overrides):
    state = {
        "protocol_steps": [],
        "matched_records": [],
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


class TestEvidenceMatrixBuildNode:
    def setup_method(self):
        self.node = EvidenceMatrixBuildNode()

    def test_succeeds_in_mock_mode_with_no_secret_bound(self, monkeypatch):
        monkeypatch.setenv("USE_MOCK", "true")
        monkeypatch.delenv("STG_MOCK_MODE", raising=False)
        protocol_steps = [{"step_id": "IQ-01", "description": "Install pump", "acceptance_criteria": "spec"}]
        matched_records = [{"step_id": "IQ-01", "source_ref": "mock://test-records/IQ-01"}]
        state = _base_state(protocol_steps=protocol_steps, matched_records=matched_records)
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS.value
        assert len(result["evidence_matrix"]) == 1
        assert result["evidence_matrix"][0]["signature_status"] == "signed"

    def test_dom08_flags_unknown_acceptance_criteria_not_omitted(self, monkeypatch):
        monkeypatch.setenv("USE_MOCK", "true")
        protocol_steps = [{"step_id": "IQ-02", "description": "Unknown step", "acceptance_criteria": None}]
        matched_records = [{"step_id": "IQ-02", "source_ref": "mock://test-records/IQ-02"}]
        state = _base_state(protocol_steps=protocol_steps, matched_records=matched_records)
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS.value
        row = result["evidence_matrix"][0]
        assert row["step_id"] == "IQ-02"
        assert row["acceptance_criteria_met"] == "unknown"

    def test_unexecuted_step_flagged_false(self, monkeypatch):
        monkeypatch.setenv("USE_MOCK", "true")
        protocol_steps = [{"step_id": "IQ-03", "description": "No records", "acceptance_criteria": "spec"}]
        state = _base_state(protocol_steps=protocol_steps, matched_records=[])
        result = self.node.execute(state)
        row = result["evidence_matrix"][0]
        assert row["acceptance_criteria_met"] is False
        assert row["signature_status"] == "unsigned"

    def test_errors_when_protocol_steps_missing(self, monkeypatch):
        monkeypatch.setenv("USE_MOCK", "true")
        state = _base_state(protocol_steps=[])
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.ERROR.value
