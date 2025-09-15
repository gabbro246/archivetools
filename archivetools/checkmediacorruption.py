import os
import argparse
import logging
from archivetools import __version__, MEDIA_EXTENSIONS, RunSummary
from PIL import Image
import subprocess

def check_image_file(path):
    try:
        with Image.open(path) as img:
            img.verify()
        return True, ""
    except Exception as e:
        return False, str(e)

def check_video_file(path):
    # Try a minimal ffprobe read to ensure the file is decodable and has duration
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            return False, result.stderr.strip()
        if not result.stdout.strip():
            return False, "ffprobe could not read duration (possible corruption)"
        return True, ""
    except Exception as e:
        return False, str(e)

def check_media_files(folder, verbose=False, summary=None):
    s = summary  # summary tracker (optional)
    for root, _, files in os.walk(folder):
        all_ok = True
        if files:
            if s: s.inc("folders_scanned")
        corrupt_files = []
        for name in files:
            ext = os.path.splitext(name)[1].lower()
            file_path = os.path.join(root, name)
            if ext in MEDIA_EXTENSIONS:
                if s: s.inc("scanned")
                if ext in ['.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif', '.webp', '.heic', '.heif', '.raw', '.dng', '.cr2', '.arw', '.orf', '.rw2', '.ico', '.eps', '.ai', '.indd']:
                    ok, msg = check_image_file(file_path)
                elif ext in ['.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.m4v', '.3gp', '.mpeg', '.mpg', '.m4v', '.mts', '.ts', '.vob', '.mxf', '.ogv', '.rm', '.divx', '.asf', '.f4v', '.m2ts', '.webm']:
                    ok, msg = check_video_file(file_path)
                else:
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
                        # keep a few sample notes
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

def main():
    parser = argparse.ArgumentParser(
        description="Checks all media files in a folder and its subfolders. Only logs OK for whole subfolders unless --verbose is set.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('-v', '--version', action='version', version=f'ArchiveTools {__version__}')
    parser.add_argument('-f', '--folder', required=True, help='Path to the folder to process')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)

    # summary tracker
    s = RunSummary()
    check_media_files(args.folder, verbose=args.verbose, summary=s)

    scanned = s['scanned'] or 0
    ok = s['ok'] or 0
    corrupt = s['corrupt'] or 0
    timeouts = s['timeouts'] or 0

    pct = (100.0 * corrupt / scanned) if scanned else 0.0
    line1 = f"Scanned {scanned} media files in {s.duration_hms} — {ok} OK, {corrupt} corrupt ({pct:.2f}%)."
    line2 = f"Timeouts: {timeouts}." if timeouts else None

    # include up to 3 example corrupt files
    examples = getattr(s, 'notes', [])[:3]
    line3 = None
    if corrupt and examples:
        line3 = "Examples: " + "; ".join(examples)

    lines = [line1]
    if line2: lines.append(line2)
    if line3: lines.append(line3)

    s.emit_lines(lines, json_extra={
        'scanned': scanned, 'ok': ok, 'corrupt': corrupt, 'timeouts': timeouts
    })

if __name__ == "__main__":
    main()
