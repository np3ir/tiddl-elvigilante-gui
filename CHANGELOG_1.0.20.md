# tiddl by ElVigilante 1.0.20

## Diagnostics & resilience

- **Crash log.** If the app ever closes unexpectedly while processing, it now
  writes the cause to `gui-crash.log` in your tiddl config folder (`~/.tiddl` by
  default) — native crashes and uncaught errors included. This makes a
  "closed while downloading" actually diagnosable instead of vanishing silently.
- **Per-album resilience (engine v1.4.2).** When downloading a whole artist (or
  a playlist expanded into artists), one album failing — geo-block, a transient
  API error, a bad manifest — no longer aborts the rest of the discography. Each
  album is tried independently and failures are logged and skipped. A run-wide
  safety stop (e.g. authentication) still stops the run as before.

## Notes

- If you hit "closes after many artists", grab `gui-crash.log` — it now records
  what happened. Very large jobs (expanding a whole playlist into full
  discographies in stereo) can still exhaust TIDAL's rate limits; do those in
  smaller batches and re-run `tiddl auth login` if the token gets flagged.
- Bundled TIDAL engine → v1.4.2.
