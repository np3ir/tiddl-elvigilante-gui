# tiddl GUI — Manual de uso

[English](MANUAL.md) · **Español** · [← Volver al README](../README.es.md)

> Solo para uso personal, educativo y de archivo. Sin afiliación con ningún servicio de streaming
> de música. Eres responsable de cumplir los términos de servicio de tu servicio de streaming y las
> leyes de derechos de autor locales. El contenido
> descargado es para uso personal y no puede compartirse ni redistribuirse.

Pega un enlace, elige la calidad y listo — una app de escritorio con todo el poder del motor
[`tiddl`](https://github.com/np3ir/tiddl-elvigilante) por debajo. Requiere una suscripción activa a
un servicio de música (HiFi para calidad sin pérdida).

---

## Primeros pasos (3 pasos)

### 1. Instala la app

- **Windows** — baja `tiddl-ElVigilante-Setup-x.x.x.exe` de la página de
  [Releases](../../../releases) y ejecútalo. Trae todo incluido: no hace falta Python ni ffmpeg.
  SmartScreen avisará porque el instalador no está firmado — pulsa
  **Más información → Ejecutar de todas formas**.
- **Linux** — extrae `tiddl-ElVigilante-x.x.x-linux-x64.tar.gz`, instala ffmpeg de tu distro
  (`sudo apt install ffmpeg`) y corre `./tiddl-gui`.
- **macOS** — abre el `.dmg` (Apple Silicon) y arrastra la app a Aplicaciones. Si dice *"dañado"*,
  quita la cuarentena una vez:
  ```bash
  chmod -R u+w "/Applications/tiddl-gui.app"
  xattr -cr "/Applications/tiddl-gui.app"
  ```

### 2. Inicia sesión en tu cuenta

Abre la app y pulsa **Log in**. Usa un flujo de inicio de sesión por código de dispositivo, así que
tu navegador se abre para aprobar la app.

> **Importante:** el navegador se abre **dos veces** — una para Hi-Res y otra para Lossless.
> **Aprueba las dos.** El login solo cuenta como completo cuando se guardan ambos tokens de calidad.
> Usa **Log out** cuando quieras para cerrar la sesión.

### 3. Tu primera descarga

En la pestaña **Descargar**, pega uno o más enlaces de música en **la caja de enlaces** — canción,
álbum, playlist, artista o mix, **uno por línea**. Elige una **Calidad** y pulsa **Descargar**. La
barra muestra `N/M · %`, la canción actual y un registro con hora.

> Antes de tu primera descarga, abre **Ajustes** y fija tu **Carpeta de descarga**.

![La pestaña Descargar](../assets/screenshots/01-download.png)

---

## Edición y calidad

Dos controles independientes deciden *qué* obtienes y *con cuánta rigidez*.

### Niveles de calidad

| Nivel | Qué entrega |
|---|---|
| **Low** / **Normal** | AAC con pérdida — archivos más pequeños; Low no exige un nivel de suscripción concreto. |
| **High (sin pérdida)** | FLAC calidad CD. No necesita remux con ffmpeg, así que es la opción sin pérdida más rápida. |
| **MAX (alta resolución)** | FLAC Hi-Res hasta 24 bits. High y MAX **prefieren FLAC**; una canción solo-Atmos en MAX **sube** al mejor FLAC de 24 bits disponible. |
| **Atmos (Dolby Atmos)** | Toma primero la edición Dolby Atmos, cuando existe. |

### Edición de audio y política de calidad

- **Automática (enlace original)** — mantiene el álbum o canción del enlace que diste, incluido
  Atmos si esa es la edición enlazada.
- **Solo estéreo** — busca en el catálogo una edición estéreo equivalente y rechaza un manifiesto Atmos
  antes de transferir audio. Funciona en enlaces de **álbum** directos **y** de **artista**
  completo; un álbum sin edición estéreo conserva la original.
- **Flexible** — trata la calidad elegida como un **techo** y usa el mejor nivel disponible igual o
  por debajo (MAX puede bajar a High, Normal o Low).
- **Estricta** — exige el nivel **exacto**. Si el servicio no lo entrega, la descarga se detiene en vez
  de degradarse en silencio.

> **Revisa antes de bajar:** usa **Comprobar versiones disponibles** (solo enlaces de álbum
> directos, con **Solo estéreo**) para ver una edición estéreo compatible y comparar diferencias en
> la lista de canciones *antes* de transferir audio.

---

## Playlists y artistas

Cuando pegas un enlace de playlist o de artista, la app te pregunta cómo expandirlo para que la
estructura de carpetas y las plantillas salgan bien.

### Enlace de playlist detectado — cómo descargarlo

- **Como playlist** — plantilla y carpeta de playlist, más un `.m3u` si está activado.
- **Álbumes completos** — el álbum completo de cada canción (sin duplicados).
- **Discografías de artista** — todo de cada artista acreditado. **Puede ser MUCHÍSIMO.**
- **Solo las canciones** — cada canción por separado, con su plantilla y carpetas.

> **Diálogo de seguridad:** para descargas de artista completo, un diálogo te avisa antes de bajar
> una discografía entera (cientos de álbumes) y te deja elegir singles / videos por corrida. Nada
> grande arranca sin un **Continuar**. Un enlace a una canción dentro de un álbum pregunta:
> **Álbum completo** o **Solo esa canción**.

**Saltar recopilatorios / álbumes en vivo.** En **Ajustes → Descarga avanzada**, dos casillas dejan
fuera recopilatorios y/o discos en vivo en descargas de artista completo. Se identifican desde la
página del artista del servicio — las mismas secciones de Recopilatorios / En vivo que muestra la
app — así que el emparejamiento es fiable. Desactivadas por defecto.

![El diálogo de playlist](../assets/screenshots/04-playlist-dialog.png)

---

## Ajustes, sección por sección

Los ajustes aplican a cada descarga de esta ventana. **Guardar como predeterminados** también los
escribe en el `config.toml` de tiddl (se crea un respaldo), así la línea de comandos también los
usa. **Recargar** vuelve a leer ese archivo.

- **📁 Carpetas** — Carpeta de descarga (dónde se guarda la música), Carpeta de escaneo (dónde se
  detectan descargas existentes, normalmente la misma), Carpeta de videos (override opcional),
  Carpeta de listas (opcional; puede ser otro disco).
- **🔤 Nombres de archivo** — plantillas para predeterminado / canción / álbum / playlist / video /
  mix, más un Separador de artistas. Usa variables como `{album.artist}`, `{album.title}`,
  `{item.number:02}` — mira la pestaña **Ayuda** dentro de la app.
- **🏷️ Metadata / etiquetas** — Incrustar carátula en el archivo; Incrustar reseña del álbum en el
  comentario.
- **🖼️ Archivo de carátula (.jpg)** — Guardar un cover.jpg junto al audio; Tamaño (px, máx 1280);
  Guardar para: Canciones / Álbumes / Playlists / Mixes.
- **⚙️ Descarga avanzada** — Calidad de video; Cliente HiRes (auto / always / never); Peticiones /
  min; Concurrencia de artista; Máx. canciones / sesión; Reescribir metadata en archivos
  existentes; Fecha del archivo = fecha de lanzamiento; Saltar recopilatorios / en vivo (descargas
  de artista).
- **📃 Listas (.m3u)** — Generar archivos .m3u; Generar para: Canciones / Álbumes / Playlists /
  Mixes.
- **🚀 Rendimiento y filtros** — Hilos, Retardo entre canciones, Retardo entre álbumes (anti-bot);
  Incrustar letras en etiquetas; Guardar .lrc aparte; Filtros de Singles / Videos.
- **🎨 Apariencia** — Idioma (English / Español), Tema (violeta oscuro o claro), Tamaño de letra
  (Normal / Grande / Extra grande). Se bloquean mientras corre una descarga — termina o cancela
  primero.

![La pestaña Ajustes](../assets/screenshots/02-settings.png)

---

## Mientras corre — progreso, reanudar y el registro

- **Reanudar (saltar recursos ya hechos)** — salta archivos que ya están en tu biblioteca al
  re-correr.
- **Re-descargar archivos existentes** — lo contrario: fuerza una copia nueva.
- **Cancelar** — detiene la corrida limpiamente; el registro se congela al instante y no arranca
  nada más.
- **Copiar registro** — copia el log completo con horas al portapapeles para diagnóstico.
- **Bloqueo de descarga única** — varias ventanas no pueden golpear la API a la vez.

> **"Exists" no es un error.** Cuando una canción muestra *Exists*, ya está en tu carpeta de
> escaneo / biblioteca y se salta correctamente. `Total downloads: 0` significa que ya estaba
> todo — nada falló.

---

## Solución de problemas

**Windows bloquea el instalador (SmartScreen).** El instalador no está firmado. Pulsa **Más
información → Ejecutar de todas formas** — es seguro, solo no tiene firma de código.

**macOS dice que la app está "dañada y no se puede abrir".** Es la cuarentena de una app sin
firmar. Corre `chmod -R u+w "/Applications/tiddl-gui.app"` y luego
`xattr -cr "/Applications/tiddl-gui.app"` una vez, y ábrela de nuevo.

**Me limitan la tasa / errores 429.** Deja **Cliente HiRes = auto** (Ajustes → Descarga avanzada)
para usar el cliente Hi-Res solo en MAX — eso evita la mayoría de los 429. Si bajas mucho, baja
**Peticiones / min** y añade un **Retardo entre canciones** pequeño.

**"Not logged in".** Pulsa **Log in** y aprueba **las dos** ventanas del
navegador (Hi-Res + Lossless). La calidad sin pérdida / Hi-Res requiere una suscripción HiFi activa.

**Estructura de carpetas equivocada.** Para una playlist, el diálogo de expansión (Como playlist /
Álbumes completos / Discografías de artista / Solo las canciones) elige la estructura. Las
plantillas están en **Ajustes → Nombres de archivo**; la pestaña **Ayuda** lista cada variable.

**¿Dónde se guardan mis ajustes?** **Guardar como predeterminados** escribe en el `config.toml` de
tiddl (primero se crea un respaldo con fecha), así la CLI y el GUI comparten los mismos valores.

![La pestaña Ayuda dentro de la app](../assets/screenshots/03-help.png)

---

*tiddl GUI by ElVigilante — un front-end de escritorio para el descargador
[tiddl-elvigilante](https://github.com/np3ir/tiddl-elvigilante).*
