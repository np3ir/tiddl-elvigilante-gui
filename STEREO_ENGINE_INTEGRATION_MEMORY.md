# Stereo Resolver GUI Integration — Continuation Memory

Last updated: 2026-08-31

The engine repository is the sibling directory `../tiddl-elvigilante`.
Authoritative technical state is recorded in its
`STEREO_EDITION_RESOLVER_MEMORY.md`.

## Current GUI status

- GUI 1.0.16 passes the selected audio edition and quality policy to the engine.
- The new controls, catalog-only verification action, fatal-stop handling and
  responsive layout are implemented and covered by the release audit below.
- **GUI 1.0.23 (PUBLISHED — immutable artifacts):** source commit
  **`125a932bae6b4d71b54b21f35a9acafd8e37cd70`**, embedded engine
  **`b25ff9ce8d69fbb4f2d91d5cfbc36e6568c5e881`** (release **v1.5.4**). The published 1.0.23
  installers/binaries embed **v1.5.4** and their hashes are fixed; do **not** treat those public
  artifacts as containing v1.5.5. v1.5.4 fixed the frequent-429 regression in large `--artists` /
  high-quality runs by keeping enumeration on the TV client, selecting HiRes per track, and sharing one
  request budget across both clients, and made `max_tracks_per_session` stop new work reliably through
  atomic per-track reservation. It also carries the v1.5.3 host-safe cooperative stop
  (Cancel / rate-limit 429 / account-flagged 401 raise `click.exceptions.Exit` instead of `sys.exit()`,
  so the in-process engine no longer hard-kills this GUI on a stop; `run_tiddl` catches it and returns
  the exit code) and the earlier v1.5.0–v1.5.2 work: giant-run hardening (429 breaker, bounded-memory
  pool, `--resume` checkpoint), the quality cascade with Atmos + FLAC-over-Atmos, and the `-q atmos` and
  resume-signature fixes.
- **CURRENT SOURCE (GUI 1.0.24 — source prepared; first Windows build REJECTED after smoke; not published):** `requirements.txt` pins
  engine **`13c4e9151cc3fb41954ca5312f11c5d34e2ad181`** (release **v1.5.5**), which adds the cross-folder
  `Exists (Alt)` / Dolby Atmos skip fix on top of v1.5.4: skip-existing is scoped to each track's own
  folder (a same-titled FLAC in another album no longer masks an Atmos track), the real on-disk
  name/casing is preserved, and an Atmos request treats Atmos as a distinct modality; TV/HiRes routing,
  the quality cascade and the RPM budget are unchanged from v1.5.4. This source **also** carries the
  destination-identity features: **B1** (a status view — trusted / untrusted / marker-pending-adoption /
  absent / disabled / error — read through `tiddl destination status`, with Trust = one confirmation and
  Adopt = double confirmation, path captured/shown, re-validate before Adopt, re-query after each
  mutation, never auto-run) and **B2** (a `destination_identity` selector `off`/`strict`, persisted in the
  engine config and synced to the embedded engine before each run; changing the mode never creates,
  adopts, or removes identity, and switching to `strict` requires a fresh check). `APP_VERSION` is bumped
  to **1.0.24** in source. The GUI source is 1.0.24; its first Windows artifacts **were built** from this
  source but were **rejected** after the isolated startup smoke (see "v1.0.24 first Windows build" below), so
  **no valid v1.0.24 artifact has been installed or published**. The public release remains **1.0.23**. This
  is the authoritative engine pin for the 1.0.24 source and any future build.
