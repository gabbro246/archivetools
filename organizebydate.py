import os
import shutil
import argparse
import datetime
import calendar
from PIL import Image
from _atcore import get_dates_from_file, select_date, SIDECAR_EXTENSIONS, MEDIA_EXTENSIONS, GERMAN_MONTH_NAMES

def move_sidecar_files(file_path, target_folder):
    base_name, file_extension = os.path.splitext(os.path.basename(file_path))
    base_path = os.path.splitext(file_path)[0]
    
    for ext in SIDECAR_EXTENSIONS:
        # Check both naming patterns
        potential_sidecars = [
            f"{base_path}{ext}",  # filename.sidecarextension
            f"{file_path}{ext}"   # filename.fileextension.sidecarextension
        ]
        
        for sidecar_path in potential_sidecars:
            if os.path.exists(sidecar_path):
                sidecar_name = os.path.basename(sidecar_path)
                target_sidecar_path = os.path.join(target_folder, sidecar_name)
                target_sidecar_path = generate_unique_filename(target_sidecar_path)
                try:
                    shutil.move(sidecar_path, target_sidecar_path)
                    print(f"Moved sidecar file {sidecar_name} to {target_folder}")
                except FileNotFoundError as e:
                    print(f"Error: Sidecar file {sidecar_name} could not be moved. File not found at {sidecar_path}.")


def get_week_ranges(iso_year, iso_week):
    start_date = datetime.datetime.strptime(f'{iso_year}-W{iso_week}-1', "%G-W%V-%u").date()
    end_date = start_date + datetime.timedelta(days=6)
    
    # Compare start_date.year and end_date.year directly
    if start_date.year != end_date.year:
        # Return two ranges if the week crosses the year boundary
        return [(start_date, datetime.datetime(year=start_date.year, month=12, day=31).date()), 
                (datetime.datetime(year=end_date.year, month=1, day=1).date(), end_date)]
    else:
        return [(start_date, end_date)]

def generate_unique_filename(target_path):
    base, extension = os.path.splitext(target_path)
    counter = 1
    while os.path.exists(target_path):
        target_path = f"{base}_{counter}{extension}"
        counter += 1
    return target_path

def organize_files_by_day(target_dir, mode, rename_files):
    for file_name in os.listdir(target_dir):
        file_path = os.path.join(target_dir, file_name)
        file_extension = os.path.splitext(file_name)[1].lower()
        if os.path.isfile(file_path) and file_extension in MEDIA_EXTENSIONS:
            dates = get_dates_from_file(file_path)
            selected_date_info = select_date(dates, mode=mode)
            if selected_date_info:
                date_source, date_used = selected_date_info
            else:
                print(f"No valid date found for {file_path}")
                continue

            folder_name = date_used.strftime('%Y%m%d')
            target_folder = os.path.join(target_dir, folder_name)
            os.makedirs(target_folder, exist_ok=True)

            target_path = os.path.join(target_folder, file_name)
            
            if os.path.exists(file_path):
                if os.path.exists(target_path):
                    if rename_files:
                        target_path = generate_unique_filename(target_path)
                    else:
                        print(f"Skipping {file_name} - A file with the same name already exists in {folder_name}.")
                        continue
                try:
                    shutil.move(file_path, target_path)
                    print(f"{file_name}\tDate used: {date_source} ({date_used})\tMoved to: {folder_name}")
                    move_sidecar_files(file_path, target_folder)
                except FileNotFoundError as e:
                    print(f"Error: {file_name} could not be moved. File not found at {file_path}.")
            else:
                print(f"Warning: {file_name} does not exist at the expected location.")

