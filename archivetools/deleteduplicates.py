import os
import sys
import argparse
import logging
from collections import defaultdict
from archivetools import (
    __version__,
    get_dates_from_file,
    select_date,
    calculate_file_hash,
    MEDIA_EXTENSIONS,
    RunSummary,
    add_target_args,
    resolve_target,
)

def prioritize_file(files, mode="default", verbose=False):
    """
    Decide which file to KEEP among exact-duplicate files (same content hash).
    Preference:
      - Use select_date(mode) over detected dates; fall back to file mtime if none.
      - Keep OLDEST by default; keep NEWEST if mode == 'newest'.
    Returns the filepath to keep.
    """
    dated = []
    for f in files:
        try:
            dates = get_dates_from_file(f)
            sel = select_date(dates, mode=mode)
            if sel:
                _, dt = sel
            else:
                dt = None
        except Exception:
            dt = None
        if dt is None:
            try:
                dt = os.path.getmtime(f)
            except Exception:
                dt = 0
        dated.append((f, dt))
    reverse = True if mode == "newest" else False
    keep = sorted(dated, key=lambda t: t[1], reverse=reverse)[0][0]
    if verbose:
        logging.debug(
            "Keeping representative duplicate: %s",
            os.path.basename(keep),
            extra={'target': os.path.basename(keep)},
        )
    return keep


def process_folder(folder_path, mode="default", dry_run=False, verbose=False, summary=None):
    s = summary
    # 1) Hash all media files (group by content hash)
    buckets = defaultdict(list)
    for root, _, files in os.walk(folder_path):
        for name in files:
            path = os.path.join(root, name)
            ext = os.path.splitext(name)[1].lower()
            if ext not in MEDIA_EXTENSIONS:
                continue
            if s: s.inc('scanned')
            try:
                h = calculate_file_hash(path)
                buckets[h].append(path)
                if s: s.inc('hashed')
                if verbose:
                    logging.debug("Hashed %s", path, extra={'target': name})
            except Exception as e:
                logging.error("Failed to hash file: %s", e, extra={'target': name})
                if s: s.inc('errors')

    # 2) For each hash-bucket with duplicates, choose one to keep and delete others
    largest_set = 0
    for digest, files in buckets.items():
        if len(files) <= 1:
            continue
        if s: s.inc('duplicate_sets')
        if len(files) > largest_set:
            largest_set = len(files)

        keep = prioritize_file(files, mode=mode, verbose=verbose)
        to_delete = [f for f in files if f != keep]

        for f in to_delete:
            try:
                size = os.path.getsize(f)
            except OSError:
                size = 0

            if dry_run:
                if verbose:
                    logging.debug(
                        "Would delete duplicate: %s (kept %s)",
                        f, keep,
                        extra={'target': os.path.basename(f)},
                    )
                continue

            try:
                os.remove(f)
                if s:
                    s.inc('deleted')
                    s.add_bytes('reclaimed_bytes', size)
                logging.info(
                    "Deleted duplicate (kept %s)",
                    os.path.basename(keep),
                    extra={'target': os.path.basename(f)},
                )
            except Exception as e:
                logging.error("Failed to delete duplicate: %s", e, extra={'target': os.path.basename(f)})
                if s: s.inc('errors')

    # record a few metrics
    if s:
        s.set('largest_set', int(largest_set))
        s.set('mode', mode)


