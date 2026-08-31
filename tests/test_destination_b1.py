"""Offline tests for GUI B1 — destination-identity status + trust/adopt.

Exercise the Flet-independent core in main.py (command builders, the status
classifier, ConfirmationGate and DestinationController) with a fake engine that
records every argv and scripts the `tiddl destination` responses. No flet UI,
no network, no real anchor files.

Covers the B1 spec AND the five auditor/Sourcery findings on the first head:
  1. classify returns error on a non-zero exit even if output says "trusted";
  2. the mutated path can't diverge from the authorized/displayed path;
  3. the --adopt-existing path re-queries status; the adopt hint is separate and
     bound to the path;
  4. any non-empty path always runs `destination status` (isdir/mode refine
     afterwards, never skip the command);
  5. worker UI updates are batched into a single _run_on_ui / page.update.
"""
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main  # noqa: E402

STATUS = ["destination", "status"]
TRUST = ["destination", "trust"]
PATH = "/vol"


class FakeEngine:
    """Records every argv and scripts `destination` responses. `status` reports
    `status_reason` at `status_code` (or `status_lines` verbatim if set); a
    successful mutate flips the reported reason to "trusted" unless
    `flip_on_mutate` is False."""

    def __init__(self, status_reason="unknown_root"):
        self.calls = []
        self.status_reason = status_reason
        self.status_code = 0
        self.status_lines = None
        self.trust_code = 0
        self.trust_lines = ["Trusted '/vol' (anchor abcd1234...)."]
        self.adopt_code = 0
        self.adopt_lines = ["Adopted anchor abcd1234... for '/vol'."]
        self.flip_on_mutate = True

    def __call__(self, argv):
        self.calls.append(list(argv))
        if argv[:2] == STATUS:
            if self.status_lines is not None:
                return self.status_code, list(self.status_lines)
            return self.status_code, [f"{argv[2]}: {self.status_reason}"]
        if argv[:2] == TRUST and "--adopt-existing" in argv:
            if self.flip_on_mutate:
                self.status_reason = "trusted"
            return self.adopt_code, list(self.adopt_lines)
        if argv[:2] == TRUST:
            if self.flip_on_mutate:
                self.status_reason = "trusted"
            return self.trust_code, list(self.trust_lines)
        raise AssertionError(f"unexpected argv {argv!r}")


def make(reason="unknown_root", isdir=True):
    eng = FakeEngine(reason)
    ctl = main.DestinationController(eng, isdir=lambda _p: isdir)
    return ctl, eng


def mutating(eng):
    return [c for c in eng.calls if c[:2] == TRUST]


def status_calls(eng):
    return [c for c in eng.calls if c[:2] == STATUS]


def adopt_calls(eng):
    return [c for c in eng.calls if "--adopt-existing" in c]


def reach_marker_unadopted(ctl, eng, path=PATH):
    """The only req-6-compliant route to marker-unadopted: a trust attempt whose
    engine output reveals an existing marker (no mutation), then a re-query."""
    ctl.refresh(path, "strict")
    eng.trust_code = 1
    eng.trust_lines = [
        "A marker already exists at /vol/.tiddl-anchor, but it doesn't match what "
        "this machine has recorded. If this is genuinely a shared root, re-run "
        "with --adopt-existing.",
    ]
    eng.flip_on_mutate = False
    g = main.ConfirmationGate(1)
    g.confirm()
    ctl.trust(g, path, "strict")
    assert ctl.state == "marker_unadopted"


# ---------------------------------------------------------------------------
# Exact argv (spec req 2)
# ---------------------------------------------------------------------------
def test_status_argv_exact():
    assert main.dest_status_argv(PATH) == ["destination", "status", "/vol"]


def test_trust_argv_exact():
    assert main.dest_trust_argv(PATH) == ["destination", "trust", "/vol", "--confirm-mounted"]


def test_adopt_argv_exact():
    assert main.dest_adopt_argv(PATH) == [
        "destination", "trust", "/vol", "--adopt-existing", "--confirm-mounted",
    ]