def organize_files_by_week(target_dir, mode, rename_files):
    for file_name in os.listdir(target_dir):
        file_path = os.path.join(target_dir, file_name)
        file_extension = os.path.splitext(file_name)[1].lower()
        if os.path.isfile(file_path) and file_extension in MEDIA_EXTENSIONS:
            dates = get_dates_from_file(file_path)
            selected_date_info = select_date(dates, mode=mode)  
            if selected_date_info:
                date_source, date_used = selected_date_info
            else:
                print(f"No valid date found for {file_path}")
                continue

            iso_year, iso_week, _ = date_used.isocalendar()
            week_ranges = get_week_ranges(iso_year, iso_week)

            for start_date, end_date in week_ranges:
                folder_name = f'{start_date.strftime("%Y%m%d")}-{end_date.strftime("%Y%m%d")} - KW{iso_week:02d}'
                target_folder = os.path.join(target_dir, folder_name)
                os.makedirs(target_folder, exist_ok=True)

                target_path = os.path.join(target_folder, file_name)
                
                if os.path.exists(file_path):
                    if os.path.exists(target_path):
                        if rename_files:
                            target_path = generate_unique_filename(target_path)
                        else:
                            print(f"Skipping {file_name} - A file with the same name already exists in {folder_name}.")
                            continue
                    try:
                        shutil.move(file_path, target_path)
                        print(f"{file_name}\tDate used: {date_source} ({date_used})\tMoved to: {folder_name}")
                        move_sidecar_files(file_path, target_folder)
                    except FileNotFoundError as e:
                        print(f"Error: {file_name} could not be moved. File not found at {file_path}.")
                else:
                    print(f"Warning: {file_name} does not exist at the expected location.")

def organize_files_by_month(target_dir, mode, rename_files):
    for file_name in os.listdir(target_dir):
        file_path = os.path.join(target_dir, file_name)
        file_extension = os.path.splitext(file_name)[1].lower()
        if os.path.isfile(file_path) and file_extension in MEDIA_EXTENSIONS:
            dates = get_dates_from_file(file_path)
            selected_date_info = select_date(dates, mode=mode) 
            if selected_date_info:
                date_source, date_used = selected_date_info
            else:
                print(f"No valid date found for {file_path}")
                continue

            start_date = datetime.datetime(date_used.year, date_used.month, 1)
            end_date = datetime.datetime(date_used.year, date_used.month, calendar.monthrange(date_used.year, date_used.month)[1])
            month_name_german = GERMAN_MONTH_NAMES[date_used.month]
            folder_name = f'{start_date.strftime("%Y%m%d")}-{end_date.strftime("%Y%m%d")} - {month_name_german}'
            target_folder = os.path.join(target_dir, folder_name)
            os.makedirs(target_folder, exist_ok=True)

            target_path = os.path.join(target_folder, file_name)
            
            if os.path.exists(file_path):
                if os.path.exists(target_path):
                    if rename_files:
                        target_path = generate_unique_filename(target_path)
                    else:
                        print(f"Skipping {file_name} - A file with the same name already exists in {folder_name}.")
                        continue
                try:
                    shutil.move(file_path, target_path)
                    print(f"{file_name}\tDate used: {date_source} ({date_used})\tMoved to: {folder_name}")
                    move_sidecar_files(file_path, target_folder)
                except FileNotFoundError as e:
                    print(f"Error: {file_name} could not be moved. File not found at {file_path}.")
            else:
                print(f"Warning: {file_name} does not exist at the expected location.")

def organize_files_by_year(target_dir, mode, rename_files):
    for file_name in os.listdir(target_dir):
        file_path = os.path.join(target_dir, file_name)
        file_extension = os.path.splitext(file_name)[1].lower()
        if os.path.isfile(file_path) and file_extension in MEDIA_EXTENSIONS:
            dates = get_dates_from_file(file_path)
            selected_date_info = select_date(dates, mode=mode) 
            if selected_date_info:
                date_source, date_used = selected_date_info
            else:
                print(f"No valid date found for {file_path}")
                continue


            folder_name = date_used.strftime('%Y')
            target_folder = os.path.join(target_dir, folder_name)
            os.makedirs(target_folder, exist_ok=True)

            target_path = os.path.join(target_folder, file_name)
            
            if os.path.exists(file_path):
                if os.path.exists(target_path):
                    if rename_files:
                        target_path = generate_unique_filename(target_path)
                    else:
                        print(f"Skipping {file_name} - A file with the same name already exists in {folder_name}.")
                        continue
                try:
                    shutil.move(file_path, target_path)
                    print(f"{file_name}\tDate used: {date_source} ({date_used})\tMoved to: {folder_name}")
                    move_sidecar_files(file_path, target_folder)
                except FileNotFoundError as e:
                    print(f"Error: {file_name} could not be moved. File not found at {file_path}.")
            else:
                print(f"Warning: {file_name} does not exist at the expected location.")

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
