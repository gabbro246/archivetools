import os
import sys
import argparse
import datetime
import logging
import subprocess
from PIL import Image, ExifTags
import piexif
from _atcore import get_dates_from_file, select_date, SIDECAR_EXTENSIONS, MEDIA_EXTENSIONS

# Set up logging
logging.basicConfig(level=logging.INFO, format="[%(levelname)s]\t%(target)s:\t%(message)s")

def set_file_timestamp(file_path, selected_date, dry_run=False):
    try:
        if not dry_run:
            os.utime(file_path, (selected_date.timestamp(), selected_date.timestamp()))
        return True
    except Exception as e:
        logging.error("Failed to set file dates: %s", e, extra={'target': os.path.basename(file_path)})
        return False

def set_sidecar_timestamps(file_path, selected_date, dry_run=False):
    base_path, _ = os.path.splitext(file_path)
    updated = False
    for ext in SIDECAR_EXTENSIONS:
        sidecar_path = f"{base_path}{ext}"
        if os.path.exists(sidecar_path):
            try:
                if not dry_run:
                    os.utime(sidecar_path, (selected_date.timestamp(), selected_date.timestamp()))
                updated = True
            except Exception as e:
                logging.error("Failed to set sidecar file dates: %s", e, extra={'target': os.path.basename(sidecar_path)})
    return updated

def set_exif_date(file_path, selected_date, dry_run=False):
    try:
        if dry_run:
            return True
        # Load or initialize EXIF
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

def set_ffprobe_date(file_path, selected_date, dry_run=False):
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

def set_selected_date(file_path, selected_date_info, current_dates, force=False, dry_run=False):
    if not selected_date_info:
        logging.info("No date selected. Skipping.", extra={'target': os.path.basename(file_path)})
        return

    date_source, selected_date = selected_date_info
    actions_taken = []

    # Always update file timestamps
    if set_file_timestamp(file_path, selected_date, dry_run=dry_run):
        actions_taken.append("File timestamps")

    # Sidecar timestamps
    if set_sidecar_timestamps(file_path, selected_date, dry_run=dry_run):
        actions_taken.append("Sidecar(s)")

    # Write EXIF for JPEGs
    if file_path.lower().endswith(('.jpg', '.jpeg')):
        if set_exif_date(file_path, selected_date, dry_run=dry_run):
            actions_taken.append("EXIF")

    # Write ffprobe metadata for videos
    if file_path.lower().endswith(('.mp4', '.mov')):
        if set_ffprobe_date(file_path, selected_date, dry_run=dry_run):
            actions_taken.append("FFprobe")

    # Summary log line
    logging.info("Updated (%s): %s (%s: %s)",
                 ', '.join(actions_taken) if actions_taken else "Nothing",
                 os.path.basename(file_path),
                 date_source,
                 selected_date.strftime('%Y-%m-%d %H:%M:%S'),
                 extra={'target': os.path.basename(file_path)})

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Set the selected date for media files and sidecar files.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('-f', '--folder', type=str, required=True, help='Target folder to process')
    parser.add_argument('--mode', type=str, default='default', choices=[
        'default', 'oldest', 'newest', 'exif', 'ffprobe', 'sidecar', 'filename', 'folder', 'metadata'
    ], help='Date selection mode')
    parser.add_argument('--force', action='store_true', help='Force overwrite of all timestamps regardless of age')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without modifying files')
    args = parser.parse_args()

    folder_path = args.folder
    mode = args.mode
    force = args.force
    dry_run = args.dry_run

    for file in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file)
        if os.path.isfile(file_path) and os.path.splitext(file)[1].lower() in MEDIA_EXTENSIONS:
            current_dates = get_dates_from_file(file_path)
            selected_date_info = select_date(current_dates, mode)
            set_selected_date(file_path, selected_date_info, current_dates, force=force, dry_run=dry_run)
