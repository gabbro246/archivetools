import os
import argparse
import logging
import shutil

from archivetools import (
    configure_logging,
    add_target_args,
    resolve_target,
    iter_files,
    iter_dirs,
    is_hidden,
    SIDECAR_EXTENSIONS,
    JUNK_FILENAMES,
    JUNK_PREFIXES,
    RunSummary,
)

# ------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------

def _is_empty_file(path: str) -> bool:
    try:
        return os.path.getsize(path) == 0
    except OSError:
        return False


def _delete_file(path: str, *, dry_run: bool, verbose: bool, summary: RunSummary | None, reason_key: str, reason_label: str) -> None:
    name = os.path.basename(path)
    try:
        size = os.path.getsize(path)
    except OSError:
        size = 0

    if verbose:
        logging.debug(
            "%s %s",
            "Would delete" if dry_run else "Deleting",
            path,
            extra={"target": name},
        )
    if not dry_run:
        try:
            os.remove(path)
        except Exception as e:
            logging.error("Failed to delete %s: %s", path, e, extra={"target": name})
            if summary:
                summary.inc("errors")
            return
    logging.info("Removed %s", reason_label, extra={"target": name})
    if summary:
        summary.inc("files_removed")
        summary.inc(reason_key)
        summary.add_bytes("freed_bytes", size)


def _delete_folder(path: str, *, dry_run: bool, verbose: bool, summary: RunSummary | None, reason_key: str, reason_label: str) -> None:
    name = os.path.basename(path)
    if verbose:
        logging.debug(
            "%s folder %s",
            "Would remove" if dry_run else "Removing",
            path,
            extra={"target": name},
        )
    if not dry_run:
        try:
            shutil.rmtree(path)
        except Exception as e:
            logging.error("Failed to remove folder %s: %s", path, e, extra={"target": name})
            if summary:
                summary.inc("errors")
            return
    logging.info("Removed %s", reason_label, extra={"target": name})
    if summary:
        summary.inc("folders_removed")
        summary.inc(reason_key)


def _cleanup_junk_files(root: str, *, recursive: bool, include_hidden: bool, dry_run: bool, verbose: bool, summary: RunSummary | None) -> None:
    """
    Remove known junk files (e.g., .DS_Store, desktop.ini, Thumbs.db) and resource-fork
    '._' prefixed files. Honors include_hidden.
    """
    junk_names = set(JUNK_FILENAMES)
    prefixes = tuple(JUNK_PREFIXES)

    # Collect files (non-recursive by default)
    for path in iter_files(root, recursive=recursive, include_hidden=include_hidden):
        name = os.path.basename(path)
        if name in junk_names or name.startswith(prefixes):
            _delete_file(path, dry_run=dry_run, verbose=verbose, summary=summary, reason_key="junk_files_removed", reason_label="junk file")


def _cleanup_empty_sidecars(root: str, *, recursive: bool, include_hidden: bool, dry_run: bool, verbose: bool, summary: RunSummary | None) -> None:
    """
    Remove empty sidecar files (size == 0) based on SIDECAR_EXTENSIONS.
    """
    sidecars = set(SIDECAR_EXTENSIONS)
    for path in iter_files(root, recursive=recursive, include_hidden=include_hidden):
        _, ext = os.path.splitext(path)
        if ext.lower() in sidecars and _is_empty_file(path):
            _delete_file(path, dry_run=dry_run, verbose=verbose, summary=summary, reason_key="empty_sidecars_removed", reason_label="empty sidecar")


def _cleanup_junk_folders(root: str, *, recursive: bool, include_hidden: bool, dry_run: bool, verbose: bool, summary: RunSummary | None) -> None:
    """
    Remove folders that are known junk by name (e.g., '__MACOSX', '.Trashes', '.Spotlight-V100').
    Honors include_hidden.
    """
    junk_names = set(JUNK_FILENAMES)
    prefixes = tuple(JUNK_PREFIXES)
    # Choose directory iteration approach
    if recursive:
        dirs = list(iter_dirs(root, recursive=True, include_hidden=include_hidden))
    else:
        dirs = list(iter_dirs(root, recursive=False, include_hidden=include_hidden))

    # Remove junk-named or junk-prefixed folders. Remove deepest first to minimize failures.
    dirs.sort(key=lambda p: p.count(os.sep), reverse=True)
    for d in dirs:
        name = os.path.basename(d)
        if name in junk_names or name.startswith(prefixes):
            _delete_folder(d, dry_run=dry_run, verbose=verbose, summary=summary, reason_key="junk_folders_removed", reason_label="junk folder")


def _remove_empty_dirs(root: str, *, recursive: bool, include_hidden: bool, dry_run: bool, verbose: bool, summary: RunSummary | None) -> None:
    """
    Remove empty directories.
    - Non-recursive: only consider immediate subfolders of root.
    - Recursive: walk bottom-up and remove any empty descendant directories.
    """
    if not recursive:
        # Only immediate children
        for d in iter_dirs(root, recursive=False, include_hidden=include_hidden):
            try:
                if not os.listdir(d):
                    _delete_folder(d, dry_run=dry_run, verbose=verbose, summary=summary, reason_key="empty_folders_removed", reason_label="empty folder")
            except FileNotFoundError:
                continue
            except Exception as e:
                logging.error("Failed to check folder %s: %s", d, e, extra={"target": os.path.basename(d)})
                if summary:
                    summary.inc("errors")
        return

    # Recursive: bottom-up traversal
    for curr, dirs, files in os.walk(root, topdown=False):
        if os.path.abspath(curr) == os.path.abspath(root):
            continue  # don't remove root
        if not include_hidden and is_hidden(curr):
            continue
        try:
            if not os.listdir(curr):
                _delete_folder(curr, dry_run=dry_run, verbose=verbose, summary=summary, reason_key="empty_folders_removed", reason_label="empty folder")
        except FileNotFoundError:
            continue
        except Exception as e:
            logging.error("Failed to remove empty folder %s: %s", curr, e, extra={"target": os.path.basename(curr)})
            if summary:
                summary.inc("errors")


