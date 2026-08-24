# tiddl by ElVigilante — 1.0.22

## What's new

- **Bundled engine → v1.5.2.** Brings the post-1.0.21 fixes for the quality cascade and `--resume`:
  - `-q atmos` no longer crashes with **Stereo** audio-mode and no longer stalls under a **Strict** quality
    policy.
  - The **"Dolby Atmos" label** now reflects the stream actually delivered (a FLAC or degraded AAC is no
    longer mislabelled).
  - The **`--resume` checkpoint signature** now covers every option that changes what a resource writes to
    disk (quality, video quality, audio-mode, edition-match, quality-policy, hires-client, naming templates,
    embedded metadata, standalone cover file, m3u, video path) — change any of them and it starts a fresh
    resume instead of skipping resources done under the old settings.
- **Resume checkbox wording:** now says it skips already-done **items** (any resource), not just artists.

## Novedades

- **Motor embebido → v1.5.2.** Trae los arreglos posteriores a 1.0.21 de la cascada de calidad y `--resume`:
  - `-q atmos` ya no rompe con audio-mode **Estéreo** ni se detiene con política **Estricta**.
  - La **etiqueta "Dolby Atmos"** ahora refleja el stream realmente entregado (un FLAC o AAC degradado ya no
    se rotula mal).
  - La **firma del checkpoint `--resume`** ahora cubre toda opción que cambie lo que un recurso escribe en
    disco (calidad, calidad de video, audio-mode, edition-match, quality-policy, hires-client, plantillas de
    nombres, metadata embebida, carátula suelta, m3u, ruta de video) — cambiar cualquiera arranca un resume
    limpio en vez de saltar recursos hechos con los ajustes viejos.
- **Texto del checkbox Resume:** ahora dice que salta **items** ya hechos (cualquier recurso), no solo artistas.
