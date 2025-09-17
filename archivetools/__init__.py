from .__version__ import __version__

import os
import sys
import json
import datetime as _dt
import logging
import hashlib
import subprocess
import argparse
from pathlib import Path

from PIL import Image, ExifTags  # type: ignore
from pillow_heif import register_heif_opener  # type: ignore
from colorama import Fore, Style, init as _colorama_init  # type: ignore
import getpass

_colorama_init(autoreset=True)

register_heif_opener()
_HEIF_SUPPORTED = True


# =============================================================================
# Logging (colored)
# =============================================================================

_LEVEL_TO_COLOR = {
    logging.DEBUG: Style.DIM,
    logging.INFO: Fore.GREEN,
    logging.WARNING: Fore.YELLOW + Style.BRIGHT,
    logging.ERROR: Fore.RED + Style.BRIGHT,
    logging.CRITICAL: Fore.RED + Style.BRIGHT,
}

class _ColoredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.__dict__.setdefault("target", "")
        color = _LEVEL_TO_COLOR.get(record.levelno, Style.NORMAL)
        # Temporarily replace the levelname for colorization
        original_levelname = record.levelname
        try:
            record.levelname = f"{color}{original_levelname}{Style.RESET_ALL}"
            return super().format(record)
        finally:
            record.levelname = original_levelname


def configure_logging(verbose: bool = False) -> None:
    """
    Configure a colored root logger. Safe to call multiple times.
    Ensures ALL StreamHandlers get a colored formatter (even if they were added earlier).
    """
    root = logging.getLogger()
    level = logging.DEBUG if verbose else logging.INFO
    root.setLevel(level)

    # If there is no stream handler yet, add one.
    has_stream = any(isinstance(h, logging.StreamHandler) for h in root.handlers)
    if not has_stream:
        handler = logging.StreamHandler()
        handler.setFormatter(_ColoredFormatter("%(levelname)s:\t%(target)s\t%(message)s"))
        root.addHandler(handler)

    # Update ALL stream handlers to colored format and level
    for h in root.handlers:
        try:
            if isinstance(h, logging.StreamHandler):
                h.setLevel(level)
                # If it's not already a _ColoredFormatter, swap it so INFO gets color too.
                if not isinstance(getattr(h, "formatter", None), _ColoredFormatter):
                    h.setFormatter(_ColoredFormatter("%(levelname)s:\t%(target)s\t%(message)s"))
        except Exception:
            # be resilient; never hard-crash logging config
            pass



# Configure once with default INFO; individual scripts can call configure_logging()
configure_logging(verbose=False)

# =============================================================================
# Constants
# =============================================================================

# Sidecar extensions that commonly accompany media files
SIDECAR_EXTENSIONS = [
    ".aae", ".xmp", ".json", ".txt",
    ".srt", ".sub", ".idx", ".vtt", ".lrc",
    ".md", ".log", ".nfo", ".mta",
    ".thm",
]

# Image & video extensions
IMAGE_EXTENSIONS = [
    ".jpg", ".jpeg", ".jpe",
    ".png",
    ".tif", ".tiff",
    ".bmp",
    ".gif",
    ".webp",
    ".heic", ".heif",
    ".dng", ".nef", ".cr2", ".cr3", ".arw", ".orf", ".rw2", ".raf",
    ".ico", ".eps",
]

VIDEO_EXTENSIONS = [
    ".mp4", ".m4v", ".mov",
    ".mkv",
    ".avi",
    ".wmv",
    ".flv",
    ".webm",
    ".mts", ".m2ts", ".ts",
    ".3gp", ".3g2",
    ".mxf",
    ".ogv",
    ".rm",
    ".divx",
    ".asf",
    ".f4v",
]

OTHER_EXTENSIONS = [".gpx", ".kmz", ".kml"]

MEDIA_EXTENSIONS = sorted(set(IMAGE_EXTENSIONS + VIDEO_EXTENSIONS))

JUNK_FILENAMES = [
    "desktop.ini", ".DS_Store", "Thumbs.db",
    ".Spotlight-V100", ".Trashes", "__MACOSX",
]

JUNK_PREFIXES = ["._"]

MONTH_NAMES = {
    1: "Jänner",     2: "Februar",  3: "März",      4: "April",
    5: "Mai",        6: "Juni",     7: "Juli",      8: "August",
    9: "September", 10: "Oktober", 11: "November", 12: "Dezember",
}
WEEK_PREFIX = "KW"

# =============================================================================
# CLI helpers
# =============================================================================

