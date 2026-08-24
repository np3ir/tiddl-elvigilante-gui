#!/bin/bash
# Release macOS de tiddl GUI (BINARIO UNICO: tiddl viaja embebido in-process,
# igual que en Windows/Linux — NO se compila un `tiddl` aparte con PyInstaller).
# Correr EN el Mac, desde la carpeta del repo tiddl-gui.
#
#   ./release_macos.sh            # version = APP_VERSION de main.py
#   ./release_macos.sh 1.1.0      # version explicita
#
# Requisitos (una sola vez):
#   1. Xcode completo (App Store) y aceptar licencia:
#        sudo xcodebuild -license accept
#   2. Homebrew (si no lo tienes: https://brew.sh) y luego:
#        brew install python ffmpeg cocoapods
#   3. Entorno Python. Usa python3.14 de brew EXPLICITAMENTE: si el venv se
#      crea con un python3 viejo, hereda un pip anticuado que no ve flet
#      0.86.1 ("Could not find a version ... flet[all]==0.86.1"). Actualiza
#      pip antes de instalar. NO hace falta instalar tiddl ni pyinstaller aqui:
#      flet build embebe tiddl leyendo requirements.txt (dependencia git), asi
#      la GUI corre tiddl in-process.
#        python3.14 -m venv ~/tiddl-venv   # o "$(brew --prefix)/bin/python3.14"
#        source ~/tiddl-venv/bin/activate
#        python -m pip install --upgrade pip
#        pip install "flet[all]==0.86.1" tomlkit
#   Correr este script SIEMPRE con el venv activado.
#
# Resultado: dist-mac/tiddl-ElVigilante-<version>-macos.dmg
# Nota Gatekeeper: app sin firmar -> ver BUILD_MACOS.md (xattr -cr ...).

set -euo pipefail

# ---- Correr desde el repo (fuente real, no un default) ----
if [[ ! -f main.py || ! -f requirements.txt ]]; then
  echo "ERROR: corre este script desde la carpeta del repo tiddl-gui (falta main.py/requirements.txt)." >&2
  exit 1
fi

# ---- Version: arg 1, o APP_VERSION de main.py; NUNCA un default silencioso ----
if [[ -n "${1:-}" ]]; then
  VERSION="$1"
else
  VERSION="$(grep -oE '^APP_VERSION = "[0-9]+\.[0-9]+\.[0-9]+"' main.py | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || true)"
  if [[ -z "$VERSION" ]]; then
    echo "ERROR: sin argumento de version y no se pudo leer APP_VERSION (X.Y.Z) de main.py." >&2
    echo "Uso: ./release_macos.sh <X.Y.Z>" >&2
    exit 1
  fi
  echo "Version tomada de main.py: $VERSION"
fi
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "ERROR: version invalida '$VERSION' (esperado X.Y.Z)." >&2
  exit 1
fi

echo "[1/3] GUI (flet build macos) — tiddl embebido via requirements.txt..."
# flet build EMPAQUETA todo lo que haya en la carpeta del proyecto ->
# compilar desde un staging limpio con solo main.py, requirements.txt y assets.
# echo (no `yes`): cuando flet termina, `yes` muere por SIGPIPE (141) y con
# pipefail eso abortaria el script aunque el build haya sido exitoso.
WORKDIR="$HOME/.tiddl-gui-build"
# Guard: no borrar nada si WORKDIR no es la ruta esperada bajo $HOME.
if [[ -z "${HOME:-}" || "$WORKDIR" != "$HOME/.tiddl-gui-build" ]]; then
  echo "ERROR: WORKDIR inseguro ('$WORKDIR') — abortado antes de borrar." >&2
  exit 1
fi
rm -rf "$WORKDIR" && mkdir -p "$WORKDIR"
cp main.py requirements.txt "$WORKDIR/"
# Sincronizacion explicita de assets (no silenciosa).
if [[ -d assets ]]; then
  cp -r assets "$WORKDIR/"
  echo "      assets/ sincronizado."
else
  echo "      AVISO: no hay carpeta assets/ — el icono de la app puede faltar."
fi
pushd "$WORKDIR" > /dev/null
echo y | flet build macos --project tiddl-gui --product "tiddl by ElVigilante" \
    --company ElVigilante --build-version "$VERSION"
popd > /dev/null

# ---- Verificacion posterior: existe el .app ----
APP=$(ls -d "$WORKDIR"/build/macos/*.app 2>/dev/null | head -1 || true)
if [[ -z "$APP" || ! -d "$APP" ]]; then
  echo "ERROR: flet build fallo: no se genero ningun .app en $WORKDIR/build/macos/." >&2
  exit 1
fi

echo "[2/3] Empacando ffmpeg dentro del .app + re-firma..."
BINDIR="$APP/Contents/MacOS"
# ffmpeg del sistema (brew) junto al ejecutable; main.py antepone {app} al PATH.
cp "$(command -v ffmpeg)" "$BINDIR/ffmpeg"
# u+w too: Homebrew's ffmpeg is read-only, which later blocks `xattr -cr`
# (removing the download quarantine) on the user's machine.
chmod u+rwx "$BINDIR/ffmpeg"
# Ad-hoc re-sign: bundling ffmpeg invalidates flet's signature, and an
# unsigned app fails to launch on Apple Silicon. (Does not remove the
# download-quarantine step; only notarization would.)
codesign --force --deep --sign - "$APP" 2>/dev/null || true

echo "[3/3] Creando DMG..."
mkdir -p dist-mac
# Stage the app next to an Applications symlink so the DMG has the standard
# drag-to-Applications layout instead of a bare .app with no drop target.
STAGE="$WORKDIR/dmg-stage"
rm -rf "$STAGE" && mkdir "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
DMG="dist-mac/tiddl-ElVigilante-$VERSION-macos.dmg"
hdiutil create -volname "tiddl by ElVigilante" -srcfolder "$STAGE" -ov -format UDZO "$DMG"

# ---- Verificacion posterior: existe el DMG ----
if [[ ! -f "$DMG" ]]; then
  echo "ERROR: no se creo el DMG '$DMG'." >&2
  exit 1
fi

echo ""
echo "RELEASE OK -> $DMG"
echo "Subir al release de GitHub:"
echo "  gh release upload v$VERSION $DMG -R np3ir/tiddl-elvigilante-gui"
