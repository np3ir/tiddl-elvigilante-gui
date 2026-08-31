"""Offline tests for GUI B2 — the destination-identity mode selector.

B2 exposes CONFIG.download.destination_identity (off/strict) in Settings and
integrates with B1 (already merged) WITHOUT duplicating trust logic or touching
anchor files. These tests drive the Flet-independent helpers and the real
handler/persistence methods through lightweight probes (SimpleNamespace fields),
never a live Flet page and never the real config on disk (temp-file monkeypatch).

Covers the 16 required checks: only off/strict accepted; invalid → off; initial
load / save / reload round-trip; a stash preserves an unsaved choice; apply_runtime
feeds CONFIG; off → B1 disabled with no actions; off→strict invalidates and
re-requires a check; a mode switch runs no destination command and creates/removes
no anchors; trust/adopt stay refused in incompatible states; EN/ES parity; and the
APP_VERSION / engine-pin invariants via AST + a pin regex (not fragile text search).
"""
import ast
import os
import re
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS = ["destination", "status"]
TRUST = ["destination", "trust"]
PATH = "/vol"


# --- shared B1 fake engine / controller helpers ----------------------------
class FakeEngine:
    def __init__(self, status_reason="unknown_root"):
        self.calls = []
        self.status_reason = status_reason
        self.status_code = 0
        self.trust_code = 0
        self.trust_lines = ["Trusted '/vol'."]
        self.flip_on_mutate = True

    def __call__(self, argv):
        self.calls.append(list(argv))
        if argv[:2] == STATUS:
            return self.status_code, [f"{argv[2]}: {self.status_reason}"]
        if argv[:2] == TRUST:
            if self.flip_on_mutate:
                self.status_reason = "trusted"
            return self.trust_code, list(self.trust_lines)
        raise AssertionError(f"unexpected argv {argv!r}")


def make(reason="unknown_root", isdir=True):
    eng = FakeEngine(reason)
    return main.DestinationController(eng, isdir=lambda _p: isdir), eng


def reach_marker_unadopted(ctl, eng):
    ctl.refresh(PATH, "strict")
    eng.trust_code = 1
    eng.trust_lines = ["A marker exists ... re-run with --adopt-existing."]
    eng.flip_on_mutate = False
    g = main.ConfirmationGate(1)
    g.confirm()
    ctl.trust(g, PATH, "strict")
    assert ctl.state == "marker_unadopted"


def mutating(eng):
    return [c for c in eng.calls if c[:2] == TRUST]


# ---------------------------------------------------------------------------
# 1 & 2: only off/strict are accepted; anything else normalizes to off
# ---------------------------------------------------------------------------
def test_identity_modes_are_exactly_off_and_strict():
    assert main.IDENTITY_MODES == ("off", "strict")


def test_valid_modes_pass_through():
    assert main._norm_identity("off") == "off"
    assert main._norm_identity("strict") == "strict"


def test_case_and_whitespace_are_normalized():
    assert main._norm_identity("OFF") == "off"
    assert main._norm_identity("Strict") == "strict"
    assert main._norm_identity("  strict  ") == "strict"


def test_invalid_values_conservatively_become_off():
    for bad in (None, "", "warn", "on", "true", "1", "garbage", 123, [], {"x": 1}):
        assert main._norm_identity(bad) == "off"


# ---------------------------------------------------------------------------
# 3: the initial load reflects the persisted value
# ---------------------------------------------------------------------------
def test_identity_from_config_reflects_persisted_value():
    assert main.identity_from_config({"download": {"destination_identity": "strict"}}) == "strict"
    assert main.identity_from_config({"download": {"destination_identity": "off"}}) == "off"


def test_identity_from_config_defaults_and_normalizes():
    assert main.identity_from_config({"download": {}}) == "off"
    assert main.identity_from_config({}) == "off"
    assert main.identity_from_config({"download": {"destination_identity": "bogus"}}) == "off"


# ===========================================================================
# Probes
# ===========================================================================
_NS = types.SimpleNamespace


