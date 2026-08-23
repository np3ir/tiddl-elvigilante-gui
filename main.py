"""tiddl GUI - Flet frontend for the tiddl-elvigilante downloader.

Paste TIDAL links, pick quality, download. A Settings tab exposes paths,
naming templates and performance options, QBDLX-style. The heavy lifting is
done by tiddl, imported and run IN-PROCESS (single binary - no separate
tiddl.exe), so every core feature (skip database, metadata enrichment,
retries, delays) works unchanged.
Settings are passed as CLI flags per run; "Save as defaults" writes them
back to tiddl's own config.toml (with a timestamped backup).
UI language is switchable (English/Spanish), persisted in gui.json.
"""

from __future__ import annotations

import datetime
import io
import os
import re
import shutil
import sys
import time
from pathlib import Path

IS_WIN = sys.platform == "win32"

# --- Single-binary mode ---------------------------------------------------
# tiddl runs IN-PROCESS (imported), not as a separate tiddl.exe subprocess.
# tiddl resolves its data dir (auth/config/cache) from TIDDL_PATH at import
# time, so pin it to the user profile BEFORE the first tiddl import. A wide
# COLUMNS keeps rich (force_terminal) from wrapping the progress frames the
# log parser reads. The app dir is prepended to PATH so a bundled ffmpeg
# sitting next to the executable is found.
os.environ.setdefault("TIDDL_PATH", str(Path.home() / ".tiddl"))
os.environ.setdefault("COLUMNS", "400")
try:
    os.environ["PATH"] = (
        str(Path(sys.executable).resolve().parent) + os.pathsep + os.environ.get("PATH", "")
    )
except Exception:
    pass

import flet as ft
import tomlkit

try:
    import tiddl  # noqa: F401  bundled in single-binary mode
    TIDDL_AVAILABLE = True
except Exception:
    TIDDL_AVAILABLE = False

# Cooperative cancel lives in feat/cancel-hook; optional so the GUI still runs
# against a tiddl that predates it (cancel then only takes effect between runs).
try:
    from tiddl.core import cancel as tiddl_cancel
except Exception:
    tiddl_cancel = None


def _tiddl_commit() -> str:
    """Short git commit of the bundled tiddl-elvigilante (empty if unknown).
    Read from the pip direct_url.json shipped in the dist-info — no import of
    tiddl.cli.app (which would reconfigure stdout and break the embedded app)."""
    try:
        import importlib.metadata as _md
        import json as _json
        raw = _md.distribution("tiddl-elvigilante").read_text("direct_url.json")
        if raw:
            return (_json.loads(raw).get("vcs_info") or {}).get("commit_id", "")[:8]
    except Exception:
        pass
    return ""


TIDDL_COMMIT = _tiddl_commit()

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    tomllib = None

# Bump this every release; the built installer version should match.
APP_VERSION = "1.0.21"
GUI_REPO = "np3ir/tiddl-elvigilante-gui"
RELEASES_URL = f"https://github.com/{GUI_REPO}/releases/latest"
API_LATEST = f"https://api.github.com/repos/{GUI_REPO}/releases/latest"

# --- Crash logging -----------------------------------------------------------
# tiddl runs in-process under flet's embedded Python; a native crash or an
# uncaught worker-thread exception otherwise makes the window vanish with no
# trace. Capture everything to TIDDL_PATH/gui-crash.log so a "closed while
# processing" can actually be diagnosed.
import faulthandler as _faulthandler
import threading as _threading
import traceback as _tb


def crash_log_path() -> Path:
    base = os.environ.get("TIDDL_PATH") or str(Path.home() / ".tiddl")
    p = Path(base)
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return p / "gui-crash.log"


def write_crash(header: str, exc: BaseException | None = None) -> None:
    try:
        with open(crash_log_path(), "a", encoding="utf-8") as f:
            f.write(
                f"\n===== {header} @ {datetime.datetime.now().isoformat()} "
                f"(app {APP_VERSION}) =====\n"
            )
            if exc is not None:
                f.write("".join(_tb.format_exception(type(exc), exc, exc.__traceback__)))
            f.flush()
    except Exception:
        pass


# faulthandler dumps a traceback (native/fatal faults included, all threads) here.
try:
    _CRASH_FILE = open(crash_log_path(), "a", encoding="utf-8")
    _faulthandler.enable(file=_CRASH_FILE, all_threads=True)
except Exception:
    _CRASH_FILE = None


def _thread_excepthook(args):
    write_crash(
        f"uncaught exception in thread {getattr(args, 'thread', None)!r}",
        args.exc_value,
    )


_threading.excepthook = _thread_excepthook
# -----------------------------------------------------------------------------
OFFLINE_MODE = os.environ.get("TIDDL_GUI_OFFLINE", "").strip().casefold() in {
    "1", "true", "yes", "on"
}

QUALITIES = ["low", "normal", "atmos", "high", "max"]
AUDIO_MODES = ["auto", "stereo"]
QUALITY_POLICIES = ["flexible", "strict"]
SINGLES_FILTERS = ["none", "only", "include"]
VIDEOS_FILTERS = ["none", "allow", "only"]
VIDEO_QUALITIES = ["audio", "360", "480", "720", "1080", "fhd"]
HIRES_CLIENTS = ["auto", "always", "never"]
COVER_TARGETS = ["track", "album", "playlist"]
M3U_TARGETS = ["album", "playlist", "mix"]


def _parse_version(s: str) -> tuple:
    """'v1.2.3' -> (1, 2, 3) for comparison; ignores prefix and suffixes."""
    nums = re.findall(r"\d+", (s or "").strip())
    return tuple(int(n) for n in nums[:3]) or (0,)


def latest_release() -> str | None:
    """Query GitHub for the latest release tag. None on any failure/offline."""
    import json
    import urllib.request

    try:
        req = urllib.request.Request(
            API_LATEST, headers={"Accept": "application/vnd.github+json", "User-Agent": "tiddl-gui"}
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.load(resp)
        return data.get("tag_name")
    except Exception:
        return None

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07\x1b]*(\x07|\x1b\\)")
BOX_CHARS = set("╭╮╰╯│─┌┐└┘━┏┓┗┛┃┤├")
TOTAL_RE = re.compile(r"Total downloads:\s*(\d+)")
# Combined TIDAL link: .../album/<id>/track/<id>
COMBO_RE = re.compile(r"(album/\d+)/track/(\d+)")
# "[n/total] type/id" heartbeat printed by expanded runs (--albums/--artists/--tracks)
HEART_RE = re.compile(r"^\[(\d+)/(\d+)\]\s")
# "0.04s ... 12/537" frames from the CLI's own Total Progress bar
PROG_FRAME_RE = re.compile(r"^[\d.]+s\b.*?(\d+)/(\d+)")
# Rich braille spinner characters (in-flight track frames)
SPINNER_RE = re.compile(r"[⠀-⣿]")


class _LineSink(io.TextIOBase):
    """Capture tiddl's forced-terminal rich stream and emit it line by line,
    exactly like iterating a subprocess pipe. isatty()->True keeps rich in
    ANSI mode (tiddl already sets force_terminal=True, so ANSI codes flow
    through and the log parser strips them as before)."""

    def __init__(self, on_line):
        self._on_line = on_line
        self._buf = ""

    def isatty(self) -> bool:
        return True

    def writable(self) -> bool:
        return True

    def write(self, s) -> int:
        if not isinstance(s, str):
            s = str(s)
        self._buf += s
        while True:
            i_n = self._buf.find("\n")
            i_r = self._buf.find("\r")
            idx = min([x for x in (i_n, i_r) if x >= 0], default=-1)
            if idx < 0:
                break
            line, self._buf = self._buf[:idx], self._buf[idx + 1:]
            if line:
                self._on_line(line)
        return len(s)

    def drain(self) -> None:
        if self._buf:
            line, self._buf = self._buf, ""
            self._on_line(line)

    def flush(self) -> None:
        pass

