# Template Design Specification

**Status:** completed
**Date:** 2026-07-28
**Reviewer:** [TBD]

## Position in AgentCore Architecture

- **Agent Class**: `Graph` (outer), `DomainWorkflowGraph` (inner)
- **L1 Base**: AgentBaseGraph (outer graph) — Cat 2
- **Three-Layer Separation**:
  - State: flat TypedDict composition (no Pydantic — msgpack incompatible)
  - Node: L1 inheritance (Template Method: `execute(self, state: dict) -> dict` override only)
  - Graph: composition (`register_nodes()` for node substitution)

## Architecture Overview

This is a **Cat 2** template. The outer graph keeps the framework-owned fixed 5-node
backbone (`initialize → pre_process → main → {route} → post_process → finalize`); all
domain-specific evidence-reconciliation logic (RAG record matching, evidence-matrix
construction, gap detection, deviation cross-check, and brief drafting) is encapsulated
inside the `main` slot via a `GraphNode` subclass wrapping an inner
`DomainWorkflowGraph` (`BaseGraph`, custom topology).

Rationale for two layers: the outer backbone provides input validation (`pre_process`)
and the mandatory S-3 output-validation / disclaimer step (`post_process`) uniformly,
while the inner graph is free to define a fully custom, non-`pre/main/post` topology
matching the 5 domain steps (Record Match → Evidence Matrix Build → Gap Detect →
Deviation Cross-Check → Brief Draft) described in the proposal.

### Node Configuration

**Outer graph** (`src/graph/graph.py`, `AgentBaseGraph`):

| Node | Responsibility | Input State | Output State | Inherits/Overrides |
|------|---------------|-------------|--------------|-------------------|
| initialize | Framework default: sets `schema_version`, `session_id`, `trust_level` | — | `schema_version`, `session_id`, `trust_level` | InitializeNode (default, not overridden) |
| pre_process | **Protocol Ingest** — parse the raw JSON evidence package (`user_input`), validate presence of protocol/records/criteria/deviation-log/signatures, extract structured protocol steps | `user_input`, `input_context` | `validated_input`, `protocol_steps`, `enriched_context`, `error_log`, `status` | `PreProcessNode` (`FunctionNode`) |
| main | Wraps the inner domain workflow (Record Match → Evidence Matrix Build → Gap Detect → Deviation Cross-Check → Brief Draft) | `validated_input`, `protocol_steps` | `evidence_matrix`, `gap_list`, `annotated_gap_list`, `draft_brief`, `result`, `status` | `EvidenceReconciliationGraphNode` (`GraphNode`) |
| post_process | **Output Validate (S-3)** — strip raw confidential record content from the draft brief, append the mandatory reviewer-approval disclaimer | `draft_brief`, `evidence_matrix`, `annotated_gap_list` | `formatted_output`, `status` | `PostProcessNode` (`FunctionNode`) |
| finalize | Framework default: builds `response_metadata`, `total_time_ms` | — | `response_metadata`, `total_time_ms` | FinalizeNode (default, not overridden) |

**Inner graph** (`src/graph/domain_workflow_graph.py`, `DomainWorkflowGraph(BaseGraph)`):

| Node | Responsibility | Input State | Output State | Inherits/Overrides |
|------|---------------|-------------|--------------|-------------------|
| record_match | **Record Match** — RAG retrieval + matching of executed test records to protocol steps via `RecordMatchService` (vector DB) | `validated_input` (JSON string), `protocol_steps` | `matched_records`, `status` | `RecordMatchNode` (`FunctionNode`) |
| evidence_matrix_build | **Evidence Matrix Build** — construct requirement-to-evidence traceability matrix with source references via `ProtocolKbService` | `protocol_steps`, `matched_records` | `evidence_matrix`, `status` | `EvidenceMatrixBuildNode` (`FunctionNode`) |
| gap_detect | **Gap Detect** — identify unexecuted, unsigned, or missing-acceptance-criteria steps | `evidence_matrix` | `gap_list`, `status` | `GapDetectNode` (`FunctionNode`) |
| deviation_cross_check | **Deviation Cross-Check** — cross-reference gaps against open deviation-log entries via `DeviationLogService` | `gap_list` | `annotated_gap_list`, `status` | `DeviationCrossCheckNode` (`FunctionNode`) |
| brief_draft | **Brief Draft** — generate structured reviewer brief with provenance references (LLM-assisted) | `evidence_matrix`, `annotated_gap_list` | `draft_brief`, `status` | `BriefDraftNode` (`FunctionNode`) |

