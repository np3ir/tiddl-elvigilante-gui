"""Real-Flet compatibility tests for the B2 destination-identity selector.

The v1.0.24 Windows smoke crashed at startup with
`TypeError: Dropdown.__init__() got an unexpected keyword argument 'on_change'`
because `build_settings_tab` built the B2 selector as
`ft.Dropdown(..., on_change=self.on_dest_mode_change)`. The bundled Flet (0.86.1)
does NOT accept `on_change` as a `Dropdown` constructor keyword — the handler must
be attached AFTER construction, as an attribute (the pattern already used for
`f_cover_save`).

Unlike the other B2 tests, which stub controls with `SimpleNamespace` and so could
never see this, these tests instantiate REAL `ft.Dropdown` objects using the same
Flet version the build packages. They fail against the old constructor pattern and
pass against the fixed post-construction binding.
"""
import ast
import importlib.metadata as _md
import os
import sys

import pytest

import flet as ft  # the same package the Windows build bundles (0.86.1)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(ROOT, "main.py")


# --- the Flet version under test matches the one the build packages ---------
def test_flet_version_is_the_bundled_one():
    """These tests only prove compatibility for the Flet the build ships. If the
    environment's Flet drifts away from 0.86.x the guarantee no longer holds and
    the coupling must be revisited (the build must not silently move Flet)."""
    ver = _md.version("flet")
    assert ver.startswith("0.86."), (
        f"expected the build-bundled Flet 0.86.x, got {ver!r}; the real-ctor "
        "assertions below are only valid for the packaged version"
    )


# --- 1. the real Flet Dropdown constructor rejects on_change ----------------
def test_real_dropdown_constructor_rejects_on_change_kwarg():
    """The exact failure the smoke hit: passing on_change to the constructor of a
    real ft.Dropdown raises TypeError. This is what crashed build_settings_tab."""
    with pytest.raises(TypeError):
        ft.Dropdown(
            label="Mode",
            width=220,
            value="off",
            options=[
                ft.DropdownOption(key="off", text="Off"),
                ft.DropdownOption(key="strict", text="Strict"),
            ],
            on_change=lambda e: None,
        )


# --- 2. the compatible pattern (attribute after construction) works ---------
def test_real_dropdown_attribute_binding_pattern_works():
    """Constructing WITHOUT on_change and then assigning it as an attribute does
    not raise, binds the handler, and preserves value/options — the pattern the
    fix uses (mirrors f_cover_save.on_change = ...)."""
    handler = lambda e: None  # noqa: E731
    dd = ft.Dropdown(
        label="Mode",
        width=220,
        value="off",
        options=[
            ft.DropdownOption(key="off", text="Off"),
            ft.DropdownOption(key="strict", text="Strict"),
        ],
    )
    dd.on_change = handler
    assert dd.on_change is handler
    assert dd.value == "off"
    assert [o.key for o in dd.options] == ["off", "strict"]


# --- 3. the REAL code path: main.build_dest_mode_dropdown with real Flet -----
def test_build_dest_mode_dropdown_builds_real_flet_control():
    """Exercise the actual helper build_settings_tab uses, with a real ft.Dropdown.
    A regression that moves on_change back into the constructor makes THIS call
    raise TypeError, so the crash cannot silently return."""
    handler = lambda e: None  # noqa: E731
    dd = main.build_dest_mode_dropdown("Mode", "strict", "Off", "Strict", handler)
    assert isinstance(dd, ft.Dropdown)
    assert dd.on_change is handler          # handler bound (post-construction)
    assert dd.value == "strict"             # seeded value preserved
    assert dd.width == 220
    assert dd.label == "Mode"
    assert [o.key for o in dd.options] == ["off", "strict"]
    assert [o.text for o in dd.options] == ["Off", "Strict"]


def test_build_dest_mode_dropdown_accepts_off_value():
    handler = lambda e: None  # noqa: E731
    dd = main.build_dest_mode_dropdown("M", "off", "O", "S", handler)
    assert dd.value == "off"
    assert dd.on_change is handler


# --- 4. complementary AST guard on the real main.py source ------------------
def _load_main_ast():
    with open(MAIN_PY, "r", encoding="utf-8") as fh:
        return ast.parse(fh.read())


def _func(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function {name} not found in main.py")


def _dropdown_calls(node):
    """Every ft.Dropdown(...) call inside a function body."""
    out = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
           and sub.func.attr == "Dropdown":
            out.append(sub)
    return out


def test_helper_never_passes_on_change_to_constructor():
    """In build_dest_mode_dropdown, the ft.Dropdown(...) call must NOT carry an
    on_change keyword, and the handler must be bound via a `<x>.on_change = ...`
    assignment. Catches a regression at the source, not just at runtime."""
    fn = _func(_load_main_ast(), "build_dest_mode_dropdown")
    for call in _dropdown_calls(fn):
        kwnames = [k.arg for k in call.keywords]
        assert "on_change" not in kwnames, (
            "on_change must not be a Dropdown constructor kwarg (Flet 0.86.1 "
            "rejects it and crashes the settings tab)"
        )
    # an attribute-style on_change assignment must exist in the helper
    attr_binds = [
        n for n in ast.walk(fn)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Attribute) and t.attr == "on_change" for t in n.targets)
    ]
    assert attr_binds, "helper must bind on_change as an attribute after construction"


def test_build_settings_tab_uses_the_helper_not_a_raw_dropdown():
    """The selector must be built through build_dest_mode_dropdown, and no raw
    ft.Dropdown(...) inside build_settings_tab may pass on_change (which is what
    the smoke crash was)."""
    fn = _func(_load_main_ast(), "build_settings_tab")
    # no ft.Dropdown(...) in the settings tab may carry on_change
    for call in _dropdown_calls(fn):
        assert "on_change" not in [k.arg for k in call.keywords], (
            "build_settings_tab must not pass on_change to any Dropdown constructor"
        )
    # f_dest_mode must be assigned from a build_dest_mode_dropdown(...) call
    helper_used = False
    for n in ast.walk(fn):
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call):
            callee = n.value.func
            if isinstance(callee, ast.Name) and callee.id == "build_dest_mode_dropdown":
                for t in n.targets:
                    if isinstance(t, ast.Attribute) and t.attr == "f_dest_mode":
                        helper_used = True
    assert helper_used, "f_dest_mode must be built via build_dest_mode_dropdown(...)"
