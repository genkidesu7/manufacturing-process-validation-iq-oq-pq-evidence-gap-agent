"""AgentCore Platform v1.0"""

# Service layer: the one place that builds the reviewer-brief prompt and
# constructs AzureOpenAIClient. Nodes call this; credentials are resolved by
# the calling node from its invocation-scoped SecretProvider and passed in —
# never read from os.environ here.

from __future__ import annotations

import json
from typing import Any

from framework.secrets import SecretProvider

_BRIEF_SYSTEM_PROMPT = (
    "You draft a reviewer-ready gap and remediation brief for an IQ/OQ/PQ "
    "process-validation package. You are advisory only: never approve, certify "
    "or release anything; that authority stays with the accountable human QA "
    "reviewer. Use only the evidence matrix and gap list you are given, keep "
    "every source reference (step_id, evidence_refs, deviation_ref) verbatim, "
    "and state plainly when evidence is missing instead of inferring it."
)


def build_brief_messages(
    evidence_matrix: list[dict[str, Any]], annotated_gap_list: list[dict[str, Any]]
) -> list[dict[str, str]]:
    """Build the chat messages for the brief-draft LLM call."""
    payload = json.dumps(
        {"evidence_matrix": evidence_matrix, "annotated_gap_list": annotated_gap_list},
        indent=2,
        sort_keys=True,
    )
    return [
        {"role": "system", "content": _BRIEF_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Draft the structured brief (summary, per-gap findings with source references, "
                "remediation actions, known-deviation notes) from this data:\n" + payload
            ),
        },
    ]


def call_llm(
    messages: list[dict[str, str]],
    credential_handle: SecretProvider,
    max_tokens: int = 1500,
    temperature: float = 0.2,
) -> str:
    """Run one chat completion through AzureOpenAIClient and return the text."""
    from shared.services.llm.azure_openai_client import AzureOpenAIClient  # lazy import

    client = AzureOpenAIClient(
        config={
            "api_key": credential_handle.require("AZURE_OPENAI_API_KEY"),
            "azure_endpoint": credential_handle.require("AZURE_OPENAI_ENDPOINT"),
            "azure_deployment": credential_handle.require("AZURE_OPENAI_DEPLOYMENT"),
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
    )
    return str(client.complete(messages)["content"])