### Data Flow

**Outer graph:**
```
START → initialize → pre_process → main → {route} → post_process → finalize → END
                                            ↓ (retry, max 3)
                                          pre_process
```

**Inner graph** (linear — no branching required; each step depends strictly on the
previous step's output, and there is no domain condition under which skipping a step
is valid):
```
START → record_match → evidence_matrix_build → gap_detect → deviation_cross_check → brief_draft → END
```

### State Definition

| Field | Type | Purpose | Required |
|-------|------|---------|----------|
| `validated_input` | `str` | Raw JSON evidence package string after `pre_process` validation (inherited from `AgentState`) | Yes (set by pre_process) |
| `protocol_steps` | `list[dict]` | Parsed protocol steps with id, description, expected acceptance criteria, required signature roles | Yes (set by pre_process) |
| `matched_records` | `list[dict]` | Executed test records matched to protocol steps, each `{step_id, record_id, record_summary, source_ref, match_confidence}` | Yes (set by inner record_match) |
| `evidence_matrix` | `list[dict]` | Requirement-to-evidence traceability rows, each `{step_id, requirement, evidence_refs, acceptance_criteria_met, signature_status}` | Yes (set by inner evidence_matrix_build) |
| `gap_list` | `list[dict]` | Detected gaps, each `{step_id, gap_type, description}` where `gap_type` in `unexecuted`/`unsigned`/`missing_criteria`/`contradictory` | Yes (set by inner gap_detect) |
| `annotated_gap_list` | `list[dict]` | `gap_list` rows annotated with `{deviation_ref: str \| None, known_deviation: bool}` | Yes (set by inner deviation_cross_check) |
| `draft_brief` | `str` | Drafted reviewer-ready gap/remediation brief text (pre output-validation) | Yes (set by inner brief_draft) |
| `result` | `str` | Mapped from inner graph's `sub_result.output` (inherited from `AgentState`) | Yes (set by main via merge_output) |
| `formatted_output` | `str` | Final brief with confidential content stripped and disclaimer appended (inherited from `AgentState`) | Yes (set by post_process) |

**State Constraints (mandatory):**
- Flat TypedDict only (primitives + JSON-serializable types)
- No JWT, API keys, credentials in State (checkpoint DB leakage)
- InvocationContext via `config["configurable"]` only (not in State)
- No Pydantic models, dataclass, arbitrary Python objects (msgpack incompatible)
- All list fields above are plain `list[dict]` (replaced wholesale each return), not
  `Annotated[list, operator.add]` accumulators — each is fully rebuilt by its owning
  node, not appended to across nodes.

## Framework Utilization

### Shared Components Used
- [x] InvocationContext (correlation_id, session_id, permissions, credential handle) — via `config["configurable"]["invocation_context"]`, used by `RecordMatchNode` (vector DB credential) and `BriefDraftNode` (LLM credential)
- [x] ConnectionPolicy (retry/timeout strategy) — outer graph `max_retry: 3`, `timeout_seconds: 30` from `config/agent.yaml`
- [x] SecurityViolationError — implicitly via the framework's default S-2/S-3 gates (no domain code raises it directly)
- [x] S-2: `_extra_security_gate_input()` — domain-specific input check hook
      implemented on `PreProcessNode` to reject an evidence package with zero protocol
      steps parsed (input-size / structural sanity guard on the domain payload, beyond
      the default PII scan which only covers free-text `user_input`)
- [x] S-3: `_extra_security_gate_output()` — domain-specific output check hook
      implemented on `PostProcessNode` to (a) strip any raw `record_summary`/source
      excerpt text that leaked into `formatted_output` beyond the summary already
      redacted in `execute()`, and (b) verify the mandatory reviewer-approval
      disclaimer string is present in the final output — re-appends it if a defect in
      `execute()` ever dropped it, so the disclaimer can never silently go missing
- [x] S-4: `emit_trace_event()` — at least one domain-specific event inside each `execute()`:
      `protocol_ingested` (pre_process), `records_matched` (inner record_match),
      `evidence_matrix_built` (inner evidence_matrix_build), `gaps_detected` (inner
      gap_detect), `deviations_cross_checked` (inner deviation_cross_check),
      `brief_drafted` (inner brief_draft), `output_validated` (post_process)

