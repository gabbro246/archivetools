import os
import sys
import argparse
import datetime
import logging
from PIL import Image, ExifTags

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

# Supported sidecar extensions
SIDECAR_EXTENSIONS = ['.xmp', '.json', '.txt', '.srt']
IMAGE_VIDEO_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.tiff', '.tif', '.mp4', '.mov', '.avi', '.mkv', '.psd', '.heic', '.nef', '.gif', '.bmp', '.flv', '.wmv', '.webm', '.3gp', '.dng']

# Function to get all available dates from a file and its sidecar
def get_dates_from_file(file_path):
    dates = {}
    # Get EXIF dates
    try:
        with Image.open(file_path) as img:
            exif_data = img._getexif()
            if exif_data:
                for tag, value in exif_data.items():
                    decoded = ExifTags.TAGS.get(tag, tag)
                    if decoded in ["DateTime", "DateTimeOriginal", "DateTimeDigitized"]:
                        dates[decoded] = datetime.datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
    except Exception as e:
        logging.warning(f"No EXIF data for {os.path.basename(file_path)}: {e}")

    # Get file creation and modification dates
    try:
        stat = os.stat(file_path)
        dates['Created'] = datetime.datetime.fromtimestamp(stat.st_ctime)
        dates['Modified'] = datetime.datetime.fromtimestamp(stat.st_mtime)
    except Exception as e:
        logging.warning(f"Could not get file dates for {os.path.basename(file_path)}: {e}")

    # Get dates from sidecar files
    base_path, _ = os.path.splitext(file_path)
    for ext in SIDECAR_EXTENSIONS:
        sidecar_path = f"{base_path}{ext}"
        if os.path.exists(sidecar_path):
            try:
                with open(sidecar_path, 'r') as f:
                    for line in f:
                        if 'date' in line.lower():
                            try:
                                potential_date = datetime.datetime.fromisoformat(line.strip())
                                dates[f"Sidecar ({ext})"] = potential_date
                            except ValueError:
                                pass
            except Exception as e:
                logging.warning(f"Could not read sidecar file {os.path.basename(sidecar_path)}: {e}")

    return dates

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
