import os
import sys
import argparse
import datetime
import logging
import subprocess
from PIL import Image, ExifTags
import piexif
from archivetools import __version__, get_dates_from_file, select_date, SIDECAR_EXTENSIONS, MEDIA_EXTENSIONS, RunSummary

logging.basicConfig(level=logging.INFO, format="[%(levelname)s]\t%(target)s:\t%(message)s")

def set_file_timestamp(file_path, selected_date, dry_run=False, verbose=False):
    if verbose:
        logging.debug(f"{'Would set' if dry_run else 'Setting'} OS timestamps for {file_path} to {selected_date}", extra={'target': os.path.basename(file_path)})
    try:
        if not dry_run:
            os.utime(file_path, (selected_date.timestamp(), selected_date.timestamp()))
        return True
    except Exception as e:
        logging.error("Failed to set file dates: %s", e, extra={'target': os.path.basename(file_path)})
        return False

def set_sidecar_timestamps(file_path, selected_date, dry_run=False, verbose=False):
    base_path, _ = os.path.splitext(file_path)
    updated = False
    for ext in SIDECAR_EXTENSIONS:
        sidecar_path = f"{base_path}{ext}"
        if os.path.exists(sidecar_path):
            if verbose:
                logging.debug(f"{'Would set' if dry_run else 'Setting'} sidecar timestamps for {sidecar_path} to {selected_date}", extra={'target': os.path.basename(sidecar_path)})
            try:
                if not dry_run:
                    os.utime(sidecar_path, (selected_date.timestamp(), selected_date.timestamp()))
                updated = True
            except Exception as e:
                logging.error("Failed to set sidecar file dates: %s", e, extra={'target': os.path.basename(sidecar_path)})
    return updated

def set_exif_date(file_path, selected_date, dry_run=False, verbose=False):
    if verbose:
        logging.debug(f"{'Would set' if dry_run else 'Setting'} EXIF date for {file_path} to {selected_date}", extra={'target': os.path.basename(file_path)})
    try:
        if dry_run:
            return True
        try:
            exif_dict = piexif.load(file_path)
        except Exception:
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
        dt_str = selected_date.strftime("%Y:%m:%d %H:%M:%S")
        exif_dict["0th"][piexif.ImageIFD.DateTime] = dt_str.encode()
        exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = dt_str.encode()
        exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = dt_str.encode()
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, file_path)
        return True
    except Exception as e:
        logging.error("Failed to write EXIF date: %s", e, extra={'target': os.path.basename(file_path)})
        return False