# ---------------------------------------------------------------------------
# Status classification
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "reason, state",
    [
        ("trusted", "trusted"),
        ("unknown_root", "untrusted"),
        ("id_mismatch", "untrusted"),
        ("marker_invalid", "untrusted"),
        ("marker_unreadable", "untrusted"),
        ("local_state_invalid", "untrusted"),
        ("local_state_unreadable", "untrusted"),
        ("not_contained", "untrusted"),
        ("no_root_configured", "untrusted"),
        ("marker_absent", "absent"),
    ],
)
def test_classify_reason_to_state(reason, state):
    assert main.classify_dest_status(0, [f"/vol: {reason}"]) == state


def test_classify_unrecognized_output_is_error():
    assert main.classify_dest_status(0, ["some unrelated output"]) == "error"


def test_classify_empty_output_is_error():
    assert main.classify_dest_status(0, []) == "error"


def test_classify_ignores_warning_line_and_reads_reason():
    lines = [
        "⚠️  The destination-anchor local state could not be parsed.",
        "/vol: id_mismatch (local state and marker anchor ids disagree)",
    ]
    assert main.classify_dest_status(0, lines) == "untrusted"


# --- FINDING 1: non-zero exit is an error even when output contains "trusted"
def test_classify_nonzero_exit_is_error_even_with_trusted():
    assert main.classify_dest_status(1, ["/vol: trusted"]) == "error"
    assert main.classify_dest_status(2, ["/vol: trusted (anchor abcd...)"]) == "error"


def test_refresh_treats_nonzero_status_exit_as_error():
    ctl, eng = make("trusted")
    eng.status_code = 3  # the engine somehow failed the read
    assert ctl.refresh(PATH, "strict") == "error"


# ---------------------------------------------------------------------------
# FINDING 4: any non-empty path ALWAYS runs `destination status`
# ---------------------------------------------------------------------------
def test_non_dir_path_still_runs_status_then_refines_absent():
    ctl, eng = make("unknown_root", isdir=False)
    assert ctl.refresh(PATH, "strict") == "absent"
    assert status_calls(eng) == [["destination", "status", "/vol"]]  # command DID run


def test_disabled_mode_still_runs_status_then_reports_disabled():
    ctl, eng = make("trusted")
    assert ctl.refresh(PATH, "off") == "disabled"
    assert status_calls(eng) == [["destination", "status", "/vol"]]


def test_empty_path_is_absent_without_query():
    ctl, eng = make("trusted")
    assert ctl.refresh("", "strict") == "absent"
    assert eng.calls == []


def test_refresh_is_otherwise_read_only():
    ctl, eng = make("trusted")
    ctl.refresh(PATH, "strict")
    assert mutating(eng) == []


# ---------------------------------------------------------------------------
# Trust: needs one confirmation; cancel => zero mutating (spec req 3/4)
# ---------------------------------------------------------------------------
def test_trust_without_confirmation_runs_no_command():
    ctl, eng = make("unknown_root")
    ctl.refresh(PATH, "strict")
    res = ctl.trust(main.ConfirmationGate(1), PATH, "strict")
    assert res.ran is False
    assert mutating(eng) == []


def test_trust_cancelled_runs_no_command():
    ctl, eng = make("unknown_root")
    ctl.refresh(PATH, "strict")
    g = main.ConfirmationGate(1)
    g.confirm()
    g.cancel()
    res = ctl.trust(g, PATH, "strict")
    assert res.ran is False
    assert mutating(eng) == []


def test_trust_with_confirmation_runs_exact_command_and_succeeds():
    ctl, eng = make("unknown_root")
    ctl.refresh(PATH, "strict")
    g = main.ConfirmationGate(1)
    g.confirm()
    res = ctl.trust(g, PATH, "strict")
    assert res.ran is True and res.reason == "ok" and res.state == "trusted"
    assert ["destination", "trust", "/vol", "--confirm-mounted"] in eng.calls


