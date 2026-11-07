"""The update button (and the GitHub / login links) opened nothing in 1.0.26.

In Flet 0.86 ``Page.launch_url`` is a coroutine function. ``on_click=lambda e:
page.launch_url(url)`` only created a coroutine that was never awaited, so the
click silently did nothing. All callers must go through ``TiddlGui.open_url``,
which schedules it with ``page.run_task``.
"""
import ast
import inspect
from pathlib import Path

import flet as ft

MAIN = Path(__file__).resolve().parent.parent / "main.py"


def test_flet_launch_url_is_a_coroutine_function():
    # The decorator hides it from inspect.iscoroutinefunction, so unwrap first.
    fn = inspect.unwrap(ft.Page.launch_url)
    assert inspect.iscoroutinefunction(fn) or inspect.iscoroutinefunction(
        ft.Page.launch_url
    ) or "async def" in inspect.getsource(ft.Page.launch_url)


def _launch_url_uses():
    tree = ast.parse(MAIN.read_text(encoding="utf-8"))
    uses = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Attribute) and sub.attr == "launch_url":
                    uses.append((node.name, sub.lineno))
    return uses


def test_launch_url_only_referenced_inside_the_async_helper():
    # Page.launch_url is async and run_task rejects it (deprecated wrapper), so
    # no other function in main.py may reference a `.launch_url` attribute.
    names = {name for name, _ in _launch_url_uses()}
    assert names == {"_launch_url"}, names


def test_open_url_schedules_a_real_coroutine_function():
    src = MAIN.read_text(encoding="utf-8")
    assert "self.page.run_task(self._launch_url, url)" in src
    assert "await ft.UrlLauncher().launch_url(url)" in src


def test_run_task_accepts_the_helper_but_rejects_page_launch_url():
    class _P:  # mimic what run_task checks
        pass

    async def _launch_url(url):
        return None

    assert inspect.iscoroutinefunction(_launch_url)
    assert not inspect.iscoroutinefunction(ft.Page.launch_url)  # why it was rejected
    assert inspect.iscoroutinefunction(ft.UrlLauncher.launch_url)
