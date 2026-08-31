"""Guard the bundled-engine pin and the app version against accidental drift.

The GUI ships tiddl in-process (single binary); `requirements.txt` is the SINGLE
source of truth for which engine commit is bundled. `TIDDL_COMMIT` is derived at
RUNTIME from the installed package's `direct_url.json` (see `main._tiddl_commit`),
so it is deliberately NOT duplicated. 1.0.24 is pinned to engine **v1.5.5**.

`main.py` is checked by parsing its SOURCE with `ast` — never imported (no
`flet`/`tiddl` needed) — and, per the Sourcery finding, we require EXACTLY ONE
module-scope assignment for each variable, so a later re-assignment that would
override the value cannot slip past a first-match text search.
"""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The exact engine commit published as v1.5.5 (post-merge tiddl-elvigilante main).
ENGINE_V1_5_5_COMMIT = "13c4e9151cc3fb41954ca5312f11c5d34e2ad181"
EXPECTED_APP_VERSION = "1.0.24"


def _requirements_text() -> str:
    return (ROOT / "requirements.txt").read_text(encoding="utf-8")


def _main_text() -> str:
    return (ROOT / "main.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# The engine pin (requirements.txt)
# ---------------------------------------------------------------------------
def test_engine_pinned_to_v1_5_5_commit():
    m = re.search(
        r"tiddl-elvigilante\s*@\s*git\+https://github\.com/np3ir/"
        r"tiddl-elvigilante\.git@([0-9a-f]{40})",
        _requirements_text(),
    )
    assert m, "engine pin line not found or not a full 40-hex commit"
    assert m.group(1) == ENGINE_V1_5_5_COMMIT


def test_pin_is_a_single_immutable_commit_not_a_branch_or_tag():
    pins = re.findall(r"tiddl-elvigilante\s*@\s*git\+\S+@(\S+)", _requirements_text())
    assert len(pins) == 1, f"expected exactly one engine pin, got {pins!r}"
    assert re.fullmatch(r"[0-9a-f]{40}", pins[0]), (
        f"pin must be a full commit sha, not a branch/tag: {pins[0]!r}"
    )


# ---------------------------------------------------------------------------
# AST: module-scope bindings of a name (excludes function/class bodies)
# ---------------------------------------------------------------------------
def _module_scope_bindings(source: str, name: str) -> list:
    """Every statement that binds/mutates `name` at MODULE scope — top level or
    inside module-level control flow (`if`/`try`/…), but NOT inside any function
    or class body. Returns the Assign / AnnAssign(with value) / AugAssign nodes."""
    found: list = []

    class _V(ast.NodeVisitor):
        # Do not descend into nested scopes: those bindings are not module-level.
        def visit_FunctionDef(self, node):  # noqa: N802
            return

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, node):  # noqa: N802
            return

        def visit_Assign(self, node):  # noqa: N802
            if any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
                found.append(node)
            self.generic_visit(node)

        def visit_AnnAssign(self, node):  # noqa: N802
            if (
                isinstance(node.target, ast.Name)
                and node.target.id == name
                and node.value is not None
            ):
                found.append(node)
            self.generic_visit(node)

        def visit_AugAssign(self, node):  # noqa: N802
            if isinstance(node.target, ast.Name) and node.target.id == name:
                found.append(node)
            self.generic_visit(node)

    _V().visit(ast.parse(source))
    return found


def _app_version_ok(source: str) -> bool:
    """True iff exactly ONE module-scope assignment of APP_VERSION exists and its
    literal value is EXPECTED_APP_VERSION."""
    binds = _module_scope_bindings(source, "APP_VERSION")
    if len(binds) != 1 or not isinstance(binds[0], ast.Assign):
        return False
    value = binds[0].value
    return (
        isinstance(value, ast.Constant)
        and isinstance(value.value, str)
        and value.value == EXPECTED_APP_VERSION
    )


def _tiddl_commit_ok(source: str) -> bool:
    """True iff exactly ONE module-scope assignment of TIDDL_COMMIT exists and its
    value is exactly a no-argument call to `_tiddl_commit()`."""
    binds = _module_scope_bindings(source, "TIDDL_COMMIT")
    if len(binds) != 1 or not isinstance(binds[0], ast.Assign):
        return False
    value = binds[0].value
    return (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id == "_tiddl_commit"
        and not value.args
        and not value.keywords
    )


# ---------------------------------------------------------------------------
# Positive: the real main.py
# ---------------------------------------------------------------------------
def test_app_version_single_module_assignment_is_1_0_24():
    assert _app_version_ok(_main_text())


def test_tiddl_commit_single_module_assignment_is_derived_call():
    assert _tiddl_commit_ok(_main_text())


def test_reference_source_passes_both_checks():
    good = 'APP_VERSION = "1.0.24"\nTIDDL_COMMIT = _tiddl_commit()\n'
    assert _app_version_ok(good)
    assert _tiddl_commit_ok(good)


# ---------------------------------------------------------------------------
# Negative: synthetic sources with a duplicate/overriding assignment are rejected
# (these are exactly what a first-match text search would have wrongly accepted)
# ---------------------------------------------------------------------------
_DUP_APP_VERSION = 'APP_VERSION = "1.0.24"\nAPP_VERSION = "9.9.9"\n'
_APP_VERSION_OVERRIDDEN_IN_IF = (
    'APP_VERSION = "1.0.24"\nif True:\n    APP_VERSION = "9.9.9"\n'
)
_APP_VERSION_WRONG_VALUE = 'APP_VERSION = "9.9.9"\n'
_TIDDL_HARDCODED_AFTER = 'TIDDL_COMMIT = _tiddl_commit()\nTIDDL_COMMIT = "deadbeef"\n'
_TIDDL_WITH_ARGS = 'TIDDL_COMMIT = _tiddl_commit("x")\n'
_TIDDL_NOT_A_CALL = 'TIDDL_COMMIT = "deadbeef"\n'


def test_duplicate_app_version_assignment_is_rejected():
    assert _app_version_ok(_DUP_APP_VERSION) is False


def test_module_level_override_of_app_version_is_rejected():
    assert _app_version_ok(_APP_VERSION_OVERRIDDEN_IN_IF) is False


def test_wrong_app_version_value_is_rejected():
    assert _app_version_ok(_APP_VERSION_WRONG_VALUE) is False


def test_hardcoded_reassignment_of_tiddl_commit_is_rejected():
    assert _tiddl_commit_ok(_TIDDL_HARDCODED_AFTER) is False


def test_tiddl_commit_with_arguments_is_rejected():
    assert _tiddl_commit_ok(_TIDDL_WITH_ARGS) is False


def test_tiddl_commit_not_a_call_is_rejected():
    assert _tiddl_commit_ok(_TIDDL_NOT_A_CALL) is False
