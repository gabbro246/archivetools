import os
import argparse
import logging
import shutil
from archivetoolscore import __version__, SIDECAR_EXTENSIONS, JUNK_FILENAMES, JUNK_PREFIXES

def is_empty_file(path):
    return os.path.getsize(path) == 0

def is_junk_file(filename):
    if filename in JUNK_FILENAMES:
        return True
    for prefix in JUNK_PREFIXES:
        if filename.startswith(prefix):
            return True
    return False

def cleanup_files(folder, verbose=False):
    removed_files = []
    removed_folders = []
    # First pass: Remove junk and empty sidecar files, junk folders
    for root, dirs, files in os.walk(folder, topdown=True):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        files = [f for f in files if not f.startswith('.')]
        for name in files:
            file_path = os.path.join(root, name)
            ext = os.path.splitext(name)[1].lower()
            if ext in SIDECAR_EXTENSIONS and is_empty_file(file_path):
                try:
                    if verbose:
                        logging.debug(f"Deleting empty sidecar file: {file_path}", extra={'target': name})
                    os.remove(file_path)
                    removed_files.append(file_path)
                    logging.info("Deleted empty sidecar file.", extra={'target': name})
                except Exception as e:
                    logging.error(f"Error deleting file: {e}", extra={'target': name})
            elif is_junk_file(name):
                try:
                    if verbose:
                        logging.debug(f"Deleting junk file: {file_path}", extra={'target': name})
                    os.remove(file_path)
                    removed_files.append(file_path)
                    logging.info("Deleted junk file.", extra={'target': name})
                except Exception as e:
                    logging.error(f"Error deleting file: {e}", extra={'target': name})
        for d in dirs[:]:
            dir_path = os.path.join(root, d)
            if is_junk_file(d):
                try:
                    if verbose:
                        logging.debug(f"Deleting junk folder: {dir_path}", extra={'target': d})
                    shutil.rmtree(dir_path)
                    removed_folders.append(dir_path)
                    logging.info("Deleted junk folder.", extra={'target': d})
                    dirs.remove(d)
                except Exception as e:
                    logging.error(f"Error deleting folder: {e}", extra={'target': d})
    # Second pass: Remove all empty folders (bottom-up)
    for root, dirs, _ in os.walk(folder, topdown=False):
        for d in dirs:
            dir_path = os.path.join(root, d)
            try:
                if not os.listdir(dir_path):
                    if verbose:
                        logging.debug(f"Deleting empty folder: {dir_path}", extra={'target': d})
                    os.rmdir(dir_path)
                    removed_folders.append(dir_path)
                    logging.info("Deleted empty folder.", extra={'target': d})
            except Exception as e:
                logging.error(f"Error deleting folder: {e}", extra={'target': d})
    if verbose:
        logging.debug(
            f"Cleanup finished. Removed {len(removed_files)} files and {len(removed_folders)} folders.",
            extra={'target': os.path.basename(folder)}
        )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Deletes all empty sidecar files, unnecessary junk files/folders (like .DS_Store, desktop.ini, NCFLsDat, AppleDouble, __MACOSX, etc.), and all empty folders in the target folder and its subfolders. Extensions and names are defined in _atcore.py.",
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

    cleanup_files(args.folder, verbose=args.verbose)
