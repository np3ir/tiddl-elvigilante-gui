"""Host-safe handling of the engine's cooperative-stop exit (engine v1.5.3+).

A cooperative safety stop — Cancel, a TIDAL rate-limit (429) or a flagged/blocked
account (401) — now reaches the in-process host as `click.exceptions.Exit`
instead of a process-killing `sys.exit()`. `run_tiddl()` must:

* convert that Exit into a return code (`int(exc.exit_code or 0)`),
* keep the host process alive and reusable for the next in-process run,
* keep the defensive `SystemExit` handling, and
* always restore `sys.stdout`, `sys.stderr` and `sys.argv` in `finally`.

These tests drive the REAL `run_tiddl` and only substitute the bundled engine's
Typer app object (`tiddl.cli.app.app`) so no auth/network is needed.
"""
import os
import sys

import click
import pytest

# main.py lives at the GUI repo root (one level up from tests/).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main  # noqa: E402
import tiddl.cli.app as tiddl_app_mod  # noqa: E402


def _noop(_line):
    pass


def _set_engine_app(monkeypatch, fn):
    # run_tiddl does `from tiddl.cli.app import app as tiddl_app` at call time, so
    # patching tiddl.cli.app.app controls exactly what the real run_tiddl invokes.
    monkeypatch.setattr(tiddl_app_mod, "app", fn)


def _raise_cooperative_exit(*args, **kwargs):
    # What the engine's download group's call_on_close raises on a cooperative stop.
    raise click.exceptions.Exit(1)


def _clean_run(*args, **kwargs):
    return None


def test_cooperative_exit_1_becomes_return_1(monkeypatch):
    _set_engine_app(monkeypatch, _raise_cooperative_exit)
    assert main.run_tiddl(["download", "url", "track/1"], _noop) == 1


def test_host_survives_cooperative_stop(monkeypatch):
    # "Survives" = run_tiddl RETURNS an int instead of the process exiting. If the
    # Exit escaped (or a SystemExit propagated), this call would not return here.
    _set_engine_app(monkeypatch, _raise_cooperative_exit)
    result = main.run_tiddl(["download", "url", "track/1"], _noop)
    assert isinstance(result, int) and result == 1


def test_second_in_process_run_returns_zero(monkeypatch):
    # 1st run: cooperative stop -> 1; 2nd run in the SAME process -> clean 0.
    _set_engine_app(monkeypatch, _raise_cooperative_exit)
    assert main.run_tiddl(["download", "url", "track/1"], _noop) == 1
    _set_engine_app(monkeypatch, _clean_run)
    assert main.run_tiddl(["download", "url", "track/1"], _noop) == 0


@pytest.mark.parametrize("code, expected", [(2, 2), (None, 0), ("boom", 1)])
def test_defensive_systemexit_still_handled(monkeypatch, code, expected):
    def _raise_systemexit(*args, **kwargs):
        raise SystemExit(code)

    _set_engine_app(monkeypatch, _raise_systemexit)
    assert main.run_tiddl(["download", "url", "track/1"], _noop) == expected


@pytest.mark.parametrize("engine_app", [_raise_cooperative_exit, _clean_run])
def test_streams_and_argv_always_restored(monkeypatch, engine_app):
    _set_engine_app(monkeypatch, engine_app)
    saved_out, saved_err, saved_argv = sys.stdout, sys.stderr, sys.argv
    main.run_tiddl(["download", "url", "track/1"], _noop)
    assert sys.stdout is saved_out
    assert sys.stderr is saved_err
    assert sys.argv is saved_argv
