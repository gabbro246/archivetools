import os
import shutil
import argparse
import datetime
import calendar
import logging
from PIL import Image  # noqa: F401

from archivetools import (
    __version__,
    get_dates_from_file,
    select_date,
    SIDECAR_EXTENSIONS,
    MEDIA_EXTENSIONS,
    MONTH_NAMES,
    WEEK_PREFIX,
    RunSummary,  # <— added
)

def move_sidecar_files(file_path, target_folder, verbose=False):
    base_name, file_extension = os.path.splitext(os.path.basename(file_path))
    base_path = os.path.splitext(file_path)[0]
    for ext in SIDECAR_EXTENSIONS:
        potential_sidecars = [
            f"{base_path}{ext}",
            f"{file_path}{ext}"
        ]
        for sidecar_path in potential_sidecars:
            if os.path.exists(sidecar_path):
                target_sidecar_path = os.path.join(target_folder, os.path.basename(sidecar_path))
                target_sidecar_path = generate_unique_filename(target_sidecar_path)
                try:
                    if verbose:
                        logging.debug(f"Moving sidecar: {sidecar_path} -> {target_sidecar_path}", extra={'target': os.path.basename(sidecar_path)})
                    shutil.move(sidecar_path, target_sidecar_path)
                    logging.info("Moved sidecar file to %s", target_folder, extra={'target': os.path.basename(sidecar_path)})
                except FileNotFoundError:
                    logging.error("Sidecar file could not be moved. File not found.", extra={'target': os.path.basename(sidecar_path)})

def generate_unique_filename(target_path):
    base, extension = os.path.splitext(target_path)
    counter = 1
    candidate = target_path
    while os.path.exists(candidate):
        candidate = f"{base}_{counter}{extension}"
        counter += 1
    return candidate

def organize_files(target_dir, mode, rename_files, midnight_shift, get_folder_name_func, verbose=False, summary=None):  # <— summary
    if verbose:
        logging.debug(f"Organizing files in {target_dir} with mode={mode}", extra={'target': os.path.basename(target_dir)})

    for file_name in os.listdir(target_dir):
        file_path = os.path.join(target_dir, file_name)
        file_extension = os.path.splitext(file_name)[1].lower()
        if os.path.isfile(file_path) and file_extension in MEDIA_EXTENSIONS:
            if summary: summary.inc('found')  # <— added
            if verbose:
                logging.debug(f"Processing file: {file_path}", extra={'target': file_name})

            dates = get_dates_from_file(file_path)
            selected_date_info = select_date(dates, mode=mode, midnight_shift=midnight_shift)
            if selected_date_info:
                date_source, date_used = selected_date_info
                if summary: summary.inc(f"source_{str(date_source).lower()}")  # <— added
                if verbose:
                    logging.debug(f"Date selected for {file_name}: {date_used} (source: {date_source})", extra={'target': file_name})
            else:
                if verbose:
                    logging.debug(f"No valid date found for {file_name}, skipping.", extra={'target': file_name})
                logging.info("No valid date found. Skipping.", extra={'target': os.path.basename(file_name)})
                if summary: summary.inc('skipped_no_date')  # <— added
                continue

            folder_name = get_folder_name_func(date_used)
            target_folder = os.path.join(target_dir, folder_name)

            if not os.path.exists(target_folder):
                if verbose:
                    logging.debug(f"Creating folder: {target_folder}", extra={'target': folder_name})
                os.makedirs(target_folder, exist_ok=True)
                if summary: summary.inc('folders_created')  # <— added

            target_path = os.path.join(target_folder, file_name)
            if os.path.exists(file_path):
                if os.path.exists(target_path):
                    if rename_files:
                        new_target_path = generate_unique_filename(target_path)
                        if verbose:
                            logging.debug(f"Renaming {file_name} -> {os.path.basename(new_target_path)}", extra={'target': file_name})
                        target_path = new_target_path
                        if summary: summary.inc('renamed')  # <— added
                    else:
                        if verbose:
                            logging.debug(f"File with same name exists in {target_folder}, skipping {file_name}.", extra={'target': file_name})
                        logging.warning("Skipping - File with same name exists.", extra={'target': os.path.basename(file_name)})
                        if summary: summary.inc('skipped_conflict')  # <— added
                        continue
                try:
                    if verbose:
                        logging.debug(f"Moving {file_name} to {target_folder}", extra={'target': file_name})
                    shutil.move(file_path, target_path)
                    if summary: summary.inc('moved')  # <— added
                    logging.info("Moved file to %s (%s: %s)", target_folder, date_source, date_used.strftime('%Y-%m-%d'), extra={'target': os.path.basename(file_name)})

                    move_sidecar_files(file_path, target_folder, verbose=verbose)
                except FileNotFoundError:
                    logging.error("File could not be moved. File not found.", extra={'target': os.path.basename(file_name)})
                    if summary: summary.inc('errors')  # <— added

    if verbose:
        logging.debug(f"Finished organizing files in {target_dir}", extra={'target': os.path.basename(target_dir)})

def organize_files_by_day(target_dir, mode, rename_files, midnight_shift, verbose=False, summary=None):  # <— summary
    organize_files(target_dir, mode, rename_files, midnight_shift, lambda date: date.strftime('%Y%m%d'), verbose=verbose, summary=summary)

