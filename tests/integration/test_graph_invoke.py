# INT-01/02/03: real .compile() + .invoke() path for both the outer Graph and
# the inner DomainWorkflowGraph, in mock mode. Per sdk-expertise's guidance:
# a unit test that stubs state directly bypasses LangGraph's schema
# projection and can pass while the compiled graph is actually broken (this
# caught the protocol_steps-not-carried-into-inner-graph bug during
# implementation — see docs/implement_tasks.md Task 8 decision log).

import json

import pytest

from framework.secrets.context import bound_secrets
from shared.secrets.inmemory_provider import InMemoryProvider

from src.graph.domain_workflow_graph import DomainWorkflowGraph
from src.graph.graph import Graph

VALID_PACKAGE = {
    "protocol": {
        "steps": [
            {
                "step_id": "IQ-01",
                "description": "Install pump",
                "acceptance_criteria": "Pump installed per spec",
                "required_signature_roles": ["engineer"],
            },
            {
                "step_id": "OQ-01",
                "description": "Verify pump operation",
                "acceptance_criteria": "Pump runs at spec flow rate",
                "required_signature_roles": ["qa"],
            },
        ]
    },
    "test_records": [],
    "acceptance_criteria": [],
    "deviation_log": [],
    "signatures": [],
}


@pytest.fixture(autouse=True)
def _mock_mode(monkeypatch):
    monkeypatch.setenv("USE_MOCK", "true")
    monkeypatch.delenv("STG_MOCK_MODE", raising=False)


class TestOuterGraphInvoke:
    def test_int01_full_invoke_success_in_mock_mode(self):
        agent = Graph(config={"max_retry": 1})
        agent.compile()
        provider = InMemoryProvider({})
        agent.provision_secrets(provider)

        with bound_secrets(provider):
            result = agent.invoke(json.dumps(VALID_PACKAGE))

        assert result["status"] == "success"
        assert result["output"]
        assert "ADVISORY OUTPUT ONLY" in result["output"]
        assert result["node_history"] == [
            "InitializeNode",
            "PreProcessNode",
            "EvidenceReconciliationGraphNode",
            "PostProcessNode",
            "FinalizeNode",
        ]

    def test_int03_structural_rejection_does_not_crash_the_compiled_graph(self):
        agent = Graph(config={"max_retry": 1})
        agent.compile()
        provider = InMemoryProvider({})
        agent.provision_secrets(provider)

        with bound_secrets(provider):
            result = agent.invoke(json.dumps({"protocol": {"steps": []}}))

        # AgentBaseGraph.get_output() surfaces output/status/trace_id/
        # correlation_id/node_history only — error_log lives on the internal
        # state, not the shaped output dict. The contract this asserts is:
        # the compiled graph terminates cleanly with status: error instead of
        # raising/crashing.
        assert result["status"] == "error"
        assert result["output"] is None
        assert result["node_history"] == [
            "InitializeNode",
            "PreProcessNode",
            "EvidenceReconciliationGraphNode",
            "FinalizeNode",
        ]


class TestInnerGraphInvoke:
    def test_int02_full_invoke_success_in_mock_mode(self):
        inner = DomainWorkflowGraph()
        inner.compile()
        provider = InMemoryProvider({})
        inner.provision_secrets(provider)

        encoded_input = json.dumps({"protocol_steps": VALID_PACKAGE["protocol"]["steps"]})

        with bound_secrets(provider):
            result = inner.invoke(encoded_input)

        assert result["status"] == "success"
        assert result["output"]
        assert "MOCK REVIEWER BRIEF" in result["output"]
