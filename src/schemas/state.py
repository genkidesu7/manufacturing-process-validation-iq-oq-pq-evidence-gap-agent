"""AgentCore Platform v1.0"""

# ADR-005: State must be a flat TypedDict (see ADR-005 for the prohibited
# alternatives). LangGraph checkpoints use msgpack serialization, so only
# plain serializable fields are allowed. Do NOT add credentials or secrets.

from typing import Any

from framework.schemas.agent_state import AgentState


class State(AgentState):
    """Agent state for the IQ/OQ/PQ Evidence Gap Agent (MFG-C2-140).

    All shared fields (user_input, status, session_id, node_history,
    error_log, hitl_*, etc.) are inherited from AgentState.

    Domain fields (see docs/02_design.md § State Definition):
      - protocol_steps: parsed IQ/OQ/PQ protocol steps (set by pre_process /
        PreProcessNode). Each item: {step_id, description,
        acceptance_criteria, required_signature_roles}.
      - matched_records: executed test records matched to protocol steps
        (set by the inner record_match node). Each item: {step_id,
        record_id, record_summary, source_ref, match_confidence}.
      - evidence_matrix: requirement-to-evidence traceability rows (set by
        the inner evidence_matrix_build node). Each item: {step_id,
        requirement, evidence_refs, acceptance_criteria_met,
        signature_status}.
      - gap_list: detected gaps (set by the inner gap_detect node). Each
        item: {step_id, gap_type, description} where gap_type is one of
        "unexecuted" | "unsigned" | "missing_criteria" | "contradictory".
      - annotated_gap_list: gap_list rows annotated against the deviation
        log (set by the inner deviation_cross_check node). Each item adds
        {deviation_ref: str | None, known_deviation: bool}.
      - draft_brief: drafted reviewer-ready gap/remediation brief text,
        pre output-validation (set by the inner brief_draft node).
    """

    protocol_steps: list[dict[str, Any]]
    matched_records: list[dict[str, Any]]
    evidence_matrix: list[dict[str, Any]]
    gap_list: list[dict[str, Any]]
    annotated_gap_list: list[dict[str, Any]]
    draft_brief: str
