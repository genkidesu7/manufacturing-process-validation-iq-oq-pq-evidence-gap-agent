import pytest

from framework.schemas.agent_status import AgentStatus
from framework.secrets import MissingSecret, bound_secrets
from shared.secrets import InMemoryProvider

from src.nodes.brief_draft_node import BriefDraftNode


def _base_state(**overrides):
    state = {
        "evidence_matrix": [],
        "annotated_gap_list": [],
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


class TestBriefDraftNode:
    def setup_method(self):
        self.node = BriefDraftNode()

    def test_dom11_succeeds_in_mock_mode_with_no_secret_bound(self, monkeypatch):
        monkeypatch.setenv("USE_MOCK", "true")
        monkeypatch.delenv("STG_MOCK_MODE", raising=False)
        state = _base_state(
            evidence_matrix=[{"step_id": "S1"}],
            annotated_gap_list=[{"step_id": "S1", "gap_type": "unsigned"}],
        )
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS.value
        assert result["draft_brief"]
        assert "MOCK REVIEWER BRIEF" in result["draft_brief"]

    def test_dom11_real_path_requires_azure_secrets_when_no_mock_alias_set(self, monkeypatch):
        """Outside mock mode (every alias cleared) a missing Azure OpenAI secret must
        fail fast with MissingSecret — never proceed with a placeholder credential."""
        monkeypatch.delenv("USE_MOCK", raising=False)
        monkeypatch.delenv("STG_MOCK_MODE", raising=False)
        with bound_secrets(InMemoryProvider({})):
            with pytest.raises(MissingSecret):
                self.node.execute(_base_state())

    def test_dom11_real_path_drafts_brief_through_azure_openai_client(self, monkeypatch):
        monkeypatch.delenv("USE_MOCK", raising=False)
        monkeypatch.delenv("STG_MOCK_MODE", raising=False)
        captured: dict = {}

        class FakeAzureClient:
            def __init__(self, config):
                captured["config"] = config

            def complete(self, messages):
                captured["messages"] = messages
                return {"content": "LLM drafted brief"}

        monkeypatch.setattr("shared.services.llm.azure_openai_client.AzureOpenAIClient", FakeAzureClient)
        secrets = InMemoryProvider(
            {
                "AZURE_OPENAI_API_KEY": "key",
                "AZURE_OPENAI_ENDPOINT": "https://example.services.ai.azure.com",
                "AZURE_OPENAI_DEPLOYMENT": "dep",
            }
        )
        state = _base_state(
            evidence_matrix=[{"step_id": "S1"}],
            annotated_gap_list=[{"step_id": "S1", "gap_type": "unsigned"}],
        )
        with bound_secrets(secrets):
            result = self.node.execute(state)

        assert result["status"] == AgentStatus.SUCCESS.value
        assert result["draft_brief"] == "LLM drafted brief"
        assert captured["config"]["azure_deployment"] == "dep"
        assert "S1" in captured["messages"][1]["content"]
