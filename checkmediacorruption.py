import os
import argparse
import logging
from archivetoolscore import __version__, MEDIA_EXTENSIONS
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
    # Use ffprobe for video file integrity check
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

def check_media_files(folder, verbose=False):
    for root, _, files in os.walk(folder):
        all_ok = True
        corrupt_files = []
        for name in files:
            ext = os.path.splitext(name)[1].lower()
            file_path = os.path.join(root, name)
            if ext in MEDIA_EXTENSIONS:
                if ext in ['.jpg', '.jpeg', '.png', '.tiff', '.tif', '.psd', '.heic', '.nef', '.gif', '.bmp', '.dng', '.raw', '.svg', '.webp', '.cr2', '.arw', '.orf', '.rw2', '.ico', '.eps', '.ai', '.indd']:
                    ok, msg = check_image_file(file_path)
                elif ext in ['.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.webm', '.3gp', '.mpeg', '.mpg', '.m4v', '.mts', '.ts', '.vob', '.mxf', '.ogv', '.rm', '.divx', '.asf', '.f4v', '.m2ts', '.nev']:
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
                elif verbose:
                    logging.info("File OK.", extra={'target': name})
        if not files:
            continue
        if all_ok and not verbose:
            logging.info("All media files OK.", extra={'target': os.path.relpath(root, folder)})

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Checks all media files in a folder and its subfolders for corruption. Logs all errors. Only logs OK for whole subfolders unless --verbose is set.",
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

    check_media_files(args.folder, verbose=args.verbose)