def organize_files_by_week(target_dir, mode, rename_files, midnight_shift, verbose=False, summary=None):  # <— summary
    def get_folder_name(date_used):
        iso_year, iso_week, _ = date_used.isocalendar()
        start_date = datetime.datetime.strptime(f'{iso_year}-W{iso_week}-1', "%G-W%V-%u").date()
        end_date = start_date + datetime.timedelta(days=6)
        return f'{start_date.strftime("%Y%m%d")}-{end_date.strftime("%Y%m%d")} - {WEEK_PREFIX}{iso_week:02d}'
    organize_files(target_dir, mode, rename_files, midnight_shift, get_folder_name, verbose=verbose, summary=summary)

def organize_files_by_month(target_dir, mode, rename_files, midnight_shift, verbose=False, summary=None):  # <— summary
    def get_folder_name(date_used):
        start_date = datetime.datetime(date_used.year, date_used.month, 1)
        end_date = datetime.datetime(date_used.year, date_used.month, calendar.monthrange(date_used.year, date_used.month)[1])
        return f'{start_date.strftime("%Y%m")} - {MONTH_NAMES[date_used.month]} {date_used.year}'
    organize_files(target_dir, mode, rename_files, midnight_shift, get_folder_name, verbose=verbose, summary=summary)

def organize_files_by_year(target_dir, mode, rename_files, midnight_shift, verbose=False, summary=None):  # <— summary
    organize_files(target_dir, mode, rename_files, midnight_shift, lambda date: date.strftime('%Y'), verbose=verbose, summary=summary)

def main():
    parser = argparse.ArgumentParser(
        description=("Organizes media files into subfolders by date (day/week/month/year) using EXIF/ffprobe/sidecar/filename/folder metadata. Automatically moves matching sidecar files."),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-v", "--version", action="version", version=f"ArchiveTools {__version__}")
    parser.add_argument("-f", "--folder", type=str, required=True, help="Path to the folder to process")
    parser.add_argument("--rename", action="store_true", help="Rename files on name conflict instead of skipping")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-d", "--day", action="store_true", help="Organize files by day")
    group.add_argument("-w", "--week", action="store_true", help="Organize files by week")
    group.add_argument("-m", "--month", action="store_true", help="Organize files by month")
    group.add_argument("-y", "--year", action="store_true", help="Organize files by year")

    parser.add_argument(
        "--mode",
        type=str,
        default="default",
        choices=["default", "oldest", "newest", "exif", "ffprobe", "sidecar", "filename", "folder", "metadata"],
        help="Date selection strategy.",
    )
    parser.add_argument(
        "--midnight-shift",
        nargs="?",
        const=3,
        type=int,
        default=0,
        help="Shift dates earlier by N hours to avoid late-night spillover (e.g., 3 moves 00:00–02:59 to the previous day). If flag is provided without a value, defaults to 3.",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    args = parser.parse_args()

    logging.getLogger().setLevel(logging.DEBUG if args.verbose else logging.INFO)

    target_dir = args.folder
    rename_files = args.rename
    mode = args.mode
    midnight_shift = args.midnight_shift

    # summary tracker (tiny + optional)
    s = RunSummary()
    s.set('mode', mode)
    s.set('rename', bool(rename_files))
    s.set('midnight_shift_h', int(midnight_shift or 0))
    granularity = None

    if args.day:
        granularity = 'day'
        organize_files_by_day(target_dir, mode, rename_files, midnight_shift, verbose=args.verbose, summary=s)
    elif args.week:
        granularity = 'week'
        organize_files_by_week(target_dir, mode, rename_files, midnight_shift, verbose=args.verbose, summary=s)
    elif args.month:
        granularity = 'month'
        organize_files_by_month(target_dir, mode, rename_files, midnight_shift, verbose=args.verbose, summary=s)
    elif args.year:
        granularity = 'year'
        organize_files_by_year(target_dir, mode, rename_files, midnight_shift, verbose=args.verbose, summary=s)

    # end-of-run summary (2–3 lines)
    s.set('granularity', granularity)
    found = s['found'] or 0
    moved = s['moved'] or 0
    skipped_no_date = s['skipped_no_date'] or 0
    skipped_conflict = s['skipped_conflict'] or 0
    folders_created = s['folders_created'] or 0
    renamed = s['renamed'] or 0
    skipped_total = skipped_no_date + skipped_conflict

    # source distribution
    source_counts = {k.replace('source_', ''): v for k, v in s.counters.items() if k.startswith('source_')}
    total_src = sum(source_counts.values())
    src_line = None
    if total_src:
        def lab(k): return {'ffprobe': 'FFprobe', 'exif': 'EXIF'}.get(k, k.replace('_', ' ').title())
        parts = [f"{lab(k)} {int(round(100.0*v/total_src))}%" for k, v in sorted(source_counts.items(), key=lambda kv: -kv[1])]
        src_line = "Date sources — " + ", ".join(parts) + "."

    lines = [
        f"Moved {moved}/{found} media files ({skipped_total} skipped: {skipped_no_date} no date, {skipped_conflict} name conflict). "
        f"Created {folders_created} folders in {s.duration_hms}.",
    ]
    if src_line: lines.append(src_line)
    lines.append(f"Renames: {renamed}. Mode: {s['mode']}. Midnight-shift: {s['midnight_shift_h']}h.")
    s.emit_lines(lines, json_extra={
        'found': found, 'moved': moved, 'skipped_no_date': skipped_no_date, 'skipped_conflict': skipped_conflict,
        'folders_created': folders_created, 'renamed': renamed, 'granularity': s['granularity'],
        'mode': s['mode'], 'midnight_shift_h': s['midnight_shift_h'], 'sources': source_counts
    })

if __name__ == "__main__":
    main()
