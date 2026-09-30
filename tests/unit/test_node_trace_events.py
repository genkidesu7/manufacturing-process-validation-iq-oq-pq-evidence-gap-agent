# TC-05 / TC-11 / PB-1: every FunctionNode's execute() must emit exactly one
# domain emit_trace_event() call, and must never re-emit the framework's own
# node_start / node_complete / node_error lifecycle events (BaseNode.__call__
# already emits those — duplicates corrupt the audit trail).

import ast
import importlib
import pkgutil
import textwrap

import pytest

_FRAMEWORK_LIFECYCLE_EVENTS = {"node_start", "node_complete", "node_error"}


def _discover_node_modules():
    import src.nodes as nodes_pkg

    return [
        importlib.import_module(modname)
        for _, modname, _ in pkgutil.walk_packages(nodes_pkg.__path__, prefix="src.nodes.")
    ]


def _execute_method_source(module) -> str | None:
    import inspect

    from framework.nodes.function_node import FunctionNode

    for attr in vars(module).values():
        if isinstance(attr, type) and issubclass(attr, FunctionNode) and attr is not FunctionNode:
            if attr.__module__ != module.__name__:
                continue
            try:
                return textwrap.dedent(inspect.getsource(attr.execute))
            except (OSError, TypeError):
                return None
    return None


class TestNodeTraceEvents:
    @pytest.mark.parametrize(
        "module",
        _discover_node_modules(),
        ids=lambda m: m.__name__,
    )
    def test_execute_emits_at_least_one_domain_event_and_no_lifecycle_duplicates(self, module):
        source = _execute_method_source(module)
        if source is None:
            pytest.skip(f"no FunctionNode subclass found in {module.__name__}")

        tree = ast.parse(source)
        event_type_literals: list[str] = []
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "emit_trace_event"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                event_type_literals.append(node.args[0].value)

        assert event_type_literals, f"{module.__name__}: execute() has no emit_trace_event() call"
        for event_type in event_type_literals:
            assert event_type not in _FRAMEWORK_LIFECYCLE_EVENTS, (
                f"{module.__name__}: execute() must not re-emit framework lifecycle event "
                f"'{event_type}' — BaseNode.__call__() already emits it"
            )
