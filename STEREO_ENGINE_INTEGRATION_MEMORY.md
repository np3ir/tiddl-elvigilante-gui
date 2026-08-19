# Stereo Resolver GUI Integration — Continuation Memory

Last updated: 2026-08-19

The engine repository is the sibling directory `../tiddl-elvigilante`.
Authoritative technical state is recorded in its
`STEREO_EDITION_RESOLVER_MEMORY.md`.

## Current GUI status

- GUI remains behavior-compatible and does not yet pass `--audio-mode`.
- Existing GUI improvements target release 1.0.15: visible cover.jpg controls,
  responsive advanced settings, numeric validation, version synchronization.
- The bundled engine pin in `requirements.txt` must not be changed until the
  resolver download integration and stream validation are tested and committed.

## Planned GUI work

After the engine is validated:

1. Add audio-mode selector: `Automatic/original link` and `Stereo only`.
2. Keep `Automatic` as the migration-safe default.
3. Quality remains independent: High requests Lossless; MAX requests HiRes
   Lossless with the existing fallback policy.
4. Present an Flet confirmation dialog when the engine reports track-list
   differences; do not rely on terminal `typer.confirm` in the embedded GUI.
5. Display original/replacement IDs, score, missing tracks, and extra tracks.
6. Validate actual playback stream mode/quality before claiming Stereo/MAX.

## Do not do yet

- Do not expose a GUI switch before the engine has a non-interactive planning
  API suitable for Flet.
- Do not add MusicBrainz or ISRC-based external resolution.
- Do not update the bundled commit merely because the CLI diagnostic exists.
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
- Added `Verify versions` to the Download tab. It accepts direct album links,
  requires `Audio edition = stereo`, passes the selected quality/policy with
  `--dry-run`, and exits in the engine before `Downloader` is constructed.
- The verification button shares the normal run lock and is disabled while a
  run is active, so it cannot overlap a download.
- Final offline engine regression baseline: 326 passed, 3 skipped, 0 failed.
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
- Inno Setup (`ISCC.exe`) is not installed, so the final `.exe` installer cannot
  be produced offline on this machine yet.
- At audit time `requirements.txt` pinned an older remote engine commit; it was
  subsequently updated to the local resolver commit recorded below.

### Local release branches

- Engine branch: `codex/stereo-quality-policies`.
- Engine commit: `862dec07455aa2716089f4d0ba587f5eecb91d47`.
- GUI `requirements.txt` now pins that exact commit. A remote/clean build must
  wait until the engine branch or commit is pushed to GitHub.
