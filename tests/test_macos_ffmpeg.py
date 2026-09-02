"""Offline tests for the macOS external-FFmpeg model (GUI v1.0.24).

macOS stops bundling FFmpeg inside the .app/DMG (parity with Linux): the user
installs it (`brew install ffmpeg`) and the GUI resolves it at runtime. These
tests exercise the resolver, its priority order, the validation rules, the
bilingual missing-FFmpeg message, the host-survival behaviour, and the packaging
guards in release_macos.sh. They are CI-safe (no Homebrew, no real ffmpeg,
cross-platform): filesystem/subprocess touch points are injected or monkeypatched.
"""
import ast
import os
import stat
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # test_engine_pin helpers
import main  # noqa: E402
import test_engine_pin as tep  # noqa: E402  reuse the robust AST binder

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(ROOT, "main.py")
RELEASE_MACOS = os.path.join(ROOT, "release_macos.sh")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


def _make_exec(tmp_path, name="ffmpeg", body="#!/bin/sh\nexit 0\n"):
    p = tmp_path / name
    p.write_text(body)
    os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return str(p)


# --- resolution priority (inject validate → no fs/subprocess needed) --------
def _validate_only(*allowed):
    allowed = {os.path.abspath(a) for a in allowed}
    return lambda p: (os.path.abspath(p) if os.path.abspath(p) in allowed else None)


def test_01_finds_via_explicit_override(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda *a, **k: None)
    env = {"TIDDL_FFMPEG": "/custom/ffmpeg", "PATH": ""}
    got = main.resolve_ffmpeg(env=env, validate=_validate_only("/custom/ffmpeg"))
    assert got == os.path.abspath("/custom/ffmpeg")


def test_02_finds_via_path(monkeypatch, tmp_path):
    ff = _make_exec(tmp_path)
    monkeypatch.setattr(main.shutil, "which", lambda name, path=None: ff if name == "ffmpeg" else None)
    got = main.resolve_ffmpeg(env={"PATH": str(tmp_path), "TIDDL_FFMPEG": ""},
                              validate=lambda p: main.valid_ffmpeg(p, version_check=lambda _p: True))
    assert got == os.path.realpath(ff)


def test_03_finds_homebrew_apple_silicon_with_minimal_path(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda *a, **k: None)  # Finder-minimal PATH
    got = main.resolve_ffmpeg(env={"PATH": "/usr/bin:/bin", "TIDDL_FFMPEG": ""},
                              validate=_validate_only("/opt/homebrew/bin/ffmpeg"))
    assert got == os.path.abspath("/opt/homebrew/bin/ffmpeg")


def test_04_finds_homebrew_intel_with_minimal_path(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda *a, **k: None)
    got = main.resolve_ffmpeg(env={"PATH": "/usr/bin:/bin", "TIDDL_FFMPEG": ""},
                              validate=_validate_only("/usr/local/bin/ffmpeg"))
    assert got == os.path.abspath("/usr/local/bin/ffmpeg")


def test_05_priority_order_override_beats_the_rest(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda *a, **k: "/usr/bin/ffmpeg")
    env = {"TIDDL_FFMPEG": "/custom/ffmpeg", "PATH": "/usr/bin"}
    # everything is "valid" → the FIRST candidate (the override) must win
    got = main.resolve_ffmpeg(
        env=env,
        validate=_validate_only("/custom/ffmpeg", "/usr/bin/ffmpeg",
                                "/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"),
    )
    assert got == os.path.abspath("/custom/ffmpeg")


def test_05b_priority_path_beats_homebrew(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda *a, **k: "/usr/bin/ffmpeg")
    got = main.resolve_ffmpeg(
        env={"TIDDL_FFMPEG": "", "PATH": "/usr/bin"},
        validate=_validate_only("/usr/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"),
    )
    assert got == os.path.abspath("/usr/bin/ffmpeg")


def test_05c_priority_homebrew_beats_usr_local(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda *a, **k: None)
    got = main.resolve_ffmpeg(
        env={"TIDDL_FFMPEG": "", "PATH": ""},
        validate=_validate_only("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"),
    )
    assert got == os.path.abspath("/opt/homebrew/bin/ffmpeg")


