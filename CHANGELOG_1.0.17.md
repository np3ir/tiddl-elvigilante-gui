# tiddl by ElVigilante 1.0.17

## Stereo editions

- **Stereo now works on artist links.** Selecting *Stereo only* and pasting an
  artist URL resolves every album in the artist's discography to its stereo
  edition (honouring the singles filter). An album with no stereo edition keeps
  its original and is still downloaded, so no album is silently dropped. Album,
  playlist, mix and single-track behaviour is unchanged.

## Interface

- Fixed clipped field labels in the Settings sections: the top of each
  section's first row of fields was cut off (e.g. "Delay por álbum (s)" showed
  as just "(s)"). Labels now render in full.
- The Help tab shows the format modifier inline for number and date variables
  (zero-pad `{item.number:02}` → 06; date `{album.date:%Y}` → 1997), instead of
  only in the separate Format-modifiers section.

## Engine

- Bundled TIDAL engine updated to v1.3.1 (+ dedup polish): artist-URL stereo
  resolution, plus the earlier non-zero exit on a safety stop and the
  strict `Normal` → TIDAL `HIGH` mapping.

## Validation

- Engine offline suite: 333 passed, 3 skipped, 0 failed.
- Windows and Linux rebuilt from this revision; macOS DMG to follow.
