import os
import argparse
import logging
import shutil
from archivetools import (
    __version__,
    SIDECAR_EXTENSIONS,
    JUNK_FILENAMES,
    JUNK_PREFIXES,
    RunSummary,
    add_target_args,
    resolve_target,
)

def is_empty_file(path):
    try:
        return os.path.getsize(path) == 0
    except OSError:
        return False

def is_junk_file(name):
    if name in JUNK_FILENAMES:
        return True
    for prefix in JUNK_PREFIXES:
        if name.startswith(prefix):
            return True
    return False

def _folder_size_bytes(path):
    total = 0
    for root, _, files in os.walk(path):
        for n in files:
            fp = os.path.join(root, n)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total

def cleanup_files(folder, verbose=False, summary=None):
    """
    Batch mode (-f): remove junk files/folders, empty sidecars, then empty folders.
    """
    removed_files = []
    removed_folders = []
    s = summary

    for root, dirs, files in os.walk(folder, topdown=True):
        # ignore hidden
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        files = [f for f in files if not f.startswith('.')]

        # files
        for name in files:
            file_path = os.path.join(root, name)
            ext = os.path.splitext(name)[1].lower()

            if ext in SIDECAR_EXTENSIONS and is_empty_file(file_path):
                try:
                    size = 0
                    try:
                        size = os.path.getsize(file_path)
                    except OSError:
                        pass
                    if verbose:
                        logging.debug(f"Deleting empty sidecar file: {file_path}", extra={'target': name})
                    os.remove(file_path)
                    removed_files.append(file_path)
                    if s:
                        s.inc('files_removed'); s.inc('empty_sidecars_removed'); s.add_bytes('freed_bytes', size)
                    logging.info("Deleted empty sidecar file.", extra={'target': name})
                except Exception as e:
                    logging.error(f"Error deleting file: {e}", extra={'target': name})
                    if s: s.inc('errors')
                continue

            if is_junk_file(name):
                try:
                    size = 0
                    try:
                        size = os.path.getsize(file_path)
                    except OSError:
                        pass
                    if verbose:
                        logging.debug(f"Deleting junk file: {file_path}", extra={'target': name})
                    os.remove(file_path)
                    removed_files.append(file_path)
                    if s:
                        s.inc('files_removed'); s.inc('junk_files_removed'); s.add_bytes('freed_bytes', size)
                    logging.info("Deleted junk file.", extra={'target': name})
                except Exception as e:
                    logging.error(f"Error deleting file: {e}", extra={'target': name})
                    if s: s.inc('errors')

        # junk folders
        for d in dirs[:]:
            dir_path = os.path.join(root, d)
            if is_junk_file(d):
                try:
                    size = _folder_size_bytes(dir_path)
                    if verbose:
                        logging.debug(f"Deleting junk folder: {dir_path}", extra={'target': d})
                    shutil.rmtree(dir_path)
                    removed_folders.append(dir_path)
                    if s:
                        s.inc('folders_removed'); s.inc('junk_folders_removed'); s.add_bytes('freed_bytes', size)
                    logging.info("Deleted junk folder.", extra={'target': d})
                    dirs.remove(d)
                except Exception as e:
                    logging.error(f"Error deleting folder: {e}", extra={'target': d})
                    if s: s.inc('errors')

    # empty folders (bottom-up)
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

def clean_single_file(file_path, verbose=False, summary=None):
    """
    Single mode (-s): evaluate exactly one file; delete if junk or empty sidecar.
    """
    s = summary
    name = os.path.basename(file_path)
    if not os.path.isfile(file_path):
        logging.error("The specified path is not a file.", extra={'target': name})
        if s: s.inc('errors')
        return

    ext = os.path.splitext(name)[1].lower()

    # empty sidecar?
    if ext in SIDECAR_EXTENSIONS and is_empty_file(file_path):
        try:
            sz = 0
            try:
                sz = os.path.getsize(file_path)
            except OSError:
                pass
            if verbose:
                logging.debug(f"Deleting empty sidecar file: {file_path}", extra={'target': name})
            os.remove(file_path)
            if s:
                s.inc('files_removed'); s.inc('empty_sidecars_removed'); s.add_bytes('freed_bytes', sz)
            logging.info("Deleted empty sidecar file.", extra={'target': name})
        except Exception as e:
            logging.error(f"Error deleting file: {e}", extra={'target': name})
            if s: s.inc('errors')
        return

    # junk file?
    if is_junk_file(name):
        try:
            sz = 0
            try:
                sz = os.path.getsize(file_path)
            except OSError:
                pass
            if verbose:
                logging.debug(f"Deleting junk file: {file_path}", extra={'target': name})
            os.remove(file_path)
            if s:
                s.inc('files_removed'); s.inc('junk_files_removed'); s.add_bytes('freed_bytes', sz)
            logging.info("Deleted junk file.", extra={'target': name})
        except Exception as e:
            logging.error(f"Error deleting file: {e}", extra={'target': name})
            if s: s.inc('errors')
        return

    # not junk / not empty sidecar -> leave as-is
    if verbose:
        logging.debug("No cleanup action for file.", extra={'target': name})
    logging.info("No cleanup needed for this file.", extra={'target': name})


def main():
    parser = argparse.ArgumentParser(
        description="Deletes empty sidecar files, unnecessary junk files/folders, and empty folders. Use -f for whole-folder cleanup or -s for a single file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('-v', '--version', action='version', version=f'ArchiveTools {__version__}')
    add_target_args(
        parser,
        folder_help="Batch mode: clean the contents of this folder (and subfolders)",
        single_help="Single mode: evaluate this one file for cleanup",
        required=True,
    )
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    args = parser.parse_args()

    logging.getLogger().setLevel(logging.DEBUG if args.verbose else logging.INFO)

    # -s expects a FILE, -f expects a FOLDER
    mode_sel, target = resolve_target(args, single_expect='file', folder_expect='folder')

    # Summary tracker
    s = RunSummary()

    if mode_sel == 'single':
        clean_single_file(target, verbose=args.verbose, summary=s)
    else:
        cleanup_files(target, verbose=args.verbose, summary=s)

    # Emit end-of-run summary
    files_removed = s['files_removed'] or 0
    junk_files_removed = s['junk_files_removed'] or 0
    empty_sidecars_removed = s['empty_sidecars_removed'] or 0
    folders_removed = s['folders_removed'] or 0
    junk_folders_removed = s['junk_folders_removed'] or 0
    empty_folders_removed = s['empty_folders_removed'] or 0
    freed_h = s.hbytes('freed_bytes')
    errors = s['errors'] or 0

    if mode_sel == 'single':
        action_line = f"Checked one file. {'Removed it' if files_removed else 'No removal needed'}."
    else:
        action_line = "Completed folder cleanup."

    line1 = (
        f"{action_line} Removed {files_removed} file(s) "
        f"({junk_files_removed} junk, {empty_sidecars_removed} empty sidecars) and "
        f"{folders_removed} folder(s) ({junk_folders_removed} junk, {empty_folders_removed} empty) "
        f"in {s.duration_hms}."
    )
    line2 = f"Freed {freed_h}. Errors: {errors}."

    s.emit_lines([line1, line2], json_extra={
        'target_mode': mode_sel,
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
