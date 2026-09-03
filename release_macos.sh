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
. "$(dirname "$0")/release_lib.sh"

# ---- Correr desde el repo (fuente real, no un default) ----
if [[ ! -f main.py || ! -f requirements.txt ]]; then
  echo "ERROR: corre este script desde la carpeta del repo tiddl-gui (falta main.py/requirements.txt)." >&2
  exit 1
fi

# ---- Version: SIEMPRE APP_VERSION de main.py; si se paso un arg, DEBE coincidir
# (la version externa del binario no puede contradecir la interna de la app) ----
APP_VERSION="$(grep -oE '^APP_VERSION = "[0-9]+\.[0-9]+\.[0-9]+"' main.py | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || true)"
if [[ -z "$APP_VERSION" ]]; then
  echo "ERROR: no se pudo leer APP_VERSION (X.Y.Z) de main.py." >&2
  exit 1
fi
if [[ -n "${1:-}" && "$1" != "$APP_VERSION" ]]; then
  echo "ERROR: la version pedida ('$1') no coincide con APP_VERSION de main.py ('$APP_VERSION')." >&2
  exit 1
fi
VERSION="$APP_VERSION"
if ! valid_semver "$VERSION"; then
  echo "ERROR: version invalida '$VERSION' (esperado X.Y.Z)." >&2
  exit 1
fi

echo "[1/3] GUI (flet build macos) — tiddl embebido via requirements.txt..."
# flet build EMPAQUETA todo lo que haya en la carpeta del proyecto ->
# compilar desde un staging limpio con solo main.py, requirements.txt y assets.
# echo (no `yes`): cuando flet termina, `yes` muere por SIGPIPE (141) y con
# pipefail eso abortaria el script aunque el build haya sido exitoso.
WORKDIR="$HOME/.tiddl-gui-build"
REPO_DIR="$(pwd -P)"
# Guard: WORKDIR bajo $HOME, y el repo NUNCA igual o dentro del staging (canonico:
# si el repo estuviera en $HOME/.tiddl-gui-build[/...], el rm -rf lo borraria).
if [[ -z "${HOME:-}" || "$WORKDIR" != "$HOME/.tiddl-gui-build" ]]; then
  echo "ERROR: WORKDIR inseguro ('$WORKDIR') — abortado antes de borrar." >&2
  exit 1
fi
assert_source_not_under_staging "$REPO_DIR" "$WORKDIR" || exit 1
# Limpieza estricta (falla si el dir sigue existiendo) + staging limpio.
remove_dir_strict "$WORKDIR" || exit 1
mkdir -p "$WORKDIR"
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

echo "[2/3] macOS: FFmpeg es dependencia EXTERNA — NO se empaqueta en el .app..."
# FFmpeg NO se embebe (paridad con Linux): el usuario lo instala (brew install
# ffmpeg) y la GUI lo resuelve en runtime (main.py: resolve_ffmpeg / _ensure_ffmpeg_on_macos,
# que antepone su directorio al PATH). Empaquetar el ffmpeg de Homebrew arrastraba
# dylibs de /opt/homebrew no portables y era arm64-only -> DMG no distribuible.
# Guarda dura (funcion testeable en release_lib.sh, cubierta por
# tests/release_lib.test.sh): el .app NO debe contener un 'ffmpeg' embebido en
# NINGUNA forma — archivo regular O symlink (incluso roto).
assert_no_bundled_ffmpeg "$APP" || exit 1
echo "      OK: sin ffmpeg embebido en el .app (dependencia externa)."
# NO re-firmar el bundle. 'flet build macos' ya lo firma ad-hoc CON los entitlements
# que necesita el file-picker (com.apple.security.files.user-selected.read-write).
# La re-firma previa 'codesign --force --deep --sign -' (sin --entitlements ni
# --preserve-metadata) BORRABA ese entitlement -> el boton "Browse"
# (get_directory_path, main.py) fallaba con PlatformException(ENTITLEMENT_NOT_FOUND).
# Confirmado por el diagnostico A/B/C: presente tras 'flet build', ausente tras la
# re-firma. Como el .app ya NO se modifica tras 'flet build' (PR #24 dejo de copiar
# ffmpeg), la re-firma era redundante ademas de danina; se elimina. Un fallo de
# verificacion o de la guarda DEBE abortar: sin tolerancias silenciosas.
codesign --verify --deep --strict "$APP"
assert_required_entitlement "$APP" || exit 1
echo "      codesign verificado (firma ad-hoc de flet) + entitlement de file-picker presente."

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