# --- candidate list order (unit) -------------------------------------------
def test_candidate_order_and_dedup(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda name, path=None: "/w/ffmpeg")
    cands = main.macos_ffmpeg_candidates({"TIDDL_FFMPEG": "/o/ffmpeg", "PATH": "/x"})
    assert cands == ["/o/ffmpeg", "/w/ffmpeg", "/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"]


# --- validation rules (#6-#10) ---------------------------------------------
def test_06_rejects_nonexistent_file():
    assert main.valid_ffmpeg("/no/such/ffmpeg", version_check=lambda _p: True) is None


def test_07_rejects_directory(tmp_path):
    d = tmp_path / "adir"
    d.mkdir()
    assert main.valid_ffmpeg(str(d), version_check=lambda _p: True) is None


def test_08_rejects_non_executable(monkeypatch, tmp_path):
    ff = _make_exec(tmp_path)
    monkeypatch.setattr(main.os, "access", lambda p, mode: False)  # simulate no +x
    assert main.valid_ffmpeg(ff, version_check=lambda _p: True) is None


def test_09_rejects_when_version_fails(tmp_path):
    ff = _make_exec(tmp_path)
    assert main.valid_ffmpeg(ff, version_check=lambda _p: False) is None


def test_09b_accepts_regular_executable_with_version_ok(tmp_path):
    ff = _make_exec(tmp_path)
    assert main.valid_ffmpeg(ff, version_check=lambda _p: True) == os.path.realpath(ff)


def test_10_version_check_handles_timeout(monkeypatch):
    import subprocess as sp

    def boom(*a, **k):
        raise sp.TimeoutExpired(cmd="ffmpeg", timeout=5)

    monkeypatch.setattr(main.subprocess, "run", boom)
    assert main._ffmpeg_version_ok("/whatever/ffmpeg", timeout=0.1) is False


def test_10b_version_check_true_on_zero_exit(monkeypatch):
    class R:
        returncode = 0

    monkeypatch.setattr(main.subprocess, "run", lambda *a, **k: R())
    assert main._ffmpeg_version_ok("/x/ffmpeg") is True


# --- controlled absence (#11) ----------------------------------------------
def test_11_returns_none_when_no_candidate_resolves(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda *a, **k: None)
    got = main.resolve_ffmpeg(env={"TIDDL_FFMPEG": "", "PATH": ""}, validate=lambda p: None)
    assert got is None


# --- bilingual message (#12, #13) ------------------------------------------
def test_12_english_message():
    m = main.STRINGS["en"]["ffmpeg_missing"]
    assert m == ("FFmpeg was not found. Install it with `brew install ffmpeg`, "
                 "restart the application, and try again.")


def test_13_spanish_message():
    m = main.STRINGS["es"]["ffmpeg_missing"]
    assert m == ("No se encontró FFmpeg. Instálalo con `brew install ffmpeg`, "
                 "reinicia la aplicación y vuelve a intentarlo.")


def test_12b_message_keys_have_en_es_parity():
    assert "ffmpeg_missing" in main.STRINGS["en"]
    assert "ffmpeg_missing" in main.STRINGS["es"]
    assert set(main.STRINGS["en"]) == set(main.STRINGS["es"])  # full EN/ES key parity


# --- host survival + PATH prepend (#14) ------------------------------------
class _Probe:
    def __init__(self):
        self.lang = "en"
        self.calls = []
        self.running = "unset"

    def set_running(self, v):
        self.running = v

    def set_status(self, text, error=False):
        self.calls.append(("status", text, error))

    def log(self, text):
        self.calls.append(("log", text))

    def flush_log(self):
        self.calls.append(("flush",))

    def t(self, key, **kw):
        return main.STRINGS.get(self.lang, {}).get(key) or main.STRINGS["en"].get(key, key)