# --- FINDING 2: the mutated path can't diverge from the authorized one
def test_trust_rejects_a_path_that_is_not_the_authorized_one():
    ctl, eng = make("unknown_root")
    ctl.refresh(PATH, "strict")  # authorizes /vol
    g = main.ConfirmationGate(1)
    g.confirm()
    res = ctl.trust(g, "/somewhere-else", "strict")
    assert res.ran is False and res.reason == "path_mismatch"
    assert mutating(eng) == []


# ---------------------------------------------------------------------------
# Adopt: two confirmations; only in the marker-unadopted state (spec req 4)
# ---------------------------------------------------------------------------
def test_trust_attempt_revealing_marker_moves_to_unadopted():
    ctl, eng = make("unknown_root")
    reach_marker_unadopted(ctl, eng)
    assert ctl.can_adopt() is True
    assert ctl.can_trust() is False
    assert ctl.adopt_hint_path == PATH


def test_adopt_with_single_confirmation_runs_no_command():
    ctl, eng = make("unknown_root")
    reach_marker_unadopted(ctl, eng)
    g = main.ConfirmationGate(2)
    g.confirm()  # only one of two
    res = ctl.adopt(g, PATH, "strict")
    assert res.ran is False
    assert adopt_calls(eng) == []


def test_adopt_cancelled_runs_no_command():
    ctl, eng = make("unknown_root")
    reach_marker_unadopted(ctl, eng)
    g = main.ConfirmationGate(2)
    g.confirm()
    g.cancel()
    res = ctl.adopt(g, PATH, "strict")
    assert res.ran is False
    assert adopt_calls(eng) == []


def test_adopt_with_double_confirmation_runs_exact_command():
    ctl, eng = make("unknown_root")
    reach_marker_unadopted(ctl, eng)
    eng.flip_on_mutate = True  # adoption succeeds; status then reports trusted
    g = main.ConfirmationGate(2)
    g.confirm()
    g.confirm()
    res = ctl.adopt(g, PATH, "strict")
    assert res.ran is True and res.state == "trusted"
    assert [
        "destination", "trust", "/vol", "--adopt-existing", "--confirm-mounted",
    ] in eng.calls


# --- FINDING 3: adopt re-queries; hint is separate and bound to the path
def test_trust_reveals_marker_re_queries_status():
    ctl, eng = make("unknown_root")
    reach_marker_unadopted(ctl, eng)
    last_trust = max(i for i, c in enumerate(eng.calls) if c[:2] == TRUST)
    assert any(c[:2] == STATUS for c in eng.calls[last_trust + 1:])


def test_marker_hint_yields_trusted_if_requery_shows_trusted():
    ctl, eng = make("unknown_root")
    ctl.refresh(PATH, "strict")
    eng.trust_code = 1
    eng.trust_lines = ["... re-run with --adopt-existing."]
    eng.flip_on_mutate = True  # re-query surprisingly shows trusted
    g = main.ConfirmationGate(1)
    g.confirm()
    res = ctl.trust(g, PATH, "strict")
    assert res.reason == "ok" and res.state == "trusted"


def test_adopt_re_queries_status_after():
    ctl, eng = make("unknown_root")
    reach_marker_unadopted(ctl, eng)
    eng.flip_on_mutate = True
    g = main.ConfirmationGate(2)
    g.confirm()
    g.confirm()
    ctl.adopt(g, PATH, "strict")
    last_adopt = max(i for i, c in enumerate(eng.calls) if "--adopt-existing" in c)
    assert any(c[:2] == STATUS for c in eng.calls[last_adopt + 1:])


def test_plain_refresh_clears_the_adopt_hint():
    ctl, eng = make("unknown_root")
    reach_marker_unadopted(ctl, eng)
    assert ctl.can_adopt() is True
    ctl.refresh(PATH, "strict")  # a plain status read can't confirm a marker
    assert ctl.can_adopt() is False
    assert ctl.adopt_hint_path is None


