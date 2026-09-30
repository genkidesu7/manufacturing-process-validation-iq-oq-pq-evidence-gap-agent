# MFG-C2-140 — Manufacturing Process Validation IQ/OQ/PQ Evidence Gap Agent

> **Category**: Cat 2 (multi-step domain workflow — job-to-be-done)
> **Industry**: MFG (Manufacturing)
> **Inherits**: DocGenerationAgent (Level 2)
> **Status**: Draft

## Overview

Validation/QA engineers at regulated pharmaceutical, food, and other high-reliability
manufacturing plants must reconcile a full IQ/OQ/PQ (Installation/Operational/Performance
Qualification) validation package against a configured protocol and acceptance criteria before
a process can be released for production. This agent ingests the protocol, executed test
records, acceptance criteria, deviation log, and approval/signature records; builds a traceable
requirement-to-evidence matrix; detects unexecuted, unsigned, or contradictory steps; cross-
checks flagged gaps against the open deviation log; and drafts a structured, reviewer-ready gap
and remediation brief with source references preserved throughout.

The agent is **advisory-only**: it never approves a release, certification, or production
change. That authority always remains with the accountable human QA reviewer.

## Features

- **Protocol Ingest** — parses IQ/OQ/PQ protocol steps, expected acceptance criteria, and
  required signatures.
- **Record Match (RAG)** — retrieves and matches executed test records to protocol steps
  against a vector-indexed protocol/acceptance-criteria knowledge base.
- **Evidence Matrix Build** — constructs a requirement-to-evidence traceability matrix with
  source references for every protocol step.
- **Gap Detect** — flags unexecuted, unsigned, or missing-acceptance-criteria steps.
- **Deviation Cross-Check** — cross-references detected gaps against open deviation-log
  entries so already-tracked deviations are annotated, not re-raised.
- **Brief Draft** — generates a structured, provenance-linked gap/remediation brief.
- **Output Validate (S-3)** — strips raw confidential record content and appends the mandatory
  reviewer-approval disclaimer before the response is returned.

See `docs/02_design.md` for the technical design and `docs/03_test_spec.md` for the test specification.

## Requirements

- Python 3.11 or later.
- The AGENTIC STAR agent framework (`agenticstar-agentcore`), which is distributed through an internal
  package registry rather than public PyPI. It supplies the `framework` and `shared` packages this
  template imports.
- For real (non-mock) runs, an Azure OpenAI deployment. Provide `AZURE_OPENAI_API_KEY`,
  `AZURE_OPENAI_ENDPOINT` (the bare resource endpoint) and `AZURE_OPENAI_DEPLOYMENT` as environment
  variables or through the platform's secret provider.

### Behaviour without the platform

Without the framework package the template cannot be imported, so neither the server nor the tests
run. With it installed but no platform around it:

- The server in `src/api/server.py` runs standalone. Progress events go to a no-op emitter, so nothing
  is sent anywhere.
- With `USE_MOCK=true` (or `STG_MOCK_MODE=true`) the whole pipeline runs against stub data and needs no
  credentials.
- Without a mock flag, only the brief-drafting step is real: it calls Azure OpenAI and fails fast with
  a missing-secret error if the three Azure OpenAI variables are absent. The test-record matching,
  protocol knowledge-base and deviation-log steps always use the stub data in `src/services/mock_data.py`,
  because no live connector is provisioned for them.

## Quick Start

```bash
source .venv/bin/activate
uv pip install -e ".[dev]"
python -m pytest tests/ -v
uvicorn src.api.server:app --reload
```

## Usage

Start the API server locally:

```bash
source .venv/bin/activate
uvicorn src.api.server:app --reload
```

Invoke the agent with an IQ/OQ/PQ evidence package. The `input` field is a
JSON-encoded string with `protocol.steps` (each step: `step_id`,
`description`, `acceptance_criteria`, `required_signature_roles`),
`test_records`, `acceptance_criteria`, `deviation_log`, and `signatures`:

```bash
curl -X POST http://127.0.0.1:8000/invoke \
  -H "Content-Type: application/json" \
  -d '{"input": "{\"protocol\": {\"steps\": [{\"step_id\": \"IQ-01\", \"description\": \"Install pump\", \"acceptance_criteria\": \"Pump installed per spec\", \"required_signature_roles\": [\"engineer\"]}]}, \"test_records\": [], \"acceptance_criteria\": [], \"deviation_log\": [], \"signatures\": []}"}'
```

Response shape:

```json
{
  "output": "<reviewer brief text, with mandatory advisory disclaimer appended>",
  "status": "success",
  "trace_id": "...",
  "correlation_id": "...",
  "node_history": ["InitializeNode", "PreProcessNode", "EvidenceReconciliationGraphNode", "PostProcessNode", "FinalizeNode"]
}
```

The response contains the evidence matrix, the gap/exception list, and the reviewer-ready
brief. Set `USE_MOCK=true` (or `STG_MOCK_MODE=true`, the alias set by the `deploy-stg` CI job)
to exercise the full pipeline against stub data with no external LLM/vector-DB credentials.

## API Endpoints

| Method | Path | Description |
|--------|------|--------------|
| `POST` | `/invoke` | Submit an IQ/OQ/PQ evidence package; returns the evidence matrix, gap/exception list, and reviewer brief. |
| `GET` | `/health` | Health check. |

## Configuration

Static identity lives in `config/agent.yaml` (id, name, namespace, category, industry, entry-point class,
required trust level, and the secrets and extras the agent needs). Runtime parameters live in
`config/config.yaml`:

- `max_retry` / `timeout_s` — retry budget and timeout.
- `hitl.enabled: false` — this agent has no in-graph human-in-the-loop gate; the human reviewer's
  approval decision happens entirely outside the agent invocation.
- Mock mode is resolved by one shared helper, `mock_mode_enabled()`, which honours both `USE_MOCK`
  (canonical) and `STG_MOCK_MODE` (the alias set by the staging deploy job).
- `INVOKE_AUTH_TOKEN`, when set on the server, requires callers to send it as a Bearer token.

## Project Structure

```
.
├── cli.py                      # AGENTIC STAR Marketplace entry point
├── config/
│   ├── agent.yaml              # Agent manifest
│   └── config.yaml             # Runtime parameters
├── docs/                       # Design (02_design.md) and test specification (03_test_spec.md)
├── scripts/                    # Local and CI check scripts
├── src/
│   ├── api/server.py           # FastAPI entry point (/invoke, /health)
│   ├── graph/
│   │   ├── graph.py            # Outer graph (fixed backbone with a GraphNode main slot)
│   │   └── domain_workflow_graph.py  # Inner workflow: Record Match -> Evidence Matrix Build ->
│   │                                 # Gap Detect -> Deviation Cross-Check -> Brief Draft
│   ├── nodes/                  # One FunctionNode per pipeline stage
│   ├── schemas/state.py        # Agent state (flat TypedDict)
│   └── services/               # LLM service, stub-backed connectors, mock-mode helper
└── tests/
    ├── unit/                   # Node and service unit tests
    ├── proof_of_boundary/      # Proof-of-boundary tests
    └── integration/            # Graph and HTTP-level tests
```

## Customising

- Replace the stub-backed connectors in `src/services/` (`record_match_service.py`,
  `protocol_kb_service.py`, `deviation_log_service.py`) with real integrations, and declare any new
  secret under `requires.secrets` in `config/agent.yaml`.
- Change the brief prompt in `src/services/service.py`.
- If a node ever needs elevated trust, raise `required_trust_level` on the node and in
  `config/agent.yaml` together.

## License

Released under the MIT License. See `LICENSE`.

## Status of this repository

This repository is provided as-is, with no warranty of any kind and no support commitment. The agent's
output is advisory only and must be reviewed by a qualified QA/validation reviewer before any release,
certification or production-change decision.
