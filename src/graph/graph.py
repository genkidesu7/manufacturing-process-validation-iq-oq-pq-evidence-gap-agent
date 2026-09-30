"""AgentCore Platform v1.0"""

# Cat 2 outer graph — MFG-C2-140 IQ/OQ/PQ Evidence Gap Agent.
#
# Outer backbone (framework-owned, fixed):
#   START -> initialize -> pre_process -> main -> {route} -> post_process -> finalize -> END
#                                             ^ (retry, max 3)
#                                          pre_process
#
# Domain complexity (Record Match -> Evidence Matrix Build -> Gap Detect ->
# Deviation Cross-Check -> Brief Draft) is encapsulated inside the `main` slot
# via EvidenceReconciliationGraphNode, which wraps the inner
# DomainWorkflowGraph (src/graph/domain_workflow_graph.py).
#
# See docs/02_design.md for the full architecture and design decision record.

from typing import Any, ClassVar

from framework.graph.agent_base_graph import AgentBaseGraph
from framework.nodes.graph_node import GraphNode
from framework.schemas.agent_state import AgentState

from src.nodes.post_process_node import PostProcessNode
from src.nodes.pre_process_node import PreProcessNode
from src.schemas.state import State


class EvidenceReconciliationGraphNode(GraphNode):
    """Wraps the inner IQ/OQ/PQ evidence-reconciliation domain workflow."""

    # "propagate" (default): a partial/incorrect evidence matrix is worse than
    # a hard failure for an advisory compliance document (docs/02_design.md
    # § Composition Pattern).
    error_strategy: ClassVar[str] = "propagate"

    # Not applicable — this agent does not use HITL (config/agent.yaml
    # hitl.enabled: false; docs/01_proposal.md HITL Gate).
    propagate_hitl: ClassVar[bool] = False

    def __init__(self) -> None:
        super().__init__()
        # Cache the inner graph instance — construction is cheap here, but
        # caching avoids rebuilding the StateGraph on every execute() call.
        from src.graph.domain_workflow_graph import DomainWorkflowGraph

        self._subgraph = DomainWorkflowGraph(config=self._parent_config())

    def get_subgraph(self) -> Any:
        return self._subgraph

    def extract_input(self, state: AgentState) -> str:
        """Serialize the parsed protocol_steps as JSON for the inner graph.

        GraphNode.execute() -> subgraph.invoke(user_input, ...) builds a brand
        new initial_state for the inner graph containing only user_input
        (BaseGraph.invoke() never copies protocol_steps or any other outer
        state field in). Since protocol_steps (not just validated_input) is
        required by every inner node, it must be smuggled through the single
        string channel available: user_input itself, JSON-encoded.
        """
        import json

        protocol_steps = state.get("protocol_steps", [])
        return json.dumps({"protocol_steps": protocol_steps})

    def merge_output(self, state: AgentState, sub_result: dict[str, Any]) -> dict[str, Any]:
        """Map inner DomainWorkflowGraph.get_output() fields back into outer state.

        Returns only the changed keys (never the full state).
        """
        return {
            "result": sub_result.get("output"),
            "status": sub_result.get("status"),
            "evidence_matrix": sub_result.get("evidence_matrix", []),
            "annotated_gap_list": sub_result.get("annotated_gap_list", []),
            "draft_brief": sub_result.get("draft_brief", ""),
        }

    def _parent_config(self) -> dict[str, Any]:
        """No config keys currently need to be forwarded to the inner graph."""
        return {}


class Graph(AgentBaseGraph):
    """Outer AgentBaseGraph for the IQ/OQ/PQ Evidence Gap Agent (MFG-C2-140)."""

    @property
    def name(self) -> str:
        return "MFG-C2-140"

    @property
    def state_schema(self) -> type:
        return State

    def register_nodes(self) -> None:
        super().register_nodes()  # injects InitializeNode + FinalizeNode

        self._nodes["pre_process"] = PreProcessNode()
        self._nodes["main"] = EvidenceReconciliationGraphNode()
        self._nodes["post_process"] = PostProcessNode()

    # add_edges() is NOT overridden — backbone wiring belongs to the framework.