TEMPLATE_VARS = (
    "{item.title} {item.artist} {item.artists} {item.number} "
    "{album.artist} {album.title} {album.date:%Y} {playlist.title} {quality}"
)

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "tab_download": "Download",
        "tab_settings": "Settings",
        "tab_help": "Help",
        "help_intro": (
            "Naming templates control the folder structure and file names of your "
            "downloads. Write a path using the variables below in curly braces, "
            "using / to separate folders. The last segment becomes the file name "
            "(the extension is added automatically)."
        ),
        "help_example_label": "Example",
        "help_example": "{artist_initials}/{album.artist}/({album.date:%Y}) {album.title}/{item.number:02} - {item.title}",
        "help_example_note": "produces, e.g.:  R/Radiohead/(1997) OK Computer/06 - Karma Police.flac",
        "help_sec_shortcuts": "Handy shortcuts",
        "help_sec_item": "Track / video — {item.*}",
        "help_sec_album": "Album — {album.*}",
        "help_sec_playlist": "Playlist — {playlist.*}",
        "help_playlist_tip": (
            "Tip — numbering playlists: use {playlist.index} to number tracks in "
            "playlist order (e.g. {playlist.index:03} → 001, 002…). Don't use "
            "{item.number} here: that's the track's number within its ORIGINAL "
            "album, so in a playlist it looks out of order (11, 1, 8, 7…)."
        ),
        "help_sec_formats": "Format modifiers",
        "help_col_var": "Variable",
        "help_col_desc": "Description",
        "help_fmt_intro": "Some variables accept a modifier after a colon:",
        "help_fmt_dates": "Dates use Python strftime codes: {album.date:%Y} → 1997, {album.date:%Y-%m-%d} → 1997-06-16.",
        "help_fmt_numbers": "Numbers can be zero-padded: {item.number:02} → 06.",
        "help_fmt_explicit": "Explicit tag renders only when the track is explicit, otherwise nothing:",
        "help_fmt_flags": "Dolby Atmos / Master render the text you write only when the track qualifies:",
        "help_safe_note": (
            "Tip: the safe_* variants (safe_title, safe_artist, ...) are pre-cleaned "
            "of characters some file systems dislike. Multiple artists are joined with "
            "the separator set in your tiddl config (artist_separator)."
        ),
        "links_label": "TIDAL links",
        "links_hint": "Paste one or more links (track / album / playlist / artist / mix), one per line",
        "quality": "Quality",
        "quality_low": "Low",
        "quality_normal": "Normal",
        "quality_atmos": "Atmos (Dolby Atmos)",
        "quality_high": "High (lossless)",
        "quality_max": "MAX (Hi-Res lossless)",
        "quality_help": (
            "Starting rung of the cascade  max > high > atmos > normal > low. "
            "Each track is taken at the first rung from here DOWN that it offers. "
            "Start at high/max to prefer FLAC; an Atmos track's only FLAC is 'max' "
            "(so 'high' falls to Atmos), and 'atmos' takes Dolby Atmos first."
        ),
        "resume": "Resume (skip artists already done)",
        "resume_tip": (
            "Skip whole resources completed in a prior run of this SAME job "
            "(same links + options) before any API call — cheap continuation of a "
            "run stopped by a rate-limit or cancel. Trusts its checkpoint over disk."
        ),
        "audio_mode": "Audio edition",
        "audio_mode_auto": "Automatic (original link)",
        "audio_mode_stereo": "Stereo only",
        "audio_mode_help": (
            "Stereo-EDITION resolver. 'stereo' finds a separately-published stereo "
            "album edition and verifies it — it applies to ALBUM and ARTIST links "
            "ONLY. On a playlist/mix it does nothing (you'll see \"keeping ... "
            "unchanged\"). To avoid Atmos / prefer FLAC on ANY link, use the Quality "
            "cascade instead (it works per track). 'auto' uses the supplied link."
        ),
        "quality_policy": "Quality policy",
        "quality_policy_flexible": "Flexible (allow lower tiers)",
        "quality_policy_strict": "Strict (exact tier only)",
        "quality_policy_help": (
            "flexible = treat the selected quality as a ceiling and use the highest available "
            "tier below it; strict = transfer only the exact selected quality. (No-Atmos is "
            "handled by the Quality cascade, which already prefers FLAC over Atmos per track.)"
        ),
        "core_stopped": "Download engine stopped the run for safety (authentication or stream policy)",
        "redownload": "Re-download existing files",
        "btn_download": "Download",
        "btn_verify": "Check available versions",
        "verify_album_only": "Version verification currently accepts direct album links only",
        "verify_stereo_required": "Select the stereo audio edition to verify alternate versions",
        "btn_cancel": "Cancel",
        "copy_log": "Copy log",
        "log_copied": "Log copied to clipboard",
        "log_copy_fail": "Could not copy: {err}",
        "update_available": "Update available",
        "update_tooltip": "Version {ver} is available (you have {cur}) - click to download",
        "ready": "Ready",
        "err_no_tiddl": "ERROR: tiddl executable not found on PATH",
        "browse": "Browse",
        "sec_folders": "Folders",
        "dl_folder": "Download folder",
        "dl_folder_hint": "Where music is saved",
        "scan_folder": "Scan folder",
        "scan_folder_hint": "Where existing downloads are detected (usually same as above)",
        "video_folder": "Video folder",
        "video_folder_hint": "Optional - overrides download folder for videos",
        "playlist_folder": "Playlist folder",
        "playlist_folder_hint": "Optional - playlists download here instead (can be another disk)",
        "sec_naming": "File naming",
        "tpl_vars": "Variables: " + TEMPLATE_VARS,
        "tpl_default": "Default template",
        "tpl_track": "Track template",
        "tpl_album": "Album template",
        "tpl_playlist": "Playlist template",
        "tpl_video": "Video template",
        "sec_perf": "Performance and filters",
        "embed_lyrics_cb": "Embed lyrics in tags",
        "save_lrc_cb": "Save .lrc lyrics file",
        # --- new: metadata / cover ---
        "sec_metadata": "Metadata / tags",
        "embed_cover_cb": "Embed cover art in the file",
        "album_review_cb": "Embed album review in comment",
        "sec_coverfile": "Cover file (.jpg)",
        "cover_save_cb": "Save a cover.jpg next to the audio",
        "cover_size": "Size (px, max 1280)",
        "cover_allowed_lbl": "Save for:",
        "cover_help": "For albums, one cover.jpg is saved beside the downloaded tracks.",
        "cover_target_required": "Choose at least one destination for cover.jpg",
        "target_track": "Tracks",
        "target_album": "Albums",
        "target_playlist": "Playlists",
        "target_mix": "Mixes",
        # --- new: advanced download ---
        "sec_advanced": "Advanced download",
        "video_quality": "Video quality",
        "hires_client": "HiRes client",
        "hires_client_hint": "auto = HiRes only at max quality (avoids 429); always/never force it",
        "rpm": "Requests / min",
        "concurrency": "Artist concurrency",
        "max_tracks": "Max tracks / session (0 = ∞)",
        "rewrite_cb": "Rewrite metadata on existing files",
        "mtime_cb": "Set file date to release date",
        "exclude_comp_cb": "Skip compilations (artist downloads)",
        "exclude_live_cb": "Skip live albums (artist downloads)",
        "exclude_help": (
            "When downloading a whole artist, leave these out. Identified from "
            "the TIDAL artist page, the same as the app's Compilations / Live "
            "albums sections."
        ),
        # --- new: m3u ---
        "sec_m3u": "Playlists (.m3u)",
        "m3u_save_cb": "Generate .m3u playlist files",
        "m3u_allowed_lbl": "Generate for:",
        # --- new: naming extras ---
        "tpl_mix": "Mix template",
        "artist_sep": "Artist separator",
        "threads": "Threads",
        "track_delay": "Track delay (s)",
        "album_delay": "Album delay (s)",
        "singles": "Artist singles",
        "videos": "Videos",
        "language": "Language",
        "theme": "Theme",
        "theme_dark": "Dark",
        "theme_light": "Light",
        "font_size": "Font size",
        "font_normal": "Normal",
        "font_large": "Large",
        "font_xlarge": "Extra large",
        "font_locked": "Finish or cancel the download before changing font size",
        "theme_locked": "Finish or cancel the download before changing theme",
        "save_defaults": "Save as defaults",
        "reload": "Reload",
        "reloaded": "Reloaded from config.toml",
        "saved": "Saved to {path} (backup created)",
        "save_failed": "Save failed: {err}",
        "invalid_number": "Invalid numeric value in Settings",
        "invalid_number_short": "Check the numeric fields in Settings",
        "footer": (
            "Settings apply to every download started from this window. "
            "\"Save as defaults\" also writes them to tiddl's config.toml (backup created), "
            "so the command line uses them too."
        ),
        "lang_locked": "Finish or cancel the download before changing language",
        "paste_link": "Paste at least one TIDAL link",
        "dlg_playlist_title": "Playlist link detected",
        "dlg_playlist_q": "How do you want to download it?",
        "opt_playlist": "As playlist",
        "opt_playlist_d": "Playlist template and folder, m3u if enabled",
        "opt_albums": "Full albums",
        "opt_albums_d": "The complete album of every track (deduped)",
        "opt_artists": "Artist discographies",
        "opt_artists_d": "Everything by every credited artist - can be A LOT",
        "opt_tracks": "Only the tracks",
        "opt_tracks_d": "Each track standalone, track template and folders",
        "dlg_artist_title": "Artist download options",
        "dlg_artist_msg": "{n} artist link(s) - the FULL discography of each one will be downloaded.",
        "dlg_artist_msg_expand": (
            "Every credited artist in the playlist gets their full discography - "
            "this can be hundreds of albums."
        ),
        "btn_continue": "Continue",
        "dlg_combo_title": "Album link with a track",
        "dlg_combo_q": "This link points to a specific track inside an album.\nWhat do you want to download?",
        "opt_full_album": "Full album",
        "opt_only_track": "Only that track",
        "btn_login": "Log in to TIDAL",
        "btn_logout": "Log out",
        "login_needed": "Not logged in to TIDAL - click 'Log in to TIDAL' to authenticate",
        "login_wait": "Complete the login in your browser - it opens TWICE (HiRes + Lossless), approve BOTH...",
        "login_ok": "Logged in to TIDAL",
        "login_fail": "Login failed or expired - try again",
        "logout_title": "Log out of TIDAL?",
        "logout_q": "This clears your session (both quality tokens). You'll need to log in again to download.",
        "logout_confirm": "Log out",
        "logout_wait": "Logging out...",
        "logout_ok": "Logged out - log in again to download",
        "lock_busy_title": "Another window is downloading",
        "lock_busy_msg": (
            "To protect your TIDAL account from rate limits, only one window "
            "may download at a time. Wait for the other download to finish, "
            "or cancel it in that window."
        ),
        "lock_startup_warn": "Another window is already downloading - only one download at a time",
        "starting": "Starting download...",
        "run_sep": "--- Run {i}/{n} ---",
        "cancelled": "Cancelled",
        "cancelled_n": "Cancelled - {n} download(s) completed",
        "done_n": "Done - {n} download(s)",
        "errors_n": "Finished with errors (exit {c}) - {n} download(s)",
        "error": "Error: {e}",
    },
    "es": {
        "tab_download": "Descargar",
        "tab_settings": "Ajustes",
        "tab_help": "Ayuda",
        "help_intro": (
            "Los templates de nombres controlan la estructura de carpetas y los "
            "nombres de archivo de tus descargas. Escribe una ruta usando las "
            "variables de abajo entre llaves, separando carpetas con /. El último "
            "segmento es el nombre del archivo (la extensión se agrega sola)."
        ),
        "help_example_label": "Ejemplo",
        "help_example": "{artist_initials}/{album.artist}/({album.date:%Y}) {album.title}/{item.number:02} - {item.title}",
        "help_example_note": "produce, por ejemplo:  R/Radiohead/(1997) OK Computer/06 - Karma Police.flac",
        "help_sec_shortcuts": "Atajos útiles",
        "help_sec_item": "Canción / video — {item.*}",
        "help_sec_album": "Álbum — {album.*}",
        "help_sec_playlist": "Playlist — {playlist.*}",
        "help_playlist_tip": (
            "Consejo — numerar playlists: usa {playlist.index} para numerar las "
            "canciones en el orden de la playlist (p. ej. {playlist.index:03} → "
            "001, 002…). No uses {item.number} aquí: ese es el número dentro de su "
            "álbum ORIGINAL, así que en una playlist se ve desordenado (11, 1, 8, 7…)."
        ),
        "help_sec_formats": "Modificadores de formato",
        "help_col_var": "Variable",
        "help_col_desc": "Descripción",
        "help_fmt_intro": "Algunas variables aceptan un modificador tras dos puntos:",
        "help_fmt_dates": "Las fechas usan códigos strftime de Python: {album.date:%Y} → 1997, {album.date:%Y-%m-%d} → 1997-06-16.",
        "help_fmt_numbers": "Los números se pueden rellenar con ceros: {item.number:02} → 06.",
        "help_fmt_explicit": "La marca explícita aparece solo si la canción es explícita, si no queda vacía:",
        "help_fmt_flags": "Dolby Atmos / Master muestran el texto que escribas solo si la canción califica:",
        "help_safe_note": (
            "Tip: las variantes safe_* (safe_title, safe_artist, ...) vienen limpias "
            "de caracteres que a algunos sistemas de archivos no les gustan. Los "
            "artistas múltiples se unen con el separador de tu config de tiddl "
            "(artist_separator)."
        ),
        "links_label": "Enlaces de TIDAL",
        "links_hint": "Pega uno o más enlaces (canción / álbum / playlist / artista / mix), uno por línea",
        "quality": "Calidad",
        "quality_low": "Low (baja)",
        "quality_normal": "Normal",
        "quality_atmos": "Atmos (Dolby Atmos)",
        "quality_high": "High (sin pérdida)",
        "quality_max": "MAX (alta resolución sin pérdida)",
        "quality_help": (
            "Escalón inicial de la cascada  max > high > atmos > normal > low. "
            "Cada pista se toma en el primer escalón disponible hacia ABAJO. "
            "Empieza en high/max para preferir FLAC; en una pista Atmos el único FLAC "
            "es 'max' (así 'high' cae a Atmos), y 'atmos' toma Dolby Atmos primero."
        ),
        "resume": "Reanudar (saltar artistas ya hechos)",
        "resume_tip": (
            "Salta recursos completados en una corrida previa del MISMO trabajo "
            "(mismos enlaces + opciones) antes de llamar a la API — continuación barata "
            "de una corrida detenida por rate-limit o cancelada. Confía en su checkpoint."
        ),
        "redownload": "Re-descargar archivos existentes",
        "audio_mode": "Edición de audio",
        "audio_mode_auto": "Automática (enlace original)",
        "audio_mode_stereo": "Solo estéreo",
        "audio_mode_help": (
            "Resolver de EDICIÓN estéreo. 'Solo estéreo' busca una edición de álbum "
            "estéreo publicada aparte y la verifica — aplica SOLO a enlaces de ÁLBUM "
            "y ARTISTA. En una playlist/mix no hace nada (verás \"keeping ... "
            "unchanged\"). Para evitar Atmos / preferir FLAC en CUALQUIER enlace, usa "
            "la cascada de Calidad (actúa por pista). 'Automática' usa el enlace tal cual."
        ),
        "quality_policy": "Política de calidad",
        "quality_policy_flexible": "Flexible (permite calidades inferiores)",
        "quality_policy_strict": "Estricta (solo la calidad exacta)",
        "quality_policy_help": (
            "Flexible usa la calidad seleccionada como máximo y elige la mejor disponible sin "
            "superarla. Estricta exige exactamente la calidad seleccionada. (Lo de evitar Atmos "
            "lo maneja la cascada de Calidad, que ya prefiere FLAC sobre Atmos por pista.)"
        ),
        "core_stopped": "El motor detuvo la ejecución por seguridad (autenticación o política de audio)",
        "btn_download": "Descargar",
        "btn_verify": "Comprobar versiones disponibles",
        "verify_album_only": "La comprobación solo acepta enlaces directos de álbum por ahora",
        "verify_stereo_required": "Selecciona Solo estéreo para buscar una edición alternativa",
        "btn_cancel": "Cancelar",
        "copy_log": "Copiar registro",
        "log_copied": "Registro copiado al portapapeles",
        "log_copy_fail": "No se pudo copiar: {err}",
        "update_available": "Actualización disponible",
        "update_tooltip": "La versión {ver} está disponible (tienes {cur}) - clic para descargar",
        "ready": "Listo",
        "err_no_tiddl": "ERROR: no se encontró el ejecutable tiddl en el PATH",
        "browse": "Elegir",
        "sec_folders": "Carpetas",
        "dl_folder": "Carpeta de descarga",
        "dl_folder_hint": "Dónde se guarda la música",
        "scan_folder": "Carpeta de escaneo",
        "scan_folder_hint": "Dónde se detectan las descargas existentes (normalmente la misma de arriba)",
        "video_folder": "Carpeta de videos",
        "video_folder_hint": "Opcional - reemplaza la carpeta de descarga para videos",
        "playlist_folder": "Carpeta de playlists",
        "playlist_folder_hint": "Opcional - las playlists se descargan aquí (puede ser otro disco)",
        "sec_naming": "Nombres de archivo",
        "tpl_vars": "Variables: " + TEMPLATE_VARS,
        "tpl_default": "Template por defecto",
        "tpl_track": "Plantilla de canción",
        "tpl_album": "Template de álbum",
        "tpl_playlist": "Template de playlist",
        "tpl_video": "Template de video",
        "sec_perf": "Rendimiento y filtros",
        "embed_lyrics_cb": "Incrustar letras en los tags",
        "save_lrc_cb": "Guardar archivo de letras .lrc",
        # --- new: metadata / cover ---
        "sec_metadata": "Metadata / etiquetas",
        "embed_cover_cb": "Incrustar la carátula en el archivo",
        "album_review_cb": "Incrustar reseña del álbum en el comentario",
        "sec_coverfile": "Archivo de carátula (.jpg)",
        "cover_save_cb": "Guardar un cover.jpg junto al audio",
        "cover_size": "Tamaño (px, máx 1280)",
        "cover_allowed_lbl": "Guardar para:",
        "cover_help": "Para álbumes, se guarda un cover.jpg junto a las canciones descargadas.",
        "cover_target_required": "Selecciona al menos un destino para cover.jpg",
        "target_track": "Canciones",
        "target_album": "Álbumes",
        "target_playlist": "Playlists",
        "target_mix": "Mixes",
        # --- new: advanced download ---
        "sec_advanced": "Descarga avanzada",
        "video_quality": "Calidad de video",
        "hires_client": "Cliente HiRes",
        "hires_client_hint": "auto = HiRes solo en calidad máx (evita 429); always/never lo fuerzan",
        "rpm": "Peticiones / min",
        "concurrency": "Álbumes en paralelo (artista)",
        "max_tracks": "Máx. canciones / sesión (0 = ∞)",
        "rewrite_cb": "Reescribir metadatos en archivos existentes",
        "mtime_cb": "Fecha del archivo = fecha de lanzamiento",
        "exclude_comp_cb": "Omitir recopilatorios (descargas de artista)",
        "exclude_live_cb": "Omitir álbumes en directo (descargas de artista)",
        "exclude_help": (
            "Al descargar un artista completo, déjalos fuera. Se identifican "
            "desde la página del artista en TIDAL, igual que las secciones "
            "Compilations / Live albums de la app."
        ),
        # --- new: m3u ---
        "sec_m3u": "Listas (.m3u)",
        "m3u_save_cb": "Generar archivos de lista .m3u",
        "m3u_allowed_lbl": "Generar para:",
        # --- new: naming extras ---
        "tpl_mix": "Template de mix",
        "artist_sep": "Separador de artistas",
        "threads": "Hilos",
        "track_delay": "Delay por track (s)",
        "album_delay": "Delay por álbum (s)",
        "singles": "Singles de artista",
        "videos": "Videos",
        "language": "Idioma",
        "theme": "Tema",
        "theme_dark": "Oscuro",
        "theme_light": "Claro",
        "font_size": "Tamaño de letra",
        "font_normal": "Normal",
        "font_large": "Grande",
        "font_xlarge": "Extra grande",
        "font_locked": "Termina o cancela la descarga antes de cambiar el tamaño de letra",
        "theme_locked": "Termina o cancela la descarga antes de cambiar el tema",
        "save_defaults": "Guardar como default",
        "reload": "Recargar",
        "reloaded": "Recargado desde config.toml",
        "saved": "Guardado en {path} (backup creado)",
        "save_failed": "Error al guardar: {err}",
        "invalid_number": "Hay un valor numérico inválido en Ajustes",
        "invalid_number_short": "Revisa los campos numéricos de Ajustes",
        "footer": (
            "Los ajustes aplican a cada descarga iniciada desde esta ventana. "
            "\"Guardar como default\" también los escribe en el config.toml de tiddl "
            "(con backup), así la línea de comandos usa los mismos valores."
        ),
        "lang_locked": "Termina o cancela la descarga antes de cambiar el idioma",
        "paste_link": "Pega al menos un link de TIDAL",
        "dlg_playlist_title": "Link de playlist detectado",
        "dlg_playlist_q": "¿Cómo la quieres descargar?",
        "opt_playlist": "Como playlist",
        "opt_playlist_d": "Template y carpeta de playlist, m3u si está activado",
        "opt_albums": "Álbumes completos",
        "opt_albums_d": "El álbum completo de cada canción (sin duplicados)",
        "opt_artists": "Discografías de artistas",
        "opt_artists_d": "Todo de cada artista acreditado - puede ser MUCHÍSIMO",
        "opt_tracks": "Solo las canciones",
        "opt_tracks_d": "Cada canción suelta, con template y carpetas de track",
        "dlg_artist_title": "Opciones de descarga de artista",
        "dlg_artist_msg": "{n} link(s) de artista - se descargará la discografía COMPLETA de cada uno.",
        "dlg_artist_msg_expand": (
            "Cada artista acreditado en la playlist baja su discografía completa - "
            "pueden ser cientos de álbumes."
        ),
        "btn_continue": "Continuar",
        "dlg_combo_title": "Link de álbum con track",
        "dlg_combo_q": "Este link apunta a una canción específica dentro de un álbum.\n¿Qué quieres descargar?",
        "opt_full_album": "Álbum completo",
        "opt_only_track": "Solo esa canción",
        "btn_login": "Iniciar sesión en TIDAL",
        "btn_logout": "Cerrar sesión",
        "login_needed": "Sin sesión de TIDAL - usa 'Iniciar sesión en TIDAL' para autenticarte",
        "login_wait": "Completa el login en tu navegador - se abre DOS veces (HiRes + Lossless), aprueba AMBAS...",
        "login_ok": "Sesión de TIDAL activa",
        "login_fail": "El login falló o expiró - inténtalo de nuevo",
        "logout_title": "¿Cerrar sesión de TIDAL?",
        "logout_q": "Esto borra tu sesión (los dos tokens de calidad). Tendrás que iniciar sesión de nuevo para descargar.",
        "logout_confirm": "Cerrar sesión",
        "logout_wait": "Cerrando sesión...",
        "logout_ok": "Sesión cerrada - inicia sesión de nuevo para descargar",
        "lock_busy_title": "Otra ventana está descargando",
        "lock_busy_msg": (
            "Para proteger tu cuenta de TIDAL de los límites de solicitudes, solo una ventana "
            "puede descargar a la vez. Espera a que termine la otra descarga, "
            "o cancélala en esa ventana."
        ),
        "lock_startup_warn": "Otra ventana ya está descargando - solo una descarga a la vez",
        "starting": "Iniciando descarga...",
        "run_sep": "--- Corrida {i}/{n} ---",
        "cancelled": "Cancelado",
        "cancelled_n": "Cancelado - {n} descarga(s) completadas",
        "done_n": "Listo - {n} descarga(s)",
        "errors_n": "Terminó con errores (exit {c}) - {n} descarga(s)",
        "error": "Error: {e}",
    },
}