def test_adopt_hint_is_bound_to_its_path():
    ctl, eng = make("unknown_root")
    reach_marker_unadopted(ctl, eng)
    g = main.ConfirmationGate(2)
    g.confirm()
    g.confirm()
    res = ctl.adopt(g, "/other", "strict")  # different path than the hint's
    assert res.ran is False and res.reason == "path_mismatch"
    assert adopt_calls(eng) == []


# ---------------------------------------------------------------------------
# Non-zero exits never fake a "trusted" success (spec req 5)
# ---------------------------------------------------------------------------
def test_trust_nonzero_without_marker_hint_is_not_trusted():
    ctl, eng = make("unknown_root")
    ctl.refresh(PATH, "strict")
    eng.trust_code = 1
    eng.trust_lines = ["'/vol' does not exist. 'trust' never creates the destination."]
    eng.flip_on_mutate = False
    g = main.ConfirmationGate(1)
    g.confirm()
    res = ctl.trust(g, PATH, "strict")
    assert res.state != "trusted" and res.reason == "error"


def test_status_with_only_a_warning_is_error_not_trusted():
    ctl, eng = make()
    eng.status_lines = ["⚠️  local anchor state could not be read."]
    assert ctl.refresh(PATH, "strict") == "error"


# ---------------------------------------------------------------------------
# Trust/adopt refuse in incompatible states (spec req 8)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("reason", ["trusted", "marker_absent"])
def test_trust_refused_in_incompatible_status(reason):
    ctl, eng = make(reason)
    ctl.refresh(PATH, "strict")
    g = main.ConfirmationGate(1)
    g.confirm()
    res = ctl.trust(g, PATH, "strict")
    assert res.ran is False and res.reason == "incompatible_state"
    assert mutating(eng) == []


def test_trust_refused_when_identity_disabled():
    ctl, eng = make("trusted")
    ctl.refresh(PATH, "off")  # -> disabled
    g = main.ConfirmationGate(1)
    g.confirm()
    res = ctl.trust(g, PATH, "strict")
    assert res.ran is False and res.reason == "incompatible_state"
    assert mutating(eng) == []


def test_adopt_refused_when_not_marker_unadopted():
    ctl, eng = make("unknown_root")
    ctl.refresh(PATH, "strict")  # untrusted, not marker_unadopted
    g = main.ConfirmationGate(2)
    g.confirm()
    g.confirm()
    res = ctl.adopt(g, PATH, "strict")
    assert res.ran is False
    assert adopt_calls(eng) == []


# ---------------------------------------------------------------------------
# ConfirmationGate semantics
# ---------------------------------------------------------------------------
def test_gate_needs_all_confirmations():
    g = main.ConfirmationGate(2)
    assert g.proceed is False
    g.confirm()
    assert g.proceed is False
    g.confirm()
    assert g.proceed is True


def test_gate_cancel_wins_even_after_confirmations():
    g = main.ConfirmationGate(1)
    g.confirm()
    g.cancel()
    assert g.proceed is False


# ---------------------------------------------------------------------------
# EN/ES parity (spec req 7)
# ---------------------------------------------------------------------------
def test_en_es_full_key_parity():
    assert set(main.STRINGS["en"]) == set(main.STRINGS["es"])


def test_destination_keys_present_in_both_languages():
    required = {
        "sec_destination", "dest_intro", "dest_path_label", "dest_status_label",
        "dest_state_trusted", "dest_state_untrusted", "dest_state_marker_unadopted",
        "dest_state_absent", "dest_state_disabled", "dest_state_error",
        "dest_btn_check", "dest_btn_trust", "dest_btn_adopt",
        "dest_trust_title", "dest_trust_q", "dest_trust_confirm",
        "dest_adopt_title1", "dest_adopt_q1", "dest_adopt_confirm1",
        "dest_adopt_title2", "dest_adopt_q2", "dest_adopt_confirm2",
    }
    for lang in ("en", "es"):
        assert required <= set(main.STRINGS[lang]), lang