> **S-2/S-3 gate behaviour by node type (ADR-017):**
> - `FunctionNode` subclass → framework `@final` gate always runs automatically;
>   extend via `_extra_security_gate_input()` / `_extra_security_gate_output()` only
> - `GraphNode` / `RemoteAgentNode` → deliberate no-op (upstream or remote node's gate already applied) — applies to `EvidenceReconciliationGraphNode` in the `main` slot; the inner graph's own nodes each run their own S-2/S-3 gates
> - Custom `BaseNode` subclass → must implement `_security_gate_input()` and
>   `_security_gate_output()` directly (`@abstractmethod` — omission raises `TypeError` at instantiation) — not used in this design; all nodes are `FunctionNode`/`GraphNode`

### Composition Pattern

- **Pattern**: GraphNode (subgraph) — `EvidenceReconciliationGraphNode` in the outer
  `main` slot wraps `DomainWorkflowGraph` (inner)
- **Composition target**: `src/graph/domain_workflow_graph.py` — 5 linear `FunctionNode`s (record_match, evidence_matrix_build, gap_detect, deviation_cross_check, brief_draft)
- **Error propagation strategy**: `propagate` (default) — any inner-graph node failure
  (e.g. `RecordMatchService` unreachable) raises `SubgraphError` in the outer graph
  rather than attempting graceful degradation. Rationale: a partial/incorrect evidence
  matrix is worse than a hard failure for an advisory compliance document — the
  reviewer must be able to trust that any brief returned is based on complete evidence
  reconciliation, not partial data silently masked as success.
- **`propagate_hitl`**: `False` (default) — not applicable, this agent does not use HITL (`hitl.enabled: false`, see `docs/01_proposal.md` HITL Gate)

## Services

| Service | File | Responsibility | Used By |
|---------|------|-----------------|---------|
| `ProtocolKbService` | `src/services/protocol_kb_service.py` | Retrieves the reference protocol/acceptance-criteria KB entry for a given protocol step (vector-indexed lookup); builds evidence-matrix rows | `EvidenceMatrixBuildNode` |
| `RecordMatchService` | `src/services/record_match_service.py` | RAG-based retrieval + matching of executed test records to protocol steps against the vector DB | `RecordMatchNode` |
| `DeviationLogService` | `src/services/deviation_log_service.py` | Looks up open deviation-log entries related to a given protocol step / gap | `DeviationCrossCheckNode` |
| `mock_mode` (helper module, not a class) | `src/services/mock_mode.py` | Shared `mock_mode_enabled()` helper resolving both `USE_MOCK` and `STG_MOCK_MODE` env vars (`.claude/rules/implementation_rule.md` Rule 1) | All three services above, plus `BriefDraftNode` for LLM credential short-circuit |

All three domain services expose an async `mock_mode_enabled()`-gated pair of code
paths: a real path that requires a resolved `credential_handle`
(vector DB / LLM), and a `stub_*` mock path (`mock_data.py`-style stub data) that never
touches `credential_handle` at all — per `.claude/rules/implementation_rule.md` Rule 2,
nodes must not call `ctx.secrets.require(...)` before checking mock mode.

## Error Handling

- **Transient failures** (e.g. vector DB / LLM call times out or returns a retryable
  error) inside inner-graph nodes: return `AgentStatus.RETRY` from that node's
  `execute()`; `error_strategy: propagate` on the outer `GraphNode` means a `RETRY`
  status that exhausts `max_retry` (3) at the outer level surfaces as `SubgraphError` →
  outer graph's own retry/error routing takes over from there.
- **Permanent failures** (e.g. malformed protocol package with no parseable steps,
  unknown protocol schema version): `pre_process` (`PreProcessNode`) returns
  `AgentStatus.ERROR` immediately — this is a structural input problem, not a transient
  one, so no retry attempt is made.
- **Unknown protocol step / missing acceptance-criteria entry** (Risk #3 in
  `docs/01_proposal.md`): `EvidenceMatrixBuildNode` does not fail or silently omit the
  row — it emits an evidence-matrix row with `acceptance_criteria_met: "unknown"` and a
  `gap_list` entry of `gap_type: "missing_criteria"`, so the reviewer sees an explicit
  flag rather than a silent omission.

## Security Considerations

- **S-1** (trust gate): all nodes default `required_trust_level = TrustLevel.ANONYMOUS`
  except none require elevation — this agent reads submitted package data and internal
  KB/deviation-log lookups, it does not perform privileged write operations. The
  `/invoke` HTTP entry point itself is protected by `INVOKE_AUTH_TOKEN` bearer auth
  (scaffold default, `src/api/server.py`), independent of per-node trust levels.
- **S-2** (input): default PII scan on `user_input`/`validated_input` plus the domain
  `_extra_security_gate_input()` structural-sanity check on `PreProcessNode` (§ Framework
  Utilization above).
- **S-3** (output): default credential-pattern scan plus the domain
  `_extra_security_gate_output()` confidential-content-strip + disclaimer-presence
  check on `PostProcessNode` (§ Framework Utilization above). This directly implements
  the proposal's Step 7 (`OUTPUT VALIDATE`) and mitigates Risk #1 (a gap brief being
  misread as an approval/certification decision) — the disclaimer text is a mandatory,
  code-enforced part of every response, not optional prose from the LLM prompt.
