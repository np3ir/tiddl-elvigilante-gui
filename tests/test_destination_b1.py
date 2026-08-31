"""Offline tests for GUI B1 — destination-identity status + trust/adopt.

These exercise the Flet-independent core in main.py (command builders, the
status classifier, ConfirmationGate and DestinationController) with a fake
engine that records every argv and scripts the `tiddl destination` responses.
No flet UI, no network, no real anchor files — the engine is the only thing
that would ever touch destination_anchors.json / .tiddl-anchor, and here it is
a stand-in, so nothing on disk is read or written.

Covers, per the B1 spec:
  * status is read-only;
  * exact argv for status/trust/adopt;
  * cancelling any dialog issues zero mutating commands;
  * trust needs one confirmation, adopt needs two;
  * every mutating op re-queries status afterwards;
  * non-zero exits / exceptions never leave a falsely-"trusted" state;
  * trust/adopt refuse in incompatible states;
  * EN/ES key-set parity;
  * a second operation in the same process still works.
"""
import os
import sys

import pytest

# main.py lives at the GUI repo root (one level up from tests/).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main  # noqa: E402

STATUS = ["destination", "status"]
TRUST = ["destination", "trust"]
PATH = "/vol"


class FakeEngine:
    """Records every argv and scripts `destination` responses. `status` reports
    `status_reason` (or `status_lines` verbatim if set); a successful mutate
    flips the reported reason to "trusted" unless `flip_on_mutate` is False."""

    def __init__(self, status_reason="unknown_root"):
        self.calls = []
        self.status_reason = status_reason
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
                return 0, list(self.status_lines)
            return 0, [f"{argv[2]}: {self.status_reason}"]
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


def reach_marker_unadopted(ctl, eng):
    """Drive the controller to the marker-unadopted state the only compliant
    way: a trust attempt whose engine output reveals an existing marker."""
    ctl.refresh(PATH, "strict")
    eng.trust_code = 1
    eng.trust_lines = [
        "A marker already exists at /vol/.tiddl-anchor, but it doesn't match "
        "what this machine has recorded. If this is genuinely a shared root, "
        "re-run with --adopt-existing.",
    ]
    eng.flip_on_mutate = False
    g = main.ConfirmationGate(1)
    g.confirm()
    ctl.trust(g, "strict")
    assert ctl.state == "marker_unadopted"


# ---------------------------------------------------------------------------
# Exact argv (req 2)
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
# Status classification (differentiated states)
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
        "⚠️  The destination-anchor local state could not be parsed. It has NOT "
        "been modified by this listing.",
        "/vol: id_mismatch (local state and marker anchor ids disagree)",
    ]
    assert main.classify_dest_status(0, lines) == "untrusted"


# ---------------------------------------------------------------------------
# Status is read-only (req 1)
# ---------------------------------------------------------------------------
def test_refresh_only_issues_a_status_query():
    ctl, eng = make("trusted")
    ctl.refresh(PATH, "strict")
    assert eng.calls == [["destination", "status", "/vol"]]
    assert mutating(eng) == []


def test_disabled_mode_does_not_query_and_reports_disabled():
    ctl, eng = make("trusted")
    assert ctl.refresh(PATH, "off") == "disabled"
    assert eng.calls == []


def test_absent_when_path_is_not_a_directory():
    ctl, eng = make("trusted", isdir=False)
    assert ctl.refresh(PATH, "strict") == "absent"
    assert eng.calls == []


def test_absent_when_no_path_configured():
    ctl, eng = make("trusted")
    assert ctl.refresh("", "strict") == "absent"
    assert eng.calls == []


# ---------------------------------------------------------------------------
# Trust: needs exactly one confirmation; cancel → zero mutating (req 3/4)
# ---------------------------------------------------------------------------
def test_trust_without_confirmation_runs_no_command():
    ctl, eng = make("unknown_root")
    ctl.refresh(PATH, "strict")
    res = ctl.trust(main.ConfirmationGate(1), "strict")  # never confirmed
    assert res.ran is False
    assert mutating(eng) == []


def test_trust_cancelled_runs_no_command():
    ctl, eng = make("unknown_root")
    ctl.refresh(PATH, "strict")
    g = main.ConfirmationGate(1)
    g.confirm()
    g.cancel()
    res = ctl.trust(g, "strict")
    assert res.ran is False
    assert mutating(eng) == []


def test_trust_with_confirmation_runs_exact_command_and_succeeds():
    ctl, eng = make("unknown_root")
    ctl.refresh(PATH, "strict")
    g = main.ConfirmationGate(1)
    g.confirm()
    res = ctl.trust(g, "strict")
    assert res.ran is True and res.reason == "ok" and res.state == "trusted"
    assert ["destination", "trust", "/vol", "--confirm-mounted"] in eng.calls


# ---------------------------------------------------------------------------
# Adopt: needs two confirmations; only in the marker-unadopted state (req 4)
# ---------------------------------------------------------------------------
def test_trust_attempt_revealing_marker_moves_to_unadopted():
    ctl, eng = make("unknown_root")
    reach_marker_unadopted(ctl, eng)
    assert ctl.can_adopt() is True
    assert ctl.can_trust() is False


