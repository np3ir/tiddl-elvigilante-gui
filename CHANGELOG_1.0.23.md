# tiddl by ElVigilante — 1.0.23

## What's new

- **Bundled engine updated to v1.5.5.** The GUI now pins the exact published
  engine commit `13c4e9151cc3fb41954ca5312f11c5d34e2ad181`.
- **Cross-folder `Exists (Alt)` fix (v1.5.5).** The skip-existing check is now
  scoped to each track's own folder, so a Dolby Atmos track is no longer skipped
  because a same-titled FLAC lives in a different album. The real on-disk
  name/casing is preserved, and an Atmos request treats Atmos as a distinct
  modality (a stereo file no longer satisfies it).
- **Fewer HTTP 429 responses in large high-quality runs.** Playlist, artist,
  album and credit enumeration stays on the TV client; the HiRes client is used
  per track only when the requested quality requires it. Both clients share one
  request budget.
- **High and Max retain their intended behavior.** High prefers lossless FLAC
  without promoting the whole run to HiRes. Max requests 24-bit
  `HI_RES_LOSSLESS` when TIDAL offers it and degrades according to the selected
  quality policy when it does not.
- **The session track limit now stops new work reliably.** Once
  `max_tracks_per_session` is reached, no new resource is dequeued or started;
  already-started work finishes cleanly. Atomic per-track reservation prevents
  concurrent workers from exceeding the configured cap.
- The host-safe behavior introduced with engine v1.5.3 remains in place:
  cooperative Cancel, 401 and 429 stops do not close the GUI, and the same app
  instance remains available for another download.

## Novedades

- **Motor embebido actualizado a v1.5.5.** La GUI fija ahora el commit publicado
  exacto del motor: `13c4e9151cc3fb41954ca5312f11c5d34e2ad181`.
- **Corrección de `Exists (Alt)` entre carpetas (v1.5.5).** La comprobación de
  «ya existe» se limita ahora a la carpeta propia de cada pista, de modo que una
  pista Dolby Atmos ya no se omite porque exista un FLAC homónimo en otro álbum.
  Se preserva el nombre/casing real en disco, y una solicitud Atmos trata Atmos
  como una modalidad distinta (un archivo estéreo ya no la satisface).
- **Menos respuestas HTTP 429 en corridas grandes de alta calidad.** La
  enumeración de playlists, artistas, álbumes y créditos permanece en el cliente
  TV; el cliente HiRes se usa por pista únicamente cuando la calidad solicitada
  lo requiere. Ambos clientes comparten un solo presupuesto de peticiones.
- **High y Max conservan el comportamiento esperado.** High prefiere FLAC sin
  pérdida sin promover toda la corrida a HiRes. Max solicita
  `HI_RES_LOSSLESS` de 24 bits cuando TIDAL lo ofrece y degrada según la política
  de calidad seleccionada cuando no está disponible.
- **El límite de pistas por sesión detiene de forma fiable el trabajo nuevo.** Al
  alcanzar `max_tracks_per_session`, no se toma ni inicia ningún recurso nuevo;
  el trabajo ya iniciado termina limpiamente. La reserva atómica por pista evita
  que trabajadores concurrentes excedan el límite configurado.
- Se conserva el comportamiento host-safe introducido con el motor v1.5.3: las
  paradas cooperativas por Cancel, 401 y 429 no cierran la GUI, y la misma
  instancia queda disponible para otra descarga.