class ModeProbe:
    """Binds the real B2 selector handler + the render/mode helpers, with a
    _run_on_ui-free page (mode change updates on the UI thread directly)."""

    lang = "en"
    pal = {"error": "red"}
    t = main.TiddlGui.t
    _dest_mode = main.TiddlGui._dest_mode
    _dest_path = main.TiddlGui._dest_path
    _dest_render = main.TiddlGui._dest_render
    on_dest_mode_change = main.TiddlGui.on_dest_mode_change

    def __init__(self, ctl, mode_value):
        self.dest_ctl = ctl
        self.updates = 0
        self.f_dest_mode = _NS(value=mode_value)
        self.f_download_path = _NS(value=ctl.path or PATH)
        self.dest_status_text = _NS(value=None, color=None)
        self.dest_path_text = _NS(value=None)
        self.status_text = _NS(value=None, color=None)
        self.dest_check_btn = _NS(disabled=False, visible=False)
        self.dest_trust_btn = _NS(disabled=False, visible=False)
        self.dest_adopt_btn = _NS(disabled=False, visible=False)
        self.page = _NS(update=self._update)

    def _update(self, *a, **k):
        self.updates += 1


# ---------------------------------------------------------------------------
# 8, 9, 10, 11: mode-change behavior — invalidate state, never run an engine
# command, never create/remove anchors, and require a fresh check under strict
# ---------------------------------------------------------------------------
def test_switch_to_off_shows_disabled_and_hides_actions():
    ctl, eng = make("unknown_root")
    ctl.refresh(PATH, "strict")  # untrusted
    before = len(eng.calls)
    p = ModeProbe(ctl, "off")
    p.on_dest_mode_change(None)
    assert ctl.state == "disabled"
    assert ctl.can_trust() is False and ctl.can_adopt() is False
    assert len(eng.calls) == before  # no engine command on the switch
    assert p.dest_trust_btn.visible is False and p.dest_adopt_btn.visible is False


def test_switch_to_strict_marks_unchecked_and_requires_new_check():
    ctl, eng = make("trusted")
    ctl.refresh(PATH, "strict")  # trusted
    before = len(eng.calls)
    ModeProbe(ctl, "strict").on_dest_mode_change(None)
    assert ctl.state == "unknown"  # invalidated; a fresh Check is required
    assert ctl.can_trust() is False and ctl.can_adopt() is False
    assert len(eng.calls) == before
    # the fresh Check then re-enables actions
    ctl.refresh(PATH, "strict")
    assert ctl.state == "trusted"  # (engine still reports trusted here)


def test_off_to_strict_from_a_checked_state_still_requires_recheck():
    ctl, eng = make("unknown_root")
    ctl.refresh(PATH, "strict")  # untrusted → Trust would be available
    assert ctl.can_trust() is True
    ModeProbe(ctl, "off").on_dest_mode_change(None)   # disabled
    ModeProbe(ctl, "strict").on_dest_mode_change(None)  # back to strict
    assert ctl.state == "unknown" and ctl.can_trust() is False


def test_mode_change_normalizes_the_selector_value():
    ctl, _ = make("unknown_root")
    p = ModeProbe(ctl, "STRICT")
    p.on_dest_mode_change(None)
    assert p.f_dest_mode.value == "strict"
    p2 = ModeProbe(ctl, "nonsense")
    p2.on_dest_mode_change(None)
    assert p2.f_dest_mode.value == "off"


def test_no_transition_runs_a_destination_command_or_touches_anchors():
    ctl, eng = make("unknown_root")
    reach_marker_unadopted(ctl, eng)  # a real sequence with commands recorded
    before = list(eng.calls)
    for mode in ("off", "strict", "off", "strict", "off"):
        ModeProbe(ctl, mode).on_dest_mode_change(None)
    assert eng.calls == before  # zero engine commands from ANY transition
    added = eng.calls[len(before):]  # only what the transitions themselves issued
    assert added == []
    assert not any(
        ("--confirm-mounted" in c) or ("--adopt-existing" in c) for c in added
    )


