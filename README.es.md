# tiddl GUI — by ElVigilante

[English](README.md) · **Español**

> [!WARNING]
> Esta app es solo para fines personales, educativos y de archivo. No está afiliada con TIDAL. Los usuarios deben asegurarse de que su uso cumpla con los términos de servicio de TIDAL y con todas las leyes de derechos de autor locales aplicables. El contenido descargado es para uso personal y no puede compartirse ni redistribuirse. El desarrollador no asume ninguna responsabilidad por el mal uso de esta app.

Interfaz de escritorio para [tiddl-elvigilante](https://github.com/np3ir/tiddl-elvigilante). Pega un enlace de TIDAL, elige la calidad y descarga usando todas las funciones del motor de línea de comandos.

**Instalador de Windows con todo incluido**: sin instalar Python, ni pip, ni ffmpeg. Instalas, inicias sesión con tu cuenta de TIDAL, y a descargar.

![Tab de descarga](assets/screenshots/01-download.png)

## Funciones

- **Pega cualquier enlace de TIDAL** — canción, álbum, playlist, artista o mix; cientos a la vez (las listas largas se dividen automáticamente)
- **Control independiente de edición y calidad** — usa el enlace original o busca una edición solo estéreo (álbumes **y** artistas completos); selecciona Low, Normal, High o MAX con política flexible o estricta
- **Comprobación sin descarga** — para enlaces directos de álbum, busca una edición estéreo compatible y muestra las diferencias antes de transferir audio
- **Omitir recopilatorios / álbumes en directo** — déjalos fuera al descargar un artista completo (se identifican desde la página del artista en TIDAL, como las secciones de la app)
- **Manejo inteligente de playlists** — bájala como playlist, o expándela en **álbumes completos**, **discografías de artistas** o **canciones sueltas** (cada uno con su estructura de carpetas y templates)
- **Diálogo de seguridad para artistas** — confirma antes de descargas masivas de discografías y te deja elegir singles/videos por corrida
- **Progreso en vivo** — barra de progreso real con contador, canción descargándose con porcentaje, log con marcas de tiempo
- **Ajustes completos, estilo QBDLX** — carpetas de descarga/escaneo/videos, una **carpeta de playlists** aparte (otro disco si quieres), templates de nombres, hilos y delays anti-bot, letras (incrustadas en los tags y/o archivos `.lrc`)
- **Inicio de sesión de TIDAL integrado** — flujo de código de dispositivo directamente desde la app
- **English / Español**, temas violeta oscuro y claro, tamaño de letra ajustable
- **Candado de descarga única** — varias ventanas no pueden saturar la API a la vez

## Capturas

| Ajustes | Ayuda |
|---|---|
| ![Tab de ajustes](assets/screenshots/02-settings.png) | ![Tab de ayuda](assets/screenshots/03-help.png) |

Diálogo inteligente de playlist — bájala como playlist, o expándela en álbumes, discografías de artistas o canciones sueltas:

![Diálogo de playlist](assets/screenshots/04-playlist-dialog.png)

## Instalar (Windows)

1. Descarga `tiddl-ElVigilante-Setup-x.x.x.exe` desde [Releases](../../releases)
2. SmartScreen te advertirá (instalador sin firmar): **Más información → Ejecutar de todas formas**
3. Abre la app → **Iniciar sesión en TIDAL** → configura tus carpetas en Ajustes → descarga

Requiere una suscripción activa de TIDAL (HiFi para calidad lossless).

### Edición de audio y calidad

- **Automática** conserva el álbum o la canción del enlace original, incluido Atmos si esa es la edición suministrada.
- **Solo estéreo** busca dentro del catálogo de TIDAL una edición equivalente y rechaza cualquier manifiesto Atmos antes de transferir audio. Funciona con enlaces directos de **álbum** y con enlaces de **artista** completo (se resuelve cada álbum de la discografía; si un álbum no tiene edición estéreo, se mantiene el original).
- **Flexible** toma la calidad seleccionada como máximo y usa la mejor calidad disponible sin superarla. Por ejemplo, MAX puede bajar a High, Normal o Low.
- **Estricta** exige exactamente la calidad seleccionada; si TIDAL no la entrega, la descarga se detiene en lugar de degradar.
- **Comprobar versiones disponibles** consulta el catálogo y presenta el resultado sin descargar archivos de audio.

### Omitir recopilatorios / álbumes en directo

En **Ajustes → Descarga avanzada**, dos casillas te dejan excluir recopilatorios
y/o álbumes en directo al descargar un artista completo. TIDAL los lista como
álbumes normales, así que se identifican desde la página del artista — las mismas
secciones Compilations / Live albums que muestra la app — para que el match sea
fiable. Desactivadas por defecto; se guardan con tus ajustes.

## Instalar (Linux)

1. Descarga `tiddl-ElVigilante-x.x.x-linux-x64.tar.gz` desde [Releases](../../releases) y descomprímelo
2. Instala ffmpeg de tu distro (`sudo apt install ffmpeg` o el equivalente)
3. Ejecuta `./tiddl-gui` → inicia sesión en TIDAL → configura tus carpetas → descarga

## Instalar (macOS)

1. Descarga `tiddl-ElVigilante-x.x.x-macos.dmg` desde [Releases](../../releases) (Apple Silicon), ábrelo y arrastra la app a Aplicaciones
2. La app no está firmada, así que macOS la pone en cuarentena. Si ves **"tiddl-gui is damaged and can't be opened"**, es esa marca de cuarentena — quítasela una vez desde la Terminal:
   ```bash
   chmod -R u+w "/Applications/tiddl-gui.app"
   xattr -cr "/Applications/tiddl-gui.app"
   ```
3. Ahora abre la app → inicia sesión en TIDAL → configura tus carpetas → descarga

Para compilar el DMG tú mismo, mira [BUILD_MACOS.md](BUILD_MACOS.md).

## Compilar desde el código

La GUI es una app de un solo archivo en [Flet](https://flet.dev) (`main.py`) que ejecuta el CLI `tiddl` como subproceso — cada función del core (base de datos de saltos, enriquecimiento de metadata, reintentos, límite de tasa) vive en [el CLI](https://github.com/np3ir/tiddl-elvigilante) y funciona sin cambios.

Correr en desarrollo: instala el CLI, `pip install flet tomlkit`, luego `python main.py`.

Release completo (`release.ps1`): compila la GUI con `flet build windows`, el `tiddl.exe` standalone con PyInstaller, y el instalador con Inno Setup. Lee los comentarios del script — hay varios detalles ganados a golpes documentados ahí (Flutter rechaza rutas con caracteres especiales, PyInstaller necesita los submódulos Unicode dinámicos de rich, flet empaqueta todo lo que haya en la carpeta del proyecto).

## Licencia

[MIT](LICENSE)
