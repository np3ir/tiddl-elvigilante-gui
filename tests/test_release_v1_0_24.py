"""Documentation / version / pin guards for the GUI v1.0.24 source release.

These verify the release paperwork and the invariants of a version bump WITHOUT
fragile first-match text search: `APP_VERSION` and `TIDDL_COMMIT` are checked via
AST (module-scope, single-assignment), the engine pin via an exact-commit regex,
and the "B1 stays 62 / B2 stays 41" coverage floors via a deterministic AST
pytest-case counter (test functions × parametrize expansion). No build, install,
tag, Release or publication is implied by any of this.
"""
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANGELOG = os.path.join(ROOT, "CHANGELOG_1.0.24.md")
NOTES = os.path.join(ROOT, "RELEASE_NOTES_v1.0.24.md")
MAIN = os.path.join(ROOT, "main.py")
REQ = os.path.join(ROOT, "requirements.txt")

ENGINE_PIN = "13c4e9151cc3fb41954ca5312f11c5d34e2ad181"


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# 1 & 2: the release files exist
# ---------------------------------------------------------------------------
def test_changelog_1_0_24_exists():
    assert os.path.isfile(CHANGELOG)


def test_release_notes_v1_0_24_exists():
    assert os.path.isfile(NOTES)


# ---------------------------------------------------------------------------
# 3: both carry EN and ES content
# ---------------------------------------------------------------------------
def test_changelog_has_en_and_es_sections():
    t = _read(CHANGELOG)
    assert "## What's new" in t and "## Novedades" in t


def test_notes_have_en_and_es_sections():
    t = _read(NOTES)
    assert "🇬🇧 What's new" in t and "🇪🇸 Novedades" in t


# ---------------------------------------------------------------------------
# 4, 5, 6: the notes mention engine v1.5.5, B1, and B2 (off/strict)
# ---------------------------------------------------------------------------
def test_notes_mention_engine_v1_5_5():
    t = _read(NOTES)
    assert "v1.5.5" in t
    assert ENGINE_PIN in t  # the exact bundled commit


def test_notes_mention_b1():
    t = _read(NOTES)
    low = t.lower()
    assert "b1" in low
    assert ("destination identity" in low) or ("identidad del destino" in low)
    # the confirmations and no-auto-run contract are stated
    assert "adopt" in low and "trust" in low


def test_notes_mention_b2_off_and_strict():
    t = _read(NOTES)
    low = t.lower()
    assert "b2" in low
    assert "off" in low and "strict" in low
    assert "destination_identity" in t


def _norm_ws(text):
    # Markdown wraps prose across lines; collapse whitespace so a content check is
    # not defeated by an incidental line break inside a phrase.
    return re.sub(r"\s+", " ", text)


def test_notes_state_path_captured_contract_in_both_languages():
    # The path-capture safety contract must be stated in BOTH the EN and ES notes.
    t = _norm_ws(_read(NOTES))
    assert "captured and used exactly for the operation" in t
    assert "captura y usa exactamente para la operación" in t


def test_adopt_revalidation_timing_is_precise_in_both_docs():
    # Adopt re-validates before OPENING the confirmation flow — not "immediately
    # before confirming". The precise, parallel EN/ES wording must be present in
    # both docs, and the over-strict wording must be gone.
    for path in (CHANGELOG, NOTES):
        t = _norm_ws(_read(path))
        assert "before opening the confirmation flow" in t
        assert "antes de abrir el flujo de confirmación" in t
        for bad in (
            "immediately before confirming",
            "just before confirming",
            "justo antes de confirmar",
        ):
            assert bad not in t, (path, bad)


# ---------------------------------------------------------------------------
# 7 & 8: distinguish public 1.0.23 from unpublished 1.0.24, and never present
# v1.5.4 as the engine of 1.0.24.
# ---------------------------------------------------------------------------
def _distinguishes_public_from_prepared(text):
    low = text.lower()
    has_both_versions = "1.0.23" in text and "1.0.24" in text
    not_yet = any(p in low for p in ("not yet", "todavía", "no publicada", "no publicado",
                                     "not been built", "not built"))
    return has_both_versions and not_yet


def test_changelog_distinguishes_public_and_prepared():
    assert _distinguishes_public_from_prepared(_read(CHANGELOG))


def test_notes_distinguish_public_and_prepared():
    assert _distinguishes_public_from_prepared(_read(NOTES))


def test_no_doc_line_calls_v1_0_24_a_v1_5_4_engine():
    # No single line may claim 1.0.24 is powered by v1.5.4 (the mistaken claim).
    for path in (CHANGELOG, NOTES):
        for line in _read(path).splitlines():
            assert not ("1.0.24" in line and "v1.5.4" in line), (path, line)


def test_docs_bind_1_0_24_to_v1_5_5_and_public_1_0_23_to_v1_5_4():
    for path in (CHANGELOG, NOTES):
        low = _read(path).lower()
        assert "1.0.24" in low and "v1.5.5" in low
        # the public artifact is explicitly v1.5.4
        assert "1.0.23" in low and "v1.5.4" in low


# ---------------------------------------------------------------------------
# AST guards: reuse the ROBUST single-source binder/checkers from
# test_engine_pin.py — they detect Assign, AnnAssign (with value) AND AugAssign
# at module scope (including inside module-level if/try/with), excluding function
# and class bodies. Reusing them avoids a second, weaker implementation here.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(ROOT, "tests"))
from test_engine_pin import (  # noqa: E402
    _app_version_ok,
    _module_scope_bindings,
    _tiddl_commit_ok,
    EXPECTED_APP_VERSION,
)