def process_single_file(file_path, mode="default", dry_run=False, verbose=False, summary=None):
    """
    Single mode:
      - hash the anchor file
      - scan its parent directory tree for media files with the same hash
      - pick a keeper (per mode) and delete the rest (including the anchor if needed)
    """
    s = summary
    name = os.path.basename(file_path)
    parent_root = os.path.dirname(os.path.abspath(file_path))

    if not os.path.isfile(file_path):
        logging.error("The specified path is not a file.", extra={'target': name})
        if s: s.inc('errors')
        return

    anchor_ext = os.path.splitext(name)[1].lower()
    if anchor_ext not in MEDIA_EXTENSIONS:
        logging.info("Not a supported media file. Skipping.", extra={'target': name})
        return

    # Hash anchor
    try:
        anchor_hash = calculate_file_hash(file_path)
        if s:
            s.inc('hashed')  # count the anchor
            s.inc('scanned')
    except Exception as e:
        logging.error("Failed to hash anchor file: %s", e, extra={'target': name})
        if s: s.inc('errors')
        return

    # Collect candidates with same hash within parent_root (recursive)
    candidates = []
    for root, _, files in os.walk(parent_root):
        for fname in files:
            p = os.path.join(root, fname)
            ext = os.path.splitext(fname)[1].lower()
            if ext not in MEDIA_EXTENSIONS:
                continue
            if s: s.inc('scanned')
            try:
                h = calculate_file_hash(p)
                if s: s.inc('hashed')
            except Exception as e:
                logging.error("Failed to hash file: %s", e, extra={'target': fname})
                if s: s.inc('errors')
                continue
            if h == anchor_hash:
                candidates.append(p)
                if verbose:
                    logging.debug("Match by hash: %s", p, extra={'target': fname})

    # If only the anchor is present, no duplicates
    if len(candidates) <= 1:
        if verbose:
            logging.debug("No duplicates found for %s", file_path, extra={'target': name})
        # largest_set could still capture 1
        if s:
            s.set('largest_set', max(int(s['largest_set'] or 0), 1))
        return

    # We have a duplicate set
    if s: s.inc('duplicate_sets')
    if s: s.set('largest_set', max(int(s['largest_set'] or 0), len(candidates)))

    keep = prioritize_file(candidates, mode=mode, verbose=verbose)
    to_delete = [f for f in candidates if f != keep]

    for f in to_delete:
        try:
            size = os.path.getsize(f)
        except OSError:
            size = 0

        if dry_run:
            if verbose:
                logging.debug(
                    "Would delete duplicate: %s (kept %s)",
                    f, os.path.basename(keep),
                    extra={'target': os.path.basename(f)},
                )
            continue

        try:
            os.remove(f)
            if s:
                s.inc('deleted')
                s.add_bytes('reclaimed_bytes', size)
            logging.info(
                "Deleted duplicate (kept %s)",
                os.path.basename(keep),
                extra={'target': os.path.basename(f)},
            )
        except Exception as e:
            logging.error("Failed to delete duplicate: %s", e, extra={'target': os.path.basename(f)})
            if s: s.inc('errors')

    if s:
        s.set('mode', mode)


def main():
    parser = argparse.ArgumentParser(
        description="Deletes duplicate media files based on content hash. Use -f/--folder to process a folder tree, or -s/--single to check duplicates for one file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('-v', '--version', action='version', version=f'ArchiveTools {__version__}')
    add_target_args(
        parser,
        folder_help="Batch mode: check all media in this folder tree for duplicates",
        single_help="Single mode: check duplicates for this one file (scope = its parent folder tree)",
        required=True,
    )
    parser.add_argument(
        '--mode',
        type=str,
        default='default',
        choices=['default','oldest','newest','exif','ffprobe','sidecar','filename','folder','metadata'],
        help='Date selection strategy for prioritizing which duplicate to keep'
    )
    parser.add_argument('--dry-run', action='store_true', help='Show what would be removed without deleting files')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    args = parser.parse_args()

    logging.getLogger().setLevel(logging.DEBUG if args.verbose else logging.INFO)

    mode_sel, target = resolve_target(args, single_expect='file', folder_expect='folder')

    s = RunSummary()
    s.set('mode', args.mode)
    s.set('dry_run', bool(args.dry_run))

    if mode_sel == 'single':
        logging.info("Processing anchor file", extra={'target': os.path.basename(target)})
        process_single_file(target, mode=args.mode, dry_run=args.dry_run, verbose=args.verbose, summary=s)
    else:
        if not os.path.isdir(target):
            logging.error("The specified path is not a valid directory", extra={'target': os.path.basename(target)})
            sys.exit(1)
        logging.info("Processing folder", extra={'target': os.path.basename(target)})
        process_folder(target, mode=args.mode, dry_run=args.dry_run, verbose=args.verbose, summary=s)
        logging.info("Processing complete.", extra={'target': os.path.basename(target)})

    # end-of-run summary
    scanned = s['scanned'] or 0
    hashed = s['hashed'] or 0
    dup_sets = s['duplicate_sets'] or 0
    deleted = s['deleted'] or 0
    reclaimed_h = s.hbytes('reclaimed_bytes')
    largest = s['largest_set'] or 0
    errors = s['errors'] or 0

    if mode_sel == 'single':
        head = "Checked for duplicates of the selected file."
    else:
        head = "Completed duplicate scan for folder."

    line1 = f"{head} Scanned {scanned} media files — computed {hashed} hashes in {s.duration_hms}."
    line2 = f"Duplicate sets found: {dup_sets}. Deleted {deleted} files, reclaimed {reclaimed_h}. Largest set size: {largest}."
    line3 = f"Mode: {s['mode']}. Dry-run: {'yes' if s['dry_run'] else 'no'}. Errors: {errors}."

    s.emit_lines([line1, line2, line3], json_extra={
        'target_mode': mode_sel,
        'scanned': scanned,
        'hashed': hashed,
        'duplicate_sets': dup_sets,
        'deleted': deleted,
        'reclaimed_bytes': s['reclaimed_bytes'] or 0,
        'largest_set': largest,
        'errors': errors,
        'mode': s['mode'],
        'dry_run': s['dry_run'],
    })

if __name__ == "__main__":
    main()