def test_14_missing_ffmpeg_does_not_kill_host(monkeypatch):
    monkeypatch.setattr(main, "resolve_ffmpeg", lambda *a, **k: None)
    p = _Probe()
    ok = main.TiddlGui._ensure_ffmpeg_on_macos(p)  # must NOT raise / exit
    assert ok is False
    assert p.running is False
    statuses = [c for c in p.calls if c[0] == "status"]
    assert statuses and statuses[0][2] is True  # error status shown
    assert "brew install ffmpeg" in statuses[0][1]


def test_14b_found_ffmpeg_prepends_its_dir_to_path(monkeypatch):
    monkeypatch.setattr(main, "resolve_ffmpeg", lambda *a, **k: "/opt/homebrew/bin/ffmpeg")
    monkeypatch.setenv("PATH", "/usr/bin")
    p = _Probe()
    ok = main.TiddlGui._ensure_ffmpeg_on_macos(p)
    assert ok is True
    assert os.environ["PATH"].split(os.pathsep)[0] == os.path.dirname("/opt/homebrew/bin/ffmpeg")


# --- Windows/Linux unchanged (#15, #16) ------------------------------------
def _func(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    raise AssertionError(f"{name} not found")


def test_15_preflight_is_macos_gated_in_worker():
    tree = ast.parse(_read(MAIN_PY))
    worker = _func(tree, "worker")
    guarded = False
    for node in ast.walk(worker):
        if isinstance(node, ast.If):
            names = {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)}
            calls = {c.func.attr for c in ast.walk(node)
                     if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)}
            if "IS_MAC" in names and "_ensure_ffmpeg_on_macos" in calls:
                guarded = True
    assert guarded, "the ffmpeg preflight must be guarded by `if IS_MAC ...` in worker()"


def test_15b_platform_constants_present():
    assert main.IS_WIN == (sys.platform == "win32")
    assert main.IS_MAC == (sys.platform == "darwin")


def test_16_resolve_ffmpeg_is_only_called_from_the_macos_helper():
    """No unconditional resolve_ffmpeg() call — it lives only inside the
    macOS-gated helper, so Windows/Linux never invoke it."""
    tree = ast.parse(_read(MAIN_PY))
    callers = []
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef):
            for c in ast.walk(fn):
                if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == "resolve_ffmpeg":
                    callers.append(fn.name)
    assert callers == ["_ensure_ffmpeg_on_macos"], f"resolve_ffmpeg called from {callers}"


def test_15c_bundled_path_prepend_still_present():
    """Windows/macOS bundled-binary discovery: the app dir is still prepended to
    PATH at startup (unchanged)."""
    src = _read(MAIN_PY)
    assert "Path(sys.executable).resolve().parent" in src
    assert 'os.environ["PATH"]' in src


# --- release_macos.sh guards (#17, #18) ------------------------------------
def test_17_release_macos_no_longer_copies_system_ffmpeg():
    src = _read(RELEASE_MACOS)
    assert "command -v ffmpeg" not in src
    assert 'cp "$(command -v ffmpeg)"' not in src


def test_18_release_macos_guards_against_embedded_ffmpeg_and_hard_signs():
    src = _read(RELEASE_MACOS)
    # a hard guard that finds & rejects an ffmpeg executable in the .app
    assert "-name 'ffmpeg'" in src and "exit 1" in src
    # no silent codesign tolerance (the pre-existing `|| true` on the APP_VERSION
    # grep is a legitimate different use — only codesign must not swallow failures)
    for line in src.splitlines():
        if "codesign" in line:
            assert "|| true" not in line, f"codesign must abort on failure, not swallow it: {line!r}"
    assert "codesign --verify --deep --strict" in src


# --- invariants (#19, #20) -------------------------------------------------
def test_19_app_version_unchanged_ast():
    assert tep._app_version_ok(_read(MAIN_PY)) is True  # APP_VERSION == "1.0.24" (robust AST)


def test_20_engine_and_flet_pins_unchanged():
    req = _read(os.path.join(ROOT, "requirements.txt"))
    assert "flet==0.86.1" in req
    assert "tiddl-elvigilante.git@13c4e9151cc3fb41954ca5312f11c5d34e2ad181" in req
