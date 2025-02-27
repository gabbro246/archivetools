import os
import sys
import argparse
import datetime
import logging
from PIL import Image, ExifTags
from archivetoolsutils import get_dates_from_file

# Set up logging
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

# Supported sidecar extensions
SIDECAR_EXTENSIONS = ['.xmp', '.json', '.txt', '.srt']
IMAGE_VIDEO_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.tiff', '.tif', '.mp4', '.mov', '.avi', '.mkv', '.psd', '.heic', '.nef', '.gif', '.bmp', '.flv', '.wmv', '.webm', '.3gp', '.dng']

# Function to set the oldest date to file and its sidecar
def set_oldest_date(file_path, dates):
    if not dates:
        logging.info(f"No valid dates found for {os.path.basename(file_path)}. Skipping.")
        return

    oldest_date = min(dates.values())
    date_source = [k for k, v in dates.items() if v == oldest_date][0]
    logging.info(f"{os.path.basename(file_path)} Date set to {oldest_date} from {date_source}")

    # Update file timestamps
    try:
        os.utime(file_path, (oldest_date.timestamp(), oldest_date.timestamp()))
    except Exception as e:
        logging.error(f"Failed to set file dates for {os.path.basename(file_path)}: {e}")

    # Update sidecar file timestamps
    base_path, _ = os.path.splitext(file_path)
    for ext in SIDECAR_EXTENSIONS:
        sidecar_path = f"{base_path}{ext}"
        if os.path.exists(sidecar_path):
            try:
                os.utime(sidecar_path, (oldest_date.timestamp(), oldest_date.timestamp()))
            except Exception as e:
                logging.error(f"Failed to set sidecar file dates for {os.path.basename(sidecar_path)}: {e}")

# Main function to iterate through files in a folder
def process_folder(folder_path):
    for root, _, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            if os.path.splitext(file)[1].lower() in IMAGE_VIDEO_EXTENSIONS:
                dates = get_dates_from_file(file_path)
                set_oldest_date(file_path, dates)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Set the oldest date for media files and sidecar files.')
    parser.add_argument('-f', '--folder', type=str, required=True, help='Target folder to process')
    args = parser.parse_args()
    process_folder(args.folder)
