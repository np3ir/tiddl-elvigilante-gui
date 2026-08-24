#!/bin/bash
# Release Linux de tiddl GUI (BINARIO UNICO: tiddl viaja embebido in-process,
# igual que en Windows — NO se compila un `tiddl` aparte con PyInstaller).
# Correr EN Linux (nativo o WSL2), desde el repo tiddl-gui.
#
#   ./release_linux.sh            # version = APP_VERSION de main.py
#   ./release_linux.sh 1.1.0      # version explicita
#
# Requisitos del sistema (una sola vez, Debian/Ubuntu):
#   sudo apt install -y python3-pip python3-venv clang cmake ninja-build \
#       pkg-config libgtk-3-dev liblzma-dev git curl unzip xz-utils zip
# Entorno Python (venv recomendado):
#   pip install "flet[all]==0.86.1" tomlkit
#   (tiddl NO se instala aqui: flet build lo embebe leyendo requirements.txt,
#    que lo declara como dependencia git. Asi la GUI corre tiddl in-process y
#    no necesita un binario tiddl separado ni Python del sistema >= 3.12.)
#
# Resultado: dist-linux/tiddl-ElVigilante-<version>-linux-x64.tar.gz
# El usuario final necesita ffmpeg del sistema:  sudo apt install ffmpeg
# (no se bundlea: el de las distros es dinamico y no viaja bien entre sistemas)

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

echo "[1/3] GUI (flet build linux) — tiddl embebido via requirements.txt..."
# flet build EMPAQUETA todo lo que haya en la carpeta del proyecto ->
# compilar desde un staging limpio con solo main.py, requirements.txt y assets.
# echo (no `yes`): al terminar flet, `yes` muere por SIGPIPE (141) y con
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
echo y | flet build linux --project tiddl-gui --product "tiddl by ElVigilante" \
    --company ElVigilante --build-version "$VERSION"
popd > /dev/null

# ---- Verificacion posterior: existe el binario ----
BUNDLE="$WORKDIR/build/linux"
if [[ ! -f "$BUNDLE/tiddl-gui" ]]; then
  echo "ERROR: flet build fallo: no existe el ejecutable '$BUNDLE/tiddl-gui'." >&2
  exit 1
fi

echo "[2/3] README..."
cat > "$BUNDLE/README.txt" <<EOF
tiddl by ElVigilante $VERSION (Linux x64)

1. Instala ffmpeg:   sudo apt install ffmpeg   (o el equivalente de tu distro)
2. Ejecuta:          ./tiddl-gui
3. Inicia sesion en TIDAL desde la app y configura tus carpetas en Settings.

https://github.com/np3ir/tiddl-elvigilante-gui
EOF

echo "[3/3] Creando tar.gz..."
mkdir -p dist-linux
STAGE="dist-linux/tiddl-ElVigilante-$VERSION"
rm -rf "$STAGE" && mkdir "$STAGE"
cp -r "$BUNDLE"/. "$STAGE"/
TARBALL="dist-linux/tiddl-ElVigilante-$VERSION-linux-x64.tar.gz"
tar -czf "$TARBALL" -C dist-linux "tiddl-ElVigilante-$VERSION"
rm -rf "$STAGE"

# ---- Verificacion posterior: existe el tarball ----
if [[ ! -f "$TARBALL" ]]; then
  echo "ERROR: no se creo el tarball '$TARBALL'." >&2
  exit 1
fi

echo ""
echo "RELEASE OK -> $TARBALL"
echo "Subir al release de GitHub:"
echo "  gh release upload v$VERSION $TARBALL"