# ---------------------------------------------------------------------------
# 12: Trust/Adopt stay refused in the states a switch leaves behind
# ---------------------------------------------------------------------------
def test_trust_refused_after_switching_to_off():
    ctl, eng = make("unknown_root")
    ctl.refresh(PATH, "strict")
    ModeProbe(ctl, "off").on_dest_mode_change(None)  # disabled
    g = main.ConfirmationGate(1)
    g.confirm()
    res = ctl.trust(g, PATH, "strict")
    assert res.ran is False and mutating(eng) == []


def test_adopt_refused_after_switch_clears_marker_state():
    ctl, eng = make("unknown_root")
    reach_marker_unadopted(ctl, eng)
    ModeProbe(ctl, "off").on_dest_mode_change(None)   # disabled, hint cleared
    ModeProbe(ctl, "strict").on_dest_mode_change(None)  # unknown
    g = main.ConfirmationGate(2)
    g.confirm()
    g.confirm()
    res = ctl.adopt(g, PATH, "strict")
    assert res.ran is False
    assert [c for c in eng.calls if "--adopt-existing" in c] == []


# ---------------------------------------------------------------------------
# 7: apply_runtime_config feeds the selected mode into CONFIG.download.*
# ---------------------------------------------------------------------------
class ApplyProbe:
    _dest_mode = main.TiddlGui._dest_mode
    apply_runtime_config = main.TiddlGui.apply_runtime_config

    def __init__(self, mode_value):
        self.logged = []
        self.f_dest_mode = _NS(value=mode_value)
        # everything else apply_runtime_config reads, with benign values
        for name in (
            "f_cover", "f_album_review", "f_cover_save", "f_update_mtime",
            "f_exclude_compilations", "f_exclude_live", "f_cover_track",
            "f_cover_album", "f_cover_playlist", "f_m3u_save", "f_m3u_album",
            "f_m3u_playlist", "f_m3u_mix",
        ):
            setattr(self, name, _NS(value=False))
        self.f_cover_size = _NS(value="1280")
        self.f_hires_client = _NS(value="auto")
        self.f_rpm = _NS(value="20")
        self.f_max_tracks = _NS(value="0")
        self.f_tpl_mix = _NS(value="")
        self.f_artist_sep = _NS(value=" / ")

    def log(self, msg):
        self.logged.append(msg)


def _config():
    from tiddl.cli.config import CONFIG
    return CONFIG


def test_apply_runtime_config_pushes_selected_mode_to_config():
    ApplyProbe("strict").apply_runtime_config()
    assert _config().download.destination_identity == "strict"
    ApplyProbe("off").apply_runtime_config()
    assert _config().download.destination_identity == "off"


def test_apply_runtime_config_normalizes_before_pushing():
    ApplyProbe("STRICT").apply_runtime_config()
    assert _config().download.destination_identity == "strict"
    ApplyProbe("garbage").apply_runtime_config()
    assert _config().download.destination_identity == "off"