def test_adopt_with_single_confirmation_runs_no_command():
    ctl, eng = make("unknown_root")
    reach_marker_unadopted(ctl, eng)
    g = main.ConfirmationGate(2)
    g.confirm()  # only one of two
    res = ctl.adopt(g, "strict")
    assert res.ran is False
    assert [c for c in eng.calls if "--adopt-existing" in c] == []


def test_adopt_cancelled_runs_no_command():
    ctl, eng = make("unknown_root")
    reach_marker_unadopted(ctl, eng)
    g = main.ConfirmationGate(2)
    g.confirm()
    g.cancel()
    res = ctl.adopt(g, "strict")
    assert res.ran is False
    assert [c for c in eng.calls if "--adopt-existing" in c] == []


def test_adopt_with_double_confirmation_runs_exact_command():
    ctl, eng = make("unknown_root")
    reach_marker_unadopted(ctl, eng)
    eng.flip_on_mutate = True  # adoption succeeds; status then reports trusted
    g = main.ConfirmationGate(2)
    g.confirm()
    g.confirm()
    res = ctl.adopt(g, "strict")
    assert res.ran is True and res.state == "trusted"
    assert [
        "destination", "trust", "/vol", "--adopt-existing", "--confirm-mounted",
    ] in eng.calls


# ---------------------------------------------------------------------------
# Every mutating op re-queries status afterwards (req 5)
# ---------------------------------------------------------------------------
def test_trust_re_queries_status_after():
    ctl, eng = make("unknown_root")
    ctl.refresh(PATH, "strict")
    g = main.ConfirmationGate(1)
    g.confirm()
    ctl.trust(g, "strict")
    last_trust = max(i for i, c in enumerate(eng.calls) if c[:2] == TRUST)
    assert any(c[:2] == STATUS for c in eng.calls[last_trust + 1:])


def test_adopt_re_queries_status_after():
    ctl, eng = make("unknown_root")
    reach_marker_unadopted(ctl, eng)
    eng.flip_on_mutate = True
    g = main.ConfirmationGate(2)
    g.confirm()
    g.confirm()
    ctl.adopt(g, "strict")
    last_adopt = max(i for i, c in enumerate(eng.calls) if "--adopt-existing" in c)
    assert any(c[:2] == STATUS for c in eng.calls[last_adopt + 1:])


# ---------------------------------------------------------------------------
# Non-zero exits / exceptions never fake a "trusted" success (req 5)
# ---------------------------------------------------------------------------
def test_trust_nonzero_without_marker_hint_is_not_trusted():
    ctl, eng = make("unknown_root")
    ctl.refresh(PATH, "strict")
    eng.trust_code = 1
    eng.trust_lines = ["'/vol' does not exist. 'trust' never creates the destination."]
    eng.flip_on_mutate = False  # status still reports unknown_root afterwards
    g = main.ConfirmationGate(1)
    g.confirm()
    res = ctl.trust(g, "strict")
    assert res.state != "trusted"
    assert res.reason == "error"


def test_status_with_only_a_warning_is_error_not_trusted():
    ctl, eng = make()
    eng.status_lines = ["⚠️  local anchor state could not be read."]
    assert ctl.refresh(PATH, "strict") == "error"


# ---------------------------------------------------------------------------
# Trust/adopt refuse in incompatible states (req 8)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("reason", ["trusted", "marker_absent"])
def test_trust_refused_in_incompatible_status(reason):
    ctl, eng = make(reason)
    ctl.refresh(PATH, "strict")
    g = main.ConfirmationGate(1)
    g.confirm()
    res = ctl.trust(g, "strict")
    assert res.ran is False and res.reason == "incompatible_state"
    assert mutating(eng) == []


def test_trust_refused_when_identity_disabled():
    ctl, eng = make("trusted")
    ctl.refresh(PATH, "off")  # -> disabled
    g = main.ConfirmationGate(1)
    g.confirm()
    res = ctl.trust(g, "strict")
    assert res.ran is False and res.reason == "incompatible_state"
    assert mutating(eng) == []


def test_adopt_refused_when_not_marker_unadopted():
    ctl, eng = make("unknown_root")
    ctl.refresh(PATH, "strict")  # state == untrusted, NOT marker_unadopted
    g = main.ConfirmationGate(2)
    g.confirm()
    g.confirm()
    res = ctl.adopt(g, "strict")
    assert res.ran is False and res.reason == "incompatible_state"
    assert [c for c in eng.calls if "--adopt-existing" in c] == []


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
# EN/ES parity (req 7)
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
# A second operation in the same process still works (req 8)
# ---------------------------------------------------------------------------
def test_second_trust_in_same_process_still_works():
    ctl, eng = make("unknown_root")
    ctl.refresh(PATH, "strict")
    g1 = main.ConfirmationGate(1)
    g1.confirm()
    assert ctl.trust(g1, "strict").state == "trusted"

    # A different root comes up untrusted; trusting it again must still work.
    eng.status_reason = "unknown_root"
    ctl.refresh(PATH, "strict")
    g2 = main.ConfirmationGate(1)
    g2.confirm()
    res2 = ctl.trust(g2, "strict")
    assert res2.ran is True and res2.state == "trusted"
