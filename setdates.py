import os
import sys
import argparse
import datetime
import logging
from PIL import Image, ExifTags
from _atcore import get_dates_from_file, select_date, SIDECAR_EXTENSIONS, MEDIA_EXTENSIONS

# Set up logging
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

# Function to set the selected date to file and its sidecar
def set_selected_date(file_path, date_info):
    if not date_info:
        logging.info(f"No date selected for {os.path.basename(file_path)}. Skipping.")
        return

    date_source, selected_date = date_info
    logging.info(f"{os.path.basename(file_path)} Date set to {selected_date} from {date_source}")

    # Update file timestamps
    try:
        os.utime(file_path, (selected_date.timestamp(), selected_date.timestamp()))
    except Exception as e:
        logging.error(f"Failed to set file dates for {os.path.basename(file_path)}: {e}")

    # Update sidecar file timestamps
    base_path, _ = os.path.splitext(file_path)
    for ext in SIDECAR_EXTENSIONS:
        sidecar_path = f"{base_path}{ext}"
        if os.path.exists(sidecar_path):
            try:
                os.utime(sidecar_path, (selected_date.timestamp(), selected_date.timestamp()))
            except Exception as e:
                logging.error(f"Failed to set sidecar file dates for {os.path.basename(sidecar_path)}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Set the selected date for media files and sidecar files.')
    parser.add_argument('-f', '--folder', type=str, required=True, help='Target folder to process')
    parser.add_argument('-m', '--mode', type=str, default='default', choices=['default', 'oldest', 'exif', 'sidecar', 'metadata'], help='Mode for date selection')
    args = parser.parse_args()
    
    folder_path = args.folder
    mode = args.mode
    
    for file in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file)
        if os.path.isfile(file_path) and os.path.splitext(file)[1].lower() in MEDIA_EXTENSIONS:
            dates = get_dates_from_file(file_path)
            selected_date_info = select_date(dates, mode)
            set_selected_date(file_path, selected_date_info)