def test_trust_and_adopt_prompts_carry_the_path_placeholder():
    for lang in ("en", "es"):
        assert "{path}" in main.STRINGS[lang]["dest_trust_q"]
        assert "{path}" in main.STRINGS[lang]["dest_adopt_q1"]


# ---------------------------------------------------------------------------
# A second operation in the same process still works (spec req 8)
# ---------------------------------------------------------------------------
def test_second_trust_in_same_process_still_works():
    ctl, eng = make("unknown_root")
    ctl.refresh(PATH, "strict")
    g1 = main.ConfirmationGate(1)
    g1.confirm()
    assert ctl.trust(g1, PATH, "strict").state == "trusted"

    eng.status_reason = "unknown_root"
    ctl.refresh(PATH, "strict")
    g2 = main.ConfirmationGate(1)
    g2.confirm()
    res2 = ctl.trust(g2, PATH, "strict")
    assert res2.ran is True and res2.state == "trusted"


# ---------------------------------------------------------------------------
# FINDING 5: worker UI updates are batched into one _run_on_ui / page.update
# ---------------------------------------------------------------------------
class UIProbe:
    """Minimal stand-in for the App that binds the REAL destination workers and
    render/commit helpers, with a _run_on_ui that DEFERS its callback. It proves
    a worker performs no direct page.update and batches everything into exactly
    one scheduled UI callback that itself updates once."""

    lang = "en"
    pal = {"error": "red"}
    t = main.TiddlGui.t
    _dest_render = main.TiddlGui._dest_render
    _dest_commit = main.TiddlGui._dest_commit
    _dest_msg = main.TiddlGui._dest_msg
    _dest_is_err = main.TiddlGui._dest_is_err
    _dest_check_worker = main.TiddlGui._dest_check_worker
    _dest_trust_worker = main.TiddlGui._dest_trust_worker
    _dest_adopt_worker = main.TiddlGui._dest_adopt_worker

    def __init__(self, ctl):
        self.dest_ctl = ctl
        self.updates = 0
        self.scheduled = []
        ns = types.SimpleNamespace
        self.dest_status_text = ns(value=None, color=None)
        self.dest_path_text = ns(value=None)
        self.status_text = ns(value=None, color=None)
        self.dest_check_btn = ns(disabled=False, visible=False)
        self.dest_trust_btn = ns(disabled=False, visible=False)
        self.dest_adopt_btn = ns(disabled=False, visible=False)
        self.page = ns(update=self._update)

    def _dest_mode(self):
        return "strict"

    def _dest_path(self):
        return self.dest_ctl.path

    def _update(self, *a, **k):
        self.updates += 1

    def _run_on_ui(self, fn):
        self.scheduled.append(fn)  # DEFER — never executed inline


def _assert_single_batched_update(probe):
    assert probe.updates == 0, "worker touched page.update directly"
    assert len(probe.scheduled) == 1, "worker did not batch UI into one callback"
    probe.scheduled[0]()
    assert probe.updates == 1, "the batched callback must update exactly once"


def test_check_worker_batches_ui():
    ctl, eng = make("trusted")
    probe = UIProbe(ctl)
    probe._dest_check_worker("/vol")
    _assert_single_batched_update(probe)


def test_trust_worker_batches_ui():
    ctl, eng = make("unknown_root")
    ctl.refresh(PATH, "strict")
    probe = UIProbe(ctl)
    g = main.ConfirmationGate(1)
    g.confirm()
    probe._dest_trust_worker(g, PATH)
    _assert_single_batched_update(probe)


def test_adopt_worker_batches_ui():
    ctl, eng = make("unknown_root")
    reach_marker_unadopted(ctl, eng)
    eng.flip_on_mutate = True
    probe = UIProbe(ctl)
    g = main.ConfirmationGate(2)
    g.confirm()
    g.confirm()
    probe._dest_adopt_worker(g, PATH)
    _assert_single_batched_update(probe)
