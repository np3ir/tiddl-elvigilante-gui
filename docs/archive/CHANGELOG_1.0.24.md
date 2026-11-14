# tiddl by ElVigilante — 1.0.24

> Release v1.0.24 bundles engine **v1.5.5** and adds the destination-identity
> features B1 and B2. Windows, Linux and macOS artifacts were built and validated
> from the audited source. macOS is ad-hoc signed (not notarized).

## What's new

### Bundled engine → v1.5.5

- **Bundled engine updated to v1.5.5.** The GUI pins the exact published engine
  commit `13c4e9151cc3fb41954ca5312f11c5d34e2ad181`.
- **Cross-folder `Exists (Alt)` fix.** v1.5.5 corrects false `Exists (Alt)`
  detections between folders: a Dolby Atmos track is no longer skipped because a
  same-titled FLAC lives in a **different** album. Alternatives are limited to the
  track's **own** folder, the **real on-disk name and casing** are preserved, and
  an Atmos request treats Atmos as a distinct modality (a stereo file no longer
  satisfies it).
- **No routing/quality/RPM change vs v1.5.4.** TV/HiRes client routing, the quality
  cascade, and the per-run request (RPM) budget are unchanged from v1.5.4.

### B1 — Destination identity (status + trust/adopt)

- A **Destination identity** section shows the trust status of the configured
  destination volume, with differentiated states: **trusted**, **untrusted**,
  **marker present but not adopted**, **absent / not mounted**, **disabled**, and
  **error / unrecognized**.
- The status is read **through the engine** (`tiddl destination status`); the GUI
  never reads or writes the anchor files directly.
- **Trust mounted destination** shows the **exact path** and requires **one
  explicit confirmation**; **Adopt existing identity** requires **double
  confirmation** and is offered only in the appropriate state.
- The path is **captured and used exactly** for the operation. Adopt **re-validates
  the status before opening the confirmation flow and re-queries the status after
  the operation**; every mutation re-queries the status afterwards; and
  **Trust/Adopt never run automatically**.

### B2 — Identity mode selector

- A selector for `destination_identity` with values **`off`** and **`strict`**.
- The choice **persists** in the engine configuration and is **synced to the
  embedded engine** before each download.
- **`off`** allows downloads **without verifying the destination volume identity**;
  **`strict`** requires the mounted destination to match a trusted identity before
  writing.
- Changing the mode **does not create, adopt, or remove** any identity; switching
  to **`strict`** requires a **fresh status check** before any mutating action
  becomes available.

### macOS: FFmpeg is now an external dependency

- **macOS no longer bundles FFmpeg** inside the `.app`/DMG — it is an external
  dependency, the same model Linux already uses. Install it with
  `brew install ffmpeg`.
- **Why.** The previous approach copied Homebrew's `ffmpeg`, which links against
  `/opt/homebrew/…` dylibs and is arm64-only — it would not run on a clean Mac.
  That first v1.0.24 DMG was **rejected and never published**.
- **Finder-safe resolution.** The GUI resolves an external ffmpeg from a
  deterministic list — an explicit `TIDDL_FFMPEG` override, then `PATH`, then
  `/opt/homebrew/bin/ffmpeg` (Apple Silicon) and `/usr/local/bin/ffmpeg` (Intel) —
  validates it (`ffmpeg -version`), and prepends its directory to `PATH` so the
  engine finds it even when the app is launched from Finder with a minimal `PATH`.
- **Clear message when missing.** If ffmpeg is not found, the app shows a
  bilingual, actionable message and stays open (no crash) instead of starting a
  download that would break on remux.
- **Per platform:** Windows bundles `ffmpeg.exe`; Linux and macOS use an external
  ffmpeg from the system/package manager.

### Release lineage

- **Public GUI 1.0.23** — immutable artifact, engine **v1.5.4**, does **not**
  contain B1/B2.
- **GUI 1.0.24** — engine **v1.5.5**, B1 + B2; Windows, Linux and macOS artifacts
  passed their platform-specific build and smoke gates.

## Novedades

### Motor embebido → v1.5.5

