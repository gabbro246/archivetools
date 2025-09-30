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

def main():
    parser = argparse.ArgumentParser(
        description="Deletes duplicate media files based on content hash, keeping a single representative per group.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('-v', '--version', action='version', version=f'ArchiveTools {__version__}')
    parser.add_argument('-f', '--folder', type=str, required=True, help='Path to the folder to process')
    parser.add_argument(
        '--mode',
        type=str,
        default='default',
        choices=['default','oldest','newest','exif','ffprobe','sidecar','filename','folder','metadata'],
        help='Date selection strategy for prioritization'
    )
    parser.add_argument('--dry-run', action='store_true', help='Show what would be removed without deleting files')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    args = parser.parse_args()

    logging.getLogger().setLevel(logging.DEBUG if args.verbose else logging.INFO)

    folder_path = args.folder
    if not os.path.isdir(folder_path):
        logging.error("The specified path is not a valid directory", extra={'target': os.path.basename(folder_path)})
        sys.exit(1)

    s = RunSummary()
    s.set('mode', args.mode)
    s.set('dry_run', bool(args.dry_run))

    logging.info("Processing folder", extra={'target': os.path.basename(folder_path)})
    process_folder(folder_path, mode=args.mode, dry_run=args.dry_run, verbose=args.verbose, summary=s)
    logging.info("Processing complete.", extra={'target': os.path.basename(folder_path)})

    # end-of-run summary
    scanned = s['scanned'] or 0
    hashed = s['hashed'] or 0
    dup_sets = s['duplicate_sets'] or 0
    deleted = s['deleted'] or 0
    reclaimed_h = s.hbytes('reclaimed_bytes')
    largest = s['largest_set'] or 0
    errors = s['errors'] or 0

    line1 = f"Scanned {scanned} media files — computed {hashed} hashes in {s.duration_hms}."
    line2 = f"Duplicate sets found: {dup_sets}. Deleted {deleted} files, reclaimed {reclaimed_h}. Largest set size: {largest}."
    line3 = f"Mode: {s['mode']}. Dry-run: {'yes' if s['dry_run'] else 'no'}. Errors: {errors}."

    s.emit_lines([line1, line2, line3], json_extra={
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