# ---------------------------------------------------------------------------
# 9: APP_VERSION — exactly one module-scope assignment, value "1.0.24"
# ---------------------------------------------------------------------------
def test_app_version_single_module_assignment_is_1_0_24():
    assert EXPECTED_APP_VERSION == "1.0.24"
    assert _app_version_ok(_read(MAIN))
    binds = _module_scope_bindings(_read(MAIN), "APP_VERSION")
    assert len(binds) == 1 and isinstance(binds[0], ast.Assign)
    assert binds[0].value.value == "1.0.24"


# ---------------------------------------------------------------------------
# 10: the engine pin is the exact v1.5.5 commit
# ---------------------------------------------------------------------------
def test_engine_pin_is_exactly_v1_5_5_commit():
    m = re.search(
        r"tiddl-elvigilante\s*@\s*git\+https://github\.com/np3ir/"
        r"tiddl-elvigilante\.git@([0-9a-f]{40})",
        _read(REQ),
    )
    assert m and m.group(1) == ENGINE_PIN


# ---------------------------------------------------------------------------
# 11: TIDDL_COMMIT is derived from _tiddl_commit(), not hardcoded
# ---------------------------------------------------------------------------
def test_tiddl_commit_is_a_derived_call_not_hardcoded():
    assert _tiddl_commit_ok(_read(MAIN))


# ---------------------------------------------------------------------------
# Negative AST guards: a SECOND module-scope binding via AnnAssign / AugAssign /
# a module-level override must be rejected (this is exactly what an Assign-only
# guard would miss).
# ---------------------------------------------------------------------------
_APP_ASSIGN_THEN_ANNASSIGN = 'APP_VERSION = "1.0.24"\nAPP_VERSION: str = "9.9.9"\n'
_APP_ASSIGN_THEN_AUGASSIGN = 'APP_VERSION = "1.0.24"\nAPP_VERSION += ".broken"\n'
_APP_OVERRIDDEN_IN_MODULE_IF = 'APP_VERSION = "1.0.24"\nif True:\n    APP_VERSION = "9.9.9"\n'
_TIDDL_DERIVED_THEN_ANNASSIGN = 'TIDDL_COMMIT = _tiddl_commit()\nTIDDL_COMMIT: str = "deadbeef"\n'
_TIDDL_DERIVED_THEN_AUGASSIGN = 'TIDDL_COMMIT = _tiddl_commit()\nTIDDL_COMMIT += "x"\n'


def test_app_version_annassign_second_binding_is_rejected():
    assert _app_version_ok(_APP_ASSIGN_THEN_ANNASSIGN) is False
    assert len(_module_scope_bindings(_APP_ASSIGN_THEN_ANNASSIGN, "APP_VERSION")) == 2


def test_app_version_augassign_second_binding_is_rejected():
    assert _app_version_ok(_APP_ASSIGN_THEN_AUGASSIGN) is False
    assert len(_module_scope_bindings(_APP_ASSIGN_THEN_AUGASSIGN, "APP_VERSION")) == 2


def test_app_version_module_level_if_override_is_rejected():
    assert _app_version_ok(_APP_OVERRIDDEN_IN_MODULE_IF) is False
    assert len(_module_scope_bindings(_APP_OVERRIDDEN_IN_MODULE_IF, "APP_VERSION")) == 2


def test_tiddl_commit_annassign_hardcode_second_binding_is_rejected():
    assert _tiddl_commit_ok(_TIDDL_DERIVED_THEN_ANNASSIGN) is False
    assert len(_module_scope_bindings(_TIDDL_DERIVED_THEN_ANNASSIGN, "TIDDL_COMMIT")) == 2


def test_tiddl_commit_augassign_second_binding_is_rejected():
    assert _tiddl_commit_ok(_TIDDL_DERIVED_THEN_AUGASSIGN) is False
    assert len(_module_scope_bindings(_TIDDL_DERIVED_THEN_AUGASSIGN, "TIDDL_COMMIT")) == 2


# ---------------------------------------------------------------------------
# 12 & 13: the B1 / B2 suites keep their exact coverage (deterministic AST
# case count = test functions × parametrize expansion, matches pytest).
# ---------------------------------------------------------------------------
def _count_pytest_cases(path):
    tree = ast.parse(_read(path))
    total = 0
    for node in tree.body:  # module-level test functions only
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            factor = 1
            for dec in node.decorator_list:
                if (
                    isinstance(dec, ast.Call)
                    and isinstance(dec.func, ast.Attribute)
                    and dec.func.attr == "parametrize"
                    and len(dec.args) >= 2
                    and isinstance(dec.args[1], (ast.List, ast.Tuple))
                ):
                    factor *= len(dec.args[1].elts)
            total += factor
    return total


def test_b1_suite_still_has_62_cases():
    assert _count_pytest_cases(os.path.join(ROOT, "tests", "test_destination_b1.py")) == 62


def test_b2_suite_still_has_41_cases():
    assert _count_pytest_cases(os.path.join(ROOT, "tests", "test_destination_b2.py")) == 41


# ---------------------------------------------------------------------------
# 14: full EN/ES STRINGS parity is preserved
# ---------------------------------------------------------------------------
def test_en_es_strings_parity_preserved():
    import sys

    sys.path.insert(0, ROOT)
    import main  # noqa: E402

    assert set(main.STRINGS["en"]) == set(main.STRINGS["es"])