# NP3IR exam-app (C:\radioaficionado lib/theme.dart) palettes:
# violet primary; dark = near-black with dark-purple surfaces,
# light = lavender background with purple text.
PALETTES = {
    "dark": {
        "primary": "#7C3AED",       # kViolet
        "primary_dark": "#6B21A8",  # kPurple
        "on_primary": "#FFFFFF",
        "bg": "#0A0A0F",            # kBlack
        "surface": "#1A0A2E",       # kDarkPurple
        "text": "#F8F4FF",          # kWhite
        "gray": "#B794F4",          # kLavender (secondary text/hints)
        "success": "#4ADE80",       # kGreen
        "error": "#F87171",         # kRed
    },
    "light": {
        "primary": "#7C3AED",       # kViolet
        "primary_dark": "#6B21A8",  # kPurple
        "on_primary": "#FFFFFF",
        "bg": "#F5F0FF",            # kLightBg
        "surface": "#EDE4FF",       # kLightSurface
        "text": "#1A0A2E",          # kLightText
        "gray": "#6B21A8",          # kLightSubtext
        "success": "#15803D",
        "error": "#B91C1C",
    },
}

# Base text size per setting (log/status/now lines scale from this),
# mirroring the exam app's font-medium/large/xlarge.
FONT_SIZES = {"normal": 12, "large": 14, "xlarge": 17}

# Template variable reference for the Help tab: (name, {en, es}).
# Kept in sync with tiddl/core/utils/format.py (ItemTemplate/AlbumTemplate/
# PlaylistTemplate dataclasses + aliases).
HELP_SHORTCUTS = [
    ("{title}", {"en": "Track title", "es": "Título de la canción"}),
    ("{artist}", {"en": "Track's main artist", "es": "Artista principal de la canción"}),
    ("{albumartist}", {"en": "Album's main artist", "es": "Artista principal del álbum"}),
    ("{artist_initials}", {"en": "First letter of the artist, for A/B/C… folders (uses album artist)",
                           "es": "Primera letra del artista, para carpetas A/B/C… (usa el artista del álbum)"}),
    ("{release_date}", {"en": "Album release date — date format: {release_date:%Y} → 1997",
                        "es": "Fecha de lanzamiento del álbum — formato de fecha: {release_date:%Y} → 1997"}),
    ("{quality}", {"en": "Download quality (LOW/HIGH/LOSSLESS/HI_RES…)", "es": "Calidad de la descarga (LOW/HIGH/LOSSLESS/HI_RES…)"}),
    ("{now}", {"en": "Current date/time — date format: {now:%Y-%m-%d} → 1997-06-16",
               "es": "Fecha/hora actual — formato de fecha: {now:%Y-%m-%d} → 1997-06-16"}),
]
HELP_ITEM = [
    ("{item.title}", {"en": "Title", "es": "Título"}),
    ("{item.safe_title}", {"en": "Title, filesystem-safe", "es": "Título, apto para el sistema de archivos"}),
    ("{item.title_version}", {"en": "Title including version, e.g. 'Song (Remastered)'", "es": "Título con versión, ej. 'Song (Remastered)'"}),
    ("{item.version}", {"en": "Version only, e.g. 'Remastered 2011'", "es": "Solo la versión, ej. 'Remastered 2011'"}),
    ("{item.number}", {"en": "Track number — zero-pad: {item.number:02} → 06",
                        "es": "Número de pista — rellena con ceros: {item.number:02} → 06"}),
    ("{item.volume}", {"en": "Disc / volume number — zero-pad: {item.volume:02} → 01",
                       "es": "Número de disco / volumen — rellena con ceros: {item.volume:02} → 01"}),
    ("{item.artist}", {"en": "Main artist", "es": "Artista principal"}),
    ("{item.artists}", {"en": "All artists joined", "es": "Todos los artistas unidos"}),
    ("{item.features}", {"en": "Featured artists", "es": "Artistas invitados (feat.)"}),
    ("{item.artists_with_features}", {"en": "Main + featured artists", "es": "Artista principal + invitados"}),
    ("{item.genre}", {"en": "Genre", "es": "Género"}),
    ("{item.bpm}", {"en": "Beats per minute", "es": "Pulsaciones por minuto"}),
    ("{item.isrc}", {"en": "ISRC code", "es": "Código ISRC"}),
    ("{item.copyright}", {"en": "Copyright text", "es": "Texto de copyright"}),
    ("{item.quality}", {"en": "Track quality", "es": "Calidad de la pista"}),
    ("{item.explicit}", {"en": "Explicit tag (see modifiers)", "es": "Marca explícita (ver modificadores)"}),
    ("{item.dolby}", {"en": "Dolby Atmos flag (see modifiers)", "es": "Marca Dolby Atmos (ver modificadores)"}),
    ("{item.releaseDate}", {"en": "Release date — date format: {item.releaseDate:%Y} → 1997, {item.releaseDate:%Y-%m-%d} → 1997-06-16",
                            "es": "Fecha de lanzamiento — formato de fecha: {item.releaseDate:%Y} → 1997, {item.releaseDate:%Y-%m-%d} → 1997-06-16"}),
    ("{item.id}", {"en": "TIDAL track ID", "es": "ID de la pista en TIDAL"}),
]
HELP_ALBUM = [
    ("{album.title}", {"en": "Album title", "es": "Título del álbum"}),
    ("{album.safe_title}", {"en": "Album title, filesystem-safe", "es": "Título del álbum, apto para archivos"}),
    ("{album.artist}", {"en": "Album's main artist", "es": "Artista principal del álbum"}),
    ("{album.artists}", {"en": "All album artists joined", "es": "Todos los artistas del álbum unidos"}),
    ("{album.date}", {"en": "Release date — date format: {album.date:%Y} → 1997, {album.date:%Y-%m-%d} → 1997-06-16",
                      "es": "Fecha de lanzamiento — formato de fecha: {album.date:%Y} → 1997, {album.date:%Y-%m-%d} → 1997-06-16"}),
    ("{album.release}", {"en": "Type: ALBUM / EP / SINGLE…", "es": "Tipo: ALBUM / EP / SINGLE…"}),
    ("{album.explicit}", {"en": "Explicit tag (see modifiers)", "es": "Marca explícita (ver modificadores)"}),
    ("{album.master}", {"en": "Master/HiRes flag (see modifiers)", "es": "Marca Master/HiRes (ver modificadores)"}),
    ("{album.id}", {"en": "TIDAL album ID", "es": "ID del álbum en TIDAL"}),
]
HELP_PLAYLIST = [
    ("{playlist.title}", {"en": "Playlist name", "es": "Nombre de la playlist"}),
    ("{playlist.index}", {"en": "Track's position in the playlist", "es": "Posición de la canción en la playlist"}),
    ("{playlist.created}", {"en": "Creation date — date format: {playlist.created:%Y} → 1997",
                            "es": "Fecha de creación — formato de fecha: {playlist.created:%Y} → 1997"}),
    ("{playlist.updated}", {"en": "Last-updated date — date format: {playlist.updated:%Y} → 1997",
                            "es": "Fecha de última actualización — formato de fecha: {playlist.updated:%Y} → 1997"}),
    ("{playlist.uuid}", {"en": "Playlist UUID", "es": "UUID de la playlist"}),
]
HELP_EXPLICIT_FMT = [
    ("{item.explicit:E}", "E"),
    ("{item.explicit:long}", "explicit"),
    ("{item.explicit:upperlong}", "EXPLICIT"),
    ("{item.explicit:parens}", " (Explicit)"),
    ("{item.explicit:shortparens}", " (explicit)"),
]
HELP_FLAG_FMT = [
    ("{item.dolby:ATMOS}", "ATMOS"),
    ("{album.master:MASTER}", "MASTER"),
]

# Settings fields preserved across a language-switch rebuild.
STASH_FIELDS = [
    "f_download_path", "f_scan_path", "f_video_path", "f_playlist_path",
    "f_tpl_default", "f_tpl_track", "f_tpl_album", "f_tpl_playlist", "f_tpl_video",
    "f_tpl_mix", "f_artist_sep",
    "f_threads", "f_track_delay", "f_artist_delay", "f_singles", "f_videos",
    "f_embed_lyrics", "f_save_lrc",
    # metadata / cover
    "f_cover", "f_album_review",
    "f_cover_save", "f_cover_size",
    "f_cover_track", "f_cover_album", "f_cover_playlist",
    # advanced download
    "f_video_quality", "f_hires_client", "f_rpm", "f_concurrency",
    "f_max_tracks", "f_rewrite", "f_update_mtime", "f_exclude_compilations",
    "f_exclude_live", "f_audio_mode", "f_quality_policy", "f_resume",
    # m3u
    "f_m3u_save", "f_m3u_album", "f_m3u_playlist", "f_m3u_mix",
]


def config_file_path() -> Path:
    base = os.environ.get("TIDDL_PATH") or str(Path.home() / ".tiddl")
    return Path(base) / "config.toml"


def gui_settings_path() -> Path:
    """GUI-only settings (keys tiddl itself doesn't know about)."""
    return config_file_path().parent / "gui.json"


