# Every node must emit a PROGRESS_UPDATE on entry so the caller's UI has
# something to show while the agent runs (agenticstar-deploy requirement).

import importlib
import inspect
import pkgutil

import pytest

from shared.services.events.types import EventType

from tests.proof_of_boundary.test_pb_invoke_order import _NODE_STATE_OVERRIDES


def _node_modules_and_classes() -> list[tuple[str, str]]:
    from framework.nodes.function_node import FunctionNode

    pkg = importlib.import_module("src.nodes")
    found = []
    for _, modname, _ in pkgutil.walk_packages(pkg.__path__, prefix="src.nodes."):
        module = importlib.import_module(modname)
        for attr in vars(module).values():
            if (
                isinstance(attr, type)
                and issubclass(attr, FunctionNode)
                and attr is not FunctionNode
                and attr.__module__ == modname
                and not inspect.isabstract(attr)
            ):
                found.append((modname, attr.__name__))
    return found


class _RecordingEmitter:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def emit_event(self, **kwargs) -> None:
        self.events.append(kwargs)


@pytest.mark.parametrize(("modname", "class_name"), _node_modules_and_classes())
def test_node_emits_progress_update(monkeypatch, modname, class_name):
    monkeypatch.setenv("USE_MOCK", "true")
    monkeypatch.delenv("STG_MOCK_MODE", raising=False)
    recorder = _RecordingEmitter()
    module = importlib.import_module(modname)
    monkeypatch.setattr(module, "emitter", lambda: recorder)

    node = getattr(module, class_name)()
    state = {
        "caller_trust_level": "ANONYMOUS",
        "correlation_id": "c",
        "session_id": "s",
        "thread_id": "t",
        "trace_id": "tr",
        "node_history": [],
        "error_log": [],
        **_NODE_STATE_OVERRIDES.get(class_name, {}),
    }
    node.execute(state)

    assert recorder.events, f"{class_name} emitted no progress event"
    assert all(e["event_type"] is EventType.PROGRESS_UPDATE for e in recorder.events)
    assert all(e["message"] for e in recorder.events)
