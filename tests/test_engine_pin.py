"""Guard the bundled-engine pin and the app version against accidental drift.

The GUI ships tiddl in-process (single binary); `requirements.txt` is the SINGLE
source of truth for which engine commit is bundled — `flet build` reads it to
include the package. `TIDDL_COMMIT` is derived at RUNTIME from the installed
package's `direct_url.json` (see `main._tiddl_commit`), so it is deliberately NOT
duplicated here. 1.0.22 is pinned to engine **v1.5.4**.

Pure file reads — no `flet`/`tiddl` import — so this runs everywhere (incl. CI)
without the full GUI environment.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The exact engine commit published as v1.5.4 (post-merge tiddl-elvigilante main).
ENGINE_V1_5_4_COMMIT = "b25ff9ce8d69fbb4f2d91d5cfbc36e6568c5e881"
EXPECTED_APP_VERSION = "1.0.22"


def _requirements_text() -> str:
    return (ROOT / "requirements.txt").read_text(encoding="utf-8")


def _main_text() -> str:
    return (ROOT / "main.py").read_text(encoding="utf-8")


def test_engine_pinned_to_v1_5_4_commit():
    m = re.search(
        r"tiddl-elvigilante\s*@\s*git\+https://github\.com/np3ir/"
        r"tiddl-elvigilante\.git@([0-9a-f]{40})",
        _requirements_text(),
    )
    assert m, "engine pin line not found or not a full 40-hex commit"
    assert m.group(1) == ENGINE_V1_5_4_COMMIT


def test_pin_is_an_immutable_commit_not_a_branch_or_tag():
    pins = re.findall(r"tiddl-elvigilante\s*@\s*git\+\S+@(\S+)", _requirements_text())
    assert len(pins) == 1, f"expected exactly one engine pin, got {pins!r}"
    assert re.fullmatch(r"[0-9a-f]{40}", pins[0]), (
        f"pin must be a full commit sha, not a branch/tag: {pins[0]!r}"
    )


def test_app_version_unchanged():
    m = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', _main_text(), re.MULTILINE)
    assert m, "APP_VERSION not found in main.py"
    assert m.group(1) == EXPECTED_APP_VERSION


def test_tiddl_commit_is_derived_not_a_hardcoded_constant():
    # Single source of truth: the displayed engine commit is computed at runtime
    # from the installed package, never a constant duplicating the pin above.
    assert re.search(
        r"^TIDDL_COMMIT\s*=\s*_tiddl_commit\(\)", _main_text(), re.MULTILINE
    ), "TIDDL_COMMIT must stay derived via _tiddl_commit(), not a hardcoded sha"
