"""Pure-helper tests for watch scan status/message sanitising (INF-7178/7179).

Helpers are extracted from source via ast so the test runs without the
heavy app import graph (celery, DB).
"""
import ast
import pathlib

_SRC = pathlib.Path(__file__).resolve().parents[2] / "app" / "tasks" / "watch_source_tasks.py"


def _load(*names):
    tree = ast.parse(_SRC.read_text())
    body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in body} == set(names)
    ns = {}
    exec(compile(ast.Module(body=body, type_ignores=[]), str(_SRC), "exec"), ns)
    return ns


NS = _load("_scan_outcome", "_safe_scan_failure")


def test_partial_failure_is_error():
    status, msg = NS["_scan_outcome"]({"found": 3, "imported": 2, "skipped": 0, "errors": 1})
    assert status == "error" and "errors 1" in msg


def test_clean_scan_is_success():
    status, msg = NS["_scan_outcome"]({"found": 3, "imported": 3, "skipped": 0, "errors": 0})
    assert status == "success" and "errors" not in msg


def test_missing_keys_default_zero():
    assert NS["_scan_outcome"]({}) == ("success", "Found 0, imported 0, skipped 0")


def test_failure_message_hides_exception_text():
    class EndpointConnectionError(Exception):
        pass

    leaked = "http://storage:9000/b?X-Amz-Signature=abc123&token=zzz"
    msg = NS["_safe_scan_failure"]("setup", EndpointConnectionError(leaked))
    assert "abc123" not in msg and "zzz" not in msg and "http" not in msg
    assert "EndpointConnectionError" in msg and len(msg) < 200


def test_hostile_class_name_is_bounded():
    exc = type("X" * 500 + "://?", (Exception,), {})("boom")
    msg = NS["_safe_scan_failure"]("transport", exc)
    assert "://" not in msg and len(msg) < 200
