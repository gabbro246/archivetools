import os
import shutil
import argparse
import logging

from archivetools import (
    configure_logging,
    add_target_args,
    resolve_target,
    iter_files,
    iter_dirs,
    is_hidden,
    unique_path,
    RunSummary,
)

# ------------------------------------------------------------
# internal helpers
# ------------------------------------------------------------

def _move_one(src: str, dst_folder: str, *, rename_files: bool, dry_run: bool, verbose: bool, summary: RunSummary | None) -> bool:
    """
    Move file 'src' into directory 'dst_folder'.
    Returns True if moved; False if skipped due to conflict (when not renaming).
    """
    s = summary
    name = os.path.basename(src)
    dst_path = os.path.join(dst_folder, name)

    if os.path.abspath(os.path.dirname(src)) == os.path.abspath(dst_folder):
        # already in target folder
        return False

    if os.path.exists(dst_path):
        if rename_files:
            new_dst = unique_path(dst_path, style="paren")
            if verbose:
                logging.debug("Name conflict for %s; using %s", name, os.path.basename(new_dst), extra={"target": name})
            if not dry_run:
                os.makedirs(dst_folder, exist_ok=True)
                shutil.move(src, new_dst)
            if s:
                s.inc("moved")
                s.inc("renamed")
            logging.info("Moved to %s", os.path.basename(dst_folder), extra={"target": os.path.basename(new_dst)})
            return True
        else:
            logging.warning("Skipping (name exists in destination).", extra={"target": name})
            if s:
                s.inc("skipped_conflict")
            return False

    try:
        if verbose:
            logging.debug("Moving %s -> %s", name, os.path.basename(dst_folder), extra={"target": name})
        if not dry_run:
            os.makedirs(dst_folder, exist_ok=True)
            shutil.move(src, dst_path)
        if s:
            s.inc("moved")
        logging.info("Moved file to %s", dst_folder, extra={"target": os.path.basename(dst_path)})
        return True
    except Exception as e:
        logging.error("Failed to move: %s", e, extra={"target": name})
        if s:
            s.inc("errors")
        return False


def _remove_empty_dirs(root: str, *, include_hidden: bool, dry_run: bool, verbose: bool, summary: RunSummary | None) -> int:
    """
    Remove empty directories under root. Returns count removed.
    """
    removed = 0
    # Walk bottom-up so children are removed before parents
    for curr, dirs, files in os.walk(root, topdown=False):
        # never remove the root itself
        if os.path.abspath(curr) == os.path.abspath(root):
            continue
        if not include_hidden and is_hidden(curr):
            continue
        try:
            if not os.listdir(curr):
                if verbose:
                    logging.debug("Removing empty folder: %s", curr, extra={"target": os.path.basename(curr)})
                if not dry_run:
                    os.rmdir(curr)
                removed += 1
        except FileNotFoundError:
            continue
        except Exception as e:
            logging.error("Failed to remove folder: %s", e, extra={"target": os.path.basename(curr)})
            if summary:
                summary.inc("errors")
    if summary:
        summary.inc("folders_removed", removed)
    return removed


# ------------------------------------------------------------
# modes
# ------------------------------------------------------------

def _batch_mode(
    root: str,
    *,
    recursive: bool,
    include_hidden: bool,
    rename_files: bool,
    dry_run: bool,
    verbose: bool,
    summary: RunSummary | None,
) -> None:
    """
    Flatten the contents of 'root' by moving files from subfolders into 'root'.
    - Default (non-recursive): only from immediate subfolders.
    - Recursive: from all descendant subfolders.
    """
    # Collect a static list of files first to avoid iterator confusion while moving
    if recursive:
        # all files under root, but skip files already in root
        file_iter = [p for p in iter_files(root, recursive=True, include_hidden=include_hidden) if os.path.dirname(p) != os.path.abspath(root)]
    else:
        # Only files in immediate subfolders (not files already in root)
        file_list = []
        for d in iter_dirs(root, recursive=False, include_hidden=include_hidden):
            for f in iter_files(d, recursive=False, include_hidden=include_hidden):
                file_list.append(f)
        file_iter = file_list

    for src in file_iter:
        if summary:
            summary.inc("found")
        _move_one(src, root, rename_files=rename_files, dry_run=dry_run, verbose=verbose, summary=summary)

    # Remove empty folders after moving
    _remove_empty_dirs(root, include_hidden=include_hidden, dry_run=dry_run, verbose=verbose, summary=summary)