- **S-4** (audit): one domain `emit_trace_event()` per node execute(), see § Framework
  Utilization above.
- **S-5** (state/checkpoint safety): no credential-like fields in `State` (verified by
  PB-2/PB-5); `credential_handle` for `RecordMatchService`/`ProtocolKbService` (vector
  DB) and `BriefDraftNode` (LLM) is resolved via `InvocationContext.credential_handle`
  inside the node, never stored in state or logged.
- **Mock mode** (per `.claude/rules/implementation_rule.md`): resolved once via
  `src/services/mock_mode.py::mock_mode_enabled()`, checked before any
  `ctx.secrets.require(...)` call, and accepts both `USE_MOCK` (canonical) and
  `STG_MOCK_MODE` (what the `deploy-stg` CI job sets).

## Performance Requirements

- Outer graph `timeout_seconds: 30` per `config/agent.yaml` covers the full pipeline
  including the inner graph's 5 sequential steps; each individual service call
  (vector DB retrieval, LLM brief drafting) is expected to complete well within that
  budget for a single protocol package (dozens to low hundreds of steps), consistent
  with the proposal's "minutes per package" target — no new infra required, reuses
  existing LLM + vector infra per `docs/01_proposal.md` § Technical Feasibility.
- `max_retry: 3` bounds retry amplification on transient vector DB / LLM failures.

## Import Isolation Confirmation
- [x] Template does not import agenticstar-platform SDK (Level 0)
- [x] Import targets: framework/ and shared/ only (no agents/base/ required)

## Design Decision Record

| Decision | Option A | Option B | Chosen | Rationale |
|----------|----------|----------|--------|-----------|
| L1 base type | AgentBaseGraph | AutonomousBaseGraph | **AgentBaseGraph** | Fixed 7-step pipeline defined by the proposal, no self-directed reasoning loop or open-ended termination condition — Cat 2, not Cat 3 |
| Composition pattern | Standalone (all logic in outer pre/main/post) | GraphNode wrapping inner `BaseGraph` | **GraphNode wrapping inner BaseGraph** | 5 of the 7 proposal steps (Record Match, Evidence Matrix Build, Gap Detect, Deviation Cross-Check, Brief Draft) form a cohesive, strictly-ordered domain sub-workflow that does not map onto a single `main` node's `execute()`; encapsulating them in an inner graph keeps the outer backbone's `pre_process`/`post_process` semantics clean (protocol ingest vs. output validation) |
| Inner graph parent | `BaseGraph` (fully custom topology) | `AgentBaseGraph` (5-node pipeline) | **BaseGraph** | The 5 domain steps do not correspond to `pre_process`/`main`/`post_process` semantics — a fully custom linear topology (`record_match → evidence_matrix_build → gap_detect → deviation_cross_check → brief_draft`) is the more direct fit, matching the `domain_workflow_graph_sample.py` reference pattern |
| Inner graph topology | Linear | Conditional branching (e.g. skip deviation cross-check if no gaps found) | **Linear** | Running deviation cross-check even with an empty gap list is cheap (no-op lookup) and keeps the pipeline simpler/more auditable than adding a conditional edge for a marginal cost saving; no domain requirement calls for skipping a step |
| HITL | Enabled (`interrupt()` gate) | Disabled | **Disabled** | Per `docs/01_proposal.md` HITL Gate: MFG is not in the HCR/INS/FIN/GOV regulated-industry set that mandates the gate, and the agent is advisory-only — the human reviewer's approval happens entirely outside the agent invocation, not as an in-graph pause/resume |
| Error strategy (GraphNode) | propagate | handle (graceful degradation) | **propagate** | A partial/incorrect evidence matrix is worse than a hard failure for an advisory compliance document (see § Composition Pattern) |
