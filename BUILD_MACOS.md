# Build de macOS — paso a paso

Guía para compilar y publicar el DMG de tiddl GUI desde un Mac. (El build de macOS
solo puede hacerse EN un Mac — no hay cross-compile desde Windows/Linux.)

## 1. Preparación (una sola vez, ~30-60 min por las descargas)

```bash
# Xcode completo desde el App Store (es grande); cuando termine de instalar:
sudo xcodebuild -license accept

# Homebrew si no lo tienes (https://brew.sh), y luego:
brew install python ffmpeg cocoapods

# Entorno Python aislado. IMPORTANTE: usa python3.14 de Homebrew de forma
# explícita — si `python3` a secas apunta a un Python viejo del sistema, el
# venv hereda un pip anticuado que NO puede ver flet 0.86.1 (dará el error
# "Could not find a version that satisfies flet[all]==0.86.1", mostrando
# solo hasta 0.28.x). Y siempre actualiza pip primero.
python3.14 -m venv ~/tiddl-venv          # o "$(brew --prefix)/bin/python3.14" si no está en el PATH
source ~/tiddl-venv/bin/activate
python -m pip install --upgrade pip
pip install "flet[all]==0.86.1" tomlkit
```

> tiddl NO se instala aquí: `flet build` lo embebe leyendo `requirements.txt`
> (dependencia git, fijada a un commit), así la GUI corre tiddl in-process
> (binario único). Por eso el venv solo necesita flet + tomlkit.

> Nota: pega los comandos **sin las líneas de comentario** (las que empiezan con `#`);
> zsh interpreta caracteres como `(` en los comentarios y da errores de "bad pattern".

## 2. Build

```bash
git clone https://github.com/np3ir/tiddl-elvigilante-gui.git
cd tiddl-elvigilante-gui
source ~/tiddl-venv/bin/activate   # si abriste una terminal nueva
chmod +x release_macos.sh
./release_macos.sh 1.0.8           # o la version que toque
```

- La **primera corrida** descarga el Flutter SDK de flet (~10-20 min extra);
  las siguientes son rápidas.
- Al final imprime la ruta del DMG en `dist-mac/`.
- tiddl viaja **embebido dentro del `.app`** (in-process, binario único) y
  `ffmpeg` se copia junto al ejecutable — el usuario final no instala nada más.

## 3. Probar

1. Monta el DMG y arrastra la app a Applications.
2. La app va sin firmar. Un DMG **descargado** de internet queda en cuarentena
   y macOS moderno (Sequoia/15+) lo muestra como **"is damaged and can't be
   opened"** — el `click derecho → Open` de siempre ya no basta. Quita la
   cuarentena una vez:
   ```bash
   xattr -cr "/Applications/tiddl-gui.app"
   ```
   (Un DMG compilado localmente NO trae la marca; el problema solo aparece
   tras descargarlo.)
3. La app debe pedir el login de TIDAL (device flow en el navegador),
   luego configurar carpetas en Settings y probar una descarga.

## 4. Subir el DMG al release

```bash
brew install gh
gh auth login
gh release upload v1.0.8 dist-mac/tiddl-ElVigilante-1.0.8-macos.dmg -R np3ir/tiddl-elvigilante-gui
```

(O copia el DMG a otra máquina que ya tenga `gh` autenticado y súbelo desde allí.)

## Notas

- **Arquitectura**: el DMG sale para la arquitectura del Mac que compila
  (Apple Silicon en M1/M2/...). Cubre cualquier Mac moderno.
- **Versiones**: usa el mismo número que el release de GitHub existente para
  añadirle el DMG, o crea release nuevo si es una versión nueva.
- Los gotchas del build (SIGPIPE del `yes`, staging limpio porque flet
  empaqueta todo lo que ve, ícono en `assets/`) ya están resueltos dentro de
  `release_macos.sh` — leer sus comentarios si algo se comporta raro.
