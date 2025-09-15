import os
import argparse
import logging
import subprocess
from PIL import Image

from archivetools import (
    __version__,
    MEDIA_EXTENSIONS,
    RunSummary,
    add_target_args,
    resolve_target,
)

# -----------------------------
# low-level checks
# -----------------------------

def check_image_file(path):
    try:
        with Image.open(path) as img:
            img.verify()  # does not decode full image, but catches many corruptions
        return True, ""
    except Exception as e:
        return False, str(e)


def check_video_file(path):
    """
    Use ffprobe to read duration (as a simple "is this decodable" check).
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return False, result.stderr.strip() or "ffprobe non-zero exit"
        if not result.stdout.strip():
            return False, "ffprobe could not read duration (possible corruption)"
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "ffprobe timeout"
    except Exception as e:
        return False, str(e)


# -----------------------------
# batch (folder) mode
# -----------------------------

def check_media_files(folder, verbose=False, summary=None):
    s = summary
    for root, _, files in os.walk(folder):
        all_ok = True
        if files:
            if s: s.inc("folders_scanned")
        corrupt_files = []

        for name in files:
            ext = os.path.splitext(name)[1].lower()
            file_path = os.path.join(root, name)

            if ext not in MEDIA_EXTENSIONS:
                continue

            if s: s.inc("scanned")

            # choose checker
            if ext in ['.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif', '.webp', '.heic', '.heif', '.raw', '.dng', '.cr2', '.arw', '.orf', '.rw2', '.ico']:
                ok, msg = check_image_file(file_path)
            elif ext in ['.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.m4v', '.3gp', '.mpeg', '.mpg', '.mts', '.ts', '.vob', '.mxf', '.ogv', '.asf', '.m2ts', '.webm']:
                ok, msg = check_video_file(file_path)
            else:
                # generic quick read for anything else still considered media by your set
                try:
                    with open(file_path, "rb") as f:
                        f.read(512)
                    ok, msg = True, ""
                except Exception as e:
                    ok, msg = False, str(e)

            if not ok:
                all_ok = False
                corrupt_files.append((name, msg))
                logging.error(f"Corruption detected: {msg}", extra={'target': name})
                if s:
                    s.inc('corrupt')
                    if 'timeout' in msg.lower():
                        s.inc('timeouts')
                    if len(getattr(s, 'notes', [])) < 3:
                        s.note(f"{name}: {msg}")
            else:
                if s: s.inc('ok')
                if verbose:
                    logging.info("File OK.", extra={'target': name})

        if not files:
            continue

        if all_ok and not verbose:
            logging.info("All media files OK.", extra={'target': os.path.relpath(root, folder)})


# -----------------------------
# single (file) mode
# -----------------------------

def check_single_file(file_path, verbose=False, summary=None):
    s = summary
    name = os.path.basename(file_path)
    if not os.path.isfile(file_path):
        logging.error("The specified path is not a file.", extra={'target': name})
        if s: s.inc('errors')
        return

    ext = os.path.splitext(name)[1].lower()

    if ext not in MEDIA_EXTENSIONS:
        logging.info("Not a supported media file. Skipping.", extra={'target': name})
        return

    if s: s.inc('scanned')

    if ext in ['.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif', '.webp', '.heic', '.heif', '.raw', '.dng', '.cr2', '.arw', '.orf', '.rw2', '.ico']:
        ok, msg = check_image_file(file_path)
    elif ext in ['.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.m4v', '.3gp', '.mpeg', '.mpg', '.mts', '.ts', '.vob', '.mxf', '.ogv', '.asf', '.m2ts', '.webm']:
        ok, msg = check_video_file(file_path)
    else:
        try:
            with open(file_path, "rb") as f:
                f.read(512)
            ok, msg = True, ""
        except Exception as e:
            ok, msg = False, str(e)

    if ok:
        if s: s.inc('ok')
        logging.info("File OK.", extra={'target': name})
    else:
        if s: s.inc('corrupt')
        if 'timeout' in msg.lower() and s: s.inc('timeouts')
        logging.error(f"Corruption detected: {msg}", extra={'target': name})
        if s and len(getattr(s, 'notes', [])) < 3:
            s.note(f"{name}: {msg}")


# -----------------------------
# CLI
# -----------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Checks media files for basic corruption. Use -f/--folder to scan a folder tree, or -s/--single to check one file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('-v', '--version', action='version', version=f'ArchiveTools {__version__}')
    add_target_args(
        parser,
        folder_help="Batch mode: scan all media in this folder (recursively)",
        single_help="Single mode: check exactly this file",
        required=True,
    )
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    args = parser.parse_args()

    logging.getLogger().setLevel(logging.DEBUG if args.verbose else logging.INFO)

    # -s expects a FILE, -f expects a FOLDER
    mode_sel, target = resolve_target(args, single_expect='file', folder_expect='folder')

    # summary tracker
    s = RunSummary()

    if mode_sel == 'single':
        check_single_file(target, verbose=args.verbose, summary=s)
    else:
        check_media_files(target, verbose=args.verbose, summary=s)

    # Emit end-of-run summary
    scanned = s['scanned'] or 0
    ok = s['ok'] or 0
    corrupt = s['corrupt'] or 0
    timeouts = s['timeouts'] or 0

    pct = (100.0 * corrupt / scanned) if scanned else 0.0
    line1 = f"Scanned {scanned} media files in {s.duration_hms} — {ok} OK, {corrupt} corrupt ({pct:.2f}%)."
    line2 = f"Timeouts: {timeouts}." if timeouts else None

    examples = getattr(s, 'notes', [])[:3]
    line3 = ("Examples: " + "; ".join(examples)) if corrupt and examples else None

    lines = [line1]
    if line2: lines.append(line2)
    if line3: lines.append(line3)

    s.emit_lines(lines, json_extra={
        'target_mode': mode_sel,
        'scanned': scanned, 'ok': ok, 'corrupt': corrupt, 'timeouts': timeouts
    })


if __name__ == "__main__":
    main()
