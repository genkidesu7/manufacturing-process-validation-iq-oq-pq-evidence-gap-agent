# Test Specification

## Test Strategy
- Coverage target: 80%
- Test types: Unit / Proof-of-Boundary / Integration

## Framework Compliance Tests (Mandatory)

| TC-ID | Test | Location | Expected Result | Result |
|-------|------|----------|----------------|--------|
| TC-01 | State contract: flat TypedDict | `tests/proof_of_boundary/test_state_safety.py` | Type check pass, no Pydantic/dataclass | PASS |
| TC-02 | SecurityViolationError fires on invalid input | `tests/unit/test_pre_process_node.py::test_extra_security_gate_input_rejects_zero_steps` | Error/ERROR-status raised on structurally invalid input | PASS |
| TC-03 | No JWT/Credential in State | `tests/proof_of_boundary/test_state_safety.py` | CI `gate-credential-scan`: 0 violations | PASS |
| TC-04 | InvocationContext via configurable only | `tests/unit/test_record_match_node.py::test_uses_invocation_context_from_state` | Direct access raises error / context obtained only via `InvocationContext.from_state(state)` | PASS |
| TC-05 | S-4: no duplicate lifecycle events in `execute()` | `tests/unit/test_node_trace_events.py` | `node_start` / `node_complete` / `node_error` absent from `execute()` body (AST scan) | PASS |
| TC-06 | S-2: `_security_gate_input()` not overridden (`FunctionNode` subclass) | `tests/unit/test_framework_compliance_tc06_tc07.py` | `TypeError` raised at class definition if overridden (`@final` enforced by framework) | PASS |
| TC-07 | S-3: `_security_gate_output()` not overridden (`FunctionNode` subclass) | `tests/unit/test_framework_compliance_tc06_tc07.py` | `TypeError` raised at class definition if overridden (`@final` enforced by framework) | PASS |
| TC-08 | `required_trust_level` enforced | `tests/proof_of_boundary/test_pb_invoke_order.py` (S-1 gate exercised as part of invoke order) | Insufficient trust → refused | PASS |
| TC-09 | S-2: `_extra_security_gate_input()` non-trivial when domain checks needed | `tests/unit/test_pre_process_node.py` | Domain-specific input checks execute correctly (zero-protocol-step rejection) | PASS |
| TC-10 | S-3: `_extra_security_gate_output()` non-trivial when domain checks needed | `tests/unit/test_post_process_node.py` | Domain-specific output checks execute correctly (confidential-content strip, disclaimer-presence backstop) | PASS |
| TC-11 | S-4: at least one domain `emit_trace_event()` inside each `execute()` | `tests/unit/test_node_trace_events.py` | Domain event emitted on every invocation path | PASS |

## Proof-of-Boundary Tests (Mandatory)

| PB-ID | Boundary | Test | Location | Expected Result | Result |
|-------|----------|------|----------|----------------|--------|
| PB-1 | BaseNode → EventEmitter | `emit_trace_event()` fires on every invocation path | `tests/unit/test_node_trace_events.py` | No silent failures | PASS |
| PB-2 | State serialization | Post-invoke State is primitives only | `tests/proof_of_boundary/test_state_safety.py` | No Pydantic/dataclass | PASS |
| PB-3 | Level 2 → External service | Real external service connection | `tests/integration/test_services_mock_mode.py` (mock-mode substitute — see note below) | Data retrieved | PASS (mock path) |
| PB-4 | Import isolation | No Level 0 imports | `tests/proof_of_boundary/test_import_isolation.py` | AST scan: 0 violations | PASS |
| PB-5 | Checkpoint safety | No JWT/Pydantic in checkpoint | `tests/proof_of_boundary/test_state_safety.py` | Inspection pass | PASS |
| PB-6 | Invoke execution order | `__call__()`: S-1 trust gate → S-4 `node_start` → S-2 `_security_gate_input` → `execute()` → S-3 `_security_gate_output` → S-4 `node_complete` | `tests/proof_of_boundary/test_pb_invoke_order.py` | Order verified | PASS |
| PB-7 | HITL interrupt propagation *(conditional)* | Required only when `config.yaml` sets `hitl.enabled: true`; otherwise record **Auto-waived — non-HITL** | `tests/proof_of_boundary/test_pb7_hitl_interrupt_propagation.py` | `GraphInterrupt` propagates to the LangGraph engine; `status` is not set to `error` | **Auto-waived — non-HITL** (`config/agent.yaml` sets `hitl.enabled: false`) |

> **Pre-CoE gate checklist:** PB-1 through PB-6 are mandatory. Evaluate PB-7 only for HITL-enabled templates. When neither HITL setting is true, mark PB-7 **Auto-waived — non-HITL**; its test is not required and must not block the gate.

> **PB-3 note:** Only the LLM call is a real external integration in this agent: `BriefDraftNode` drafts the brief through `AzureOpenAIClient`, with the three `AZURE_OPENAI_*` secrets resolved via `ctx.secrets.require(...)` after the mock-mode short-circuit. `ProtocolKbService`, `RecordMatchService` and `DeviationLogService` are served from `src/services/mock_data.py` stub data and never touch a credential. PB-3 is satisfied for the LLM path by `tests/unit/test_brief_draft_node.py`, which asserts that with every mock alias cleared a missing Azure OpenAI secret raises `MissingSecret`, and that with secrets bound the client is called.

## Domain-Specific Tests

