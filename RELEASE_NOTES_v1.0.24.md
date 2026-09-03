# tiddl by ElVigilante v1.0.24

> **Release v1.0.24.** Windows, Linux and macOS artifacts were built and validated
> from the audited v1.0.24 source. macOS is ad-hoc signed (not notarized). This
> release supersedes GUI v1.0.23.

## 🇬🇧 What's new

**Bundled engine → v1.5.5.** The GUI pins engine commit
`13c4e9151cc3fb41954ca5312f11c5d34e2ad181`.

- **Cross-folder `Exists (Alt)` / Dolby Atmos fix.** A Dolby Atmos track is no
  longer skipped because a same-titled FLAC lives in a **different** album:
  alternatives are limited to the track's **own** folder, the real on-disk
  name/casing is preserved, and Atmos is treated as a distinct modality. TV/HiRes
  routing, the quality cascade, and the RPM budget are unchanged from v1.5.4.

**Destination identity (B1).**

- A status view reports whether the destination volume is **trusted**,
  **untrusted**, has a **marker pending adoption**, is **absent/not mounted**, is
  **disabled**, or is in an **error** state — read through the engine, never by
  touching the anchor files.
- **Trust** shows the exact path; the path is **captured and used exactly for the
  operation** and needs **one explicit confirmation**. **Adopt** needs **double
  confirmation**; Adopt **re-validates the status before opening the confirmation
  flow and re-queries the status after the operation**. **Trust and Adopt never run
  automatically.**

**Identity mode selector (B2).**

- Choose `destination_identity` = **`off`** or **`strict`**; the choice persists in
  the engine config and is applied to the embedded engine before each download.
- ⚠️ **`off` allows downloads to write WITHOUT verifying the destination volume
  identity.** **`strict`** requires the mounted destination to match a trusted
  identity before writing. Changing the mode does not create, adopt, or remove any
  identity; switching to `strict` requires a fresh status check before mutating
  actions become available.

**macOS: FFmpeg is now external.** macOS no longer bundles FFmpeg in the `.app`/DMG
— install it with `brew install ffmpeg` (same model as Linux). The app finds
Homebrew's ffmpeg automatically even when launched from Finder (`/opt/homebrew/bin`
on Apple Silicon, `/usr/local/bin` on Intel); if it is missing, a bilingual message
tells you and the app stays open. Windows still bundles `ffmpeg.exe`. The first
v1.0.24 macOS DMG (which bundled a non-portable Homebrew ffmpeg) was rejected and
never published.

**Release lineage.**

- **Public GUI 1.0.23** is an immutable artifact bundling engine **v1.5.4**; it does
  **not** contain B1/B2.
- **GUI 1.0.24** includes engine **v1.5.5** + B1 + B2. Its Windows, Linux and
  macOS artifacts passed their platform-specific build and smoke gates.

## 🇪🇸 Novedades

**Motor embebido → v1.5.5.** La GUI fija el commit del motor
`13c4e9151cc3fb41954ca5312f11c5d34e2ad181`.

- **Corrección de `Exists (Alt)` entre carpetas / Dolby Atmos.** Una pista Dolby
  Atmos ya no se omite porque exista un FLAC homónimo en **otro** álbum: las
  alternativas se limitan a la carpeta **propia** de la pista, se preserva el
  nombre/casing real en disco y Atmos se trata como una modalidad distinta. El
  enrutamiento TV/HiRes, la cascada de calidad y el presupuesto RPM no cambian
  respecto a v1.5.4.

**Identidad del destino (B1).**

- Una vista de estado informa si el volumen de destino es **confiable**, **no
  confiable**, tiene un **marcador pendiente de adopción**, está **ausente/no
  montado**, está **desactivado** o en estado de **error** — consultado a través del
  motor, nunca tocando los archivos de anclas.
- **Confiar** muestra la ruta exacta; la ruta se **captura y usa exactamente para
  la operación** y necesita **una confirmación explícita**. **Adoptar** necesita
  **doble confirmación**; Adoptar **revalida el estado antes de abrir el flujo de
  confirmación y vuelve a consultarlo después de la operación**. **Trust y Adopt
  nunca se ejecutan automáticamente.**

**Selector del modo de identidad (B2).**

- Elige `destination_identity` = **`off`** o **`strict`**; la elección persiste en la
  configuración del motor y se aplica al motor embebido antes de cada descarga.
- ⚠️ **`off` permite que las descargas escriban SIN verificar la identidad del
  volumen de destino.** **`strict`** exige que el destino montado coincida con una
  identidad confiable antes de escribir. Cambiar el modo no crea, adopta ni elimina
  ninguna identidad; pasar a `strict` exige una nueva comprobación antes de que las
  acciones mutadoras estén disponibles.

**macOS: FFmpeg ahora es externo.** macOS ya no incluye FFmpeg en el `.app`/DMG —
instálalo con `brew install ffmpeg` (mismo modelo que Linux). La app encuentra el
ffmpeg de Homebrew automáticamente incluso al abrir desde Finder (`/opt/homebrew/bin`
en Apple Silicon, `/usr/local/bin` en Intel); si falta, un mensaje bilingüe te avisa y
la app sigue abierta. Windows sigue incluyendo `ffmpeg.exe`. El primer DMG v1.0.24 de
macOS (que empaquetaba un ffmpeg de Homebrew no portable) fue rechazado y nunca
publicado.

**Historial de la release.**

- La **GUI 1.0.23 pública** es un artefacto inmutable con motor **v1.5.4**; **no**
  contiene B1/B2.
- La **GUI 1.0.24** incluye el motor **v1.5.5** + B1 + B2. Sus artefactos para
  Windows, Linux y macOS superaron los gates de build y smoke de cada plataforma.
