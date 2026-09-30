"""AgentCore Platform v1.0"""

# Inner graph for the Cat 2 IQ/OQ/PQ evidence-reconciliation domain workflow.
# Instantiated by EvidenceReconciliationGraphNode.get_subgraph() in graph.py.
# Only accepted path for a Cat 2 inner graph: src/graph/domain_workflow_graph.py.

from typing import Any

from langgraph.graph import END, START

from framework.graph.base_graph import BaseGraph
from framework.schemas.agent_status import AgentStatus

from src.nodes.brief_draft_node import BriefDraftNode
from src.nodes.deviation_cross_check_node import DeviationCrossCheckNode
from src.nodes.evidence_matrix_build_node import EvidenceMatrixBuildNode
from src.nodes.gap_detect_node import GapDetectNode
from src.nodes.record_match_node import RecordMatchNode
from src.schemas.state import State


class DomainWorkflowGraph(BaseGraph):
    """Inner graph for the IQ/OQ/PQ evidence-reconciliation domain workflow.

    Linear topology (docs/02_design.md § Data Flow):
        START -> record_match -> evidence_matrix_build -> gap_detect
              -> deviation_cross_check -> brief_draft -> END
    """

    @property
    def name(self) -> str:
        return "mfg_c2_140_evidence_reconciliation_workflow"

    @property
    def state_schema(self) -> type:
        return State

    def _validate_config(self) -> None:
        """No mandatory config for this inner graph."""
        pass

    def register_nodes(self) -> None:
        """No super() call — BaseGraph.register_nodes() is abstract.

        Does not register initialize/finalize — those are outer-graph concerns.
        """
        self._nodes["record_match"] = RecordMatchNode()
        self._nodes["evidence_matrix_build"] = EvidenceMatrixBuildNode()
        self._nodes["gap_detect"] = GapDetectNode()
        self._nodes["deviation_cross_check"] = DeviationCrossCheckNode()
        self._nodes["brief_draft"] = BriefDraftNode()

    def add_edges(self) -> None:
        """Linear topology — every node reachable from START."""
        self._sg.add_edge(START, "record_match")
        self._sg.add_edge("record_match", "evidence_matrix_build")
        self._sg.add_edge("evidence_matrix_build", "gap_detect")
        self._sg.add_edge("gap_detect", "deviation_cross_check")
        self._sg.add_edge("deviation_cross_check", "brief_draft")
        self._sg.add_edge("brief_draft", END)

    def route(self, state: State) -> str:
        """Required by BaseGraph ABC; not referenced (linear topology only).

        Annotated with the concrete State subclass, not AgentState — LangGraph
        infers the input schema from this annotation (sdk-expertise warning).
        """
        return END if state.get("status") == AgentStatus.ERROR.value else "brief_draft"

    def get_output(self, state: State) -> dict[str, Any]:
        """Shape the sub_result dict returned to the outer merge_output().

        Annotated with the concrete State subclass, not AgentState (see route()).
        """
        return {
            "output": state.get("draft_brief") or state.get("result"),
            "status": state.get("status"),
            "trace_id": state.get("trace_id"),
            "correlation_id": state.get("correlation_id"),
            "node_history": state.get("node_history", []),
            "evidence_matrix": state.get("evidence_matrix", []),
            "annotated_gap_list": state.get("annotated_gap_list", []),
            "draft_brief": state.get("draft_brief", ""),
        }