def _single_mode(
    folder: str,
    *,
    include_hidden: bool,
    rename_files: bool,
    dry_run: bool,
    verbose: bool,
    summary: RunSummary | None,
) -> None:
    """
    Flatten a single folder by moving its direct child files into the folder's parent.
    Does NOT recurse by design for single-mode.
    """
    parent = os.path.dirname(folder) or os.path.abspath(os.path.join(folder, ".."))
    # Move direct child files
    for f in iter_files(folder, recursive=False, include_hidden=include_hidden):
        if summary:
            summary.inc("found")
        _move_one(f, parent, rename_files=rename_files, dry_run=dry_run, verbose=verbose, summary=summary)
    # After moving files, try removing empty directories under the original folder (now likely empty)
    _remove_empty_dirs(folder, include_hidden=include_hidden, dry_run=dry_run, verbose=verbose, summary=summary)
    # If the folder itself becomes empty, remove it
    try:
        if not os.listdir(folder):
            if verbose:
                logging.debug("Removing now-empty folder: %s", folder, extra={"target": os.path.basename(folder)})
            if not dry_run:
                os.rmdir(folder)
            if summary:
                summary.inc("folders_removed")
    except Exception:
        # ignore; not fatal (folder contains subdirs or permissions)
        pass


# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Flatten folders by moving files up. "
            "Batch mode moves files from subfolders into the target folder. "
            "Single mode moves this folder's files into its parent."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    add_target_args(
        parser,
        folder_help="Batch mode: flatten this folder's contents (non-recursive by default; use -r/--recursive to include all subfolders).",
        single_help="Single mode: move this folder's files into its parent (non-recursive).",
        required=True,
    )

    parser.add_argument("--rename", action="store_true", help="Rename on conflict instead of skipping")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without moving files")

    args = parser.parse_args()

    configure_logging(getattr(args, "verbose", False))

    mode_sel, target = resolve_target(args, single_expect="folder", folder_expect="folder")

    s = RunSummary()
    s.set("recursive", bool(getattr(args, "recursive", False)))
    s.set("include_hidden", bool(getattr(args, "include_hidden", False)))
    s.set("dry_run", bool(getattr(args, "dry_run", False)))
    s.set("rename", bool(getattr(args, "rename", False)))

    if mode_sel == "single":
        _single_mode(
            target,
            include_hidden=bool(getattr(args, "include_hidden", False)),
            rename_files=bool(getattr(args, "rename", False)),
            dry_run=bool(getattr(args, "dry_run", False)),
            verbose=getattr(args, "verbose", False),
            summary=s,
        )
    else:
        _batch_mode(
            target,
            recursive=bool(getattr(args, "recursive", False)),
            include_hidden=bool(getattr(args, "include_hidden", False)),
            rename_files=bool(getattr(args, "rename", False)),
            dry_run=bool(getattr(args, "dry_run", False)),
            verbose=getattr(args, "verbose", False),
            summary=s,
        )

    # Emit compact summary
    found = s.get("found", 0)
    moved = s.get("moved", 0)
    renamed = s.get("renamed", 0)
    skipped_conflict = s.get("skipped_conflict", 0)
    folders_removed = s.get("folders_removed", 0)
    errors = s.get("errors", 0)

    line1 = (
        f"Moved {moved}/{found} files "
        f"({skipped_conflict} conflicts skipped; {renamed} renamed). "
        f"Removed {folders_removed} empty folders."
    )
    line2 = (
        f"Recursive: {s['recursive']}. Include hidden: {s['include_hidden']}. "
        f"Dry-run: {s['dry_run']}."
    )

    s.emit_lines(
        [line1, line2],
        json_extra={
            "found": found,
            "moved": moved,
            "renamed": renamed,
            "skipped_conflict": skipped_conflict,
            "folders_removed": folders_removed,
            "errors": errors,
            "recursive": s["recursive"],
            "include_hidden": s["include_hidden"],
            "dry_run": s["dry_run"],
            "rename": s["rename"],
            "target_mode": mode_sel,
            "target": target,
        },
    )


if __name__ == "__main__":
    main()
