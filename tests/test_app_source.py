# this_file: tests/test_app_source.py
# ruff: noqa: S102 - execute adapted fixture ASTs to test frame semantics
"""Source adaptation must retain evaluation order, locations and originals."""

import ast
import traceback

import pytest

from pythonqtside._app_source import adapt_source


def test_adaptation_when_method_call_has_arguments_then_callee_resolves_first():
    source = "result = receiver().method(argument())\n"
    events = []
    namespace = {
        "receiver": lambda: events.append("receiver") or object(),
        "argument": lambda: events.append("argument") or 7,
        "resolve": lambda obj, name: events.append("resolve") or (lambda value: value),
        "call": lambda function: function,
    }
    tree, report = adapt_source(
        source, "owned.py", call_name="call", resolve_name="resolve"
    )
    exec(compile(tree, "owned.py", "exec"), namespace)
    assert events == ["receiver", "resolve", "argument"], (
        "Python evaluation order must survive adaptation"
    )
    assert namespace["result"] == 7
    assert report["call_sites"] == 3
    assert report["locations"][0]["line"] == 1
    assert source == "result = receiver().method(argument())\n", (
        "original source must stay intact"
    )


def test_adaptation_when_future_import_and_error_exist_then_original_line_is_kept():
    tree, report = adapt_source(
        "from __future__ import annotations\nvalue = missing()\n",
        "original.py",
        call_name="call",
        resolve_name="resolve",
    )
    assert (
        ast.get_source_segment(report["original_source"], tree.body[0])
        == "from __future__ import annotations"
    )
    assert tree.body[1].lineno == 2
    assert report["source_sha256"] != "", "original identity must be recorded"


def test_adaptation_when_zero_argument_super_or_locals_used_then_original_frame_survives():
    source = """class Base:
    def value(self): return 7
class Child(Base):
    def value(self):
        own = 11
        return super().value(), locals()["own"]
result = Child().value()
"""
    namespace = {"call": lambda function: function, "resolve": getattr}
    tree, _ = adapt_source(source, "frame.py", call_name="call", resolve_name="resolve")
    exec(compile(tree, "frame.py", "exec"), namespace)
    assert namespace["result"] == (7, 11), (
        "super and locals depend on the original Python frame"
    )


def test_adaptation_when_frame_builtins_are_aliased_then_caller_frame_survives():
    source = """import builtins
alias = builtins.locals
execute = exec
evaluate = eval
class Base:
    def value(self): return 9
class Child(Base):
    def value(self):
        own = 11
        execute(\"extra = 13\")
        return super().value(), alias()[\"own\"], evaluate(\"own + 1\"), vars()[\"extra\"], \"own\" in dir(), globals()[\"alias\"] is alias
result = Child().value()
"""
    namespace = {"call": lambda function: function, "resolve": getattr}
    tree, _ = adapt_source(
        source, "aliases.py", call_name="call", resolve_name="resolve"
    )
    exec(compile(tree, "aliases.py", "exec"), namespace)
    assert namespace["result"] == (9, 11, 12, 13, True, True), (
        "aliased frame builtins must execute in the source frame"
    )


def test_adaptation_when_source_raises_then_traceback_uses_original_filename_and_line():
    source = "value = 1\nraise ValueError('original line')\n"
    tree, _ = adapt_source(
        source, "original_identity.py", call_name="call", resolve_name="resolve"
    )
    with pytest.raises(ValueError) as caught:
        exec(
            compile(tree, "original_identity.py", "exec"),
            {"call": lambda function: function},
        )
    final = traceback.extract_tb(caught.value.__traceback__)[-1]
    assert (final.filename, final.lineno) == ("original_identity.py", 2), (
        "traceback identity must remain original"
    )


@pytest.mark.parametrize(
    "source, expected",
    [
        ("receiver.method()\n", []),
        (
            "super().method(); super(Cls, self).other()\n",
            [{"line": 1, "column": 0}, {"line": 1, "column": 18}],
        ),
    ],
)
def test_adaptation_when_super_method_calls_are_rewritten_then_sites_are_reported(
    source: str,
    expected: list[dict[str, int]],
) -> None:
    _, report = adapt_source(
        source, "sites.py", call_name="call", resolve_name="resolve"
    )
    assert report["super_call_sites"] == len(expected)
    assert report["super_locations"] == expected, (
        "super provenance counts syntactic call sites, not runtime fallback uses"
    )