# ---------------------------------------------------------------------------
# 4 & 5: save persists exactly off/strict; reload restores it (temp round-trip)
# ---------------------------------------------------------------------------
class SettingsProbe:
    """Binds the real on_save_defaults / on_reload_settings / numeric_settings
    and the cfg_* helpers. Filesystem is redirected to a temp dir; _dest_render
    and refresh are stubbed (persistence, not rendering, is under test)."""

    lang = "en"
    theme_name = "dark"
    font_name = "m"
    on_save_defaults = main.TiddlGui.on_save_defaults
    on_reload_settings = main.TiddlGui.on_reload_settings
    numeric_settings = main.TiddlGui.numeric_settings
    _dest_mode = main.TiddlGui._dest_mode
    _dest_path = main.TiddlGui._dest_path
    cfg_dl = main.TiddlGui.cfg_dl
    cfg_tpl = main.TiddlGui.cfg_tpl
    cfg_meta = main.TiddlGui.cfg_meta
    cfg_cover = main.TiddlGui.cfg_cover
    cfg_m3u = main.TiddlGui.cfg_m3u
    t = main.TiddlGui.t

    def __init__(self, dest_mode="off"):
        self.cfg = {}
        self.dest_ctl, _ = make("unknown_root")
        self.settings_status = _NS(value=None)
        # numeric + all fields on_save/on_reload read, with valid values
        self.f_threads = _NS(value="1")
        self.f_track_delay = _NS(value="3")
        self.f_artist_delay = _NS(value="8")
        self.f_rpm = _NS(value="20")
        self.f_concurrency = _NS(value="1")
        self.f_max_tracks = _NS(value="0")
        self.f_cover_size = _NS(value="1280", disabled=False)
        self.quality_dd = _NS(value="high")
        self.f_video_quality = _NS(value="fhd")
        self.f_hires_client = _NS(value="auto")
        self.f_singles = _NS(value="none")
        self.f_videos = _NS(value="none")
        self.f_rewrite = _NS(value=False)
        self.f_exclude_compilations = _NS(value=False)
        self.f_exclude_live = _NS(value=False)
        self.f_update_mtime = _NS(value=False)
        self.f_download_path = _NS(value="/music")
        self.f_scan_path = _NS(value="/music")
        self.f_video_path = _NS(value="")
        self.f_playlist_path = _NS(value="")
        self.f_embed_lyrics = _NS(value=False)
        self.f_save_lrc = _NS(value=False)
        self.f_cover = _NS(value=False)
        self.f_album_review = _NS(value=False)
        self.f_cover_save = _NS(value=False)
        self.f_cover_track = _NS(value=False, disabled=False)
        self.f_cover_album = _NS(value=True, disabled=False)
        self.f_cover_playlist = _NS(value=False, disabled=False)
        self.f_m3u_save = _NS(value=False)
        self.f_m3u_album = _NS(value=False)
        self.f_m3u_playlist = _NS(value=False)
        self.f_m3u_mix = _NS(value=False)
        self.f_tpl_default = _NS(value="")
        self.f_tpl_track = _NS(value="")
        self.f_tpl_album = _NS(value="")
        self.f_tpl_playlist = _NS(value="")
        self.f_tpl_video = _NS(value="")
        self.f_tpl_mix = _NS(value="")
        self.f_artist_sep = _NS(value=" / ")
        self.f_audio_mode = _NS(value="auto")
        self.f_quality_policy = _NS(value="flexible")
        self.f_dest_mode = _NS(value=dest_mode)

    def _dest_render(self, **k):
        pass

    def refresh(self, *a, **k):
        pass


def _redirect_config(monkeypatch, tmp_path):
    cfg = tmp_path / "config.toml"
    gui = tmp_path / "gui.json"
    monkeypatch.setattr(main, "config_file_path", lambda: cfg)
    monkeypatch.setattr(main, "gui_settings_path", lambda: gui)
    return cfg


def test_save_persists_exactly_the_chosen_mode(monkeypatch, tmp_path):
    cfg = _redirect_config(monkeypatch, tmp_path)
    p = SettingsProbe(dest_mode="strict")
    p.on_save_defaults(None)
    import tomllib
    saved = tomllib.loads(cfg.read_text(encoding="utf-8"))
    assert saved["download"]["destination_identity"] == "strict"


def test_save_normalizes_an_invalid_mode_to_off(monkeypatch, tmp_path):
    cfg = _redirect_config(monkeypatch, tmp_path)
    p = SettingsProbe(dest_mode="garbage")
    p.on_save_defaults(None)
    import tomllib
    saved = tomllib.loads(cfg.read_text(encoding="utf-8"))
    assert saved["download"]["destination_identity"] == "off"