def _batch_mode(root: str, *, recursive: bool, include_hidden: bool, dry_run: bool, verbose: bool, summary: RunSummary | None) -> None:
    """
    Clean up a folder: remove junk files, empty sidecars, junk folders, and empty folders.
    """
    # Order: junk files -> empty sidecars -> junk folders -> empty folders
    _cleanup_junk_files(root, recursive=recursive, include_hidden=include_hidden, dry_run=dry_run, verbose=verbose, summary=summary)
    _cleanup_empty_sidecars(root, recursive=recursive, include_hidden=include_hidden, dry_run=dry_run, verbose=verbose, summary=summary)
    _cleanup_junk_folders(root, recursive=recursive, include_hidden=include_hidden, dry_run=dry_run, verbose=verbose, summary=summary)
    _remove_empty_dirs(root, recursive=recursive, include_hidden=include_hidden, dry_run=dry_run, verbose=verbose, summary=summary)


def _single_mode(folder: str, *, include_hidden: bool, dry_run: bool, verbose: bool, summary: RunSummary | None) -> None:
    """
    Single mode: clean THIS folder only (non-recursive), then try to remove it if it becomes empty.
    """
    _cleanup_junk_files(folder, recursive=False, include_hidden=include_hidden, dry_run=dry_run, verbose=verbose, summary=summary)
    _cleanup_empty_sidecars(folder, recursive=False, include_hidden=include_hidden, dry_run=dry_run, verbose=verbose, summary=summary)
    _cleanup_junk_folders(folder, recursive=False, include_hidden=include_hidden, dry_run=dry_run, verbose=verbose, summary=summary)
    _remove_empty_dirs(folder, recursive=False, include_hidden=include_hidden, dry_run=dry_run, verbose=verbose, summary=summary)

    # If the folder itself is now empty, remove it (nice cleanup when called on junk folders directly)
    try:
        if not os.listdir(folder):
            _delete_folder(folder, dry_run=dry_run, verbose=verbose, summary=summary, reason_key="empty_folders_removed", reason_label="empty folder")
    except Exception:
        pass


# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Remove junk files (e.g., .DS_Store, Thumbs.db), empty sidecars, junk-named folders (e.g., __MACOSX), "
            "and empty directories. Non-recursive by default — use --recursive to include subfolders. "
            "Hidden files are ignored by default; pass --include-hidden to also clean hidden items."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    add_target_args(
        parser,
        folder_help="Batch mode: clean this folder (non-recursive by default; use --recursive to include subfolders).",
        single_help="Single mode: clean this specific folder only (non-recursive).",
        required=True,
    )

    parser.add_argument("--dry-run", action="store_true", help="Show what would be removed without deleting anything")

    args = parser.parse_args()
    configure_logging(getattr(args, "verbose", False))

    mode_sel, target = resolve_target(args, single_expect="folder", folder_expect="folder")

    s = RunSummary()
    s.set("dry_run", bool(getattr(args, "dry_run", False)))
    s.set("recursive", bool(getattr(args, "recursive", False)))
    s.set("include_hidden", bool(getattr(args, "include_hidden", False)))

    if mode_sel == "single":
        _single_mode(
            target,
            include_hidden=bool(getattr(args, "include_hidden", False)),
            dry_run=bool(getattr(args, "dry_run", False)),
            verbose=getattr(args, "verbose", False),
            summary=s,
        )
    else:
        _batch_mode(
            target,
            recursive=bool(getattr(args, "recursive", False)),
            include_hidden=bool(getattr(args, "include_hidden", False)),
            dry_run=bool(getattr(args, "dry_run", False)),
            verbose=getattr(args, "verbose", False),
            summary=s,
        )

    files_removed = s.get("files_removed", 0) or 0
    junk_files_removed = s.get("junk_files_removed", 0) or 0
    empty_sidecars_removed = s.get("empty_sidecars_removed", 0) or 0
    folders_removed = s.get("folders_removed", 0) or 0
    junk_folders_removed = s.get("junk_folders_removed", 0) or 0
    empty_folders_removed = s.get("empty_folders_removed", 0) or 0
    errors = s.get("errors", 0) or 0

    line1 = (
        f"Removed {files_removed} file(s) "
        f"(junk: {junk_files_removed}, empty sidecars: {empty_sidecars_removed}); "
        f"Removed {folders_removed} folder(s) "
        f"(junk: {junk_folders_removed}, empty: {empty_folders_removed})."
    )
    line2 = (
        f"Freed {s.get('freed_bytes', 0) or 0} bytes. "
        f"Recursive: {s['recursive']}. Include hidden: {s['include_hidden']}. Dry-run: {s['dry_run']}. "
        f"Errors: {errors}."
    )

    s.emit_lines([line1, line2], json_extra={
        "target_mode": mode_sel,
        "files_removed": files_removed,
        "junk_files_removed": junk_files_removed,
        "empty_sidecars_removed": empty_sidecars_removed,
        "folders_removed": folders_removed,
        "junk_folders_removed": junk_folders_removed,
        "empty_folders_removed": empty_folders_removed,
        "freed_bytes": s.get("freed_bytes", 0) or 0,
        "errors": errors,
        "recursive": s["recursive"],
        "include_hidden": s["include_hidden"],
        "dry_run": s["dry_run"],
        "target": target,
    })


if __name__ == "__main__":
    main()
