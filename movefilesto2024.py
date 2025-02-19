import os
import shutil
import logging
import time
from datetime import datetime
from PIL import Image, ExifTags

def get_exif_date(file_path):
    """Extract Exif Date Taken from an image."""
    try:
        with Image.open(file_path) as img:
            exif = img._getexif()
            if exif:
                for tag, value in exif.items():
                    decoded = ExifTags.TAGS.get(tag, tag)
                    if decoded == "DateTimeOriginal":
                        return time.strptime(value, "%Y:%m:%d %H:%M:%S")
    except Exception as e:
        logging.warning(f"No Exif data for {file_path}: {e}")
    return None

def get_file_metadata_dates(file_path):
    """Get file creation and modification dates."""
    try:
        creation_time = os.path.getctime(file_path)
        modification_time = os.path.getmtime(file_path)
        return {
            "created": time.gmtime(creation_time),
            "modified": time.gmtime(modification_time),
        }
    except Exception as e:
        logging.warning(f"Error getting metadata for {file_path}: {e}")
        return {"created": None, "modified": None}

def get_oldest_date(file_path):
    """Determine the oldest date among Exif, creation, and modification dates."""
    exif_date = get_exif_date(file_path)
    metadata_dates = get_file_metadata_dates(file_path)

    dates = []
    if exif_date:
        dates.append(exif_date)
    if metadata_dates["created"]:
        dates.append(metadata_dates["created"])
    if metadata_dates["modified"]:
        dates.append(metadata_dates["modified"])

    if dates:
        return min(dates)
    return None

def move_files_with_date_in_2024(folder_path):
    """Move files with the oldest date in 2024 into a subfolder named '2024'."""
    target_folder = os.path.join(folder_path, "2024")
    os.makedirs(target_folder, exist_ok=True)
    
    for root, _, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            if target_folder in file_path:
                continue  # Skip already moved files
            try:
                oldest_date = get_oldest_date(file_path)
                if oldest_date and oldest_date.tm_year == 2024:
                    target_path = os.path.join(target_folder, file)
                    shutil.move(file_path, target_path)
                    logging.info(f"Moved {file_path} to {target_path}")
            except Exception as e:
                logging.error(f"Error processing file {file_path}: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    import sys
    if len(sys.argv) != 2:
        logging.error("Usage: python script.py path/to/folder")
        sys.exit(1)
    
    folder_path = sys.argv[1]
    
    if not os.path.isdir(folder_path):
        logging.error(f"The specified path is not a valid directory: {folder_path}")
        sys.exit(1)
    
    logging.info(f"Processing folder: {folder_path}")
    move_files_with_date_in_2024(folder_path)
    logging.info("Processing complete.")
