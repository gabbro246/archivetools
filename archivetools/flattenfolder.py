import os
import shutil
import argparse
import logging
from archivetools import __version__, RunSummary, add_target_args, resolve_target


def get_new_name(base, extension, target_folder, verbose=False):
    counter = 1
    new_name = f"{base}({counter}){extension}"
    while os.path.exists(os.path.join(target_folder, new_name)):
        counter += 1
        new_name = f"{base}({counter}){extension}"
    if verbose:
        logging.debug(
            f"Generated new filename to avoid conflict: {new_name}",
            extra={"target": new_name},
        )
    return new_name


def _move_one(src, dst_folder, rename_files, verbose, summary):
    """
    Move a single file into dst_folder, renaming on conflict if requested.
    Returns True if moved, False if skipped.
    """
    s = summary
    name = os.path.basename(src)
    dst = os.path.join(dst_folder, name)

    if os.path.exists(dst):
        if rename_files:
            base, ext = os.path.splitext(name)
            new_name = get_new_name(base, ext, dst_folder, verbose=verbose)
            dst = os.path.join(dst_folder, new_name)
            if s: s.inc("renamed")
            if verbose:
                logging.debug(
                    f"Conflict: renaming {name} -> {os.path.basename(dst)}",
                    extra={"target": name},
                )
        else:
            if s: s.inc("skipped_conflict")
            if verbose:
                logging.debug(
                    f"Conflict: file exists in {os.path.basename(dst_folder)}, skipping {name}",
                    extra={"target": name},
                )
            return False

    try:
        if verbose:
            logging.debug(
                f"Moving {name} -> {os.path.basename(dst_folder)}",
                extra={"target": name},
            )
        shutil.move(src, dst)
        if s: s.inc("moved")
        logging.info(
            "Moved file to %s",
            dst_folder,
            extra={"target": os.path.basename(dst)},
        )
        return True
    except FileNotFoundError:
        logging.error(
            "File could not be moved. File not found.",
            extra={"target": os.path.basename(src)},
        )
        if s: s.inc("errors")
        return False


def flatten_folder(root_folder, rename_files, depth=None, verbose=False, summary=None):
    """
    Batch mode (-f): Move all files from subfolders up into `root_folder`.
    Renames on conflict when `rename_files=True`, otherwise skips.
    Removes empty folders after moves (but keeps the root folder).
    """
    if not os.path.isdir(root_folder):
        logging.error(
            "The specified path is not a directory.",
            extra={"target": os.path.basename(root_folder)},
        )
        if summary:
            summary.inc("errors")
        return

    if verbose:
        logging.debug(
            f"Starting to flatten folder: {root_folder}",
            extra={"target": os.path.basename(root_folder)},
        )

    s = summary
    max_seen_level = 0

    # first pass: move files up to root
    for dirpath, dirnames, filenames in os.walk(root_folder):
        # compute depth (0 for root)
        rel = os.path.relpath(dirpath, root_folder)
        level = 0 if rel in (".", "") else len(rel.split(os.sep))
        if level == 0:
            # by definition, this mode moves only from subfolders into root
            continue
        if depth is not None and level > depth:
            max_seen_level = max(max_seen_level, level)
            continue

        max_seen_level = max(max_seen_level, level)

        for fname in filenames:
            src = os.path.join(dirpath, fname)
            if not os.path.isfile(src):
                continue
            if s: s.inc("found")
            _move_one(src, root_folder, rename_files, verbose, s)

    # second pass: remove empty directories under root (deepest-first)
    for dirpath, dirnames, filenames in os.walk(root_folder, topdown=False):
        if dirpath == root_folder:
            continue
        try:
            if not os.listdir(dirpath):
                if verbose:
                    logging.debug(
                        f"Removing empty folder: {dirpath}",
                        extra={"target": os.path.basename(dirpath)},
                    )
                os.rmdir(dirpath)
                if s: s.inc("folders_removed")
                logging.info(
                    "Removed empty folder",
                    extra={"target": os.path.basename(dirpath)},
                )
        except OSError:
            pass

    if s:
        s.set("max_depth_traversed", int(max_seen_level))
        if depth is not None:
            s.set("depth_limit", int(depth))