- **Motor embebido actualizado a v1.5.5.** La GUI fija el commit publicado exacto
  del motor: `13c4e9151cc3fb41954ca5312f11c5d34e2ad181`.
- **Corrección de `Exists (Alt)` entre carpetas.** v1.5.5 corrige falsos
  `Exists (Alt)` entre carpetas: una pista Dolby Atmos ya no se omite porque exista
  un FLAC homónimo en **otro** álbum. Las alternativas se limitan a la carpeta
  **propia** de la pista, se preserva el **nombre y casing real en disco**, y una
  solicitud Atmos trata Atmos como una modalidad distinta (un archivo estéreo ya no
  la satisface).
- **Sin cambios de routing/calidad/RPM respecto a v1.5.4.** El enrutamiento de
  clientes TV/HiRes, la cascada de calidad y el presupuesto de peticiones (RPM) por
  corrida no cambian respecto a v1.5.4.

### B1 — Identidad del destino (estado + trust/adopt)

- Una sección **Identidad del destino** muestra el estado de confianza del volumen
  de destino configurado, con estados diferenciados: **confiable**, **no
  confiable**, **marcador pendiente de adopción**, **ausente / no montado**,
  **desactivado** y **error / no reconocido**.
- El estado se consulta **a través del motor** (`tiddl destination status`); la GUI
  nunca lee ni escribe directamente los archivos de anclas.
- **Confiar destino montado** muestra la **ruta exacta** y exige **una confirmación
  explícita**; **Adoptar identidad existente** exige **doble confirmación** y solo
  se ofrece en el estado apropiado.
- La ruta se **captura y usa exactamente** para la operación. Adoptar **revalida el
  estado antes de abrir el flujo de confirmación y vuelve a consultarlo después de
  la operación**; cada mutación vuelve a consultar el estado después; y
  **Trust/Adopt nunca se ejecutan automáticamente**.

### B2 — Selector del modo de identidad

- Un selector de `destination_identity` con valores **`off`** y **`strict`**.
- La elección **persiste** en la configuración del motor y se **sincroniza con el
  motor embebido** antes de cada descarga.
- **`off`** permite descargar **sin verificar la identidad del volumen de destino**;
  **`strict`** exige que el destino montado coincida con una identidad confiable
  antes de escribir.
- Cambiar el modo **no crea, adopta ni elimina** ninguna identidad; pasar a
  **`strict`** exige una **nueva comprobación** antes de habilitar cualquier acción
  mutadora.

### macOS: FFmpeg ahora es dependencia externa

- **macOS ya no incluye FFmpeg** dentro del `.app`/DMG — es dependencia externa,
  el mismo modelo que ya usa Linux. Instálalo con `brew install ffmpeg`.
- **Por qué.** El enfoque anterior copiaba el `ffmpeg` de Homebrew, que enlaza
  contra dylibs de `/opt/homebrew/…` y es solo arm64 — no corría en un Mac limpio.
  Ese primer DMG v1.0.24 fue **rechazado y nunca publicado**.
- **Resolución compatible con Finder.** La GUI resuelve un ffmpeg externo de una
  lista determinista — override explícito `TIDDL_FFMPEG`, luego `PATH`, luego
  `/opt/homebrew/bin/ffmpeg` (Apple Silicon) y `/usr/local/bin/ffmpeg` (Intel) —,
  lo valida (`ffmpeg -version`) y antepone su directorio al `PATH` para que el
  motor lo encuentre incluso al abrir desde Finder con un `PATH` mínimo.
- **Mensaje claro si falta.** Si no se encuentra ffmpeg, la app muestra un mensaje
  bilingüe y accionable y sigue abierta (sin crash), en vez de empezar una descarga
  que fallaría en el remux.
- **Por plataforma:** Windows incluye `ffmpeg.exe`; Linux y macOS usan un ffmpeg
  externo del sistema/gestor de paquetes.

### Historial de la release

- **GUI 1.0.23 pública** — artefacto inmutable, motor **v1.5.4**, **no** contiene
  B1/B2.
- **GUI 1.0.24** — motor **v1.5.5**, B1 + B2; los artefactos de Windows, Linux y
  macOS superaron sus gates de build y smoke específicos de plataforma.