- **v1.0.24 first Windows build — reproducible but functionally INVALID (2026-08-31):** the build from
  source `07de0808e387e3ff5f0130bd4e4d42a5e96b49fd` produced deterministic, hash-verified artifacts, but the
  isolated smoke **failed before rendering the UI**: the GUI crashed on startup building the Settings tab with
  `TypeError: Dropdown.__init__() got an unexpected keyword argument 'on_change'`. The B2 selector had been
  built as `ft.Dropdown(..., on_change=...)`, which the bundled **Flet 0.86.1** rejects as a constructor
  keyword; the handler must be attached after construction (as already done for `f_cover_save`). The offline
  suite missed it because it stubs controls and never instantiates a real `ft.Dropdown`. **All prior-hash
  v1.0.24 artifacts (EXE / provenance / installer / portable) are REJECTED and must not be published**;
  they are preserved for audit under `C:\tiddl-release\_rejected\v1.0.24-startup-crash-dropdown-on-change\`.
  The **public 1.0.23 (engine v1.5.4, no B2) is unaffected.** v1.0.24 keeps its version number because it was
  never published. **Fix (branch `fix/gui-b2-dropdown-flet-compat`, base `07de080`, APP_VERSION and engine pin
  unchanged):** the selector is built through a small `build_dest_mode_dropdown(...)` helper that binds
  `on_change` after construction, plus real-Flet 0.86.1 tests (constructor rejects the kwarg; the helper builds
  a real control and preserves value/options) and an AST guard, so a Windows rebuild + re-smoke are required
  before any future 1.0.24 publication.
- _(published historical release)_ GUI 1.0.22 pinned engine
  `3f80152d26f7b3fefbd5b3de077cbd4775648f0e` (v1.5.3). Its published artifacts and hashes remain
  unchanged; do not treat the 1.0.23 source pin as part of those binaries.
- _(historical, do not use for reproduction)_ GUI 1.0.16 pinned engine
  `a13230e6861a2c12018aa11f334b2b8c1519bb05` (itself succeeding `862dec0…`; that revision added the
  non-zero-exit-on-safety-stop and strict-Normal -> TIDAL `HIGH` fixes). Kept for provenance only.

## Rebuild required (2026-08-19)

The Windows exe/installer recorded under "Windows build verification" below were
built from engine pin `862dec0`, which predates both the two engine fixes above
and the human-readable dropdown labels / Spanish polish added to `main.py`. Those
recorded SHA-256 values are therefore stale. A fresh `build_windows.ps1` on the
new pin is required before releasing 1.0.16, and the new SHA-256 values must be
re-recorded here.

## Remaining live validation

1. Confirm the run-wide 401 stop if a token expires naturally; do not force an
   account failure solely for this test.
2. Consider a native Flet comparison dialog in a later release; version
   differences are currently reported safely in the embedded engine log.

Controlled live engine validation completed on 2026-08-19: Atmos album
`549984784` resolved to stereo album `549980023`. Strict MAX produced a
2-channel FLAC at 24-bit/48 kHz; strict High produced a 2-channel FLAC at
16-bit/44.1 kHz. Both were verified with ffprobe and exited successfully after
exactly one track. Details are in the engine continuation memory.

Flexible degradation was subsequently validated with Kinito Mendez artist
`3941799`: album `14824487` advertises LOSSLESS but not HIRES_LOSSLESS. MAX +
flexible selected High and delivered a 16-bit/44.1 kHz stereo FLAC; MAX +
strict rejected it without downloading. The engine's no-candidate diagnostic
was also corrected so an already-stereo source is no longer mislabeled Atmos.

Album `8455110`, which has no lossless catalog tag, validated MAX flexible all
the way down to LOW: TIDAL delivered a 2-channel HE-AAC file at the 96 kbps
tier and the engine reported the degradation. Normal strict rejected that LOW
manifest before transfer. The live test also led to two engine fixes: safety
stops now exit non-zero, and strict Normal correctly means TIDAL `HIGH` rather
than `LOSSLESS`. Final engine regression: 328 passed, 3 skipped, 0 failed.

## Boundaries

- Do not add MusicBrainz or ISRC-based external resolution.
- Do not change the pinned engine commit without rerunning the offline suite
  and a clean Windows build.
# GUI integration update (2026-08-19)

- GUI version advanced to 1.0.16.
- The Download tab now exposes `Audio edition` with `auto` (legacy default)
  and `stereo` choices.
- `stereo` passes `--audio-mode stereo --edition-match best` and requires the
  existing quality selector to be High or MAX.
- The preference is stored in GUI-only `gui.json`; it does not add an unknown
  field to the engine's strict `config.toml` model.
- A fatal engine stop (401 or stereo stream-policy mismatch) prevents later GUI
  command chunks from starting and is reported as an error, not success.
- Playback metadata is inspected before media transfer; an Atmos manifest is
  rejected when stereo was requested.
- GUI now also exposes `Quality policy`: `flexible` preserves normal fallback,
  while `strict` requires the exact selected Low/Normal/High/MAX tier.
- Audio edition, quality, and policy are independent, providing the complete
  preference matrix including strict Stereo High and strict Stereo MAX.
- In `flexible`, the selected quality is a ceiling: the engine chooses the
  highest available catalog/playback tier at or below it.
- Added `Check available versions` (`Comprobar versiones disponibles`) to the
  Download tab. It accepts direct album links,
  requires `Audio edition = stereo`, passes the selected quality/policy with
  `--dry-run`, and exits in the engine before `Downloader` is constructed.
- The verification button shares the normal run lock and is disabled while a
  run is active, so it cannot overlap a download.
- Initial offline engine regression baseline: 326 passed, 3 skipped, 0 failed.
  The prior recover failures were eliminated by isolating tests from the local
  machine's strict destination-identity configuration.

## Offline release-readiness audit

- Added `TIDDL_GUI_OFFLINE=1`; source previews skip auth refresh and GitHub
  update checks, allowing UI inspection without touching the blocked account.
- Opened the 1.0.16 source preview successfully. The first visual pass found
  that the expanded preference/action row clipped Verify/Download/Cancel at the
  default 900 px width. Preferences and actions are now separate wrapping rows.
- Added `CHANGELOG_1.0.16.md`.
- Flet 0.86.1, Flutter 3.44.4 and Python build 1.5.0 are available locally.
- Initial probing missed the per-user Inno Setup installation; later `winget
  list` and the exact LocalAppData path confirmed Inno Setup 6.7.3 was already
  installed.
- At audit time `requirements.txt` pinned an older remote engine commit; it was
  subsequently updated to the local resolver commit recorded below.

### Local release branches

- Engine branch: `codex/stereo-quality-policies`.
- Engine commit: `862dec07455aa2716089f4d0ba587f5eecb91d47`.
- GUI `requirements.txt` now pins that exact commit. A remote/clean build must
  wait until the engine branch or commit is pushed to GitHub.

### Windows build verification

- Engine and GUI branches were pushed and their remote hashes matched locally.
- Hardened `build_windows.ps1`: validates the exact `C:\tiddl-gui` staging
  target before deleting its `build` child and no longer overwrites HOME or
  USERPROFILE.
- Flet produced `C:\tiddl-gui\build\windows\tiddl-gui.exe` successfully.
- File/Product version: 1.0.16.
- SHA-256: `C8C1429457062ADB6BF614CC23415FA5270C8E58BEC4BF29AE150C574097FE9B`.
- Packaged `direct_url.json` confirms engine commit
  `862dec07455aa2716089f4d0ba587f5eecb91d47`; compiled resolver, stream-policy
  and download-policy modules are present.
- Offline smoke launch succeeded. Visual inspection at the default 900 px width
  confirmed Quality, Audio edition, Quality policy, version check, Download
  and Cancel are fully visible after the wrapping-row fix.
- Inno Setup 6.7.3 successfully produced
  `C:\tiddl-release\installer\tiddl-ElVigilante-Setup-1.0.16.exe`.
- Installer size: 78.25 MiB. Product version: 1.0.16.
- Installer SHA-256:
  `97D6EFD9E4D5DADD6A5E814FEECD1727923E31C0AD54C4DB64A1C8228B771691`.
- Authenticode status is `NotSigned`; code signing remains a release decision.
- The installer was compiled and inspected but intentionally not installed over
  the user's existing 1.0.14 installation during this automated validation.
