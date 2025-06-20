import os
import sys
import argparse
import datetime
import logging
import subprocess
from PIL import Image, ExifTags
import piexif
from archivetoolscore import __version__, get_dates_from_file, select_date, SIDECAR_EXTENSIONS, MEDIA_EXTENSIONS

logging.basicConfig(level=logging.INFO, format="[%(levelname)s]\t%(target)s:\t%(message)s")

def set_file_timestamp(file_path, selected_date, dry_run=False, verbose=False):
    if verbose:
        logging.debug(f"{'Would set' if dry_run else 'Setting'} file timestamp for {file_path} to {selected_date}", extra={'target': os.path.basename(file_path)})
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
                logging.debug(f"{'Would set' if dry_run else 'Setting'} sidecar timestamp for {sidecar_path} to {selected_date}", extra={'target': os.path.basename(sidecar_path)})
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
        logging.debug(f"{'Would set' if dry_run else 'Setting'} ffprobe creation_time for {file_path} to {selected_date}", extra={'target': os.path.basename(file_path)})
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
        logging.error("Failed to set ffprobe creation_time: %s", e, extra={'target': os.path.basename(file_path)})
        return False

def set_selected_date(file_path, selected_date_info, current_dates, force=False, dry_run=False, verbose=False):
    if not selected_date_info:
        if verbose:
            logging.debug(f"No date selected for {file_path}. Skipping.", extra={'target': os.path.basename(file_path)})
        logging.info("No date selected. Skipping.", extra={'target': os.path.basename(file_path)})
        return

    date_source, selected_date = selected_date_info
    actions_taken = []

    if verbose:
        logging.debug(f"Selected date for {file_path}: {selected_date} (source: {date_source})", extra={'target': os.path.basename(file_path)})

    if set_file_timestamp(file_path, selected_date, dry_run=dry_run, verbose=verbose):
        actions_taken.append("File timestamps")
    if set_sidecar_timestamps(file_path, selected_date, dry_run=dry_run, verbose=verbose):
        actions_taken.append("Sidecar(s)")
    if file_path.lower().endswith(('.jpg', '.jpeg')):
        if set_exif_date(file_path, selected_date, dry_run=dry_run, verbose=verbose):
            actions_taken.append("EXIF")
    if file_path.lower().endswith(('.mp4', '.mov')):
        if set_ffprobe_date(file_path, selected_date, dry_run=dry_run, verbose=verbose):
            actions_taken.append("FFprobe")
    logging.info("Updated (%s): %s (%s: %s)",
                 ', '.join(actions_taken) if actions_taken else "Nothing",
                 os.path.basename(file_path),
                 date_source,
                 selected_date.strftime('%Y-%m-%d %H:%M:%S'),
                 extra={'target': os.path.basename(file_path)})

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Sets the creation and modification timestamps of media files and sidecar files to a selected date. Date source can be EXIF, metadata, sidecar, or filename. Supports dry run and force mode.",
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

    if args.verbose:
        logging.debug(f"Processing folder {folder_path} with mode={mode}", extra={'target': os.path.basename(folder_path)})

    for file in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file)
        if os.path.isfile(file_path) and os.path.splitext(file)[1].lower() in MEDIA_EXTENSIONS:
            if args.verbose:
                logging.debug(f"Analyzing file: {file_path}", extra={'target': file})
            current_dates = get_dates_from_file(file_path)
            if args.verbose:
                logging.debug(f"Detected dates for {file}: {current_dates}", extra={'target': file})
            selected_date_info = select_date(current_dates, mode)
            set_selected_date(file_path, selected_date_info, current_dates, force=force, dry_run=dry_run, verbose=args.verbose)
        elif args.verbose:
            logging.debug(f"Skipping non-media file: {file_path}", extra={'target': file})

    if args.verbose:
        logging.debug(f"Finished processing folder {folder_path}", extra={'target': os.path.basename(folder_path)})
