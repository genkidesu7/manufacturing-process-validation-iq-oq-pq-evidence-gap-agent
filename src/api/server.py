"""AgentCore Platform v1.0"""

# Standalone HTTP entry point for the agent.
# Entry points are adapters only — no business logic here.
# For platform-level routing, AgentGateway calls agent.invoke() directly.

import asyncio
import os
import secrets
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel

from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel
from framework.secrets.context import bound_secrets
from framework.utils.config_loader import load_agent_config
from shared.secrets import factory as secrets_factory
from shared.secrets.chained_provider import ChainedSecretProvider
from shared.secrets.env_provider import EnvProvider
from src.graph.graph import Graph

app = FastAPI(title="MFG-C2-140 IQ/OQ/PQ Evidence Gap Agent")

# Load config/config.yaml the same way AgentRegistry does — a bare Graph() runs
# with config={}, so hitl.enabled / memory_enabled / max_retry would never reach
# the graph on this path.
_config = load_agent_config(Path(__file__).resolve().parents[2])

# Process env first (secrets a platform injects as real environment variables,
# e.g. the Azure OpenAI keys), dotenv files second. A bare secrets_factory()
# only sees the dotenv files.
_secrets_provider = ChainedSecretProvider(
    EnvProvider(namespace="mfg", agent_name="mfg-c2-140"),
    secrets_factory(namespace="mfg", agent_name="mfg-c2-140"),
    namespace="mfg",
    agent_name="mfg-c2-140",
)

agent = Graph(config=_config)

# Mirror the registry's conditional checkpointer — hitl.enabled or memory_enabled
# needs one, or interrupt()/memory silently no-ops on this path. This process
# runs exactly one agent, so a private MemorySaver is sufficient.
_needs_checkpointer = agent.config.get("memory_enabled") or agent.config.get("hitl", {}).get("enabled", False)
agent.compile(checkpointer=MemorySaver() if _needs_checkpointer else None)
agent.provision_secrets(_secrets_provider)


class InvokeRequest(BaseModel):
    input: str
    session_id: str = ""


def _bearer_matches(supplied: str, expected: str) -> bool:
    """Constant-time bearer comparison that is safe for non-ASCII header input."""
    return secrets.compare_digest(supplied.encode(), f"Bearer {expected}".encode())


def _resolve_standalone_trust(
    current: TrustLevel, authorization: str, invoke_auth_token: str | None, internal_runner_token: str | None
) -> TrustLevel:
    """Authenticate standalone callers without allowing external-token elevation.

    STG_INTERNAL_RUNNER_TOKEN is a distinct, CI-generated deployment credential.
    It is considered only for an anonymous caller and maps exactly to INTERNAL;
    INVOKE_AUTH_TOKEN remains VERIFIED_EXTERNAL. Middleware-established trust is
    never changed.
    """
    if current is not TrustLevel.ANONYMOUS:
        return current
    if internal_runner_token and _bearer_matches(authorization, internal_runner_token):
        return TrustLevel.INTERNAL
    if invoke_auth_token and _bearer_matches(authorization, invoke_auth_token):
        return TrustLevel.VERIFIED_EXTERNAL
    if internal_runner_token or invoke_auth_token:
        # Generic body on purpose — do not leak whether the token was absent,
        # malformed, or wrong.
        raise HTTPException(status_code=401, detail="Token is invalid or expired.")
    return TrustLevel.ANONYMOUS


@app.post("/invoke")
async def invoke(req: InvokeRequest, request: Request) -> dict[str, Any]:
    # This adapter is the entry-point auth boundary (standalone equivalent of the
    # platform AuthMiddleware). Both tokens are deployment-level caller
    # credentials, not agent secrets: no InvocationContext exists before this
    # boundary, so ctx.secrets cannot apply.
    trust = _resolve_standalone_trust(
        getattr(request.state, "trust_level", TrustLevel.ANONYMOUS),
        request.headers.get("authorization", ""),
        os.environ.get("INVOKE_AUTH_TOKEN"),
        os.environ.get("STG_INTERNAL_RUNNER_TOKEN"),
    )
    with bound_secrets(agent._secrets_provider):
        ctx = InvocationContext(
            session_id=req.session_id or str(uuid4()),
            caller_trust_level=trust,
            caller_id=getattr(request.state, "caller_id", ""),
        )
        # agent.invoke() is sync and its nodes internally call asyncio.run().
        # Calling it directly from this async route would raise "asyncio.run()
        # cannot be called from a running event loop" inside the node, silently
        # swallowed by the node's except-Exception into status: "error" (a 200
        # response with no visible crash). asyncio.to_thread offloads to a worker
        # thread and propagates the current contextvars.Context automatically —
        # required because bound_secrets() above binds a ContextVar the worker
        # thread must still see.
        result: dict[str, Any] = await asyncio.to_thread(agent.invoke, req.input, ctx=ctx)
        return result


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "mfg-c2-140"}