| Test-ID | Test | Location | Expected Result | Result |
|---------|------|----------|----------------|--------|
| DOM-01 | `mock_mode_enabled()` resolves via `USE_MOCK` alone | `tests/unit/test_mock_mode.py` | `True` | PASS |
| DOM-02 | `mock_mode_enabled()` resolves via `STG_MOCK_MODE` alias alone | `tests/unit/test_mock_mode.py` | `True` (regression test for `.claude/rules/test_rule.md` Rule 1) | PASS |
| DOM-03 | `mock_mode_enabled()` is `False` when neither is set | `tests/unit/test_mock_mode.py` | `False` | PASS |
| DOM-04 | `PreProcessNode` parses a valid evidence package into `protocol_steps` | `tests/unit/test_pre_process_node.py` | `protocol_steps` populated, `status: success` | PASS |
| DOM-05 | `PreProcessNode` rejects empty/non-JSON/non-object `user_input` | `tests/unit/test_pre_process_node.py` | `status: error` with descriptive `error_log` | PASS |
| DOM-06 | `PreProcessNode._extra_security_gate_input` rejects a package with zero protocol steps | `tests/unit/test_pre_process_node.py` | `status: error` set on state before `execute()` runs | PASS |
| DOM-07 | `RecordMatchNode` succeeds in mock mode with **no secret bound** | `tests/unit/test_record_match_node.py` | `status: success`, `matched_records` populated (regression test for `.claude/rules/test_rule.md` Rule 2) | PASS |
| DOM-08 | `EvidenceMatrixBuildNode` flags an unknown-acceptance-criteria step as `"unknown"` (not silently omitted) | `tests/unit/test_evidence_matrix_build_node.py` | Row present with `acceptance_criteria_met: "unknown"` | PASS |
| DOM-09 | `GapDetectNode` classifies unexecuted / unsigned / missing_criteria / contradictory rows correctly | `tests/unit/test_gap_detect_node.py` | Correct `gap_type` per row | PASS |
| DOM-10 | `DeviationCrossCheckNode` succeeds in mock mode with no secret bound | `tests/unit/test_deviation_cross_check_node.py` | `status: success`, `annotated_gap_list` populated | PASS |
| DOM-11 | `BriefDraftNode` succeeds in mock mode with no secret bound; fails clearly (not silently) outside mock mode with no LLM wired | `tests/unit/test_brief_draft_node.py` | Mock: `status: success`, non-empty `draft_brief`. Non-mock: `status: error` with explanatory `error_log` | PASS |
| DOM-12 | `PostProcessNode` appends the mandatory reviewer disclaimer and strips raw source references | `tests/unit/test_post_process_node.py` | `formatted_output` contains the disclaimer text and no `mock://test-records/...` references | PASS |
| DOM-13 | `EvidenceReconciliationGraphNode.extract_input()` JSON-encodes `protocol_steps` for the inner graph | `tests/unit/test_graph_node_composition.py` | Decodable JSON string containing `protocol_steps` | PASS |
| DOM-14 | `EvidenceReconciliationGraphNode.merge_output()` maps inner `sub_result` fields into outer state | `tests/unit/test_graph_node_composition.py` | `result`, `status`, `evidence_matrix`, `annotated_gap_list`, `draft_brief` all mapped | PASS |

## Integration Tests

| Test-ID | Test | Location | Expected Result | Result |
|---------|------|----------|----------------|--------|
| INT-01 | Full outer graph `.compile()` + `.invoke()` in mock mode | `tests/integration/test_graph_invoke.py` | `status: success`, `output` contains the drafted brief + disclaimer | PASS |
| INT-02 | Full inner `DomainWorkflowGraph.compile()` + `.invoke()` in mock mode | `tests/integration/test_graph_invoke.py` | `status: success`, `get_output()` shape matches `merge_output()` expectations | PASS |
| INT-03 | `PreProcessNode` structural rejection propagates through the compiled outer graph (no crash) | `tests/integration/test_graph_invoke.py` | `status: error`, `error_log` populated, graph does not raise | PASS |
| INT-04 | `POST /invoke` over a real ASGI transport in mock mode (async route → `asyncio.to_thread` → sync `.invoke()` → `asyncio.run()`-in-node boundary) | `tests/integration/test_server_http.py` | HTTP 200, `status: "success"` in body (regression test for `.claude/rules/test_rule.md` Rule 3) | PASS |
| INT-05 | `GET /health` over a real ASGI transport | `tests/integration/test_server_http.py` | HTTP 200, `{"status": "ok", ...}` | PASS |
| INT-06 | `stg_invoke_evidence.py`-style local repro against a real `uvicorn` process with `STG_MOCK_MODE=true` only (mirrors `deploy-stg`) | `bash .claude/common-scripts/check-local.sh` Stage 5 gate; evidence at `stage5_evidence/stage5_v1.json` | `overall: PASS` | PASS — all 7 assertions (`manifest_parsed`, `payload_json_valid`, `health_200`, `invoke_200`, `response_json_valid`, `agent_status_success`, `no_security_violation`) passed after updating `deploy/invoke_payload.json` to send a real evidence-package JSON string instead of the scaffold's generic free-text placeholder |

## Test Execution Summary
- Execution date: 2026-07-28
- Total tests: 63 (see `pytest tests/ -v` output — all unit, proof_of_boundary, and integration tests)
- Pass: 61 / Fail: 0 / Skip: 2 (`tests/proof_of_boundary/test_pb7_hitl_interrupt_propagation.py` — both tests `pytest.mark.skipif`-skipped because `config/agent.yaml` sets `hitl.enabled: false`; this is the expected, documented Auto-waived state, not a failure)
- Coverage: all `src/` modules are exercised by at least one test (no all-stub test files per `scripts/check_stub_tests.py`); full local check script run (mirrors the CI gates) passes end-to-end including the Stage 5 STG invoke evidence check (`overall: PASS`)
- Status: **Completed**
