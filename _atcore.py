__version__ = "0.3.2"

import os
import datetime
from PIL import Image, ExifTags
import logging
from colorama import Fore, Style, init
import hashlib
import subprocess
import re
import getpass





# ========================================
# logs with color
# ========================================
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




# ========================================
# definitions
# ========================================
SIDECAR_EXTENSIONS = ['.xmp', '.json', '.txt', '.srt', '.xml', '.csv', '.ini', '.yaml', '.yml', '.md', '.log', '.nfo', '.sub', '.idx', '.mta', '.vtt', '.lrc']
IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.tiff', '.tif', '.psd', '.heic', '.nef', '.gif', '.bmp', '.dng', '.raw', '.svg', '.webp', '.cr2', '.arw', '.orf', '.rw2', '.ico', '.eps', '.ai', '.indd']
VIDEO_EXTENSIONS = ['.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.webm', '.3gp', '.mpeg', '.mpg', '.m4v', '.mts', '.ts', '.vob', '.mxf', '.ogv', '.rm', '.divx', '.asf', '.f4v', '.m2ts']
MEDIA_EXTENSIONS = list(set(IMAGE_EXTENSIONS + VIDEO_EXTENSIONS))
MONTH_NAMES = {1: 'Januar', 2: 'Februar', 3: 'März', 4: 'April', 5: 'Mai', 6: 'Juni', 7: 'Juli', 8: 'August', 9: 'September', 10: 'Oktober', 11: 'November', 12: 'Dezember'}
WEEK_PREFIX = "KW"





# ========================================
# ========================================
def prompt_password(confirm=True):
    """Prompt the user for a password (hidden input). Confirm if needed."""
    password = getpass.getpass("Enter password: ")
    if confirm:
        password_confirm = getpass.getpass("Confirm password: ")
        if password != password_confirm:
            raise ValueError("Passwords do not match.")
    return password





# ========================================
# Function to get all available dates from a file and its sidecar
# ========================================
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
        #logging.warning(f"could not get EXIF data: {e}", extra={'target': os.path.basename(file_path)})
        pass

    # Get file creation and modification dates
    try:
        stat = os.stat(file_path)
        dates['Created'] = datetime.datetime.fromtimestamp(stat.st_ctime)
        dates['Modified'] = datetime.datetime.fromtimestamp(stat.st_mtime)
    except Exception as e:
        logging.warning(f"could not get file dates: {e}", extra={'target': os.path.basename(file_path)})
        
    # Get creation_time from video metadata via ffprobe
    try:
        if os.path.splitext(file_path)[1].lower() in VIDEO_EXTENSIONS:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "format_tags=creation_time",
                 "-of", "default=noprint_wrappers=1:nokey=0", file_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            for line in result.stdout.splitlines():
                if 'creation_time=' in line:
                    raw_date = line.split('=')[1].strip()
                    try:
                        parsed_date = datetime.datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
                        dates['CreationTime'] = parsed_date
                    except ValueError:
                        # handle alternate formats if needed
                        try:
                            parsed_date = datetime.datetime.strptime(raw_date, "%Y-%m-%dT%H:%M:%S.%fZ")
                            dates['FFprobe CreationTime'] = parsed_date
                        except Exception:
                            pass
    except Exception as e:
        logging.warning(f"ffprobe failed: {e}", extra={'target': os.path.basename(file_path)})


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
                    
    # Extract date from filename using common patterns
    filename = os.path.basename(file_path)
    date_patterns = [
        (r"(\d{4})_(\d{2})_(\d{2})_(\d{2})_(\d{2})_(\d{2})", "%Y%m%d%H%M%S"),  # e.g. IMG_2023_04_05_14_52_10
        (r"(\d{4})(\d{2})(\d{2})[_-](\d{2})(\d{2})(\d{2})", "%Y%m%d%H%M%S"),    # e.g. 20230405-145210 or _145210
        (r"(\d{4})[._-](\d{2})[._-](\d{2})", "%Y%m%d"),                        # e.g. 2023-04-05
        (r"(\d{4})(\d{2})(\d{2})", "%Y%m%d"),                                  # e.g. 20230405
    ]
    for pattern, fmt in date_patterns:
        match = re.search(pattern, filename)
        if match:
            try:
                extracted = ''.join(match.groups())
                parsed_date = datetime.datetime.strptime(extracted, fmt)
                dates['Filename'] = parsed_date
                break
            except ValueError:
                continue
            
    # Extract date from parent folder name
    folder_name = os.path.basename(os.path.dirname(file_path))
    try:
        # Day: YYYYMMDD
        if re.match(r"^\d{8}$", folder_name):
            parsed_date = datetime.datetime.strptime(folder_name, "%Y%m%d")
            dates["FolderDate"] = parsed_date

        # Year: YYYY
        elif re.match(r"^\d{4}$", folder_name):
            parsed_date = datetime.datetime.strptime(folder_name, "%Y")
            dates["FolderDate"] = parsed_date

        # Week/Month: YYYYMMDD-YYYYMMDD - ...
        elif re.match(r"^\d{8}-\d{8}", folder_name):
            start_str, end_str = folder_name.split("-")[0], folder_name.split("-")[1].split(" ")[0]
            start_date = datetime.datetime.strptime(start_str, "%Y%m%d")
            end_date = datetime.datetime.strptime(end_str, "%Y%m%d")
            dates["FolderDateRangeStart"] = start_date
            dates["FolderDateRangeEnd"] = end_date
    except Exception as e:
        logging.warning(f"Could not extract date from folder name: {e}", extra={'target': folder_name})

    return dates



    

