# tiddl by ElVigilante — 1.0.22

## What's new

- **Cancel / 401 / 429 no longer close the app.** With the bundled engine at
  **v1.5.4**, a cooperative safety stop — cancelling a download, or the engine's
  own stop on a TIDAL rate-limit (429) or a flagged/blocked account (401) — now
  ends the run cleanly and the window stays open, ready for the next download.
  (The engine raises `click.exceptions.Exit` instead of `sys.exit()`, which the
  in-process host now catches; previously it could hard-kill the whole GUI.)
- **Bundled engine → v1.5.4.** v1.5.4 fixes the HTTP 429 regression on large `--artists` / high-quality runs (all enumeration — playlists, artists, albums, credits — stays on the lenient TV client; the 24-bit `HI_RES_LOSSLESS` tier is fetched per-track only) and makes `max_tracks_per_session` actually stop the run (atomic per-track reservation). It also keeps the post-1.0.21 fixes for the quality cascade and `--resume`:
  - `-q atmos` no longer crashes with **Stereo** audio-mode and no longer stalls under a **Strict** quality
    policy.
  - The **"Dolby Atmos" label** now reflects the stream actually delivered (a FLAC or degraded AAC is no
    longer mislabelled).
  - The **`--resume` checkpoint signature** now covers every option that changes what a resource writes to
    disk (quality, video quality, audio-mode, edition-match, quality-policy, hires-client, naming templates,
    embedded metadata, standalone cover file, m3u, video path) — change any of them and it starts a fresh
    resume instead of skipping resources done under the old settings.
- **Resume checkbox wording:** now says it skips already-done **items** (any resource), not just artists.
- **Cleaner installer upgrades.** The Windows installer now removes the previous
  version's app payload (`app`, `data`, `DLLs`, `Lib`, `site-packages`, and the
  root `*.dll` / `tiddl*.exe` / `ffmpeg.exe`) **before** copying the new one, so an
  in-place upgrade can no longer leave orphaned files behind — which could
  otherwise make the app report the wrong bundled-engine commit. Your settings,
  authentication and downloads (outside the install folder) are untouched, and the
  uninstaller is preserved.

## Novedades

- **Cancel / 401 / 429 ya no cierran la app.** Con el motor embebido en
  **v1.5.4**, una parada de seguridad cooperativa —cancelar una descarga, o la
  parada del propio motor ante un límite de tasa de TIDAL (429) o una cuenta
  marcada/bloqueada (401)— ahora finaliza la corrida de forma limpia y la ventana
  permanece abierta, lista para la siguiente descarga. (El motor lanza
  `click.exceptions.Exit` en lugar de `sys.exit()`, que el host en proceso ahora
  captura; antes podía matar de golpe toda la GUI.)
- **Motor embebido → v1.5.4.** v1.5.4 corrige la regresión HTTP 429 en corridas grandes `--artists` / de alta calidad (toda la enumeración —playlists, artistas, álbumes, créditos— se queda en el cliente TV lenient; el nivel 24-bit `HI_RES_LOSSLESS` se pide solo por-pista) y hace que `max_tracks_per_session` detenga de verdad la corrida (reserva atómica por pista). Mantiene además los arreglos posteriores a 1.0.21 de la cascada de calidad y `--resume`:
  - `-q atmos` ya no rompe con audio-mode **Estéreo** ni se detiene con política **Estricta**.
  - La **etiqueta "Dolby Atmos"** ahora refleja el stream realmente entregado (un FLAC o AAC degradado ya no
    se rotula mal).
  - La **firma del checkpoint `--resume`** ahora cubre toda opción que cambie lo que un recurso escribe en
    disco (calidad, calidad de video, audio-mode, edition-match, quality-policy, hires-client, plantillas de
    nombres, metadata embebida, carátula suelta, m3u, ruta de video) — cambiar cualquiera arranca un resume
    limpio en vez de saltar recursos hechos con los ajustes viejos.
- **Texto del checkbox Resume:** ahora dice que salta **recursos** ya hechos, no solo artistas.
- **Actualizaciones del instalador más limpias.** El instalador de Windows ahora
  **elimina** el contenido de la versión anterior (`app`, `data`, `DLLs`, `Lib`,
  `site-packages`, y en la raíz `*.dll` / `tiddl*.exe` / `ffmpeg.exe`) **antes** de
  copiar el nuevo, así una actualización in-place ya no deja archivos huérfanos
  —que podían hacer que la app mostrara el commit del motor embebido equivocado—.
  Tus ajustes, autenticación y descargas (fuera de la carpeta de instalación)
  quedan intactos, y el desinstalador se conserva.
