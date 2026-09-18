# tiddl GUI — User Manual

**English** · [Español](MANUAL.es.md) · [← Back to README](../README.md)

> For personal, educational and archival use only. Not affiliated with TIDAL. You are
> responsible for complying with TIDAL's terms of service and your local copyright laws.
> Downloaded content is for personal use and may not be shared or redistributed.

Paste a link, pick the quality, and go — a desktop app with the full power of the
[`tiddl`](https://github.com/np3ir/tiddl-elvigilante) engine underneath. Requires an active
TIDAL subscription (HiFi for lossless).

---

## Getting started (3 steps)

### 1. Install the app

- **Windows** — download `tiddl-ElVigilante-Setup-x.x.x.exe` from the
  [Releases](../../../releases) page and run it. Everything is bundled: no Python, no ffmpeg to
  install. SmartScreen will warn because the installer is unsigned — click
  **More info → Run anyway**.
- **Linux** — extract `tiddl-ElVigilante-x.x.x-linux-x64.tar.gz`, install ffmpeg from your distro
  (`sudo apt install ffmpeg`), then run `./tiddl-gui`.
- **macOS** — open the `.dmg` (Apple Silicon) and drag the app to Applications. If it says
  *"damaged"*, clear the quarantine flag once:
  ```bash
  chmod -R u+w "/Applications/tiddl-gui.app"
  xattr -cr "/Applications/tiddl-gui.app"
  ```

### 2. Log in to TIDAL

Open the app and click **Log in to TIDAL**. It uses TIDAL's device-code flow, so your browser
opens to approve the app.

> **Important:** the browser opens **twice** — once for Hi-Res and once for Lossless.
> **Approve both.** Login only counts as complete when both quality tokens are saved. Use
> **Log out** anytime to clear the session.

### 3. Your first download

On the **Download** tab, paste one or more TIDAL links into **TIDAL links** — a track, album,
playlist, artist or mix, **one per line**. Pick a **Quality**, then press **Download**. The
progress bar shows `N/M · %`, the current track and a timestamped log.

> Before your very first download, open **Settings** and set your **Download folder**.

![The Download tab](../assets/screenshots/01-download.png)

---

## Edition & quality

Two independent controls decide *what* you get and *how strictly*.

### Quality tiers

| Tier | What it delivers |
|---|---|
| **Low** / **Normal** | Lossy AAC — smallest files; Low needs no particular subscription tier. |
| **High (lossless)** | CD-quality FLAC. No ffmpeg remux needed, so it's the fastest lossless option. |
| **MAX (Hi-Res lossless)** | Up to 24-bit Hi-Res FLAC. High and MAX **prefer FLAC**; an Atmos-only track at MAX climbs to the best 24-bit FLAC available. |
| **Atmos (Dolby Atmos)** | Takes the Dolby Atmos edition first, where one exists. |

### Audio edition & quality policy

- **Automatic (original link)** — keeps the album or track from the link you supplied, including
  Atmos when that's the linked edition.
- **Stereo only** — searches TIDAL for a matching stereo edition and rejects an Atmos manifest
  before any audio transfers. Works on direct **album** links **and** whole **artist** links; an
  album with no stereo edition keeps its original.
- **Flexible** — treats the selected quality as a **ceiling** and uses the best available tier at
  or below it (MAX may fall back to High, Normal or Low).
- **Strict** — requires the **exact** tier. If TIDAL won't deliver it, the download stops instead
  of quietly degrading.

> **Check first, download later:** use **Check available versions** (direct album links only, with
> **Stereo only** selected) to see a compatible stereo edition and compare track-list differences
> *before* transferring any audio.

---

## Playlists & artists

When you paste a playlist or artist link, the app asks how to expand it so the folder layout and
templates come out right.

### Playlist link detected — how to download it

- **As playlist** — playlist template and folder, plus an `.m3u` if enabled.
- **Full albums** — the complete album of every track (deduplicated).
- **Artist discographies** — everything by every credited artist. **This can be a LOT.**
- **Only the tracks** — each track standalone, with the track template and folders.

> **Safety dialog:** for whole-artist downloads, a confirmation dialog warns you before pulling a
> full discography (hundreds of albums) and lets you choose singles / videos per run. Nothing large
> starts without a **Continue**. A link to a single track inside an album asks: **Full album** or
> **Only that track**.

**Skip compilations / live albums.** Under **Settings → Advanced download**, two checkboxes leave
compilations and/or live albums out of whole-artist downloads. They're identified from the TIDAL
artist page — the same Compilations / Live sections the TIDAL app shows — so the match is reliable.
Off by default.

![The playlist dialog](../assets/screenshots/04-playlist-dialog.png)

---

## Settings, section by section

Settings apply to every download from this window. **Save as defaults** also writes them to
tiddl's `config.toml` (a backup is made), so the command line uses them too. **Reload** re-reads
that file.

- **📁 Folders** — Download folder (where music is saved), Scan folder (where existing downloads
  are detected, usually the same), Video folder (optional override), Playlist folder (optional;
  can be another disk).
- **🔤 File naming** — templates for default / track / album / playlist / video / mix, plus an
  Artist separator. Uses variables like `{album.artist}`, `{album.title}`, `{item.number:02}` —
  see the in-app **Help** tab.
- **🏷️ Metadata / tags** — Embed cover art in the file; Embed album review in the comment.
- **🖼️ Cover file (.jpg)** — Save a cover.jpg next to the audio; Size (px, max 1280); Save for:
  Tracks / Albums / Playlists / Mixes.
- **⚙️ Advanced download** — Video quality; HiRes client (auto / always / never); Requests / min;
  Artist concurrency; Max tracks / session; Rewrite metadata on existing files; Set file date to
  release date; Skip compilations / live albums (artist downloads).
- **📃 Playlists (.m3u)** — Generate .m3u files; Generate for: Tracks / Albums / Playlists / Mixes.
- **🚀 Performance & filters** — Threads, Track delay, Album delay (anti-bot); Embed lyrics in
  tags; Save .lrc sidecar files; Singles / Videos filters.
- **🎨 Appearance** — Language (English / Español), Theme (violet dark or light), Font size
  (Normal / Large / Extra large). These lock while a download runs — finish or cancel first.

![The Settings tab](../assets/screenshots/02-settings.png)

---

## While it runs — progress, resume & the log

- **Resume (skip items already done)** — skips files already in your library on a re-run.
- **Re-download existing files** — the opposite: force a fresh copy.
- **Cancel** — stops the run cleanly; the log freezes instantly and no more items start.
- **Copy log** — puts the full timestamped log on your clipboard for troubleshooting.
- **Single-download lock** — multiple windows can't hammer the API at once.

> **"Exists" is not an error.** When a track shows *Exists*, it's already in your Scan folder /
> library and is correctly skipped. `Total downloads: 0` means everything was already there —
> nothing failed.

---

## Troubleshooting

**Windows blocks the installer (SmartScreen).** The installer is unsigned. Click **More info → Run
anyway** — it's safe, just not code-signed.

**macOS says the app is "damaged and can't be opened".** That's the quarantine flag on an unsigned
app. Run `chmod -R u+w "/Applications/tiddl-gui.app"` then `xattr -cr "/Applications/tiddl-gui.app"`
once, and open it again.

**Rate-limited / 429 errors.** Keep **HiRes client = auto** (Settings → Advanced) so the Hi-Res
client is only used at MAX — that avoids most 429s. If you're downloading a lot, lower
**Requests / min** and add a small **Track delay**.

**"Not logged in to TIDAL".** Click **Log in to TIDAL** and approve **both** browser windows
(Hi-Res + Lossless). Lossless/Hi-Res needs an active HiFi subscription.

**Wrong folder structure.** For a playlist, the expand dialog (As playlist / Full albums / Artist
discographies / Only the tracks) picks the layout. Templates live under **Settings → File
naming**; the **Help** tab lists every variable.

**Where are my settings stored?** **Save as defaults** writes to tiddl's `config.toml` (a
timestamped backup is made first), so the CLI and the GUI share the same defaults.

![The in-app Help tab](../assets/screenshots/03-help.png)

---

*tiddl GUI by ElVigilante — a desktop front-end for the
[tiddl-elvigilante](https://github.com/np3ir/tiddl-elvigilante) downloader.*
