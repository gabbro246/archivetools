import os
import datetime
import logging
from PIL import Image, ExifTags

# Supported sidecar extensions
SIDECAR_EXTENSIONS = ['.xmp', '.json', '.txt', '.srt']

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
        logging.warning(f"{os.path.basename(file_path)} could not get EXIF data: {e}")

    # Get file creation and modification dates
    try:
        stat = os.stat(file_path)
        dates['Created'] = datetime.datetime.fromtimestamp(stat.st_ctime)
        dates['Modified'] = datetime.datetime.fromtimestamp(stat.st_mtime)
    except Exception as e:
        logging.warning(f"{os.path.basename(file_path)} could not get file dates: {e}")

    # Get dates from sidecar files
    base_path, file_ext = os.path.splitext(file_path)
    for ext in SIDECAR_EXTENSIONS:
        # Handle both sidecar naming conventions
        for sidecar_path in [f"{base_path}{ext}", f"{base_path}{file_ext}{ext}"]:
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
                    logging.warning(f"{os.path.basename(sidecar_path)} could not read sidecar file: {e}")

    return dates
