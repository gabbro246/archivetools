import os
import shutil
import argparse
from archivetools import __version__, logging, RunSummary


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


def flatten_folder(root_folder, rename_files, depth=None, verbose=False, summary=None):
    """
    Move all files from subfolders up into `root_folder`.
    - If `depth` is provided, only flatten items at most that many levels deep.
      (level 1 = immediate children of root).
    - Renames on conflict when `rename_files=True`, otherwise skips.
    - Removes empty folders after moves.
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

    # counters we track for the end-of-run summary
    s = summary  # local alias

    max_seen_level = 0
    files_moved_this_run = 0
    renamed_conflicts = 0
    skipped_conflicts = 0
    folders_removed = 0

    # first pass: move files up to root
    for dirpath, dirnames, filenames in os.walk(root_folder):
        # compute depth (0 for root)
        rel = os.path.relpath(dirpath, root_folder)
        level = 0 if rel in (".", "") else len(rel.split(os.sep))
        if level == 0:
            continue
        if depth is not None and level > depth:
            max_seen_level = max(max_seen_level, level)
            continue

        max_seen_level = max(max_seen_level, level)

        for fname in filenames:
            src = os.path.join(dirpath, fname)
            if not os.path.isfile(src):
                continue  # just in case

            if s:
                s.inc("found")

            dst = os.path.join(root_folder, fname)

            if os.path.exists(dst):
                if rename_files:
                    base, ext = os.path.splitext(fname)
                    new_name = get_new_name(base, ext, root_folder, verbose=verbose)
                    dst = os.path.join(root_folder, new_name)
                    renamed_conflicts += 1
                    if s:
                        s.inc("renamed")
                    if verbose:
                        logging.debug(
                            f"Conflict: renaming {fname} -> {new_name}",
                            extra={"target": fname},
                        )
                else:
                    skipped_conflicts += 1
                    if s:
                        s.inc("skipped_conflict")
                    if verbose:
                        logging.debug(
                            f"Conflict: file exists in root, skipping {fname}",
                            extra={"target": fname},
                        )
                    continue

            try:
                if verbose:
                    logging.debug(
                        f"Moving {fname} -> {os.path.basename(root_folder)}",
                        extra={"target": fname},
                    )
                shutil.move(src, dst)
                files_moved_this_run += 1
                if s:
                    s.inc("moved")
                logging.info(
                    "Moved file to %s",
                    root_folder,
                    extra={"target": os.path.basename(dst)},
                )
            except FileNotFoundError:
                logging.error(
                    "File could not be moved. File not found.",
                    extra={"target": os.path.basename(src)},
                )
                if s:
                    s.inc("errors")

    # second pass: remove empty directories, deepest-first
    # walk bottom-up to ensure we try to remove deepest empties first
    for dirpath, dirnames, filenames in os.walk(root_folder, topdown=False):
        if dirpath == root_folder:
            continue
        try:
            # check emptiness after moves
            if not os.listdir(dirpath):
                if verbose:
                    logging.debug(
                        f"Removing empty folder: {dirpath}",
                        extra={"target": os.path.basename(dirpath)},
                    )
                os.rmdir(dirpath)
                folders_removed += 1
                if s:
                    s.inc("folders_removed")
                logging.info(
                    "Removed empty folder",
                    extra={"target": os.path.basename(dirpath)},
                )
        except OSError:
            # not empty or cannot remove; ignore
            pass

    # keep a couple of handy metrics
    if s:
        s.set("max_depth_traversed", int(max_seen_level))
        if depth is not None:
            s.set("depth_limit", int(depth))


def main():
    parser = argparse.ArgumentParser(
        description="Flattens a folder by moving files from subfolders into the root, optionally renaming on conflicts and removing empty folders.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-v", "--version", action="version", version=f"ArchiveTools {__version__}")
    parser.add_argument(
        "-f",
        "--folder",
        type=str,
        required=True,
        help="Path to the folder to flatten",
    )
    parser.add_argument(
        "--rename",
        action="store_true",
        help="Rename files instead of skipping them",
    )
    parser.add_argument("--depth", type=int, help="Depth to flatten (level 1 = direct children)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    args = parser.parse_args()

    logging.getLogger().setLevel(logging.DEBUG if args.verbose else logging.INFO)

    # summary tracker
    s = RunSummary()
    s.set("rename", bool(args.rename))
    if args.depth is not None:
        s.set("depth_limit", int(args.depth))

    flatten_folder(args.folder, args.rename, args.depth, verbose=args.verbose, summary=s)

    # emit summary
    found = s["found"] or 0
    moved = s["moved"] or 0
    renamed = s["renamed"] or 0
    skipped_conflict = s["skipped_conflict"] or 0
    folders_removed = s["folders_removed"] or 0
    max_depth = s["max_depth_traversed"] or 0
    depth_limit = s["depth_limit"]

    line1 = (
        f"Moved {moved} file(s) to root. Removed {folders_removed} empty folder(s) in {s.duration_hms}."
    )
    line2 = (
        f"Conflicts: {renamed} renamed, {skipped_conflict} skipped. "
        f"Max depth traversed: {max_depth}"
        + (f". Depth limit: {depth_limit}." if depth_limit is not None else ".")
    )

    s.emit_lines(
        [line1, line2],
        json_extra={
            "found": found,
            "moved": moved,
            "renamed": renamed,
            "skipped_conflict": skipped_conflict,
            "folders_removed": folders_removed,
            "max_depth_traversed": max_depth,
            "depth_limit": depth_limit,
        },
    )


if __name__ == "__main__":
    main()