def add_target_args(
    parser,
    *,
    folder_help: str = "Batch mode: operate on the contents of this folder (non-recursive by default).",
    single_help: str = "Single mode: operate on exactly this file/folder.",
    required: bool = False,
    include_recursive_flag: bool = True,
    include_hidden_flag: bool = True,
    include_version_flag: bool = True,
    include_verbose_flag: bool = True,
):
    """
    Adds a consistent set of common CLI arguments:
      - Mutually exclusive target: -s/--single <path>  OR  -b/--batch <folder>
      - --recursive (opt-in; default is non-recursive)
      - --include-hidden (off by default)
      - --version and --verbose (optional)
    """
    if include_version_flag:
        parser.add_argument(
            "-v", "--version", action="version", version=__version__,
            help="Show version and exit."
        )

    if include_verbose_flag:
        parser.add_argument(
            "--verbose", action="store_true", dest="verbose",
            help="Enable verbose (DEBUG) logging."
        )

    group = parser.add_mutually_exclusive_group(required=required)
    group.add_argument(
        "-s", "--single", dest="single", metavar="PATH",
        help=single_help,
    )
    # New name: -b/--batch replaces -f/--folder (keep hidden alias)
    group.add_argument(
        "-b", "--batch", dest="batch", metavar="FOLDER",
        help=folder_help,
    )
    # Legacy alias (hidden) for compatibility
    parser.add_argument(
        "-f", "--folder", dest="batch", metavar="FOLDER",
        help=argparse.SUPPRESS
    )

    if include_recursive_flag:
        parser.add_argument(
            "--recursive", action="store_true", default=False,
            help="Include subfolders (default is non-recursive)."
        )

    if include_hidden_flag:
        parser.add_argument(
            "--include-hidden", action="store_true", default=False,
            help="Also process hidden files and folders (ignored by default)."
        )

    return parser


def _exists_and_type(path: str, expect: str) -> bool:
    if expect == "file":
        return os.path.isfile(path)
    if expect == "folder":
        return os.path.isdir(path)
    if expect == "zip":
        return os.path.isfile(path) and path.lower().endswith(".zip")
    return os.path.exists(path)


def validate_path(path: str, expect: str = "file") -> str:
    """
    Return absolute normalized path if it exists and matches expectation.
    Valid expectations: 'file', 'folder', 'zip', 'any'
    """
    norm = os.path.abspath(os.path.expanduser(path))
    if not _exists_and_type(norm, expect if expect in {"file", "folder", "zip"} else "any"):
        raise argparse.ArgumentTypeError(f"Path is not a valid {expect}: {path}")
    return norm


def resolve_target(args, *, single_expect: str, folder_expect: str = "folder"):
    """
    Convenience to resolve the chosen target and mode from argparse results.

    Returns: (mode, path)
      mode = 'single' if args.single was provided, else 'folder'
      path = normalized absolute path (validated per expectation)
    """
    if getattr(args, "single", None):
        return "single", validate_path(args.single, single_expect)

    batch_path = getattr(args, "batch", None) or getattr(args, "folder", None)
    return "folder", validate_path(batch_path, folder_expect)

# =============================================================================
# File system helpers
# =============================================================================

def is_hidden(path: str) -> bool:
    """
    Determine if path is hidden based on any component starting with '.'.
    (Cross-platform conservative heuristic.)
    """
    parts = Path(path).parts
    return any(p.startswith(".") for p in parts if p not in (".", ".."))


def iter_dirs(root: str, *, recursive: bool = False, include_hidden: bool = False, follow_symlinks: bool = False):
    """
    Yield directories under root (excluding root). Non-recursive by default.
    """
    root = os.path.abspath(root)
    if not recursive:
        with os.scandir(root) as it:
            for e in it:
                if not e.is_dir(follow_symlinks=follow_symlinks):
                    continue
                if not include_hidden and is_hidden(e.path):
                    continue
                yield e.path
        return

    for curr, dirs, _ in os.walk(root, followlinks=follow_symlinks):
        if curr != root:
            if include_hidden or not is_hidden(curr):
                yield curr
        if not include_hidden:
            dirs[:] = [d for d in dirs if not d.startswith(".")]


