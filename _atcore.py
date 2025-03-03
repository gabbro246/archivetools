import os
import datetime
from PIL import Image, ExifTags
import logging
from colorama import Fore, Style, init
import hashlib


# logs with color
init(autoreset=True)
class ColoredFormatter(logging.Formatter):
    COLORS = { 'DEBUG': Fore.CYAN, 'INFO': Fore.GREEN, 'WARNING': Fore.YELLOW, 'ERROR': Fore.RED, 'CRITICAL': Fore.MAGENTA}
    def format(self, record):
        if not hasattr(record, 'target'):
            record.target = '-'  # Default value if 'target' is not provided
        log_color = self.COLORS.get(record.levelname, '')
        log_format = f"{log_color}[%(levelname)s]\t%(target)s:\t%(message)s{Style.RESET_ALL}"
        formatter = logging.Formatter(log_format)
        return formatter.format(record)
handler = logging.StreamHandler()
handler.setFormatter(ColoredFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])

# definitions
SIDECAR_EXTENSIONS = ['.xmp', '.json', '.txt', '.srt', '.xml', '.csv', '.ini', '.yaml', '.yml', '.md', '.log', '.nfo', '.sub', '.idx', '.mta', '.vtt', '.lrc']
IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.tiff', '.tif', '.psd', '.heic', '.nef', '.gif', '.bmp', '.dng', '.raw', '.svg', '.webp', '.cr2', '.arw', '.orf', '.rw2', '.ico', '.eps', '.ai', '.indd']
VIDEO_EXTENSIONS = ['.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.webm', '.3gp', '.mpeg', '.mpg', '.m4v', '.mts', '.ts', '.vob', '.mxf', '.ogv', '.rm', '.divx', '.asf', '.f4v', '.m2ts']
MEDIA_EXTENSIONS = list(set(IMAGE_EXTENSIONS + VIDEO_EXTENSIONS))
GERMAN_MONTH_NAMES = {1: 'Januar', 2: 'Februar', 3: 'März', 4: 'April', 5: 'Mai', 6: 'Juni', 7: 'Juli', 8: 'August', 9: 'September', 10: 'Oktober', 11: 'November', 12: 'Dezember'}

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
        logging.warning(f"could not get EXIF data: {e}", extra={'target': os.path.basename(file_path)})

    # Get file creation and modification dates
    try:
        stat = os.stat(file_path)
        dates['Created'] = datetime.datetime.fromtimestamp(stat.st_ctime)
        dates['Modified'] = datetime.datetime.fromtimestamp(stat.st_mtime)
    except Exception as e:
        logging.warning(f"could not get file dates: {e}", extra={'target': os.path.basename(file_path)})

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
                    logging.warning(f"could not read sidecar file: {e}", extra={'target': os.path.basename(sidecar_path)})

    return dates


def select_date(dates: dict, mode: str = 'default') -> list:
    # Define date categories
    exif_dates = {k: v for k, v in dates.items() if 'DateTime' in k}
    sidecar_dates = {k: v for k, v in dates.items() if 'Sidecar' in k}
    metadata_dates = {k: v for k, v in dates.items() if k in ['Created', 'Modified']}

    # Helper function to get the oldest date
    def get_oldest_date(date_dict: dict) -> list:
        if date_dict:
            oldest = min(date_dict.items(), key=lambda x: x[1])
            return [oldest[0], oldest[1]]
        return None

    if mode == 'default':
        return get_oldest_date(exif_dates) or get_oldest_date(sidecar_dates) or get_oldest_date(metadata_dates)

    elif mode == 'oldest':
        return get_oldest_date(dates)

    elif mode == 'exif':
        result = get_oldest_date(exif_dates)
        if result:
            return result
        logging.warning("No EXIF dates found, falling back to default mode.")
        return select_date(dates, 'default')

    elif mode == 'sidecar':
        result = get_oldest_date(sidecar_dates)
        if result:
            return result
        logging.warning("No Sidecar dates found, falling back to default mode.")
        return select_date(dates, 'default')

    elif mode == 'metadata':
        result = get_oldest_date(metadata_dates)
        if result:
            return result
        logging.warning("No Metadata dates found, falling back to default mode.")
        return select_date(dates, 'default')

    else:
        logging.error(f"Unknown mode '{mode}' provided. Falling back to default mode.")
        return select_date(dates, 'default')
    
def calculate_file_hash(file_path):
    """Calculate SHA-256 hash of a file."""
    hash_sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
    except PermissionError as e:
        logging.error(f"Permission error while accessing: {e}", extra={'target': os.path.basename(file_path)})
        raise
    return hash_sha256.hexdigest()