# ========================================
# ========================================
def select_date(dates: dict, mode: str = 'default', midnight_shift: int = 0) -> list:
    """
    Selects a date from the dictionary of found dates based on the selected mode.
    Returns a list [label, datetime] or None if no valid date was found.
    Applies a midnight shift if specified, adjusting early morning times to the previous day.
    """

    exif_dates = {k: v for k, v in dates.items() if 'DateTime' in k}
    sidecar_dates = {k: v for k, v in dates.items() if 'Sidecar' in k}
    metadata_dates = {k: v for k, v in dates.items() if k in ['Created', 'Modified']}
    ffprobe_dates = {k: v for k, v in dates.items() if 'CreationTime' in k}
    filename_dates = {k: v for k, v in dates.items() if k == 'Filename'}
    folder_dates = {k: v for k, v in dates.items() if k.startswith('FolderDate')}

    def get_oldest(date_dict: dict):
        if date_dict:
            return min(date_dict.items(), key=lambda x: x[1])
        return None

    def get_newest(date_dict: dict):
        if date_dict:
            return max(date_dict.items(), key=lambda x: x[1])
        return None

    selected = None

    if mode == 'default':
        selected = (
            get_oldest(ffprobe_dates) or
            get_oldest(exif_dates) or
            get_oldest(filename_dates) or
            get_oldest(folder_dates) or
            get_oldest(sidecar_dates) or
            get_oldest(metadata_dates)
        )

    elif mode == 'oldest':
        selected = get_oldest(dates)

    elif mode == 'newest':
        selected = get_newest(dates)

    elif mode == 'exif':
        result = get_oldest(exif_dates)
        if result:
            selected = result
        else:
            logging.warning("No EXIF dates found, falling back to default.")
            return select_date(dates, 'default', midnight_shift=midnight_shift)

    elif mode == 'ffprobe':
        result = get_oldest(ffprobe_dates)
        if result:
            selected = result
        else:
            logging.warning("No ffprobe CreationTime found, falling back to default.")
            return select_date(dates, 'default', midnight_shift=midnight_shift)

    elif mode == 'sidecar':
        result = get_oldest(sidecar_dates)
        if result:
            selected = result
        else:
            logging.warning("No sidecar dates found, falling back to default.")
            return select_date(dates, 'default', midnight_shift=midnight_shift)

    elif mode == 'filename':
        result = get_oldest(filename_dates)
        if result:
            selected = result
        else:
            logging.warning("No filename dates found, falling back to default.")
            return select_date(dates, 'default', midnight_shift=midnight_shift)

    elif mode == 'folder':
        result = get_oldest(folder_dates)
        if result:
            selected = result
        else:
            logging.warning("No folder dates found, falling back to default.")
            return select_date(dates, 'default', midnight_shift=midnight_shift)

    elif mode == 'metadata':
        result = get_oldest(metadata_dates)
        if result:
            selected = result
        else:
            logging.warning("No metadata dates found, falling back to default.")
            return select_date(dates, 'default', midnight_shift=midnight_shift)

    else:
        logging.error(f"Unknown mode '{mode}' provided. Falling back to default.")
        return select_date(dates, 'default', midnight_shift=midnight_shift)

    if selected and midnight_shift and selected[1].hour < midnight_shift:
        selected = (selected[0], selected[1] - datetime.timedelta(days=1))

    return selected
    
    
    
    
    
# ========================================
# ========================================
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