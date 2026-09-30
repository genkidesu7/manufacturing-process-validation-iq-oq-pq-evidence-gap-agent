# INT-04/05: regression tests for .claude/rules/test_rule.md Rule 3.
#
# agent.invoke() is sync and its nodes call asyncio.run() internally. Calling
# it directly from an async route (without asyncio.to_thread) raises
# "asyncio.run() cannot be called from a running event loop" inside the node,
# which the node's except-Exception silently turns into status: "error" — a
# 200 response with no visible crash. An in-process sync call to
# agent.invoke() never exercises this path; only a real ASGI transport does,
# because that puts the call inside the transport's running event loop.

import json
import os

import pytest
from httpx import ASGITransport, AsyncClient

VALID_PACKAGE = {
    "protocol": {
        "steps": [
            {
                "step_id": "IQ-01",
                "description": "Install pump",
                "acceptance_criteria": "Pump installed per spec",
                "required_signature_roles": ["engineer"],
            }
        ]
    },
    "test_records": [],
    "acceptance_criteria": [],
    "deviation_log": [],
    "signatures": [],
}


@pytest.fixture(autouse=True)
def _mock_mode(monkeypatch):
    monkeypatch.setenv("USE_MOCK", "true")
    monkeypatch.delenv("STG_MOCK_MODE", raising=False)


@pytest.fixture
def app():
    # Imported after USE_MOCK is set (autouse fixture runs first) — the module
    # constructs `agent = Graph()` and compiles it at import time, and does not
    # itself depend on USE_MOCK, so import order here is only a defensive
    # precaution, not a hard requirement.
    os.environ.setdefault("AGENTCORE_ENVIRONMENT", "development")
    from src.api.server import app as fastapi_app

    return fastapi_app


class TestServerHttp:
    @pytest.mark.asyncio
    async def test_int04_invoke_endpoint_succeeds_over_http(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/invoke", json={"input": json.dumps(VALID_PACKAGE)})

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert "ADVISORY OUTPUT ONLY" in body["output"]

    @pytest.mark.asyncio
    async def test_int05_health_endpoint_over_http(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