def test_reload_restores_the_persisted_mode(monkeypatch, tmp_path):
    _redirect_config(monkeypatch, tmp_path)
    # First persist "strict"…
    saver = SettingsProbe(dest_mode="strict")
    saver.on_save_defaults(None)
    # …then a fresh probe showing "off" reloads and must reflect "strict".
    reloader = SettingsProbe(dest_mode="off")
    reloader.on_reload_settings(None)
    assert reloader.f_dest_mode.value == "strict"
    # reload invalidates B1 state (strict → require a fresh check)
    assert reloader.dest_ctl.state == "unknown"


def test_reload_off_marks_disabled(monkeypatch, tmp_path):
    _redirect_config(monkeypatch, tmp_path)
    SettingsProbe(dest_mode="off").on_save_defaults(None)
    reloader = SettingsProbe(dest_mode="strict")
    reloader.on_reload_settings(None)
    assert reloader.f_dest_mode.value == "off"
    assert reloader.dest_ctl.state == "disabled"


def test_initial_field_value_reflects_persisted_config(monkeypatch, tmp_path):
    _redirect_config(monkeypatch, tmp_path)
    SettingsProbe(dest_mode="strict").on_save_defaults(None)
    # A newly loaded config seeds the selector via identity_from_config.
    cfg = main.load_tiddl_config()
    assert main.identity_from_config(cfg) == "strict"


# ---------------------------------------------------------------------------
# 6: a language switch / rebuild preserves an unsaved selection (stash)
# ---------------------------------------------------------------------------
def test_dest_mode_is_in_stash_fields():
    assert "f_dest_mode" in main.STASH_FIELDS


def test_stash_preserves_an_unsaved_mode_across_rebuild():
    # Mirror rebuild(): stash getattr(self, name).value for STASH_FIELDS names.
    probe = _NS(f_dest_mode=_NS(value="strict"))
    stash = {n: getattr(probe, n).value for n in main.STASH_FIELDS if hasattr(probe, n)}
    assert stash["f_dest_mode"] == "strict"
    # rebuild recreates the field seeded from config ("off"); then restore stash.
    probe.f_dest_mode = _NS(value="off")
    for n, v in stash.items():
        if hasattr(probe, n):
            getattr(probe, n).value = v
    assert probe.f_dest_mode.value == "strict"  # the unsaved choice survived


# ---------------------------------------------------------------------------
# 13: full EN/ES key parity + the B2 selector keys
# ---------------------------------------------------------------------------
def test_en_es_full_key_parity():
    assert set(main.STRINGS["en"]) == set(main.STRINGS["es"])


def test_b2_selector_keys_present_in_both_languages():
    required = {"dest_mode_label", "dest_mode_off", "dest_mode_strict", "dest_mode_help"}
    for lang in ("en", "es"):
        assert required <= set(main.STRINGS[lang]), lang
    # the help text carries the difference, the off-warning, and the no-mutation note
    for lang in ("en", "es"):
        assert main.STRINGS[lang]["dest_mode_help"]


# ---------------------------------------------------------------------------
# 14 & 15: invariants — APP_VERSION (AST) and the engine pin (regex), not a
# fragile text search.
# ---------------------------------------------------------------------------
def _module_scope_assignments(source, name):
    found = []

    class V(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            return

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, node):
            return

        def visit_Assign(self, node):
            if any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
                found.append(node)
            self.generic_visit(node)

    V().visit(ast.parse(source))
    return found


def test_app_version_is_still_1_0_23_single_module_assignment():
    src = (main.__file__ and open(os.path.join(ROOT, "main.py"), encoding="utf-8").read())
    binds = _module_scope_assignments(src, "APP_VERSION")
    assert len(binds) == 1
    value = binds[0].value
    assert isinstance(value, ast.Constant) and value.value == "1.0.23"


def test_engine_pin_is_still_v1_5_5_commit():
    req = open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8").read()
    m = re.search(
        r"tiddl-elvigilante\s*@\s*git\+https://github\.com/np3ir/"
        r"tiddl-elvigilante\.git@([0-9a-f]{40})",
        req,
    )
    assert m and m.group(1) == "13c4e9151cc3fb41954ca5312f11c5d34e2ad181"
