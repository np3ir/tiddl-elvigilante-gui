# tiddl by ElVigilante 1.0.18

## Performance

- **Artist stereo resolution is now fast.** Selecting *Stereo only* on a large
  artist previously re-queried the catalog once per album and could take
  minutes; a per-run cache now resolves a whole discography in seconds, with
  identical results. (Bundled engine updated to v1.3.2.)

## Engine

- Bundled TIDAL engine → v1.3.2 (artist-catalog cache on top of the v1.3.1
  artist-URL stereo resolution).

## Validation

- Engine offline suite: 337 passed, 3 skipped, 0 failed.
- Live dry-run (KAROL G, ~131 albums): ~7 min → ~3 s, bit-identical results.
- Windows and Linux rebuilt from this revision; macOS DMG to follow.