def load_gui_settings() -> dict:
    try:
        import json

        return json.loads(gui_settings_path().read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_gui_settings(data: dict):
    import json

    path = gui_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def run_tiddl(argv: list[str], on_line) -> int:
    """Run tiddl's CLI in-process, streaming its stdout lines to on_line().

    Replaces the old `subprocess.Popen([tiddl.exe, ...])`: tiddl is now bundled
    and imported, so there is no separate executable. Returns the CLI exit code.
    MUST be called from a worker thread (tiddl runs its own asyncio loop, and
    stdout is redirected process-wide for the duration of the call).

    CRITICAL: we invoke tiddl's Typer app with `standalone_mode=False`. The
    default (True) makes Click call `sys.exit()` when the command finishes;
    under flet's EMBEDDED Python (serious_python), a `sys.exit()` from this
    worker thread HARD-KILLS the whole process (clean exit, no traceback), so
    the packaged GUI vanished on the first tiddl call. standalone_mode=False
    makes Click return normally instead of exiting, and raise real exceptions
    (which we catch) instead of printing + exiting.
    """
    sink = _LineSink(on_line)
    old_out, old_err, old_argv = sys.stdout, sys.stderr, sys.argv
    sys.stdout = sink
    sys.stderr = sink
    try:
        # Import AFTER redirecting: tiddl.cli.app's top-level runs
        # `sys.stdout.reconfigure(...)`; with the sink (no reconfigure attr)
        # already in place that call is skipped and flet's stdout is untouched.
        from tiddl.cli.app import app as tiddl_app, _reorder_download_options
        sys.argv = _reorder_download_options(["tiddl", *argv])
        try:
            tiddl_app(standalone_mode=False)
            return 0
        except SystemExit as e:  # some paths still raise it; treat as exit code
            code = e.code
            return code if isinstance(code, int) else (0 if code is None else 1)
    except BaseException as e:  # log to gui-crash.log AND surface into the GUI log
        write_crash("run_tiddl exception", e)
        on_line(f"Error: {type(e).__name__}: {e}  (details in gui-crash.log)")
        return 1
    finally:
        sink.drain()
        sys.stdout, sys.stderr, sys.argv = old_out, old_err, old_argv


def download_lock_path() -> Path:
    return config_file_path().parent / "gui.lock"


def _pid_alive(pid: int) -> bool:
    """Check liveness. Windows: OpenProcess (os.kill(pid, 0) TERMINATES the
    process there). POSIX: signal 0 is the standard, safe liveness probe."""
    if not IS_WIN:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except Exception:
            return False

    import ctypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    handle = ctypes.windll.kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION, False, pid
    )
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        if ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return code.value == STILL_ACTIVE
        return False
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def other_instance_downloading() -> bool:
    """True if a different GUI window holds the download lock and is alive."""
    try:
        pid = int(download_lock_path().read_text(encoding="utf-8").strip())
    except Exception:
        return False
    return pid != os.getpid() and _pid_alive(pid)


def acquire_download_lock():
    path = download_lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(os.getpid()), encoding="utf-8")


def release_download_lock():
    try:
        path = download_lock_path()
        if int(path.read_text(encoding="utf-8").strip()) == os.getpid():
            path.unlink()
    except Exception:
        pass


