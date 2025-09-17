import os
import argparse
import logging
from collections import defaultdict
from typing import Dict, List, Tuple

from archivetools import (
    configure_logging,
    add_target_args,
    resolve_target,
    iter_files,
    calculate_file_hash,
    get_dates_from_file,
    select_date,
    MEDIA_EXTENSIONS,
    RunSummary,
)

# ------------------------------------------------------------
# Core duplicate detection
# ------------------------------------------------------------

def _group_candidates_by_size(paths: List[str]) -> Dict[int, List[str]]:
    by_size: Dict[int, List[str]] = defaultdict(list)
    for p in paths:
        try:
            sz = os.path.getsize(p)
        except FileNotFoundError:
            continue
        by_size[sz].append(p)
    # Only keep ambiguous sizes (more than one file)
    return {sz: lst for sz, lst in by_size.items() if len(lst) > 1}


def _group_by_hash(paths: List[str], *, algo: str, summary: RunSummary | None) -> Dict[str, List[str]]:
    by_hash: Dict[str, List[str]] = defaultdict(list)
    for p in paths:
        try:
            h = calculate_file_hash(p, algo=algo)
        except FileNotFoundError:
            continue
        by_hash[h].append(p)
        if summary:
            summary.inc("hashed")
    # Only groups with more than one file are true dup candidates
    return {h: lst for h, lst in by_hash.items() if len(lst) > 1}


def _pick_keeper_by_date(paths: List[str], mode: str, verbose: bool, summary: RunSummary | None) -> str:
    """
    Choose which file to keep based on detected dates and the selected mode.
    """
    scored: List[Tuple[str, Tuple[str, object] | None]] = []
    for p in paths:
        candidates = get_dates_from_file(p)
        choice = select_date(candidates, mode=mode)
        if verbose:
            logging.debug("Dates for %s -> %s ; choice=%s", os.path.basename(p), candidates, choice, extra={"target": os.path.basename(p)})
        scored.append((p, choice))

    # If no one has a date, fall back to keeping the first path deterministically (sorted for stability)
    any_date = [c for _, c in scored if c]
    if not any_date:
        return sorted(paths)[0]

    # Select the file whose chosen date best matches the mode (select_date already applied per file)
    # We'll just take the file with the "best" chosen date according to the same mode:
    dated = [(p, c[1]) for p, c in scored if c]
    if mode == "newest":
        keeper = max(dated, key=lambda t: t[1])[0]
    elif mode == "oldest":
        keeper = min(dated, key=lambda t: t[1])[0]
    else:
        # 'default': prefer the files that actually had EXIF/ffprobe choice first; tie-break on newest
        exif_like = []
        others = []
        for p, (label, d) in [(p, (c[0], c[1])) for p, c in scored if c]:
            if str(label).startswith("exif:") or str(label).startswith("ffprobe:"):
                exif_like.append((p, d))
            else:
                others.append((p, d))
        pool = exif_like or others
        keeper = max(pool, key=lambda t: t[1])[0]
    if summary:
        summary.inc(f"kept_by_{mode}")
    return keeper


def _delete_others(paths: List[str], keeper: str, *, dry_run: bool, verbose: bool, summary: RunSummary | None) -> None:
    """
    Delete all files in 'paths' except 'keeper'.
    """
    for p in paths:
        if os.path.abspath(p) == os.path.abspath(keeper):
            continue
        name = os.path.basename(p)
        try:
            bytes_p = os.path.getsize(p)
        except FileNotFoundError:
            bytes_p = 0

        if dry_run:
            if verbose:
                logging.debug("Would delete duplicate: %s", p, extra={"target": name})
        else:
            try:
                os.remove(p)
            except Exception as e:
                logging.error("Failed to delete duplicate: %s", e, extra={"target": name})
                if summary:
                    summary.inc("errors")
                continue

        logging.info("Deleted duplicate", extra={"target": name})
        if summary:
            summary.inc("deleted")
            summary.inc("reclaimed_bytes", bytes_p)


# ------------------------------------------------------------
# Batch mode
# ------------------------------------------------------------

def process_batch_folder(
    root: str,
    *,
    recursive: bool,
    include_hidden: bool,
    mode: str,
    algo: str,
    dry_run: bool,
    verbose: bool,
    summary: RunSummary | None,
) -> None:
    """
    Find and remove duplicate media files inside 'root'.
    """
    # Gather files (non-recursive by default)
    files = list(iter_files(root, recursive=recursive, include_hidden=include_hidden, ext_filter=set(MEDIA_EXTENSIONS)))
    if summary:
        summary.set("scanned", len(files))

    # Group by size first for speed
    by_size = _group_candidates_by_size(files)

    # For each size bucket, group by hash
    largest_set = 0
    duplicate_sets = 0

    for size, same_size_paths in by_size.items():
        # Hash only these candidates
        by_hash = _group_by_hash(same_size_paths, algo=algo, summary=summary)
        for h, dup_paths in by_hash.items():
            duplicate_sets += 1
            if len(dup_paths) > largest_set:
                largest_set = len(dup_paths)

            if verbose:
                logging.debug(
                    "Duplicate group (size=%d, hash=%s): %s",
                    size,
                    h[:12],
                    ", ".join(os.path.basename(p) for p in dup_paths),
                )

            keeper = _pick_keeper_by_date(dup_paths, mode=mode, verbose=verbose, summary=summary)
            if verbose:
                logging.debug("Keeping: %s", os.path.basename(keeper), extra={"target": os.path.basename(keeper)})

            _delete_others(dup_paths, keeper, dry_run=dry_run, verbose=verbose, summary=summary)

    if summary:
        summary.set("duplicate_sets", duplicate_sets)
        summary.set("largest_set", largest_set)
        summary.set("mode", mode)
        summary.set("algo", algo)


