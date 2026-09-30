import json

from src.graph.graph import EvidenceReconciliationGraphNode


def _base_state(**overrides):
    state = {
        "validated_input": "",
        "user_input": "",
        "protocol_steps": [],
        "caller_trust_level": "ANONYMOUS",
        "correlation_id": "c1",
        "session_id": "s1",
        "thread_id": "t1",
        "trace_id": "tr1",
        "node_history": [],
        "error_log": [],
        "hitl_allowed": True,
    }
    state.update(overrides)
    return state


class TestEvidenceReconciliationGraphNode:
    def setup_method(self):
        self.node = EvidenceReconciliationGraphNode()

    def test_dom13_extract_input_json_encodes_protocol_steps(self):
        protocol_steps = [{"step_id": "IQ-01", "description": "Install pump"}]
        state = _base_state(protocol_steps=protocol_steps)
        encoded = self.node.extract_input(state)
        decoded = json.loads(encoded)
        assert decoded["protocol_steps"] == protocol_steps

    def test_extract_input_handles_empty_protocol_steps(self):
        state = _base_state(protocol_steps=[])
        encoded = self.node.extract_input(state)
        decoded = json.loads(encoded)
        assert decoded["protocol_steps"] == []

    def test_dom14_merge_output_maps_sub_result_fields(self):
        state = _base_state()
        sub_result = {
            "output": "final brief text",
            "status": "success",
            "evidence_matrix": [{"step_id": "IQ-01"}],
            "annotated_gap_list": [{"step_id": "IQ-01", "gap_type": "unsigned"}],
            "draft_brief": "draft text",
        }
        merged = self.node.merge_output(state, sub_result)
        assert merged == {
            "result": "final brief text",
            "status": "success",
            "evidence_matrix": [{"step_id": "IQ-01"}],
            "annotated_gap_list": [{"step_id": "IQ-01", "gap_type": "unsigned"}],
            "draft_brief": "draft text",
        }

    def test_merge_output_defaults_missing_fields(self):
        state = _base_state()
        merged = self.node.merge_output(state, {})
        assert merged["result"] is None
        assert merged["status"] is None
        assert merged["evidence_matrix"] == []
        assert merged["annotated_gap_list"] == []
        assert merged["draft_brief"] == ""

    def test_error_strategy_is_propagate(self):
        assert self.node.error_strategy == "propagate"

    def test_propagate_hitl_is_false(self):
        assert self.node.propagate_hitl is False

    def test_get_subgraph_returns_domain_workflow_graph(self):
        from src.graph.domain_workflow_graph import DomainWorkflowGraph

        assert isinstance(self.node.get_subgraph(), DomainWorkflowGraph)
