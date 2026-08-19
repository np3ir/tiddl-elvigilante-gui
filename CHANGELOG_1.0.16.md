# tiddl by ElVigilante 1.0.16

## Audio editions and quality

- Added independent Audio edition (`auto` / `stereo`) and Quality policy
  (`flexible` / `strict`) selectors.
- Supports every Low, Normal, High and MAX combination.
- Flexible mode treats the selected quality as a ceiling and chooses the
  highest available tier below it.
- Strict mode requires the exact requested playback quality.
- Stereo mode resolves alternate TIDAL editions and rejects Atmos manifests
  before media transfer.
- Added `Check available versions`, a catalog-only dry run for direct album links.

## Reliability

- HTTP 401 now stops the complete run and is no longer mislabeled as a rate
  limit.
- HTTP 429 classification uses the actual response status.
- Session track-limit warning is emitted only once.
- Fatal engine stops prevent subsequent GUI command chunks from starting.
- Added `TIDDL_GUI_OFFLINE=1` for local UI validation without authentication
  refresh or update checks.

## Configuration and interface

- Made cover.jpg controls visible and enabled their dependent fields only when
  cover saving is active.
- Album is the default cover destination for older empty configurations.
- Improved advanced-field sizing, wrapping and numeric validation.
- Application and installer version advanced to 1.0.16.

## Validation

- Complete offline engine suite: 326 passed, 3 skipped, 0 failed.
- Windows application build and offline smoke launch verified at version 1.0.16
  with engine commit `862dec07`.
- Windows installer compiled successfully with Inno Setup 6.7.3; it bundles
  FFmpeg and the verified application build.
- No TIDAL account, playback or media request is required for the offline test
  suite.