def iter_files(
    root: str,
    *,
    recursive: bool = False,
    include_hidden: bool = False,
    ext_filter=None,
    follow_symlinks: bool = False,
):
    """
    Yield files under root. Non-recursive by default.

    ext_filter: None (all) or a container of lowercase extensions (e.g., {'.jpg', '.mp4'})
    """
    root = os.path.abspath(root)
    if not recursive:
        with os.scandir(root) as it:
            for e in it:
                if not e.is_file(follow_symlinks=follow_symlinks):
                    continue
                if not include_hidden and is_hidden(e.path):
                    continue
                if ext_filter:
                    ext = os.path.splitext(e.name)[1].lower()
                    if ext not in ext_filter:
                        continue
                yield e.path
        return

    for curr, dirs, files in os.walk(root, followlinks=follow_symlinks):
        if not include_hidden:
            dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in files:
            path = os.path.join(curr, name)
            if not include_hidden and is_hidden(path):
                continue
            if ext_filter:
                ext = os.path.splitext(name)[1].lower()
                if ext not in ext_filter:
                    continue
            yield path


def calculate_file_hash(path: str, algo: str = "sha256", chunk_size: int = 1024 * 1024) -> str:
    """
    Hash file contents.
    """
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def unique_path(path: str, *, style: str = "paren") -> str:
    """
    Return a unique path by appending a counter.

    style:
      - 'paren': 'name(1).ext'
      - 'underscore': 'name_1.ext'
    """
    base, ext = os.path.splitext(path)
    counter = 1
    if style == "underscore":
        candidate = f"{base}_{counter}{ext}"
        while os.path.exists(candidate):
            counter += 1
            candidate = f"{base}_{counter}{ext}"
        return candidate
    candidate = f"{base}({counter}){ext}"
    while os.path.exists(candidate):
        counter += 1
        candidate = f"{base}({counter}){ext}"
    return candidate


def is_image_ext(ext: str) -> bool:
    return ext.lower() in IMAGE_EXTENSIONS


def is_video_ext(ext: str) -> bool:
    return ext.lower() in VIDEO_EXTENSIONS


def is_media_ext(ext: str) -> bool:
    return ext.lower() in MEDIA_EXTENSIONS


def move_sidecar_files(src_file: str, target_folder: str, *, dry_run: bool = False, verbose: bool = False, sidecar_exts=None) -> int:
    """
    Move sidecar files that share the same base name as src_file into target_folder.
    Returns the count of sidecars moved.
    """
    if sidecar_exts is None:
        sidecar_exts = SIDECAR_EXTENSIONS
    count = 0
    folder = os.path.dirname(src_file)
    base, _ = os.path.splitext(os.path.basename(src_file))
    for name in os.listdir(folder):
        nbase, ext = os.path.splitext(name)
        if nbase != base:
            continue
        if ext.lower() not in sidecar_exts:
            continue
        src = os.path.join(folder, name)
        dst = os.path.join(target_folder, name)
        if os.path.abspath(src) == os.path.abspath(dst):
            continue
        if verbose:
            logging.debug("Moving sidecar %s -> %s", src, dst, extra={'target': os.path.basename(src)})
        if not dry_run:
            os.makedirs(target_folder, exist_ok=True)
            os.replace(src, dst)
        count += 1
    return count

# =============================================================================
# Run summary helper
# =============================================================================

class RunSummary(dict):
    """
    Lightweight metrics recorder for a run. Behaves like a dict with helpers.
    """
    def inc(self, key: str, n: int = 1):
        self[key] = int(self.get(key, 0)) + int(n)
        return self[key]

    def add_bytes(self, key: str, n: int = 0):
        return self.inc(key, n)

    def set(self, key: str, value):
        self[key] = value
        return value

    def emit_lines(self, lines, json_extra=None):
        """
        Emit human-friendly summary lines and one machine-readable JSON line at DEBUG level.
        """
        for ln in lines:
            logging.info(ln)
        payload = dict(self)
        if json_extra:
            payload.update(json_extra)
        try:
            logging.debug(json.dumps(payload, default=str))
        except Exception:
            logging.debug(str(payload))

# =============================================================================
# Date extraction utilities
# =============================================================================

# Build EXIF tag lookup
_EXIF_TAGS = {v: k for k, v in getattr(ExifTags, "TAGS", {}).items()}

def _parse_exif_datetime(val: str):
    # EXIF format: "YYYY:MM:DD HH:MM:SS"
    try:
        return _dt.datetime.strptime(val, "%Y:%m:%d %H:%M:%S")
    except Exception:
        return None


def _ffprobe_creation_time(path: str):
    """
    Attempt to read creation_time from ffprobe.
    Returns datetime or None.
    """
    try:
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "format_tags=creation_time:stream_tags=creation_time",
            "-of", "default=nw=1:nk=1",
            path,
        ]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, encoding="utf-8").strip()
        if not out:
            return None
        for line in out.splitlines():
            line = line.strip()
            for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
                try:
                    return _dt.datetime.strptime(line, fmt)
                except Exception:
                    continue
        try:
            return _dt.datetime.fromisoformat(out.splitlines()[0])
        except Exception:
            return None
    except Exception:
        return None


