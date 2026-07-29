#!/bin/bash
# Release Linux de tiddl GUI (BINARIO UNICO: tiddl viaja embebido in-process,
# igual que en Windows — NO se compila un `tiddl` aparte con PyInstaller).
# Correr EN Linux (nativo o WSL2), desde el repo tiddl-gui.
#
#   ./release_linux.sh            # version 1.0.0
#   ./release_linux.sh 1.1.0      # otra version
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
VERSION="${1:-1.0.0}"

echo "[1/3] GUI (flet build linux) — tiddl embebido via requirements.txt..."
# flet build EMPAQUETA todo lo que haya en la carpeta del proyecto ->
# compilar desde un staging limpio con solo main.py, requirements.txt y assets.
# echo (no `yes`): al terminar flet, `yes` muere por SIGPIPE (141) y con
# pipefail eso abortaria el script aunque el build haya sido exitoso.
WORKDIR="$HOME/.tiddl-gui-build"
rm -rf "$WORKDIR" && mkdir -p "$WORKDIR"
cp main.py requirements.txt "$WORKDIR/"
[ -d assets ] && cp -r assets "$WORKDIR/"
pushd "$WORKDIR" > /dev/null
echo y | flet build linux --project tiddl-gui --product "tiddl by ElVigilante" \
    --company ElVigilante --build-version "$VERSION"
popd > /dev/null

echo "[2/3] README..."
BUNDLE="$WORKDIR/build/linux"
cat > "$BUNDLE/README.txt" <<EOF
tiddl by ElVigilante $VERSION (Linux x64)

1. Instala ffmpeg:   sudo apt install ffmpeg   (o el equivalente de tu distro)
2. Ejecuta:          ./tiddl-gui
3. Inicia sesion en TIDAL desde la app y configura tus carpetas en Settings.

https://github.com/np3ir/tiddl-gui
EOF

echo "[3/3] Creando tar.gz..."
mkdir -p dist-linux
STAGE="dist-linux/tiddl-ElVigilante-$VERSION"
rm -rf "$STAGE" && mkdir "$STAGE"
cp -r "$BUNDLE"/. "$STAGE"/
tar -czf "dist-linux/tiddl-ElVigilante-$VERSION-linux-x64.tar.gz" -C dist-linux "tiddl-ElVigilante-$VERSION"
rm -rf "$STAGE"

echo ""
echo "RELEASE OK -> dist-linux/tiddl-ElVigilante-$VERSION-linux-x64.tar.gz"
echo "Subir al release de GitHub:"
echo "  gh release upload v$VERSION dist-linux/tiddl-ElVigilante-$VERSION-linux-x64.tar.gz"
