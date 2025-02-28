import os
import shutil
import argparse
import datetime
import calendar
from _atcore import get_dates_from_file, select_date, SIDECAR_EXTENSIONS, MEDIA_EXTENSIONS, GERMAN_MONTH_NAMES
import logging
from PIL import Image

# Set up logging
logging.basicConfig(level=logging.INFO, format="[%(levelname)s]\t%(target)s:\t%(message)s")

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
                sidecar_name = os.path.basename(sidecar_path)
                target_sidecar_path = os.path.join(target_folder, sidecar_name)
                target_sidecar_path = generate_unique_filename(target_sidecar_path)
                try:
                    shutil.move(sidecar_path, target_sidecar_path)
                    logging.info("Moved sidecar file to %s", target_folder, extra={'target': sidecar_name})
                except FileNotFoundError as e:
                    logging.error("Sidecar file could not be moved. File not found.", extra={'target': sidecar_name})


def generate_unique_filename(target_path):
    base, extension = os.path.splitext(target_path)
    counter = 1
    while os.path.exists(target_path):
        target_path = f"{base}_{counter}{extension}"
        counter += 1
    return target_path


def organize_files(target_dir, mode, rename_files, get_folder_name_func):
    for file_name in os.listdir(target_dir):
        file_path = os.path.join(target_dir, file_name)
        file_extension = os.path.splitext(file_name)[1].lower()
        if os.path.isfile(file_path) and file_extension in MEDIA_EXTENSIONS:
            dates = get_dates_from_file(file_path)
            selected_date_info = select_date(dates, mode=mode)
            if selected_date_info:
                date_source, date_used = selected_date_info
            else:
                logging.info("No valid date found. Skipping.", extra={'target': file_name})
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
                        logging.info("Skipping - File with same name exists.", extra={'target': file_name})
                        continue
                try:
                    shutil.move(file_path, target_path)
                    logging.info("Moved file to %s (%s: %s)", folder_name, date_source, date_used.strftime('%Y-%m-%d'), extra={'target': file_name})
                    move_sidecar_files(file_path, target_folder)
                except FileNotFoundError as e:
                    logging.error("File could not be moved. File not found.", extra={'target': file_name})


def organize_files_by_day(target_dir, mode, rename_files):
    organize_files(target_dir, mode, rename_files, lambda date: date.strftime('%Y%m%d'))


def organize_files_by_week(target_dir, mode, rename_files):
    def get_folder_name(date_used):
        iso_year, iso_week, _ = date_used.isocalendar()
        start_date = datetime.datetime.strptime(f'{iso_year}-W{iso_week}-1', "%G-W%V-%u").date()
        end_date = start_date + datetime.timedelta(days=6)
        return f'{start_date.strftime("%Y%m%d")}-{end_date.strftime("%Y%m%d")} - KW{iso_week:02d}'
    organize_files(target_dir, mode, rename_files, get_folder_name)


def organize_files_by_month(target_dir, mode, rename_files):
    def get_folder_name(date_used):
        start_date = datetime.datetime(date_used.year, date_used.month, 1)
        end_date = datetime.datetime(date_used.year, date_used.month, calendar.monthrange(date_used.year, date_used.month)[1])
        month_name_german = GERMAN_MONTH_NAMES[date_used.month]
        return f'{start_date.strftime("%Y%m%d")}-{end_date.strftime("%Y%m%d")} - {month_name_german}'
    organize_files(target_dir, mode, rename_files, get_folder_name)


def organize_files_by_year(target_dir, mode, rename_files):
    organize_files(target_dir, mode, rename_files, lambda date: date.strftime('%Y'))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Organize files by day, week, month, or year.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-d', '--day', action='store_true', help='Organize files by day')
    group.add_argument('-w', '--week', action='store_true', help='Organize files by week')
    group.add_argument('-m', '--month', action='store_true', help='Organize files by month')
    group.add_argument('-y', '--year', action='store_true', help='Organize files by year')
    parser.add_argument('-f', '--folder', type=str, help='Target folder for organizing files')
    parser.add_argument('--rename', action='store_true', help='Rename files if a file with the same name already exists')
    parser.add_argument('--mode', type=str, default='default', choices=['default', 'oldest', 'exif', 'sidecar', 'metadata'], help='Choose the date selection mode.')
    args = parser.parse_args()

    target_dir = args.folder
    rename_files = args.rename
    mode = args.mode

    if args.day:
        organize_files_by_day(target_dir, mode, rename_files)
    elif args.week:
        organize_files_by_week(target_dir, mode, rename_files)
    elif args.month:
        organize_files_by_month(target_dir, mode, rename_files)
    elif args.year:
        organize_files_by_year(target_dir, mode, rename_files)
