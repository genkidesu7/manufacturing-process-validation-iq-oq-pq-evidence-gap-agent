"""AgentCore Platform v1.0"""

# Stub data for the non-LLM connectors (test-record matching, protocol KB,
# deviation log) and for the LLM mock path (USE_MOCK / STG_MOCK_MODE). These
# functions never touch a credential, so mock mode short-circuits BEFORE any
# ctx.secrets.require(...) call (.claude/rules/implementation_rule.md Rule 2).

from __future__ import annotations

from typing import Any


async def stub_matched_records(protocol_steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stub RAG record-matching: one plausible matched record per protocol step."""
    return [
        {
            "step_id": step.get("step_id", f"STEP-{i}"),
            "record_id": f"MOCK-REC-{i}",
            "record_summary": "Mock executed test record summary.",
            "source_ref": f"mock://test-records/{step.get('step_id', f'STEP-{i}')}",
            "match_confidence": 0.92,
        }
        for i, step in enumerate(protocol_steps, start=1)
    ]


async def stub_evidence_matrix_row(step: dict[str, Any], matched: list[dict[str, Any]]) -> dict[str, Any]:
    """Stub evidence-matrix row construction for a single protocol step."""
    step_id = step.get("step_id", "UNKNOWN")
    records_for_step = [r for r in matched if r.get("step_id") == step_id]
    acceptance_criteria = step.get("acceptance_criteria")
    if not records_for_step:
        acceptance_criteria_met: Any = False
    elif not acceptance_criteria:
        acceptance_criteria_met = "unknown"
    else:
        acceptance_criteria_met = True
    return {
        "step_id": step_id,
        "requirement": step.get("description", ""),
        "evidence_refs": [r.get("source_ref", "") for r in records_for_step],
        "acceptance_criteria_met": acceptance_criteria_met,
        "signature_status": "signed" if records_for_step else "unsigned",
    }


async def stub_deviation_lookup(step_id: str) -> dict[str, Any]:
    """Stub deviation-log lookup: no known open deviation for mock mode."""
    return {"deviation_ref": None, "known_deviation": False}


async def stub_brief_draft(evidence_matrix: list[dict[str, Any]], annotated_gap_list: list[dict[str, Any]]) -> str:
    """Stub LLM-drafted reviewer brief."""
    gap_count = len(annotated_gap_list)
    return (
        "MOCK REVIEWER BRIEF\n"
        f"Evidence matrix rows reconciled: {len(evidence_matrix)}\n"
        f"Gaps detected: {gap_count}\n"
        "This is a mock-mode draft brief generated with stub data for testing."
    )