# ------------------------------------------------------------
# Single-file mode
# ------------------------------------------------------------

def process_single_file(
    file_path: str,
    *,
    parent_root: str,
    recursive: bool,
    include_hidden: bool,
    algo: str,
    dry_run: bool,
    verbose: bool,
    summary: RunSummary | None,
) -> None:
    """
    In single mode: hash the anchor file, then look for duplicates within the
    parent scope (non-recursive by default; use --recursive for subfolders). Always
    keep the anchor; delete other copies with the same hash.
    """
    try:
        size_anchor = os.path.getsize(file_path)
    except FileNotFoundError:
        logging.error("Anchor file not found", extra={"target": os.path.basename(file_path)})
        if summary:
            summary.inc("errors")
        return

    try:
        hash_anchor = calculate_file_hash(file_path, algo=algo)
    except FileNotFoundError:
        logging.error("Anchor file vanished during hashing", extra={"target": os.path.basename(file_path)})
        if summary:
            summary.inc("errors")
        return

    # Gather peers in scope (exclude the anchor path itself)
    peers = [
        p for p in iter_files(parent_root, recursive=recursive, include_hidden=include_hidden, ext_filter=set(MEDIA_EXTENSIONS))
        if os.path.abspath(p) != os.path.abspath(file_path)
    ]
    if summary:
        summary.set("scanned", len(peers) + 1)  # include anchor

    # Pre-filter by size
    same_size = [p for p in peers if os.path.getsize(p) == size_anchor]
    # Confirm with hash
    dups = []
    for p in same_size:
        try:
            h = calculate_file_hash(p, algo=algo)
        except FileNotFoundError:
            continue
        if h == hash_anchor:
            dups.append(p)
            if summary:
                summary.inc("hashed")

    if not dups:
        logging.info("No duplicates found for the anchor.", extra={"target": os.path.basename(file_path)})
        return

    # Delete all duplicates (anchor is the keeper)
    _delete_others([file_path] + dups, file_path, dry_run=dry_run, verbose=verbose, summary=summary)

    if summary:
        summary.set("duplicate_sets", 1)
        summary.set("largest_set", len(dups) + 1)


# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Find and remove duplicate media files. "
            "Batch mode scans a folder; single mode targets duplicates of one file. "
            "Non-recursive by default — use --recursive to include subfolders."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    add_target_args(
        parser,
        folder_help="Batch mode: scan this folder for duplicate media (non-recursive by default; use --recursive to include subfolders).",
        single_help="Single mode: find duplicates of exactly this file in its parent scope (use --recursive to include subfolders).",
        required=True,
    )

    parser.add_argument(
        "--mode",
        type=str,
        default="default",
        choices=["default", "oldest", "newest"],
        help="(Batch) Which copy to KEEP in each duplicate set, based on detected dates.",
    )
    parser.add_argument(
        "--algo",
        type=str,
        default="sha256",
        choices=["sha256", "md5", "sha1", "blake2b", "blake2s"],
        help="Hash algorithm for file content comparison.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without removing files")

    args = parser.parse_args()
    configure_logging(getattr(args, "verbose", False))

    mode_sel, target = resolve_target(args, single_expect="file", folder_expect="folder")

    s = RunSummary()
    s.set("dry_run", bool(args.dry_run))
    s.set("recursive", bool(getattr(args, "recursive", False)))
    s.set("include_hidden", bool(getattr(args, "include_hidden", False)))

    if mode_sel == "single":
        parent_root = os.path.dirname(target)
        process_single_file(
            target,
            parent_root=parent_root,
            recursive=bool(getattr(args, "recursive", False)),
            include_hidden=bool(getattr(args, "include_hidden", False)),
            algo=args.algo,
            dry_run=args.dry_run,
            verbose=getattr(args, "verbose", False),
            summary=s,
        )
    else:
        process_batch_folder(
            target,
            recursive=bool(getattr(args, "recursive", False)),
            include_hidden=bool(getattr(args, "include_hidden", False)),
            mode=args.mode,
            algo=args.algo,
            dry_run=args.dry_run,
            verbose=getattr(args, "verbose", False),
            summary=s,
        )

    # Emit summary
    scanned = s.get("scanned", 0) or 0
    hashed = s.get("hashed", 0) or 0
    dup_sets = s.get("duplicate_sets", 0) or 0
    deleted = s.get("deleted", 0) or 0
    reclaimed = s.get("reclaimed_bytes", 0) or 0
    largest = s.get("largest_set", 0) or 0
    errors = s.get("errors", 0) or 0

    line1 = (
        f"Scanned {scanned} file(s); hashed {hashed}. "
        f"Found {dup_sets} duplicate set(s) (largest set: {largest})."
    )
    line2 = f"Deleted {deleted} file(s); reclaimed {reclaimed} bytes. Errors: {errors}."
    if mode_sel == "folder":
        line3 = f"Keeper selection mode: {s.get('mode', 'default')}; hash algo: {s.get('algo', 'sha256')}."
        lines = [line1, line2, line3]
    else:
        lines = [line1, line2]

    s.emit_lines(
        lines,
        json_extra={
            "target_mode": mode_sel,
            "scanned": scanned,
            "hashed": hashed,
            "duplicate_sets": dup_sets,
            "deleted": deleted,
            "reclaimed_bytes": reclaimed,
            "largest_set": largest,
            "errors": errors,
            "mode": s.get("mode"),
            "algo": s.get("algo"),
            "dry_run": s["dry_run"],
            "recursive": s["recursive"],
            "include_hidden": s["include_hidden"],
            "target": target,
        },
    )


if __name__ == "__main__":
    main()
