import os
import shutil
import argparse
import datetime
import calendar
from _atcore import __version__, get_dates_from_file, select_date, SIDECAR_EXTENSIONS, MEDIA_EXTENSIONS, MONTH_NAMES, WEEK_PREFIX
import logging
from PIL import Image

def move_sidecar_files(file_path, target_folder):
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
                    shutil.move(sidecar_path, target_sidecar_path)
                    logging.info("Moved sidecar file to %s", target_folder, extra={'target': os.path.basename(sidecar_path)})
                except FileNotFoundError as e:
                    logging.error("Sidecar file could not be moved. File not found.", extra={'target': os.path.basename(sidecar_path)})


def generate_unique_filename(target_path):
    base, extension = os.path.splitext(target_path)
    counter = 1
    while os.path.exists(target_path):
        target_path = f"{base}_{counter}{extension}"
        counter += 1
    return target_path


def organize_files(target_dir, mode, rename_files, midnight_shift, get_folder_name_func):
    for file_name in os.listdir(target_dir):
        file_path = os.path.join(target_dir, file_name)
        file_extension = os.path.splitext(file_name)[1].lower()
        if os.path.isfile(file_path) and file_extension in MEDIA_EXTENSIONS:
            dates = get_dates_from_file(file_path)
            selected_date_info = select_date(dates, mode=mode, midnight_shift=midnight_shift)
            if selected_date_info:
                date_source, date_used = selected_date_info
            else:
                logging.info("No valid date found. Skipping.", extra={'target': os.path.basename(file_name)})
                continue

            folder_name = get_folder_name_func(date_used)
            target_folder = os.path.join(target_dir, folder_name)
            os.makedirs(target_folder, exist_ok=True)

            target_path = os.path.join(target_folder, file_name)
            if os.path.exists(file_path):
                if os.path.exists(target_path):
                    if rename_files:
                        target_path = generate_unique_filename(target_path)
                    else:
                        logging.warning("Skipping - File with same name exists.", extra={'target': os.path.basename(file_name)})
                        continue
                try:
                    shutil.move(file_path, target_path)
                    logging.info("Moved file to %s (%s: %s)", folder_name, date_source, date_used.strftime('%Y-%m-%d'), extra={'target': os.path.basename(file_name)})
                    move_sidecar_files(file_path, target_folder)
                except FileNotFoundError as e:
                    logging.error("File could not be moved. File not found.", extra={'target': os.path.basename(file_name)})


def organize_files_by_day(target_dir, mode, rename_files, midnight_shift):
    organize_files(target_dir, mode, rename_files, midnight_shift, lambda date: date.strftime('%Y%m%d'))


def organize_files_by_week(target_dir, mode, rename_files, midnight_shift):
    def get_folder_name(date_used):
        iso_year, iso_week, _ = date_used.isocalendar()
        start_date = datetime.datetime.strptime(f'{iso_year}-W{iso_week}-1', "%G-W%V-%u").date()
        end_date = start_date + datetime.timedelta(days=6)
        return f'{start_date.strftime("%Y%m%d")}-{end_date.strftime("%Y%m%d")} - {WEEK_PREFIX}{iso_week:02d}'
    organize_files(target_dir, mode, rename_files, midnight_shift, get_folder_name)


def organize_files_by_month(target_dir, mode, rename_files, midnight_shift):
    def get_folder_name(date_used):
        start_date = datetime.datetime(date_used.year, date_used.month, 1)
        end_date = datetime.datetime(date_used.year, date_used.month, calendar.monthrange(date_used.year, date_used.month)[1])
        month_name_german = MONTH_NAMES[date_used.month]
        return f'{start_date.strftime("%Y%m%d")}-{end_date.strftime("%Y%m%d")} - {month_name_german}'
    organize_files(target_dir, mode, rename_files, midnight_shift, get_folder_name)


def organize_files_by_year(target_dir, mode, rename_files, midnight_shift):
    organize_files(target_dir, mode, rename_files, midnight_shift, lambda date: date.strftime('%Y'))


import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Organizes media files into subfolders by day, week, month, or year based on metadata, EXIF data, filenames, or sidecar information. Automatically moves matching sidecar files.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('-v', '--version', action='version', version=f'ArchiveTools {__version__}')
    parser.add_argument('-f', '--folder', type=str, required=True, help='Path to the folder to process')
    parser.add_argument('--rename', action='store_true', help='Rename files if duplicates are found')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-d', '--day', action='store_true', help='Organize files by day')
    group.add_argument('-w', '--week', action='store_true', help='Organize files by week')
    group.add_argument('-m', '--month', action='store_true', help='Organize files by month')
    group.add_argument('-y', '--year', action='store_true', help='Organize files by year')
    parser.add_argument('--mode', type=str, default='default', choices=[
            'default', 'oldest', 'newest', 'exif', 'ffprobe', 'sidecar', 'filename', 'folder', 'metadata'
        ], help='Date selection strategy to use.')
    parser.add_argument('--midnight-shift', nargs='?', const=3, type=int, default=0, help="Shift early morning times (e.g., up to 3 AM) to the previous day. Default 3h if no value is given.")
    args = parser.parse_args()

    target_dir = args.folder
    rename_files = args.rename
    mode = args.mode
    midnight_shift = args.midnight_shift

    if args.day:
        organize_files_by_day(target_dir, mode, rename_files, midnight_shift)
    elif args.week:
        organize_files_by_week(target_dir, mode, rename_files, midnight_shift)
    elif args.month:
        organize_files_by_month(target_dir, mode, rename_files, midnight_shift)
    elif args.year:
        organize_files_by_year(target_dir, mode, rename_files, midnight_shift)