def load_tiddl_config() -> dict:
    cfg_file = config_file_path()
    if tomllib and cfg_file.exists():
        try:
            return tomllib.loads(cfg_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def meaningful_line(raw: str) -> str | None:
    """Filter one line of CLI output down to what a human wants to read.

    The CLI forces a rich terminal, so piped output still contains ANSI
    cursor codes and repeated Live-panel frames (borders, progress bars).
    """
    line = ANSI_RE.sub("", raw).rstrip()
    # Strip the Windows long-path prefix, visual noise only.
    line = line.replace("\\\\?\\UNC\\", "\\\\").replace("\\\\?\\", "")
    s = line.strip()
    if not s:
        return None
    # Panel borders / content frames and progress-bar frames.
    if s[0] in BOX_CHARS:
        return None
    if re.match(r"^[\d.]+s\b", s):
        return None
    return s


class TiddlGui:
    def __init__(self, page: ft.Page):
        self.page = page
        self.running = False
        self.cancelled = False
        self._log_buffer: list[tuple[str, str]] = []
        self._log_last_flush = 0.0
        self._log_lines: list[str] = []
        self.cfg = load_tiddl_config()
        self.tiddl_available = TIDDL_AVAILABLE
        gui_cfg = load_gui_settings()
        self.lang = gui_cfg.get("language", "en")
        if self.lang not in STRINGS:
            self.lang = "en"
        self.theme_name = gui_cfg.get("theme", "dark")
        if self.theme_name not in PALETTES:
            self.theme_name = "dark"
        self.font_name = gui_cfg.get("font_size", "normal")
        if self.font_name not in FONT_SIZES:
            self.font_name = "normal"
        self.build()

    @property
    def pal(self) -> dict:
        return PALETTES[self.theme_name]

    @property
    def fs(self) -> int:
        return FONT_SIZES[self.font_name]

    def t(self, key: str, **kwargs) -> str:
        text = STRINGS.get(self.lang, {}).get(key) or STRINGS["en"].get(key, key)
        return text.format(**kwargs) if kwargs else text

    def _run_on_ui(self, fn):
        """Run fn on the event-loop thread.

        Flet diffs the control tree on the loop thread inside page.update().
        Any mutation of a control's *list* property (e.g. log_view.controls)
        MUST also happen on that thread - mutating it from a worker thread
        while a diff is running desyncs the diff's cached key list from the
        live list length and crashes with 'IndexError: list index out of
        range' deep in flet's object_patch._compare_lists. Scheduling via
        call_soon_threadsafe also wakes the sleeping loop so patches render
        immediately instead of only on the next client event.
        """
        try:
            loop = self.page.session.connection.loop
            loop.call_soon_threadsafe(fn)
        except Exception:
            fn()

    def refresh(self, *controls):
        """Thread-safe page.update(), optionally scoped to specific controls.

        Scoping the patch to the changed control keeps heavy phases (log
        floods) from freezing the UI.
        """

        def do():
            if controls:
                self.page.update(*controls)
            else:
                self.page.update()

        self._run_on_ui(do)

    # ---------- config helpers ----------

    def cfg_dl(self, key: str, default=""):
        dl = self.cfg.get("download", {})
        return dl.get(key, default) if isinstance(dl, dict) else default

    def cfg_tpl(self, key: str, default=""):
        tpl = self.cfg.get("templates", {})
        return tpl.get(key, default) if isinstance(tpl, dict) else default

    def cfg_meta(self, key: str, default=False):
        meta = self.cfg.get("metadata", {})
        return meta.get(key, default) if isinstance(meta, dict) else default

    def cfg_cover(self, key: str, default=None):
        cov = self.cfg.get("cover", {})
        return cov.get(key, default) if isinstance(cov, dict) else default

    def cfg_m3u(self, key: str, default=None):
        m = self.cfg.get("m3u", {})
        return m.get(key, default) if isinstance(m, dict) else default

    # ---------- UI ----------

    GITHUB_URL = "https://github.com/np3ir/tiddl-elvigilante"

    def build(self):
        p = self.page
        p.title = f"tiddl by ElVigilante {APP_VERSION} - TIDAL Downloader"
        p.window.width = 900
        p.window.height = 820
        p.padding = 12

        exam_theme = ft.Theme(
            color_scheme=ft.ColorScheme(
                primary=self.pal["primary"],
                on_primary=self.pal["on_primary"],
                primary_container=self.pal["primary_dark"],
                secondary=self.pal["primary_dark"],
                surface=self.pal["bg"],
                on_surface=self.pal["text"],
                surface_container_highest=self.pal["surface"],
                outline=self.pal["gray"],
                outline_variant=self.pal["primary"],
                error=self.pal["error"],
            )
        )
        p.theme = exam_theme
        p.dark_theme = exam_theme
        p.theme_mode = (
            ft.ThemeMode.DARK if self.theme_name == "dark" else ft.ThemeMode.LIGHT
        )

        if not hasattr(self, "file_picker"):
            self.file_picker = ft.FilePicker()
            p.services.append(self.file_picker)
        if not hasattr(self, "clipboard"):
            # Registered service — page.clipboard is deprecated and returns an
            # unmounted instance whose set() does nothing.
            self.clipboard = ft.Clipboard()
            p.services.append(self.clipboard)

        download_tab = self.build_download_tab()
        settings_tab = self.build_settings_tab()
        help_tab = self.build_help_tab()

        p.add(
            ft.Tabs(
                length=3,
                expand=True,
                content=ft.Column(
                    [
                        ft.TabBar(
                            tabs=[
                                ft.Tab(label=self.t("tab_download"), icon=ft.Icons.DOWNLOAD),
                                ft.Tab(label=self.t("tab_settings"), icon=ft.Icons.SETTINGS),
                                ft.Tab(label=self.t("tab_help"), icon=ft.Icons.HELP_OUTLINE),
                            ]
                        ),
                        ft.TabBarView(
                            expand=True,
                            controls=[download_tab, settings_tab, help_tab],
                        ),
                    ],
                    expand=True,
                ),
            )
        )

        if not self.tiddl_available:
            self.set_status(self.t("err_no_tiddl"), error=True)
            self.download_btn.disabled = True
        elif other_instance_downloading():
            self.set_status(self.t("lock_startup_warn"))
        elif not OFFLINE_MODE:
            self.page.run_thread(self.check_auth)
        if not OFFLINE_MODE:
            self.page.run_thread(self.check_updates)
        p.update()

    def check_updates(self):
        tag = latest_release()
        if not tag:
            return
        if _parse_version(tag) > _parse_version(APP_VERSION):
            ver = tag.lstrip("vV")
            self.update_btn.tooltip = self.t("update_tooltip", ver=ver, cur=APP_VERSION)
            self.update_btn.visible = True
            self.refresh(self.update_btn)

    # ---------- auth ----------

    def check_auth(self):
        """Probe auth state; tiddl has no /me endpoint, the refresh output is
        the source of truth (same technique as the LAUNCHER.BAT hardening)."""
        lines: list[str] = []
        try:
            run_tiddl(["auth", "refresh"], lines.append)
        except Exception:
            return
        text = ANSI_RE.sub("", "\n".join(lines))
        if "Not logged in" in text or "log in" in text.lower():
            self.login_btn.visible = True
            self.logout_btn.visible = False
            self.refresh(self.login_btn, self.logout_btn)
            self.set_status(self.t("login_needed"), error=True)
        else:
            # Logged in: offer logout instead of login.
            self.login_btn.visible = False
            self.logout_btn.visible = True
            self.refresh(self.login_btn, self.logout_btn)
            for line in text.splitlines():
                if line.strip().startswith("Auth token"):
                    self.set_status(line.strip())
                    break

    def on_logout(self, e):
        def confirm(_):
            self.page.pop_dialog()
            self.logout_btn.disabled = True
            self.refresh(self.logout_btn)
            self.set_status(self.t("logout_wait"))
            self.page.run_thread(self.logout_worker)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(self.t("logout_title")),
            content=ft.Text(self.t("logout_q")),
            actions=[
                ft.TextButton(content=self.t("btn_cancel"), on_click=lambda e: self.page.pop_dialog()),
                ft.FilledButton(content=self.t("logout_confirm"), on_click=confirm),
            ],
        )
        self.page.show_dialog(dlg)

    def logout_worker(self):
        try:
            run_tiddl(["auth", "logout"], lambda _l: None)
        except Exception:
            pass
        self.logout_btn.disabled = False
        self.logout_btn.visible = False
        self.login_btn.visible = True
        self.refresh(self.logout_btn, self.login_btn)
        self.set_status(self.t("logout_ok"), error=True)

    def on_login(self, e):
        self.login_btn.disabled = True
        self.refresh(self.login_btn)
        self.set_status(self.t("login_wait"))
        self.page.run_thread(self.login_worker)

    def login_worker(self):
        # The hybrid login prints TWO device-verification URLs — one for the
        # HiRes (24-bit) client, one for the TV/LOSSLESS fallback — each as
        # `[label] Ve a 'https://link.tidal.com/…'`. Open EVERY tidal device
        # URL we see (matching the URL itself, not an English "Go to", which
        # never matched tiddl's Spanish "Ve a"), so BOTH approvals prompt in
        # the browser. Missing the 2nd is why `max` couldn't fetch 24-bit.
        launched: set[str] = set()

        def on_line(raw: str):
            line = ANSI_RE.sub("", raw).strip()
            for m in re.finditer(r"https://link\.tidal\.com/\S+", line):
                url = m.group().strip("'\"!.,)")
                if url not in launched:
                    launched.add(url)
                    loop = self.page.session.connection.loop
                    loop.call_soon_threadsafe(self.page.launch_url, url)
                    self.set_status(self.t("login_wait"))

        try:
            run_tiddl(["auth", "login"], on_line)
        except Exception:
            pass

        # Success = BOTH hybrid tokens ended up on disk (HiRes primary +
        # TV fallback). Relying on a "Logged in" line would pass with only
        # one of the two approvals done — exactly the bug that left `max`
        # without its 24-bit token.
        import json as _json

        def _has_token(name: str) -> bool:
            try:
                p = Path(os.environ.get("TIDDL_PATH", str(Path.home() / ".tiddl"))) / name
                return bool((_json.loads(p.read_text("utf-8")) or {}).get("token"))
            except Exception:
                return False

        success = _has_token("auth.json") and _has_token("auth_fallback.json")

        self.login_btn.disabled = False
        if success:
            self.login_btn.visible = False
            self.refresh(self.login_btn)
            self.set_status(self.t("login_ok"))
            self.cfg = load_tiddl_config()
            self.check_auth()
        else:
            self.refresh(self.login_btn)
            self.set_status(self.t("login_fail"), error=True)

    def rebuild(self):
        """Rebuild the whole UI (language switch), preserving field values."""
        stash = {name: getattr(self, name).value for name in STASH_FIELDS if hasattr(self, name)}
        stash["urls"] = self.urls_field.value
        stash["quality"] = self.quality_dd.value
        stash["noskip"] = self.noskip_cb.value

        self.page.controls.clear()
        self.build()

        for name, value in stash.items():
            if name == "urls":
                self.urls_field.value = value
            elif name == "quality":
                self.quality_dd.value = value
            elif name == "noskip":
                self.noskip_cb.value = value
            elif hasattr(self, name):
                getattr(self, name).value = value
        self.refresh()

    def build_download_tab(self) -> ft.Control:
        self.urls_field = ft.TextField(
            label=self.t("links_label"),
            hint_text=self.t("links_hint"),
            multiline=True,
            min_lines=3,
            max_lines=6,
            autofocus=True,
        )

        quality = self.cfg_dl("track_quality", "high")
        self.quality_dd = ft.Dropdown(
            label=self.t("quality"),
            width=230,
            value=quality if quality in QUALITIES else "high",
            tooltip=self.t("quality_help"),
            options=[
                ft.DropdownOption(key=q, text=self.t(f"quality_{q}"))
                for q in QUALITIES
            ],
        )

        _gui_cfg = load_gui_settings()
        _audio_mode = str(_gui_cfg.get("audio_mode", "auto")).casefold()
        self.f_audio_mode = ft.Dropdown(
            label=self.t("audio_mode"),
            width=240,
            value=_audio_mode if _audio_mode in AUDIO_MODES else "auto",
            tooltip=self.t("audio_mode_help"),
            options=[
                ft.DropdownOption(key=mode, text=self.t(f"audio_mode_{mode}"))
                for mode in AUDIO_MODES
            ],
        )
        _quality_policy = str(_gui_cfg.get("quality_policy", "flexible")).casefold()
        self.f_quality_policy = ft.Dropdown(
            label=self.t("quality_policy"),
            width=290,
            value=(
                _quality_policy if _quality_policy in QUALITY_POLICIES else "flexible"
            ),
            tooltip=self.t("quality_policy_help"),
            options=[
                ft.DropdownOption(key=policy, text=self.t(f"quality_policy_{policy}"))
                for policy in QUALITY_POLICIES
            ],
        )

        self.noskip_cb = ft.Checkbox(label=self.t("redownload"), value=False)
        self.f_resume = ft.Checkbox(
            label=self.t("resume"), value=False, tooltip=self.t("resume_tip")
        )

        self.download_btn = ft.FilledButton(
            content=self.t("btn_download"),
            icon=ft.Icons.DOWNLOAD,
            on_click=self.on_download,
        )
        self.verify_btn = ft.OutlinedButton(
            content=self.t("btn_verify"),
            icon=ft.Icons.SEARCH,
            on_click=self.on_verify_versions,
        )
        self.login_btn = ft.FilledButton(
            content=self.t("btn_login"),
            icon=ft.Icons.LOGIN,
            on_click=self.on_login,
            visible=False,
        )
        # Shown only while logged in (mutually exclusive with login_btn); lets
        # the user end the TIDAL session / switch accounts from the GUI.
        self.logout_btn = ft.TextButton(
            content=self.t("btn_logout"),
            icon=ft.Icons.LOGOUT,
            on_click=self.on_logout,
            visible=False,
        )
        self.update_btn = ft.TextButton(
            content=self.t("update_available"),
            icon=ft.Icons.SYSTEM_UPDATE,
            on_click=lambda e: self.page.launch_url(RELEASES_URL),
            visible=False,
        )
        self.cancel_btn = ft.OutlinedButton(
            content=self.t("btn_cancel"),
            icon=ft.Icons.CLOSE,
            on_click=self.on_cancel,
            disabled=True,
        )

        self.status_text = ft.Text(self.t("ready"), size=self.fs + 1, weight=ft.FontWeight.BOLD)
        self.progress = ft.ProgressBar(value=0, expand=True)
        self.progress_label = ft.Text("", size=self.fs, weight=ft.FontWeight.BOLD)
        self.progress_row = ft.Row(
            [self.progress, self.progress_label],
            visible=False,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.now_text = ft.Text("", size=self.fs, color=ft.Colors.PRIMARY)
        self.log_view = ft.ListView(expand=True, spacing=0, auto_scroll=True)

        return ft.Column(
            [
                ft.Container(height=4),
                self.urls_field,
                ft.Row(
                    [
                        self.quality_dd,
                        self.f_audio_mode,
                        self.f_quality_policy,
                        self.noskip_cb,
                        self.f_resume,
                    ],
                    wrap=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Text(self.t("audio_mode_help"), size=11, color=ft.Colors.OUTLINE),
                ft.Text(self.t("quality_policy_help"), size=11, color=ft.Colors.OUTLINE),
                ft.Row(
                    [
                        self.update_btn,
                        self.logout_btn,
                        self.login_btn,
                        self.verify_btn,
                        self.download_btn,
                        self.cancel_btn,
                    ],
                    wrap=True,
                    alignment=ft.MainAxisAlignment.END,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                self.status_text,
                self.progress_row,
                self.now_text,
                ft.Row(
                    [
                        ft.Text(
                            f"v{APP_VERSION}" + (f" · tiddl {TIDDL_COMMIT}" if TIDDL_COMMIT else ""),
                            size=self.fs - 1,
                            color=self.pal["gray"],
                        ),
                        ft.Container(expand=True),
                        ft.TextButton(
                            content=self.t("copy_log"),
                            icon=ft.Icons.CONTENT_COPY,
                            on_click=self.on_copy_log,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(
                    # NOTE: do NOT wrap this in ft.SelectionArea — over a log
                    # that grows to hundreds/thousands of lines it recomputes
                    # selection on every update and freezes the render. The
                    # "Copy log" button is the way to get the text out.
                    content=self.log_view,
                    expand=True,
                    border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                    border_radius=8,
                    padding=8,
                ),
            ],
            expand=True,
            spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def build_settings_tab(self) -> ft.Control:
        def path_row(label: str, value, hint: str = "") -> tuple[ft.TextField, ft.Row]:
            field = ft.TextField(label=label, value=str(value or ""), hint_text=hint, expand=True)

            async def browse(e, f=field):
                path = await self.file_picker.get_directory_path()
                if path:
                    f.value = path
                    self.refresh()

            row = ft.Row(
                [field, ft.OutlinedButton(content=self.t("browse"), icon=ft.Icons.FOLDER_OPEN, on_click=browse)],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
            return field, row

        self.f_download_path, dl_row = path_row(
            self.t("dl_folder"), self.cfg_dl("download_path"), self.t("dl_folder_hint")
        )
        self.f_scan_path, scan_row = path_row(
            self.t("scan_folder"), self.cfg_dl("scan_path"), self.t("scan_folder_hint")
        )
        self.f_video_path, video_row = path_row(
            self.t("video_folder"), self.cfg_dl("video_download_path"), self.t("video_folder_hint")
        )
        gui_cfg = load_gui_settings()
        self.f_playlist_path, playlist_row = path_row(
            self.t("playlist_folder"),
            gui_cfg.get("playlist_download_path", ""),
            self.t("playlist_folder_hint"),
        )

        self.f_tpl_default = ft.TextField(
            label=self.t("tpl_default"), value=str(self.cfg_tpl("default", "")),
            hint_text="{album.artist}/{album.title}/{item.title}",
        )
        self.f_tpl_track = ft.TextField(label=self.t("tpl_track"), value=str(self.cfg_tpl("track", "")))
        self.f_tpl_album = ft.TextField(label=self.t("tpl_album"), value=str(self.cfg_tpl("album", "")))
        self.f_tpl_playlist = ft.TextField(label=self.t("tpl_playlist"), value=str(self.cfg_tpl("playlist", "")))
        self.f_tpl_video = ft.TextField(label=self.t("tpl_video"), value=str(self.cfg_tpl("video", "")))
        self.f_tpl_mix = ft.TextField(label=self.t("tpl_mix"), value=str(self.cfg_tpl("mix", "")))
        self.f_artist_sep = ft.TextField(
            label=self.t("artist_sep"),
            value=str(self.cfg_tpl("artist_separator", " / ") or " / "),
            width=200,
        )

        self.f_threads = ft.TextField(
            label=self.t("threads"), value=str(self.cfg_dl("threads_count", 1)), width=110
        )
        self.f_track_delay = ft.TextField(
            label=self.t("track_delay"), value=str(self.cfg_dl("track_delay", 3.0)), width=150
        )
        self.f_artist_delay = ft.TextField(
            label=self.t("album_delay"), value=str(self.cfg_dl("artist_delay", 8.0)), width=150
        )

        singles = self.cfg_dl("singles_filter", "none")
        self.f_singles = ft.Dropdown(
            label=self.t("singles"),
            width=170,
            value=singles if singles in SINGLES_FILTERS else "none",
            options=[ft.DropdownOption(v) for v in SINGLES_FILTERS],
        )
        videos = self.cfg_dl("videos_filter", "none")
        self.f_videos = ft.Dropdown(
            label=self.t("videos"),
            width=170,
            value=videos if videos in VIDEOS_FILTERS else "none",
            options=[ft.DropdownOption(v) for v in VIDEOS_FILTERS],
        )

        self.f_embed_lyrics = ft.Checkbox(
            label=self.t("embed_lyrics_cb"), value=bool(self.cfg_meta("embed_lyrics"))
        )
        self.f_save_lrc = ft.Checkbox(
            label=self.t("save_lrc_cb"), value=bool(self.cfg_meta("save_lyrics"))
        )

        # --- Metadata / tags ---
        self.f_cover = ft.Checkbox(
            label=self.t("embed_cover_cb"), value=bool(self.cfg_meta("cover"))
        )
        self.f_album_review = ft.Checkbox(
            label=self.t("album_review_cb"), value=bool(self.cfg_meta("album_review"))
        )

        # --- Cover file (.jpg) ---
        _cov_allowed = self.cfg_cover("allowed", []) or []
        if not isinstance(_cov_allowed, list):
            _cov_allowed = []
        _cover_save = bool(self.cfg_cover("save", False))
        # Album is the useful default. Older configs commonly have an empty
        # `allowed`, which made enabling cover saving appear to do nothing.
        if not _cov_allowed:
            _cov_allowed = ["album"]
        self.f_cover_save = ft.Checkbox(
            label=self.t("cover_save_cb"), value=_cover_save
        )
        self.f_cover_size = ft.TextField(
            label=self.t("cover_size"), value=str(self.cfg_cover("size", 1280) or 1280),
            width=220, disabled=not _cover_save,
        )
        self.f_cover_track = ft.Checkbox(
            label=self.t("target_track"), value="track" in _cov_allowed, disabled=not _cover_save
        )
        self.f_cover_album = ft.Checkbox(
            label=self.t("target_album"), value="album" in _cov_allowed, disabled=not _cover_save
        )
        self.f_cover_playlist = ft.Checkbox(
            label=self.t("target_playlist"), value="playlist" in _cov_allowed, disabled=not _cover_save
        )

        def cover_save_changed(e):
            enabled = bool(self.f_cover_save.value)
            if enabled and not any(
                cb.value for cb in (self.f_cover_track, self.f_cover_album, self.f_cover_playlist)
            ):
                self.f_cover_album.value = True
            for control in (
                self.f_cover_size, self.f_cover_track, self.f_cover_album, self.f_cover_playlist
            ):
                control.disabled = not enabled
            self.refresh(
                self.f_cover_size, self.f_cover_track, self.f_cover_album, self.f_cover_playlist
            )

        self.f_cover_save.on_change = cover_save_changed

        # --- Advanced download ---
        _vq = self.cfg_dl("video_quality", "fhd")
        self.f_video_quality = ft.Dropdown(
            label=self.t("video_quality"), width=220,
            value=_vq if _vq in VIDEO_QUALITIES else "fhd",
            options=[ft.DropdownOption(v) for v in VIDEO_QUALITIES],
        )
        _hc = self.cfg_dl("hires_client", "auto")
        self.f_hires_client = ft.Dropdown(
            label=self.t("hires_client"), width=220,
            value=_hc if _hc in HIRES_CLIENTS else "auto",
            options=[ft.DropdownOption(v) for v in HIRES_CLIENTS],
        )
        self.f_rpm = ft.TextField(
            label=self.t("rpm"), value=str(self.cfg_dl("requests_per_minute", 20)), width=220
        )
        self.f_concurrency = ft.TextField(
            label=self.t("concurrency"), value=str(self.cfg_dl("artist_concurrency", 1)), width=260
        )
        self.f_max_tracks = ft.TextField(
            label=self.t("max_tracks"), value=str(self.cfg_dl("max_tracks_per_session", 0)), width=260
        )
        self.f_rewrite = ft.Checkbox(
            label=self.t("rewrite_cb"), value=bool(self.cfg_dl("rewrite_metadata", False))
        )
        self.f_update_mtime = ft.Checkbox(
            label=self.t("mtime_cb"), value=bool(self.cfg_dl("update_mtime", False))
        )
        self.f_exclude_compilations = ft.Checkbox(
            label=self.t("exclude_comp_cb"),
            value=bool(self.cfg_dl("exclude_compilations", False)),
        )
        self.f_exclude_live = ft.Checkbox(
            label=self.t("exclude_live_cb"),
            value=bool(self.cfg_dl("exclude_live_albums", False)),
        )

        # --- m3u ---
        _m3u_allowed = self.cfg_m3u("allowed", []) or []
        if not isinstance(_m3u_allowed, list):
            _m3u_allowed = []
        self.f_m3u_save = ft.Checkbox(
            label=self.t("m3u_save_cb"), value=bool(self.cfg_m3u("save", False))
        )
        self.f_m3u_album = ft.Checkbox(label=self.t("target_album"), value="album" in _m3u_allowed)
        self.f_m3u_playlist = ft.Checkbox(label=self.t("target_playlist"), value="playlist" in _m3u_allowed)
        self.f_m3u_mix = ft.Checkbox(label=self.t("target_mix"), value="mix" in _m3u_allowed)

        self.lang_dd = ft.Dropdown(
            label=self.t("language"),
            width=170,
            value=self.lang,
            options=[
                ft.DropdownOption("en", "English"),
                ft.DropdownOption("es", "Español"),
            ],
            on_select=self.on_language_change,
        )

        self.theme_dd = ft.Dropdown(
            label=self.t("theme"),
            width=140,
            value=self.theme_name,
            options=[
                ft.DropdownOption("dark", self.t("theme_dark")),
                ft.DropdownOption("light", self.t("theme_light")),
            ],
            on_select=self.on_theme_change,
        )

        self.font_dd = ft.Dropdown(
            label=self.t("font_size"),
            width=160,
            value=self.font_name,
            options=[
                ft.DropdownOption("normal", self.t("font_normal")),
                ft.DropdownOption("large", self.t("font_large")),
                ft.DropdownOption("xlarge", self.t("font_xlarge")),
            ],
            on_select=self.on_font_change,
        )

        self.settings_status = ft.Text("", size=12)

        def section(title: str, controls: list[ft.Control], expanded: bool = True) -> ft.Control:
            """Collapsible section; fields inside stretch to the window width."""
            return ft.ExpansionTile(
                title=ft.Text(title, size=14, weight=ft.FontWeight.BOLD),
                expanded=expanded,
                maintain_state=True,
                controls=[
                    ft.Container(
                        content=ft.Column(
                            controls,
                            spacing=8,
                            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        ),
                        # top padding gives the TextField floating labels room; without
                        # it the ExpansionTile clips the top of the first row's labels.
                        padding=ft.Padding.only(left=8, top=10, right=8, bottom=12),
                    )
                ],
            )

        return ft.Column(
            [
                ft.Container(height=4),
                section(self.t("sec_folders"), [dl_row, scan_row, video_row, playlist_row]),
                section(
                    self.t("sec_naming"),
                    [
                        ft.Text(self.t("tpl_vars"), size=11, color=ft.Colors.OUTLINE),
                        self.f_tpl_default,
                        self.f_tpl_track,
                        self.f_tpl_album,
                        self.f_tpl_playlist,
                        self.f_tpl_video,
                        self.f_tpl_mix,
                        self.f_artist_sep,
                    ],
                ),
                section(
                    self.t("sec_perf"),
                    [
                        ft.Row(
                            [self.f_threads, self.f_track_delay, self.f_artist_delay, self.f_singles, self.f_videos],
                            wrap=True,
                        ),
                    ],
                ),
                section(
                    self.t("sec_metadata"),
                    [
                        ft.Row([self.f_cover, self.f_album_review], wrap=True),
                        ft.Row([self.f_embed_lyrics, self.f_save_lrc], wrap=True),
                    ],
                ),
                section(
                    self.t("sec_coverfile"),
                    [
                        ft.Row([self.f_cover_save, self.f_cover_size], wrap=True,
                               vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Text(self.t("cover_help"), size=11, color=ft.Colors.OUTLINE),
                        ft.Text(self.t("cover_allowed_lbl"), size=12, color=ft.Colors.OUTLINE),
                        ft.Row([self.f_cover_track, self.f_cover_album, self.f_cover_playlist], wrap=True),
                    ],
                    expanded=True,
                ),
                section(
                    self.t("sec_advanced"),
                    [
                        ft.Row(
                            [self.f_video_quality, self.f_hires_client, self.f_rpm],
                            wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Row(
                            [self.f_concurrency, self.f_max_tracks],
                            wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Text(self.t("hires_client_hint"), size=11, color=ft.Colors.OUTLINE),
                        ft.Row([self.f_rewrite, self.f_update_mtime], wrap=True),
                        ft.Row([self.f_exclude_compilations, self.f_exclude_live], wrap=True),
                        ft.Text(self.t("exclude_help"), size=11, color=ft.Colors.OUTLINE),
                    ],
                    expanded=False,
                ),
                section(
                    self.t("sec_m3u"),
                    [
                        self.f_m3u_save,
                        ft.Text(self.t("m3u_allowed_lbl"), size=12, color=ft.Colors.OUTLINE),
                        ft.Row([self.f_m3u_album, self.f_m3u_playlist, self.f_m3u_mix], wrap=True),
                    ],
                    expanded=False,
                ),
                ft.Container(height=10),
                ft.Row(
                    [
                        ft.FilledButton(content=self.t("save_defaults"), icon=ft.Icons.SAVE, on_click=self.on_save_defaults),
                        ft.OutlinedButton(content=self.t("reload"), icon=ft.Icons.REFRESH, on_click=self.on_reload_settings),
                        self.lang_dd,
                        self.theme_dd,
                        self.font_dd,
                        ft.TextButton(
                            content="GitHub",
                            icon=ft.Icons.OPEN_IN_NEW,
                            on_click=lambda e: self.page.launch_url(self.GITHUB_URL),
                        ),
                        self.settings_status,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    wrap=True,
                ),
                ft.Text(
                    self.t("footer"),
                    size=11,
                    color=ft.Colors.OUTLINE,
                ),
            ],
            expand=True,
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def build_help_tab(self) -> ft.Control:
        mono = "Consolas"

        def heading(text: str) -> ft.Control:
            return ft.Text(text, size=self.fs + 3, weight=ft.FontWeight.BOLD, color=self.pal["primary"])

        def var_table(rows: list[tuple[str, dict]]) -> ft.Control:
            cells = []
            for name, desc in rows:
                cells.append(
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Text(name, font_family=mono, size=self.fs,
                                                color=self.pal["primary"], selectable=True),
                                width=230,
                            ),
                            ft.Container(
                                content=ft.Text(desc[self.lang if self.lang in ("en", "es") else "en"],
                                                size=self.fs),
                                expand=True,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    )
                )
            return ft.Column(cells, spacing=6)

        def fmt_table(rows: list[tuple[str, str]]) -> ft.Control:
            cells = []
            for tpl, out in rows:
                cells.append(
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Text(tpl, font_family=mono, size=self.fs,
                                                color=self.pal["primary"], selectable=True),
                                width=260,
                            ),
                            ft.Text("→", size=self.fs, color=self.pal["gray"]),
                            ft.Text(out if out.strip() else '"' + out + '"', font_family=mono, size=self.fs),
                        ]
                    )
                )
            return ft.Column(cells, spacing=6)

        def card(content: ft.Control) -> ft.Control:
            return ft.Container(
                content=content,
                bgcolor=self.pal["surface"],
                border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                border_radius=8,
                padding=12,
            )

        example_box = ft.Container(
            content=ft.Column(
                [
                    ft.Text(self.t("help_example"), font_family=mono, size=self.fs,
                            color=self.pal["primary"], selectable=True),
                    ft.Text(self.t("help_example_note"), size=self.fs - 1, color=self.pal["gray"]),
                ],
                spacing=6,
            ),
            bgcolor=self.pal["surface"],
            border_radius=8,
            padding=12,
        )

        return ft.Column(
            [
                ft.Container(height=4),
                ft.Text(self.t("help_intro"), size=self.fs),
                ft.Text(self.t("help_example_label"), size=self.fs, weight=ft.FontWeight.BOLD),
                example_box,
                heading(self.t("help_sec_shortcuts")),
                card(var_table(HELP_SHORTCUTS)),
                heading(self.t("help_sec_item")),
                card(var_table(HELP_ITEM)),
                heading(self.t("help_sec_album")),
                card(var_table(HELP_ALBUM)),
                heading(self.t("help_sec_playlist")),
                card(var_table(HELP_PLAYLIST)),
                ft.Text(self.t("help_playlist_tip"), size=self.fs - 1, color=self.pal["gray"]),
                heading(self.t("help_sec_formats")),
                card(
                    ft.Column(
                        [
                            ft.Text(self.t("help_fmt_intro"), size=self.fs),
                            ft.Text(self.t("help_fmt_dates"), size=self.fs),
                            ft.Text(self.t("help_fmt_numbers"), size=self.fs),
                            ft.Divider(height=8, color=ft.Colors.OUTLINE_VARIANT),
                            ft.Text(self.t("help_fmt_explicit"), size=self.fs),
                            fmt_table(HELP_EXPLICIT_FMT),
                            ft.Divider(height=8, color=ft.Colors.OUTLINE_VARIANT),
                            ft.Text(self.t("help_fmt_flags"), size=self.fs),
                            fmt_table(HELP_FLAG_FMT),
                        ],
                        spacing=8,
                    )
                ),
                ft.Text(self.t("help_safe_note"), size=self.fs - 1, color=self.pal["gray"]),
                ft.Container(height=8),
            ],
            expand=True,
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def on_language_change(self, e):
        new_lang = self.lang_dd.value or "en"
        if new_lang == self.lang:
            return
        if self.running:
            self.lang_dd.value = self.lang
            self.settings_status.value = self.t("lang_locked")
            self.refresh()
            return
        self.lang = new_lang
        gui_cfg = load_gui_settings()
        gui_cfg["language"] = new_lang
        save_gui_settings(gui_cfg)
        self.rebuild()

    def on_theme_change(self, e):
        new_theme = self.theme_dd.value or "dark"
        if new_theme == self.theme_name:
            return
        if self.running:
            self.theme_dd.value = self.theme_name
            self.settings_status.value = self.t("theme_locked")
            self.refresh()
            return
        self.theme_name = new_theme
        gui_cfg = load_gui_settings()
        gui_cfg["theme"] = new_theme
        save_gui_settings(gui_cfg)
        self.rebuild()

    def on_font_change(self, e):
        new_font = self.font_dd.value or "normal"
        if new_font == self.font_name:
            return
        if self.running:
            self.font_dd.value = self.font_name
            self.settings_status.value = self.t("font_locked")
            self.refresh()
            return
        self.font_name = new_font
        gui_cfg = load_gui_settings()
        gui_cfg["font_size"] = new_font
        save_gui_settings(gui_cfg)
        self.rebuild()

    # ---------- settings helpers ----------

    def numeric_settings(self) -> tuple[int, float, float, int, int, int, int] | None:
        try:
            threads = max(1, int((self.f_threads.value or "1").strip()))
            track_delay = float((self.f_track_delay.value or "0").strip())
            artist_delay = float((self.f_artist_delay.value or "0").strip())
            rpm = max(0, int((self.f_rpm.value or "20").strip()))
            concurrency = max(0, int((self.f_concurrency.value or "1").strip()))
            max_tracks = max(0, int((self.f_max_tracks.value or "0").strip()))
            cover_size = min(1280, max(1, int((self.f_cover_size.value or "1280").strip())))
            if track_delay < 0 or artist_delay < 0:
                return None
            return threads, track_delay, artist_delay, rpm, concurrency, max_tracks, cover_size
        except (ValueError, TypeError):
            return None

    def settings_flags(
        self,
        base_override: str | None = None,
        singles: str | None = None,
        videos: str | None = None,
    ) -> list[str] | None:
        """Build CLI flags from the Settings tab.

        base_override replaces the download AND scan folders - used to send
        playlists to their own folder (possibly another disk). singles/videos
        override the Settings values for this run (artist dialog).
        """
        nums = self.numeric_settings()
        if nums is None:
            self.set_status(self.t("invalid_number"), error=True)
            return None
        threads, track_delay, artist_delay, _rpm, concurrency, _max_tracks, _cover_size = nums

        if self.f_cover_save.value and not any(
            cb.value for cb in (self.f_cover_track, self.f_cover_album, self.f_cover_playlist)
        ):
            self.set_status(self.t("cover_target_required"), error=True)
            return None

        flags: list[str] = ["-t", str(threads), "-td", str(track_delay), "-d", str(artist_delay)]
        singles_val = singles or self.f_singles.value
        videos_val = videos or self.f_videos.value
        if singles_val:
            flags += ["-s", singles_val]
        if videos_val:
            flags += ["-vid", videos_val]

        flags.append("--embed-lyrics" if self.f_embed_lyrics.value else "--no-embed-lyrics")
        flags.append("--save-lyrics" if self.f_save_lrc.value else "--no-save-lyrics")

        # Only EXISTING core options are passed as flags here: they're present in
        # the command that the in-process run builds under the redirected stdout
        # (see run_tiddl). video_quality/-vq, concurrency/-c, rewrite/-r are typer
        # params (defaults bind at import) so they MUST be flags to change per run.
        # All the NEWER options (cover, hires_client, m3u, etc.) are applied via
        # apply_runtime_config() instead: passing them as flags would fail with
        # "No such option" because tiddl's Typer command, built during the
        # in-process embedded call, does NOT expose the dynamically-added flags —
        # only the CLI-standalone build does. CONFIG mutation is immune to that.
        if self.f_video_quality.value:
            flags += ["-vq", self.f_video_quality.value]
        flags += ["-c", str(concurrency)]
        if self.f_rewrite.value:
            flags.append("-r")

        download_path = base_override or (self.f_download_path.value or "").strip()
        scan_path = base_override or (self.f_scan_path.value or "").strip()
        if download_path:
            flags += ["-p", download_path]
        if scan_path:
            flags += ["--sp", scan_path]

        for flag, field in [
            ("-vp", self.f_video_path),
            ("-o", self.f_tpl_default),
            ("--ttf", self.f_tpl_track),
            ("--atf", self.f_tpl_album),
            ("--ptf", self.f_tpl_playlist),
            ("--vtf", self.f_tpl_video),
        ]:
            value = (field.value or "").strip()
            if value:
                flags += [flag, value]
        return flags

    def on_reload_settings(self, e):
        self.cfg = load_tiddl_config()
        self.f_download_path.value = str(self.cfg_dl("download_path") or "")
        self.f_scan_path.value = str(self.cfg_dl("scan_path") or "")
        self.f_video_path.value = str(self.cfg_dl("video_download_path") or "")
        self.f_playlist_path.value = str(load_gui_settings().get("playlist_download_path", ""))
        self.f_tpl_default.value = str(self.cfg_tpl("default", ""))
        self.f_tpl_track.value = str(self.cfg_tpl("track", ""))
        self.f_tpl_album.value = str(self.cfg_tpl("album", ""))
        self.f_tpl_playlist.value = str(self.cfg_tpl("playlist", ""))
        self.f_tpl_video.value = str(self.cfg_tpl("video", ""))
        self.f_tpl_mix.value = str(self.cfg_tpl("mix", ""))
        self.f_artist_sep.value = str(self.cfg_tpl("artist_separator", " / ") or " / ")
        self.f_threads.value = str(self.cfg_dl("threads_count", 1))
        self.f_track_delay.value = str(self.cfg_dl("track_delay", 3.0))
        self.f_artist_delay.value = str(self.cfg_dl("artist_delay", 8.0))
        self.f_singles.value = self.cfg_dl("singles_filter", "none")
        self.f_videos.value = self.cfg_dl("videos_filter", "none")
        self.f_embed_lyrics.value = bool(self.cfg_meta("embed_lyrics"))
        self.f_save_lrc.value = bool(self.cfg_meta("save_lyrics"))
        # metadata / cover
        self.f_cover.value = bool(self.cfg_meta("cover"))
        self.f_album_review.value = bool(self.cfg_meta("album_review"))
        _cov = self.cfg_cover("allowed", []) or []
        _cov = _cov if isinstance(_cov, list) else []
        self.f_cover_save.value = bool(self.cfg_cover("save", False))
        if not _cov:
            _cov = ["album"]
        self.f_cover_size.value = str(self.cfg_cover("size", 1280) or 1280)
        self.f_cover_track.value = "track" in _cov
        self.f_cover_album.value = "album" in _cov
        self.f_cover_playlist.value = "playlist" in _cov
        for control in (
            self.f_cover_size, self.f_cover_track, self.f_cover_album, self.f_cover_playlist
        ):
            control.disabled = not self.f_cover_save.value
        # advanced download
        _vq = self.cfg_dl("video_quality", "fhd")
        self.f_video_quality.value = _vq if _vq in VIDEO_QUALITIES else "fhd"
        _hc = self.cfg_dl("hires_client", "auto")
        self.f_hires_client.value = _hc if _hc in HIRES_CLIENTS else "auto"
        self.f_rpm.value = str(self.cfg_dl("requests_per_minute", 20))
        self.f_concurrency.value = str(self.cfg_dl("artist_concurrency", 1))
        self.f_max_tracks.value = str(self.cfg_dl("max_tracks_per_session", 0))
        self.f_rewrite.value = bool(self.cfg_dl("rewrite_metadata", False))
        self.f_exclude_compilations.value = bool(self.cfg_dl("exclude_compilations", False))
        self.f_exclude_live.value = bool(self.cfg_dl("exclude_live_albums", False))
        self.f_update_mtime.value = bool(self.cfg_dl("update_mtime", False))
        _audio_mode = str(load_gui_settings().get("audio_mode", "auto")).casefold()
        self.f_audio_mode.value = _audio_mode if _audio_mode in AUDIO_MODES else "auto"
        _quality_policy = str(load_gui_settings().get("quality_policy", "flexible")).casefold()
        self.f_quality_policy.value = (
            _quality_policy if _quality_policy in QUALITY_POLICIES else "flexible"
        )
        # m3u
        _m3u = self.cfg_m3u("allowed", []) or []
        _m3u = _m3u if isinstance(_m3u, list) else []
        self.f_m3u_save.value = bool(self.cfg_m3u("save", False))
        self.f_m3u_album.value = "album" in _m3u
        self.f_m3u_playlist.value = "playlist" in _m3u
        self.f_m3u_mix.value = "mix" in _m3u
        self.settings_status.value = self.t("reloaded")
        self.refresh()

    def on_save_defaults(self, e):
        nums = self.numeric_settings()
        if nums is None:
            self.settings_status.value = self.t("invalid_number_short")
            self.refresh()
            return
        threads, track_delay, artist_delay, rpm, concurrency, max_tracks, cover_size = nums
        cover_allowed = [
            t for t, cb in (
                ("track", self.f_cover_track), ("album", self.f_cover_album),
                ("playlist", self.f_cover_playlist),
            ) if cb.value
        ]
        if self.f_cover_save.value and not cover_allowed:
            self.settings_status.value = self.t("cover_target_required")
            self.refresh()
            return
        m3u_allowed = [
            t for t, cb in (
                ("album", self.f_m3u_album), ("playlist", self.f_m3u_playlist),
                ("mix", self.f_m3u_mix),
            ) if cb.value
        ]

        cfg_path = config_file_path()
        try:
            if cfg_path.exists():
                stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
                shutil.copy2(cfg_path, cfg_path.with_name(f"config.toml.bak_{stamp}"))
                doc = tomlkit.parse(cfg_path.read_text(encoding="utf-8"))
            else:
                cfg_path.parent.mkdir(parents=True, exist_ok=True)
                doc = tomlkit.document()

            if "download" not in doc:
                doc["download"] = tomlkit.table()
            dl = doc["download"]
            dl["track_quality"] = self.quality_dd.value or "high"
            dl["video_quality"] = self.f_video_quality.value or "fhd"
            dl["hires_client"] = self.f_hires_client.value or "auto"
            dl["threads_count"] = threads
            dl["requests_per_minute"] = rpm
            dl["track_delay"] = track_delay
            dl["artist_delay"] = artist_delay
            dl["artist_concurrency"] = concurrency
            dl["max_tracks_per_session"] = max_tracks
            dl["singles_filter"] = self.f_singles.value or "none"
            dl["videos_filter"] = self.f_videos.value or "none"
            dl["rewrite_metadata"] = bool(self.f_rewrite.value)
            dl["exclude_compilations"] = bool(self.f_exclude_compilations.value)
            dl["exclude_live_albums"] = bool(self.f_exclude_live.value)
            dl["update_mtime"] = bool(self.f_update_mtime.value)
            for key, field in [
                ("download_path", self.f_download_path),
                ("scan_path", self.f_scan_path),
                ("video_download_path", self.f_video_path),
            ]:
                value = (field.value or "").strip()
                if value:
                    dl[key] = value

            if "metadata" not in doc:
                doc["metadata"] = tomlkit.table()
            doc["metadata"]["embed_lyrics"] = bool(self.f_embed_lyrics.value)
            doc["metadata"]["save_lyrics"] = bool(self.f_save_lrc.value)
            doc["metadata"]["cover"] = bool(self.f_cover.value)
            doc["metadata"]["album_review"] = bool(self.f_album_review.value)

            if "cover" not in doc:
                doc["cover"] = tomlkit.table()
            doc["cover"]["save"] = bool(self.f_cover_save.value)
            doc["cover"]["size"] = cover_size
            doc["cover"]["allowed"] = cover_allowed

            if "m3u" not in doc:
                doc["m3u"] = tomlkit.table()
            doc["m3u"]["save"] = bool(self.f_m3u_save.value)
            doc["m3u"]["allowed"] = m3u_allowed

            if "templates" not in doc:
                doc["templates"] = tomlkit.table()
            tpl = doc["templates"]
            for key, field in [
                ("default", self.f_tpl_default),
                ("track", self.f_tpl_track),
                ("album", self.f_tpl_album),
                ("playlist", self.f_tpl_playlist),
                ("video", self.f_tpl_video),
                ("mix", self.f_tpl_mix),
            ]:
                value = (field.value or "").strip()
                # Never persist an empty template. An empty "default" in
                # particular used to brick the CLI; leaving keys out lets
                # tiddl apply its built-in defaults.
                if value:
                    tpl[key] = value
                elif key in tpl:
                    del tpl[key]
            # artist_separator is not a path template; persist verbatim (may be
            # " / ", ", ", etc). Only skip if the field was cleared entirely.
            sep = self.f_artist_sep.value
            if sep is not None and sep != "":
                tpl["artist_separator"] = sep

            cfg_path.write_text(tomlkit.dumps(doc), encoding="utf-8")

            # GUI-only keys live in gui.json, not in tiddl's config.
            gui_cfg = load_gui_settings()
            gui_cfg["playlist_download_path"] = (self.f_playlist_path.value or "").strip()
            gui_cfg["language"] = self.lang
            gui_cfg["theme"] = self.theme_name
            gui_cfg["font_size"] = self.font_name
            gui_cfg["audio_mode"] = self.f_audio_mode.value or "auto"
            gui_cfg["quality_policy"] = self.f_quality_policy.value or "flexible"
            save_gui_settings(gui_cfg)

            self.cfg = load_tiddl_config()
            self.settings_status.value = self.t("saved", path=cfg_path)
        except Exception as ex:
            self.settings_status.value = self.t("save_failed", err=ex)
        self.refresh()

    # ---------- status / log ----------

    def set_status(self, text: str, error: bool = False):
        self.status_text.value = text
        self.status_text.color = self.pal["error"] if error else None
        self.refresh(self.status_text)

    def log(self, line: str):
        """Buffer log lines and flush in batches - one UI patch per line at
        hundreds of lines/second floods the event loop and freezes the UI."""
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        self._log_buffer.append((stamp, line))
        now = time.monotonic()
        if now - self._log_last_flush >= 0.5 or len(self._log_buffer) >= 120:
            self.flush_log()

    def flush_log(self):
        if not self._log_buffer:
            return
        self._log_last_flush = time.monotonic()
        # Drain the buffer and build the new controls off the loop thread (safe -
        # they are not mounted yet). The plain _log_lines list is only touched
        # here and in on_copy_log after a flush, so it stays consistent.
        batch = self._log_buffer
        self._log_buffer = []
        new_controls = []
        for stamp, line in batch:
            new_controls.append(
                ft.Text(
                    spans=[
                        ft.TextSpan(f"[{stamp}] ", style=ft.TextStyle(color=self.pal["gray"])),
                        ft.TextSpan(line),
                    ],
                    size=self.fs,
                    font_family="Consolas",
                    selectable=True,
                )
            )
            self._log_lines.append(f"[{stamp}] {line}")
        if len(self._log_lines) > 5000:
            del self._log_lines[: len(self._log_lines) - 5000]

        # Mutate the mounted ListView and diff it on the SAME (loop) thread so
        # the two can never overlap. Doing the append/trim here instead of on
        # the worker thread is what prevents the object_patch IndexError crash.
        # Keep the on-screen ListView small: Flet re-diffs every child on each
        # patch, so a large list makes each flush O(n) and freezes the render
        # on long downloads. The full text stays in _log_lines for "Copy log".
        def apply():
            self.log_view.controls.extend(new_controls)
            if len(self.log_view.controls) > 300:
                del self.log_view.controls[: len(self.log_view.controls) - 250]
            self.page.update(self.log_view)

        self._run_on_ui(apply)

    async def on_copy_log(self, e):
        self.flush_log()
        text = "\n".join(self._log_lines)
        if not text:
            return
        try:
            await self.clipboard.set(text)
            self.set_status(self.t("log_copied"))
        except Exception as ex:
            self.set_status(self.t("log_copy_fail", err=ex), error=True)

    def set_running(self, running: bool):
        self.running = running
        if not running:
            release_download_lock()
        self.download_btn.disabled = running
        self.verify_btn.disabled = running
        self.cancel_btn.disabled = not running
        self.progress_row.visible = running
        self.progress.value = None if running else 0
        self.progress_label.value = ""
        self.now_text.value = ""
        self._last_prog: tuple[int, int] | None = None
        self._last_now: str | None = None
        self._last_now_ts = 0.0
        self._expanded_progress = False
        if not running:
            self.flush_log()
        self.refresh()

    def set_progress(self, done: int, total: int):
        if total <= 0:
            return
        key = (done, total)
        if key == getattr(self, "_last_prog", None):
            return
        self._last_prog = key
        fraction = min(1.0, done / total)
        self.progress.value = fraction
        self.progress_label.value = f"{done}/{total} · {round(fraction * 100)}%"
        self.refresh(self.progress, self.progress_label)

    def set_now(self, text: str):
        """Show the in-flight track line (throttled - frames arrive ~10/s)."""
        import time

        now = time.monotonic()
        if text == getattr(self, "_last_now", None):
            return
        if now - getattr(self, "_last_now_ts", 0.0) < 0.4:
            return
        self._last_now = text
        self._last_now_ts = now
        self.now_text.value = text
        self.refresh(self.now_text)

    # ---------- actions ----------

    def on_download(self, e):
        if other_instance_downloading():
            self.show_busy_dialog()
            return
        urls = [u.strip() for u in re.split(r"[\s,]+", self.urls_field.value or "") if u.strip()]
        if not urls:
            self.set_status(self.t("paste_link"), error=True)
            return
        if any("playlist/" in u for u in urls):
            self.ask_playlist_mode(urls)
            return
        self.check_combo_or_start(urls, expand=None)

    def on_verify_versions(self, e):
        """Run the stereo resolver only; the engine exits before Downloader."""
        if other_instance_downloading():
            self.show_busy_dialog()
            return
        urls = [u.strip() for u in re.split(r"[\s,]+", self.urls_field.value or "") if u.strip()]
        if not urls:
            self.set_status(self.t("paste_link"), error=True)
            return
        if (self.f_audio_mode.value or "auto").casefold() != "stereo":
            self.set_status(self.t("verify_stereo_required"), error=True)
            return
        if any("album/" not in u for u in urls):
            self.set_status(self.t("verify_album_only"), error=True)
            return
        self.start_download(urls, dry_run=True)

    def show_busy_dialog(self):
        dlg = ft.AlertDialog(
            modal=True,
            title=self.t("lock_busy_title"),
            content=ft.Text(self.t("lock_busy_msg")),
            actions=[
                ft.FilledButton(content="OK", on_click=lambda e: self.page.pop_dialog()),
            ],
        )
        self.page.show_dialog(dlg)

    def check_combo_or_start(self, urls: list[str], expand: str | None):
        if any(COMBO_RE.search(u) for u in urls):
            self.ask_album_or_track(urls, expand)
        else:
            self.maybe_artist_or_start(urls, expand)

    def maybe_artist_or_start(self, urls: list[str], expand: str | None):
        """Artist downloads are huge - confirm and pick singles/videos per run."""
        if expand == "artists" or any("artist/" in u for u in urls):
            self.ask_artist_options(urls, expand)
        else:
            self.start_download(urls, expand)

    def ask_artist_options(self, urls: list[str], expand: str | None):
        n = sum(1 for u in urls if "artist/" in u)
        singles_dd = ft.Dropdown(
            label=self.t("singles"),
            width=200,
            value=self.f_singles.value if self.f_singles.value in SINGLES_FILTERS else "none",
            options=[ft.DropdownOption(v) for v in SINGLES_FILTERS],
        )
        videos_dd = ft.Dropdown(
            label=self.t("videos"),
            width=200,
            value=self.f_videos.value if self.f_videos.value in VIDEOS_FILTERS else "none",
            options=[ft.DropdownOption(v) for v in VIDEOS_FILTERS],
        )
        msg = (
            self.t("dlg_artist_msg_expand")
            if expand == "artists"
            else self.t("dlg_artist_msg", n=n)
        )

        def go(e):
            self.page.pop_dialog()
            self.start_download(
                urls, expand, singles=singles_dd.value, videos=videos_dd.value
            )

        dlg = ft.AlertDialog(
            modal=True,
            title=self.t("dlg_artist_title"),
            content=ft.Column(
                [ft.Text(msg), singles_dd, videos_dd],
                spacing=12,
                tight=True,
                width=430,
            ),
            actions=[
                ft.TextButton(content=self.t("btn_cancel"), on_click=lambda e: self.page.pop_dialog()),
                ft.FilledButton(content=self.t("btn_continue"), on_click=go),
            ],
        )
        self.page.show_dialog(dlg)

    def ask_playlist_mode(self, urls: list[str]):
        """Playlist links can download as-is or expanded (tiddl --albums/--artists/--tracks)."""

        def choose(mode: str | None):
            def handler(e):
                self.page.pop_dialog()
                self.check_combo_or_start(urls, expand=mode)

            return handler

        def option(label: str, description: str, mode: str | None) -> ft.Control:
            return ft.OutlinedButton(
                content=ft.Column(
                    [
                        ft.Text(label, weight=ft.FontWeight.BOLD),
                        ft.Text(description, size=11, color=ft.Colors.OUTLINE),
                    ],
                    spacing=2,
                    tight=True,
                ),
                on_click=choose(mode),
            )

        dlg = ft.AlertDialog(
            modal=True,
            title=self.t("dlg_playlist_title"),
            content=ft.Column(
                [
                    ft.Text(self.t("dlg_playlist_q")),
                    option(self.t("opt_playlist"), self.t("opt_playlist_d"), None),
                    option(self.t("opt_albums"), self.t("opt_albums_d"), "albums"),
                    option(self.t("opt_artists"), self.t("opt_artists_d"), "artists"),
                    option(self.t("opt_tracks"), self.t("opt_tracks_d"), "tracks"),
                ],
                spacing=8,
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                width=430,
            ),
            actions=[
                ft.TextButton(content=self.t("btn_cancel"), on_click=lambda e: self.page.pop_dialog()),
            ],
        )
        self.page.show_dialog(dlg)

    def ask_album_or_track(self, urls: list[str], expand: str | None = None):
        """Combined album/track links are ambiguous - let the user decide."""

        def choose(mode: str):
            def handler(e):
                self.page.pop_dialog()
                resolved = []
                for u in urls:
                    m = COMBO_RE.search(u)
                    if m:
                        u = u[: m.start()] + m.group(1) if mode == "album" else f"track/{m.group(2)}"
                    resolved.append(u)
                self.maybe_artist_or_start(resolved, expand)

            return handler

        dlg = ft.AlertDialog(
            modal=True,
            title=self.t("dlg_combo_title"),
            content=ft.Text(self.t("dlg_combo_q")),
            actions=[
                ft.TextButton(content=self.t("btn_cancel"), on_click=lambda e: self.page.pop_dialog()),
                ft.OutlinedButton(content=self.t("opt_full_album"), on_click=choose("album")),
                ft.FilledButton(content=self.t("opt_only_track"), on_click=choose("track")),
            ],
        )
        self.page.show_dialog(dlg)

    def build_cmd(
        self,
        urls: list[str],
        base_override: str | None = None,
        expand: str | None = None,
        singles: str | None = None,
        videos: str | None = None,
        dry_run: bool = False,
    ) -> list[str] | None:
        flags = self.settings_flags(base_override, singles=singles, videos=videos)
        if flags is None:
            return None
        cmd = ["download", "-q", self.quality_dd.value or "high", *flags]
        audio_mode = (self.f_audio_mode.value or "auto").casefold()
        if audio_mode == "stereo":
            cmd += ["--audio-mode", "stereo", "--edition-match", "best"]
        quality_policy = (self.f_quality_policy.value or "flexible").casefold()
        if quality_policy == "strict":
            cmd += ["--quality-policy", "strict"]
        if dry_run:
            cmd.append("--dry-run")
        if expand in ("albums", "artists", "tracks"):
            cmd.append(f"--{expand}")
        if self.noskip_cb.value:
            cmd.append("-ns")
        if self.f_resume.value:
            cmd.append("--resume")
        cmd += ["url", *urls]
        return cmd

    def start_download(
        self,
        urls: list[str],
        expand: str | None = None,
        singles: str | None = None,
        videos: str | None = None,
        dry_run: bool = False,
    ):
        playlist_path = (self.f_playlist_path.value or "").strip()
        playlist_urls = [u for u in urls if "playlist/" in u]
        other_urls = [u for u in urls if u not in playlist_urls]

        # Windows caps a command line at ~32K chars; 300 URLs per run stays
        # far below it, and the worker chains runs sequentially anyway.
        def chunked(lst: list[str], n: int = 300) -> list[list[str]]:
            return [lst[i : i + n] for i in range(0, len(lst), n)]

        cmds: list[list[str]] = []

        def add_runs(run_urls: list[str], **kwargs) -> bool:
            for chunk in chunked(run_urls):
                cmd = self.build_cmd(
                    chunk,
                    singles=singles,
                    videos=videos,
                    dry_run=dry_run,
                    **kwargs,
                )
                if cmd is None:
                    return False
                cmds.append(cmd)
            return True

        if expand:
            # Expanded downloads are albums/artists/tracks, NOT playlists:
            # they go to the normal base folder, no playlist-folder split.
            if not add_runs(urls, expand=expand):
                return
        elif playlist_path and playlist_urls:
            # Playlists get their own base folder via a separate CLI run.
            if other_urls and not add_runs(other_urls):
                return
            if not add_runs(playlist_urls, base_override=playlist_path):
                return
        else:
            if not add_runs(urls):
                return

        if other_instance_downloading():
            self.show_busy_dialog()
            return

        self.log_view.controls.clear()
        self._log_buffer.clear()
        self._log_lines.clear()
        acquire_download_lock()
        self.set_running(True)
        self.set_status(self.t("starting"))
        self.page.run_thread(self.worker, cmds)

    def on_cancel(self, e):
        # In-process there is no child to kill: signal tiddl's cooperative
        # cancel flag. The download loop checks it at the top of each track,
        # after acquiring the semaphore, and per chunk while streaming bytes,
        # so the current track aborts and the queue drains.
        self.cancelled = True
        if tiddl_cancel is not None:
            tiddl_cancel.request_cancel()
        self.set_status(self.t("cancelled"))

    def apply_runtime_config(self) -> None:
        """Push the Settings options that have no usable in-process CLI flag into
        the shared tiddl CONFIG object, right before a run.

        tiddl runs in-process (see run_tiddl), so every module shares ONE CONFIG
        object (`from ...config import CONFIG`); mutating it in place propagates
        everywhere the download flow reads it at runtime. This is the ONLY robust
        path for these options in the embedded GUI: the core DOES expose matching
        CLI flags (--cover, --hires-client, --m3u, --mtf, --artist-separator, …)
        for real command-line parity, but Typer's command as built during the
        in-process, stdout-redirected call omits those dynamically-added flags,
        so passing them would raise 'No such option'. CONFIG mutation sidesteps
        the parser entirely. Best-effort: never let a bad field abort the run."""
        def _int(val, default):
            try:
                return int(float(str(val).strip()))
            except (ValueError, TypeError):
                return default
        try:
            from tiddl.cli.config import CONFIG
        except Exception as e:
            self.log(f"(config sync skipped: {e})")
            return
        try:
            CONFIG.metadata.cover = bool(self.f_cover.value)
            CONFIG.metadata.album_review = bool(self.f_album_review.value)

            CONFIG.cover.save = bool(self.f_cover_save.value)
            CONFIG.cover.size = min(1280, max(1, _int(self.f_cover_size.value, 1280)))
            CONFIG.cover.allowed = [
                t for t, cb in (
                    ("track", self.f_cover_track), ("album", self.f_cover_album),
                    ("playlist", self.f_cover_playlist),
                ) if cb.value
            ]

            CONFIG.download.hires_client = self.f_hires_client.value or "auto"
            CONFIG.download.requests_per_minute = max(0, _int(self.f_rpm.value, 20))
            CONFIG.download.update_mtime = bool(self.f_update_mtime.value)
            CONFIG.download.exclude_compilations = bool(self.f_exclude_compilations.value)
            CONFIG.download.exclude_live_albums = bool(self.f_exclude_live.value)
            CONFIG.download.max_tracks_per_session = max(0, _int(self.f_max_tracks.value, 0))

            CONFIG.m3u.save = bool(self.f_m3u_save.value)
            CONFIG.m3u.allowed = [
                t for t, cb in (
                    ("album", self.f_m3u_album), ("playlist", self.f_m3u_playlist),
                    ("mix", self.f_m3u_mix),
                ) if cb.value
            ]

            mix = (self.f_tpl_mix.value or "").strip()
            if mix:
                CONFIG.templates.mix = mix
            sep = self.f_artist_sep.value
            if sep is not None and sep != "":
                CONFIG.templates.artist_separator = sep
        except Exception as e:
            self.log(f"(config sync partial: {e})")

    def run_one(self, cmd: list[str]) -> tuple[int, int | None]:
        """Run one `download ...` invocation IN-PROCESS, parsing tiddl's
        forced-terminal rich output line by line for progress, the now-playing
        label and the human log - identical parsing to the old subprocess pipe,
        just fed from run_tiddl()'s stdout capture."""
        last_line = None
        total = None

        def on_line(raw: str):
            nonlocal last_line, total
            # Once cancelled, freeze the display: tiddl drains its queue and may
            # still emit a few lines while unwinding; showing them makes cancel
            # look like it "kept going". Drop everything after the user cancels.
            if self.cancelled:
                return
            stripped = ANSI_RE.sub("", raw).strip()
            # Visual progress: album counter of expanded runs takes priority;
            # otherwise use the CLI's own Total Progress frames (x/y items).
            hm = HEART_RE.match(stripped)
            if hm:
                self._expanded_progress = True
                self.set_progress(int(hm.group(1)), int(hm.group(2)))
            elif not getattr(self, "_expanded_progress", False):
                pm = PROG_FRAME_RE.match(stripped)
                if pm:
                    self.set_progress(int(pm.group(1)), int(pm.group(2)))

            # In-flight track frames live inside the rich "Downloading" panel
            # (lines framed with │...│); surface them as a "now downloading"
            # label since the log filter drops panel frames entirely.
            if stripped[:1] in "│┃|":
                inner = SPINNER_RE.sub("", stripped.strip("│┃| ")).strip()
                inner = re.sub(r"[━╸╺═]+", "", inner)
                inner = re.sub(r"\s{2,}", "  ", inner).strip()
                if inner and not re.match(r"^[\d.]+s\b", inner):
                    self.set_now(inner)

            line = meaningful_line(raw)
            if not line or line == last_line:
                return
            last_line = line
            m = TOTAL_RE.search(line)
            if m:
                total = int(m.group(1))
            if line.startswith("Auth token"):
                self.set_status(line)
                return
            if line.startswith("Downloading "):
                self.set_status(line)
            self.log(line)

        self.apply_runtime_config()
        code = run_tiddl(cmd, on_line)
        return code, total

    def worker(self, cmds: list[list[str]]):
        self.cancelled = False
        if tiddl_cancel is not None:
            tiddl_cancel.clear()
        grand_total = 0
        worst_code = 0
        try:
            for i, cmd in enumerate(cmds, start=1):
                if self.cancelled:
                    break
                if len(cmds) > 1:
                    self.log(self.t("run_sep", i=i, n=len(cmds)))
                code, total = self.run_one(cmd)
                self.flush_log()
                grand_total += total or 0
                worst_code = worst_code or code
                # A fatal 401 or stereo-stream policy violation raises the
                # engine's cooperative stop signal. Unlike the Cancel button,
                # this does not set self.cancelled; stop subsequent chunks and
                # surface an error instead of incorrectly reporting success.
                if (
                    tiddl_cancel is not None
                    and tiddl_cancel.is_cancelled()
                    and not self.cancelled
                ):
                    self.log(self.t("core_stopped"))
                    self.flush_log()
                    worst_code = worst_code or 1
                    break
        except Exception as ex:
            self.set_running(False)
            self.set_status(self.t("error", e=ex), error=True)
            return

        self.set_running(False)
        if self.cancelled:
            self.set_status(self.t("cancelled_n", n=grand_total))
        elif worst_code == 0:
            self.set_status(self.t("done_n", n=grand_total))
        else:
            self.set_status(self.t("errors_n", c=worst_code, n=grand_total), error=True)


def main(page: ft.Page):
    TiddlGui(page)


if __name__ == "__main__":
    ft.run(main)
