import os
import argparse
import logging
import shutil
from archivetools import __version__, SIDECAR_EXTENSIONS, JUNK_FILENAMES, JUNK_PREFIXES, RunSummary

def is_empty_file(path):
    return os.path.getsize(path) == 0

def is_junk_file(filename):
    if filename in JUNK_FILENAMES:
        return True
    for prefix in JUNK_PREFIXES:
        if filename.startswith(prefix):
            return True
    return False

def _folder_size_bytes(path):
    total = 0
    for root, _, files in os.walk(path):
        for name in files:
            fp = os.path.join(root, name)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total

def cleanup_files(folder, verbose=False, summary=None):
    removed_files = []
    removed_folders = []
    s = summary  # optional RunSummary

    # First pass: Remove junk and empty sidecar files, junk folders
    for root, dirs, files in os.walk(folder, topdown=True):
        # ignore hidden
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        files = [f for f in files if not f.startswith('.')]

        for name in files:
            file_path = os.path.join(root, name)
            ext = os.path.splitext(name)[1].lower()
            if ext in SIDECAR_EXTENSIONS and is_empty_file(file_path):
                try:
                    if verbose:
                        logging.debug(f"Deleting empty sidecar file: {file_path}", extra={'target': name})
                    size = 0
                    try:
                        size = os.path.getsize(file_path)
                    except OSError:
                        pass
                    os.remove(file_path)
                    removed_files.append(file_path)
                    if s:
                        s.inc('files_removed'); s.inc('empty_sidecars_removed'); s.add_bytes('freed_bytes', size)
                    logging.info("Deleted empty sidecar file.", extra={'target': name})
                except Exception as e:
                    logging.error(f"Error deleting file: {e}", extra={'target': name})
                    if s: s.inc('errors')
            elif is_junk_file(name):
                try:
                    if verbose:
                        logging.debug(f"Deleting junk file: {file_path}", extra={'target': name})
                    size = 0
                    try:
                        size = os.path.getsize(file_path)
                    except OSError:
                        pass
                    os.remove(file_path)
                    removed_files.append(file_path)
                    if s:
                        s.inc('files_removed'); s.inc('junk_files_removed'); s.add_bytes('freed_bytes', size)
                    logging.info("Deleted junk file.", extra={'target': name})
                except Exception as e:
                    logging.error(f"Error deleting file: {e}", extra={'target': name})
                    if s: s.inc('errors')

        for d in dirs[:]:
            dir_path = os.path.join(root, d)
            if is_junk_file(d):
                try:
                    if verbose:
                        logging.debug(f"Deleting junk folder: {dir_path}", extra={'target': d})
                    # estimate size freed by removing junk folder contents
                    size = _folder_size_bytes(dir_path)
                    shutil.rmtree(dir_path)
                    removed_folders.append(dir_path)
                    if s:
                        s.inc('folders_removed'); s.inc('junk_folders_removed'); s.add_bytes('freed_bytes', size)
                    logging.info("Deleted junk folder.", extra={'target': d})
                    dirs.remove(d)
                except Exception as e:
                    logging.error(f"Error deleting folder: {e}", extra={'target': d})
                    if s: s.inc('errors')

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
                    if s:
                        s.inc('folders_removed'); s.inc('empty_folders_removed')
                    logging.info("Deleted empty folder.", extra={'target': d})
            except Exception as e:
                logging.error(f"Error deleting folder: {e}", extra={'target': d})
                if s: s.inc('errors')

    if verbose:
        logging.debug(
            f"Cleanup finished. Removed {len(removed_files)} files and {len(removed_folders)} folders.",
            extra={'target': os.path.basename(folder)}
        )

def main():
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

    # Summary tracker
    s = RunSummary()

    cleanup_files(args.folder, verbose=args.verbose, summary=s)

    # Emit end-of-run summary
    files_removed = s['files_removed'] or 0
    junk_files_removed = s['junk_files_removed'] or 0
    empty_sidecars_removed = s['empty_sidecars_removed'] or 0
    folders_removed = s['folders_removed'] or 0
    junk_folders_removed = s['junk_folders_removed'] or 0
    empty_folders_removed = s['empty_folders_removed'] or 0
    freed_h = s.hbytes('freed_bytes')
    errors = s['errors'] or 0

    line1 = (
        f"Removed {files_removed} file(s) "
        f"({junk_files_removed} junk, {empty_sidecars_removed} empty sidecars) and "
        f"{folders_removed} folder(s) ({junk_folders_removed} junk, {empty_folders_removed} empty) "
        f"in {s.duration_hms}."
    )
    line2 = f"Freed {freed_h}. Errors: {errors}."

    s.emit_lines([line1, line2], json_extra={
        'files_removed': files_removed,
        'junk_files_removed': junk_files_removed,
        'empty_sidecars_removed': empty_sidecars_removed,
        'folders_removed': folders_removed,
        'junk_folders_removed': junk_folders_removed,
        'empty_folders_removed': empty_folders_removed,
        'freed_bytes': s['freed_bytes'] or 0,
        'errors': errors,
    })

if __name__ == "__main__":
    main()