def get_dates_from_file(path: str):
    """
    Collect plausible dates for a media file.
    Returns list of tuples (source, datetime), e.g.:
      [("exif:DateTimeOriginal", dt), ("file:mtime", dt), ...]
    """
    results = []
    ext = os.path.splitext(path)[1].lower()

    # EXIF for images
    if is_image_ext(ext):
        try:
            with Image.open(path) as img:
                exif = img.getexif()
                if exif:
                    for key_name in ("DateTimeOriginal", "CreateDate", "DateTimeDigitized", "DateTime"):
                        tag = _EXIF_TAGS.get(key_name)
                        if tag is None:
                            continue
                        val = exif.get(tag)
                        if not val:
                            continue
                        if isinstance(val, bytes):
                            try:
                                val = val.decode("utf-8", "ignore")
                            except Exception:
                                continue
                        dt = _parse_exif_datetime(str(val))
                        if dt:
                            results.append((f"exif:{key_name}", dt))
        except Exception:
            pass

    # Video metadata via ffprobe
    if is_video_ext(ext):
        dt = _ffprobe_creation_time(path)
        if dt:
            results.append(("ffprobe:creation_time", dt))

    # Filesystem times (fallbacks)
    try:
        mtime = _dt.datetime.fromtimestamp(os.path.getmtime(path))
        results.append(("file:mtime", mtime))
    except Exception:
        pass
    try:
        ctime = _dt.datetime.fromtimestamp(os.path.getctime(path))
        results.append(("file:ctime", ctime))
    except Exception:
        pass

    # De-duplicate identical timestamps keeping first label
    seen = set()
    deduped = []
    for label, dt in results:
        key = dt.replace(microsecond=0)
        if key not in seen:
            seen.add(key)
            deduped.append((label, dt))
    return deduped


def select_date(candidates, mode: str = "default"):
    """
    Given a list of (label, datetime), choose one based on mode.

    modes:
      - 'default': prefer exif DateTimeOriginal/CreateDate, else ffprobe, else mtime, else ctime
      - 'newest': maximum datetime
      - 'oldest': minimum datetime

    Returns (label, datetime) or None if empty.
    """
    if not candidates:
        return None

    if mode == "newest":
        return max(candidates, key=lambda t: t[1])
    if mode == "oldest":
        return min(candidates, key=lambda t: t[1])

    order = [
        "exif:DateTimeOriginal", "exif:CreateDate", "exif:DateTimeDigitized", "exif:DateTime",
        "ffprobe:creation_time",
        "file:mtime", "file:ctime",
    ]
    best = None
    best_rank = 1e9
    for label, dt in candidates:
        try:
            rank = order.index(label)
        except ValueError:
            rank = 999
        if rank < best_rank:
            best_rank = rank
            best = (label, dt)
    return best or max(candidates, key=lambda t: t[1])

# =============================================================================
# Simple credential helper
# =============================================================================

def prompt_password(prompt: str = "Password: "):
    """
    Prompt once for a password (no confirmation).
    """
    return getpass.getpass(prompt)

# =============================================================================
# Zip/folder hashing helpers (available for converters)
# =============================================================================

def map_relative_file_hashes(root_folder: str, *, algorithm: str = "sha256"):
    """
    Return a dict: { 'relative/posix/path': hexdigest } for all files under root_folder (recursive).
    Paths use '/' as separator for stable zip comparisons.
    """
    mapping = {}
    root_folder = os.path.abspath(root_folder)
    for curr, dirs, files in os.walk(root_folder):
        for name in files:
            fpath = os.path.join(curr, name)
            rel = os.path.relpath(fpath, root_folder).replace("\\", "/")
            mapping[rel] = calculate_file_hash(fpath, algo=algorithm)
    return mapping

__all__ = [
    "__version__",
    "SIDECAR_EXTENSIONS", "IMAGE_EXTENSIONS", "VIDEO_EXTENSIONS", "OTHER_EXTENSIONS",
    "MEDIA_EXTENSIONS", "JUNK_FILENAMES", "JUNK_PREFIXES",
    "MONTH_NAMES", "WEEK_PREFIX",
    "configure_logging", "RunSummary",
    "add_target_args", "validate_path", "resolve_target",
    "is_hidden", "iter_files", "iter_dirs", "calculate_file_hash", "unique_path",
    "is_image_ext", "is_video_ext", "is_media_ext", "move_sidecar_files",
    "get_dates_from_file", "select_date",
    "map_relative_file_hashes",
    "prompt_password",
]