def lift_contents_to_parent(selected_folder, rename_files, depth=None, verbose=False, summary=None):
    """
    Single mode (-s): Move all files from `selected_folder` (including its subfolders)
    up into the *parent directory* of `selected_folder`, ignoring any other siblings.
    Removes empty subfolders under `selected_folder` afterwards. Keeps `selected_folder` itself.
    """
    if not os.path.isdir(selected_folder):
        logging.error(
            "The specified path is not a directory.",
            extra={"target": os.path.basename(selected_folder)},
        )
        if summary:
            summary.inc("errors")
        return

    parent = os.path.dirname(os.path.abspath(selected_folder))
    if verbose:
        logging.debug(
            f"Lifting contents of {selected_folder} to parent: {parent}",
            extra={"target": os.path.basename(selected_folder)},
        )

    s = summary
    max_seen_level = 0

    # move files in the root of selected_folder first
    for fname in os.listdir(selected_folder):
        src = os.path.join(selected_folder, fname)
        if os.path.isfile(src):
            if s: s.inc("found")
            _move_one(src, parent, rename_files, verbose, s)

    # then move files from subfolders (respect depth relative to selected_folder)
    for dirpath, dirnames, filenames in os.walk(selected_folder):
        rel = os.path.relpath(dirpath, selected_folder)
        level = 0 if rel in (".", "") else len(rel.split(os.sep))
        if level == 0:
            # already processed root files above
            continue
        if depth is not None and level > depth:
            max_seen_level = max(max_seen_level, level)
            continue

        max_seen_level = max(max_seen_level, level)

        for fname in filenames:
            src = os.path.join(dirpath, fname)
            if not os.path.isfile(src):
                continue
            if s: s.inc("found")
            _move_one(src, parent, rename_files, verbose, s)

    # remove empty subfolders under selected_folder (deepest-first). keep selected_folder.
    for dirpath, dirnames, filenames in os.walk(selected_folder, topdown=False):
        if dirpath == selected_folder:
            continue
        try:
            if not os.listdir(dirpath):
                if verbose:
                    logging.debug(
                        f"Removing empty folder: {dirpath}",
                        extra={"target": os.path.basename(dirpath)},
                    )
                os.rmdir(dirpath)
                if s: s.inc("folders_removed")
                logging.info(
                    "Removed empty folder",
                    extra={"target": os.path.basename(dirpath)},
                )
        except OSError:
            pass

    if s:
        s.set("max_depth_traversed", int(max_seen_level))
        if depth is not None:
            s.set("depth_limit", int(depth))


def main():
    parser = argparse.ArgumentParser(
        description="Flattens a folder by moving files from subfolders into the root (-f), or lifts the contents of a folder to its parent (-s).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-v", "--version", action="version", version=f"ArchiveTools {__version__}")
    add_target_args(
        parser,
        folder_help="Batch mode: flatten the contents of this folder into itself (move from subfolders to root)",
        single_help="Single mode: move the contents of this folder up to its parent directory (ignore siblings)",
        required=True,
    )
    parser.add_argument(
        "--rename",
        action="store_true",
        help="Rename files instead of skipping them when a name conflict occurs",
    )
    parser.add_argument("--depth", type=int, help="Depth to traverse (relative to the selected folder). Level 1 = immediate children")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    args = parser.parse_args()

    logging.getLogger().setLevel(logging.DEBUG if args.verbose else logging.INFO)

    # resolve target (-s expects a FOLDER, -f expects a FOLDER)
    mode_sel, target = resolve_target(args, single_expect="folder", folder_expect="folder")

    # summary tracker
    s = RunSummary()
    s.set("rename", bool(args.rename))
    if args.depth is not None:
        s.set("depth_limit", int(args.depth))

    if mode_sel == "single":
        lift_contents_to_parent(target, args.rename, args.depth, verbose=args.verbose, summary=s)
    else:
        flatten_folder(target, args.rename, args.depth, verbose=args.verbose, summary=s)

    # emit summary
    found = s["found"] or 0
    moved = s["moved"] or 0
    renamed = s["renamed"] or 0
    skipped_conflict = s["skipped_conflict"] or 0
    folders_removed = s["folders_removed"] or 0
    max_depth = s["max_depth_traversed"] or 0
    depth_limit = s["depth_limit"]
    errors = s["errors"] or 0

    if mode_sel == "single":
        action_line = f"Lifted contents of '{os.path.basename(target)}' to parent."
    else:
        action_line = f"Flattened folder '{os.path.basename(target)}'."

    line1 = (
        f"{action_line} Moved {moved} file(s). Removed {folders_removed} empty folder(s) in {s.duration_hms}."
    )
    line2 = (
        f"Conflicts: {renamed} renamed, {skipped_conflict} skipped. "
        f"Max depth traversed: {max_depth}"
        + (f". Depth limit: {depth_limit}." if depth_limit is not None else ".")
        + f" Errors: {errors}."
    )

    s.emit_lines(
        [line1, line2],
        json_extra={
            "target_mode": mode_sel,
            "found": found,
            "moved": moved,
            "renamed": renamed,
            "skipped_conflict": skipped_conflict,
            "folders_removed": folders_removed,
            "max_depth_traversed": max_depth,
            "depth_limit": depth_limit,
            "errors": errors,
        },
    )


if __name__ == "__main__":
    main()
