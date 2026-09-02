#!/bin/bash
# Pruebas (positivas y NEGATIVAS) de release_lib.sh.
#   bash tests/release_lib.test.sh
set -uo pipefail
. "$(dirname "$0")/../release_lib.sh"

fail=0
pass() { echo "PASS  $1"; }
bad()  { echo "FAIL  $1"; fail=$((fail+1)); }
# Espera codigo de salida 1 (rechazo)
expect_reject() { if "$@" >/dev/null 2>&1; then return 1; else return 0; fi }
# Espera codigo de salida 0 (aceptacion)
expect_accept() { if "$@" >/dev/null 2>&1; then return 0; else return 1; fi }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
STAGING="$TMP/staging"; mkdir -p "$STAGING"
SIBLING="$TMP/staging-extra"; mkdir -p "$SIBLING"
INSIDE="$STAGING/repo"; mkdir -p "$INSIDE"
OUTSIDE="$TMP/other"; mkdir -p "$OUTSIDE"

echo "-- 1. rutas contenidas (fuente == o dentro del staging) --"
if expect_reject assert_source_not_under_staging "$STAGING" "$STAGING"; then pass "fuente == staging -> rechazado"; else bad "fuente == staging"; fi
if expect_reject assert_source_not_under_staging "$INSIDE"  "$STAGING"; then pass "fuente dentro del staging -> rechazado"; else bad "fuente dentro"; fi
if expect_reject assert_source_not_under_staging "$STAGING/a/../repo" "$STAGING"; then pass "fuente dentro (con ..) -> rechazado"; else bad "fuente dentro con .."; fi
if expect_accept assert_source_not_under_staging "$OUTSIDE"  "$STAGING"; then pass "fuente fuera -> permitido"; else bad "fuente fuera"; fi
if expect_accept assert_source_not_under_staging "$SIBLING"  "$STAGING"; then pass "prefijo hermano NO contenido"; else bad "prefijo hermano"; fi

echo "-- 2. limpieza fallida (la ruta sigue existiendo) --"
LIVE="$TMP/live"; mkdir -p "$LIVE"
if expect_reject assert_absent "$LIVE"; then pass "assert_absent sobre dir existente -> rechazo"; else bad "assert_absent existente"; fi
if expect_accept remove_dir_strict "$LIVE"; then pass "remove_dir_strict elimina y verifica"; else bad "remove_dir_strict"; fi
if [ ! -e "$LIVE" ]; then pass "el dir quedo ausente tras remove_dir_strict"; else bad "dir aun existe"; fi

echo "-- 3. versiones incorrectas --"
if expect_accept valid_semver "1.0.22"; then pass "1.0.22 valido"; else bad "1.0.22"; fi
if expect_reject valid_semver "1.0"; then pass "1.0 invalido"; else bad "1.0"; fi
if expect_reject valid_semver "1.0.x"; then pass "1.0.x invalido"; else bad "1.0.x"; fi
if expect_reject valid_semver "1.2.3.4"; then pass "1.2.3.4 invalido (4 partes)"; else bad "1.2.3.4"; fi
if expect_reject valid_semver ""; then pass "vacio invalido"; else bad "vacio"; fi

echo "-- 4. guarda de ffmpeg embebido en el .app (macOS) --"
APPT="$TMP/app"; mkdir -p "$APPT/Contents/MacOS" "$APPT/Contents/Resources/site-packages/ffmpeg"
echo "x = 1" > "$APPT/Contents/Resources/site-packages/ffmpeg/__init__.py"
# el paquete Python ffmpeg/ (directorio) NO debe confundirse con un ejecutable
if expect_accept assert_no_bundled_ffmpeg "$APPT"; then pass "app limpia (con paquete py ffmpeg/) -> aceptado"; else bad "app limpia"; fi
# archivo regular llamado ffmpeg -> rechazo
printf '#!/bin/sh\nexit 0\n' > "$APPT/Contents/MacOS/ffmpeg"; chmod +x "$APPT/Contents/MacOS/ffmpeg"
if expect_reject assert_no_bundled_ffmpeg "$APPT"; then pass "archivo ffmpeg -> rechazado"; else bad "archivo ffmpeg"; fi
rm -f "$APPT/Contents/MacOS/ffmpeg"
# symlink llamado ffmpeg -> rechazo (solo si este entorno crea symlinks POSIX)
printf '#!/bin/sh\nexit 0\n' > "$APPT/Contents/MacOS/realff"; chmod +x "$APPT/Contents/MacOS/realff"
ln -s realff "$APPT/Contents/MacOS/ffmpeg" 2>/dev/null || true
if [ -L "$APPT/Contents/MacOS/ffmpeg" ]; then
  if expect_reject assert_no_bundled_ffmpeg "$APPT"; then pass "symlink ffmpeg -> rechazado"; else bad "symlink ffmpeg"; fi
  rm -f "$APPT/Contents/MacOS/ffmpeg"
  ln -s /nonexistent/ffmpeg "$APPT/Contents/MacOS/ffmpeg" 2>/dev/null || true
  if expect_reject assert_no_bundled_ffmpeg "$APPT"; then pass "symlink roto ffmpeg -> rechazado"; else bad "symlink roto ffmpeg"; fi
  rm -f "$APPT/Contents/MacOS/ffmpeg"
else
  echo "SKIP  symlink ffmpeg (este entorno no crea symlinks POSIX; el caso de archivo regular ya cubre el rechazo)"
  rm -f "$APPT/Contents/MacOS/ffmpeg"
fi
rm -f "$APPT/Contents/MacOS/realff"
if expect_accept assert_no_bundled_ffmpeg "$APPT"; then pass "app de nuevo limpia -> aceptado"; else bad "app limpia 2"; fi

echo ""
if [ "$fail" -gt 0 ]; then echo "$fail prueba(s) FAIL"; exit 1; else echo "TODAS LAS PRUEBAS OK"; exit 0; fi