def set_ffprobe_date(file_path, selected_date, dry_run=False, verbose=False):
    if verbose:
        logging.debug(f"{'Would set' if dry_run else 'Setting'} FFprobe creation_time for {file_path} to {selected_date}", extra={'target': os.path.basename(file_path)})
    try:
        if dry_run:
            return True
        temp_file = file_path + ".tmp.mp4"
        cmd = [
            "ffmpeg", "-i", file_path, "-metadata", f"creation_time={selected_date.isoformat()}",
            "-codec", "copy", temp_file, "-y"
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        os.replace(temp_file, file_path)
        return True
    except Exception as e:
        logging.error("Failed to write FFprobe creation_time: %s", e, extra={'target': os.path.basename(file_path)})
        return False

def set_selected_date(file_path, selected_date_info, current_dates, force=False, dry_run=False, verbose=False, summary=None):
    if not selected_date_info:
        if verbose:
            logging.debug(f"No date selected for {file_path}. Skipping.", extra={'target': os.path.basename(file_path)})
        logging.info("No date selected. Skipping.", extra={'target': os.path.basename(file_path)})
        if summary is not None:
            summary.inc('no_date')
        return

    date_source, selected_date = selected_date_info
    actions_taken = []
    # summary counters
    if summary is not None:
        summary.inc('processed')

    if verbose:
        logging.debug(f"Selected date for {file_path}: {selected_date} (source: {date_source})", extra={'target': os.path.basename(file_path)})

    # track source and date range
    if summary is not None:
        summary.inc(f"source_{str(date_source).lower()}")
        # track earliest/latest date
        earliest = summary['earliest_date'] if 'earliest_date' in getattr(summary, 'metrics', {}) else None
        latest = summary['latest_date'] if 'latest_date' in getattr(summary, 'metrics', {}) else None
        try:
            if not earliest or selected_date < earliest:
                summary.set('earliest_date', selected_date)
            if not latest or selected_date > latest:
                summary.set('latest_date', selected_date)
        except Exception:
            pass

    if set_file_timestamp(file_path, selected_date, dry_run=dry_run, verbose=verbose):
        actions_taken.append("File timestamps")
        if summary is not None:
            summary.inc('timestamps')
    else:
        pass
    if set_sidecar_timestamps(file_path, selected_date, dry_run=dry_run, verbose=verbose):
        actions_taken.append("Sidecar(s)")
        if summary is not None:
            summary.inc('sidecars')
    if file_path.lower().endswith(('.jpg', '.jpeg')):
        if set_exif_date(file_path, selected_date, dry_run=dry_run, verbose=verbose):
            actions_taken.append("EXIF")
            if summary is not None:
                summary.inc('exif')
        else:
            # failed EXIF write
            if summary is not None:
                summary.inc('errors')
    if file_path.lower().endswith(('.mp4', '.mov')):
        if set_ffprobe_date(file_path, selected_date, dry_run=dry_run, verbose=verbose):
            actions_taken.append("FFprobe")
            if summary is not None:
                summary.inc('ffprobe')
        else:
            if summary is not None:
                summary.inc('errors')
    if summary is not None and actions_taken:
        summary.inc('updated')
    logging.info("Updated (%s): %s (%s: %s)",
                 ', '.join(actions_taken) if actions_taken else "Nothing",
                 os.path.basename(file_path),
                 date_source,
                 selected_date.strftime('%Y-%m-%d %H:%M:%S'),
                 extra={'target': os.path.basename(file_path)})

def main():
    parser = argparse.ArgumentParser(
        description="Sets the creation and modification timestamps for media files using the best available date from metadata, sidecar, or filename. Supports dry run and force mode.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('-v', '--version', action='version', version=f'ArchiveTools {__version__}')
    parser.add_argument('-f', '--folder', type=str, required=True, help='Path to the folder to process')
    parser.add_argument('--force', action='store_true', help='Force overwrite of all timestamps regardless of age')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without modifying files')
    parser.add_argument('--mode', type=str, default='default', choices=[
        'default', 'oldest', 'newest', 'exif', 'ffprobe', 'sidecar', 'filename', 'folder', 'metadata'
    ], help='Date selection strategy to use.')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)

    folder_path = args.folder
    mode = args.mode
    force = args.force
    dry_run = args.dry_run

    s = RunSummary()
    s.set('mode', mode)
    s.set('dry_run', bool(dry_run))
    s.set('force', bool(force))

    if args.verbose:
        logging.debug(f"Processing folder {folder_path} with mode={mode}", extra={'target': os.path.basename(folder_path)})

    if not os.path.isdir(folder_path):
        logging.error("The specified path is not a directory.", extra={'target': os.path.basename(folder_path)})
        sys.exit(1)

    for file in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file)
        if os.path.isfile(file_path) and os.path.splitext(file)[1].lower() in MEDIA_EXTENSIONS:
            if s: s.inc('processed')
            if args.verbose:
                logging.debug(f"Analyzing file: {file_path}", extra={'target': file})
            current_dates = get_dates_from_file(file_path)
            if args.verbose:
                logging.debug(f"Detected dates for {file}: {current_dates}", extra={'target': file})
            selected_date_info = select_date(current_dates, mode)
            set_selected_date(file_path, selected_date_info, current_dates, force=force, dry_run=dry_run, verbose=args.verbose, summary=s)
        elif args.verbose:
            logging.debug(f"Skipping non-media file: {file_path}", extra={'target': file})

    # End-of-run summary
    processed = s['processed'] or 0
    updated = s['updated'] or 0
    no_date = s['no_date'] or 0

    timestamps = s['timestamps'] or 0
    exif = s['exif'] or 0
    sidecars = s['sidecars'] or 0
    ffprobe = s['ffprobe'] or 0

    earliest = s['earliest_date']
    latest = s['latest_date']

    line1 = (f"Processed {processed} files — {updated} updated, {no_date} had no selected date. "
             f"Mode: {s['mode']}. Dry-run: {'yes' if s['dry_run'] else 'no'}. Force: {'yes' if s['force'] else 'no'}. "
             f"Duration {s.duration_hms}.")

    line2 = f"Applied updates — Timestamps {timestamps}, EXIF {exif}, Sidecars {sidecars}, FFprobe {ffprobe}."

    date_line = None
    if earliest and latest:
        try:
            date_line = "Date range applied: " + earliest.strftime('%Y-%m-%d %H:%M:%S') + " → " + latest.strftime('%Y-%m-%d %H:%M:%S') + "."
        except Exception:
            pass

    lines = [line1, line2]
    if date_line: lines.append(date_line)

    s.emit_lines(lines, json_extra={
        'processed': processed,
        'updated': updated,
        'no_date': no_date,
        'timestamps': timestamps,
        'exif': exif,
        'sidecars': sidecars,
        'ffprobe': ffprobe,
        'earliest_date': str(earliest) if earliest else None,
        'latest_date': str(latest) if latest else None,
        'mode': s['mode'],
        'dry_run': s['dry_run'],
        'force': s['force'],
    })

    if args.verbose:
        logging.debug(f"Finished processing folder {folder_path}", extra={'target': os.path.basename(folder_path)})

if __name__ == "__main__":
    main()
