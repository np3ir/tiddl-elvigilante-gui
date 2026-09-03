#!/bin/bash
# release_lib.sh — helpers puros compartidos por release_linux.sh y release_macos.sh.
# Source:  . "$(dirname "$0")/release_lib.sh"
#
# Solo usa builtins POSIX (cd/pwd -P/dirname/basename): sin dependencia de
# python3 ni realpath (que no siempre estan en macOS).

# Ruta canonica: absoluta, con symlinks y '..' resueltos. Funciona aunque la ruta
# no exista: canonicaliza el ancestro existente mas profundo y re-anexa el resto.
canonical_path() {
  local p="$1"
  if [ -d "$p" ]; then
    ( cd "$p" 2>/dev/null && pwd -P )
  elif [ -e "$p" ]; then
    local d b; d="$(dirname "$p")"; b="$(basename "$p")"
    echo "$( ( cd "$d" 2>/dev/null && pwd -P ) )/$b"
  else
    local d b; d="$(dirname "$p")"; b="$(basename "$p")"
    if [ -d "$d" ]; then
      echo "$( ( cd "$d" && pwd -P ) )/$b"
    else
      echo "$(canonical_path "$d")/$b"
    fi
  fi
}

# 0 (true) si $child es igual a, o descendiente de, $parent. No cae en la trampa
# del prefijo hermano (/a/staging-extra NO esta dentro de /a/staging).
path_contained() {
  local child parent
  child="$(canonical_path "$1")"
  parent="$(canonical_path "$2")"
  [ "$child" = "$parent" ] && return 0
  case "$child/" in
    "$parent"/*) return 0 ;;
    *) return 1 ;;
  esac
}

# Aborta si la fuente (repo) es igual a, o descendiente de, el staging.
assert_source_not_under_staging() {
  local source="$1" staging="$2"
  if path_contained "$source" "$staging"; then
    echo "ERROR: la fuente ('$source') es igual o esta dentro del staging ('$staging'); la limpieza borraria el repo." >&2
    return 1
  fi
  return 0
}

# Aborta si la ruta sigue existiendo (limpieza fallida = fallo explicito).
assert_absent() {
  if [ -e "$1" ]; then
    echo "ERROR: no se pudo eliminar '$1' (aun existe)." >&2
    return 1
  fi
  return 0
}

# rm -rf estricto: elimina y verifica que quedo ausente.
remove_dir_strict() {
  rm -rf "$1"
  assert_absent "$1"
}

# Valida X.Y.Z.
valid_semver() { [[ "$1" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; }

# macOS: el .app NO debe empaquetar FFmpeg (dependencia externa, paridad con
# Linux). Rechaza (return 1) si encuentra un 'ffmpeg' que sea archivo regular
# O symlink (incluido un symlink ROTO) — pero NO el paquete Python 'ffmpeg/'
# (un directorio) ni archivos como 'ffmpeg.pyc' (basename distinto de 'ffmpeg').
# Uso:  assert_no_bundled_ffmpeg "<ruta .app>"  || exit 1
assert_no_bundled_ffmpeg() {
  local app="$1" hits
  hits="$(find "$app" \( -type f -o -type l \) -name 'ffmpeg' 2>/dev/null)"
  if [[ -n "$hits" ]]; then
    echo "ERROR: 'ffmpeg' (archivo o symlink) dentro del .app; en macOS FFmpeg es externo y NO debe empaquetarse:" >&2
    echo "$hits" >&2
    return 1
  fi
  return 0
}

# macOS: lee un plist de entitlements por STDIN y devuelve 0 (true) si declara
# acceso a archivos seleccionados por el usuario — read-write O read-only con
# valor <true/>. Es el entitlement que el file-picker de Flet (get_directory_path,
# main.py) exige; sin el, lanza PlatformException(ENTITLEMENT_NOT_FOUND) en el
# boton "Browse". El match es ESTRUCTURAL (la clave inmediatamente seguida de
# <true/>, tras eliminar comentarios XML y colapsar espacios entre tags): una
# mencion del identificador dentro de un comentario o de un valor de texto NO
# cuenta, y read-write=<false/> tampoco concede. Solo builtins + tr/sed.
entitlement_file_access_granted() {
  local s
  s="$(cat)"
  s="$(printf '%s' "$s" | tr -d '\n\r\t')"
  s="$(printf '%s' "$s" | sed 's/<!--.*-->//g')"   # quita comentarios XML
  s="$(printf '%s' "$s" | sed 's/> *</></g')"        # colapsa espacios entre tags
  case "$s" in
    *'<key>com.apple.security.files.user-selected.read-write</key><true/>'*) return 0 ;;
    *'<key>com.apple.security.files.user-selected.read-only</key><true/>'*)  return 0 ;;
  esac
  return 1
}

# macOS: aborta (return 1) si el .app NO declara el entitlement de acceso a
# archivos seleccionado por el usuario que get_directory_path (Browse) exige.
# Lee los entitlements REALES firmados del bundle con codesign y los valida con
# el parser estructural de arriba. Guarda dura: tras quitar la re-firma ad-hoc
# redundante (que borraba el entitlement generado por 'flet build'), esto impide
# volver a publicar un DMG cuyo bundle haya perdido el permiso.
# Uso:  assert_required_entitlement "<ruta .app>"  || exit 1
assert_required_entitlement() {
  local app="$1" ent
  ent="$(codesign -d --entitlements - "$app" 2>/dev/null)" || ent=""
  if printf '%s' "$ent" | entitlement_file_access_granted; then
    return 0
  fi
  echo "ERROR: el .app no declara 'com.apple.security.files.user-selected.read-write' (ni read-only); el file-picker (Browse) fallaria con ENTITLEMENT_NOT_FOUND. Una re-firma sin --entitlements elimina el permiso que genera 'flet build'." >&2
  return 1
}
