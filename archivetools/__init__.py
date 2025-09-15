from .__version__ import __version__

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
    COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.MAGENTA
    }

    def format(self, record):
        if not hasattr(record, 'target'):
            record.target = '-'  # Default value if 'target' is not provided
        log_color = self.COLORS.get(record.levelname, '')
        log_format = (
            f"{log_color}[%(levelname)s]\t%(target)s:\t%(message)s{Style.RESET_ALL}"
        )
        formatter = logging.Formatter(log_format)
        return formatter.format(record)
handler = logging.StreamHandler()
handler.setFormatter(ColoredFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])




# ========================================
# definitions
# ========================================
SIDECAR_EXTENSIONS = ['.aae', '.xmp', '.json', '.txt', '.srt', '.xml', '.csv', '.ini', '.yaml', '.yml', '.md', '.log', '.nfo', '.sub', '.idx', '.mta', '.vtt', '.lrc']
IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.tiff', '.tif', '.psd', '.heic', '.nef', '.gif', '.bmp', '.dng', '.raw', '.svg', '.webp', '.cr2', '.arw', '.orf', '.rw2', '.ico', '.eps', '.ai', '.indd']
VIDEO_EXTENSIONS = ['.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.webm', '.3gp', '.mpeg', '.mpg', '.m4v', '.mts', '.ts', '.vob', '.mxf', '.ogv', '.rm', '.divx', '.asf', '.f4v', '.m2ts', '.nev']
OTHER_EXTENSIONS = ['.gpx', '.kmz', '.kml']
JUNK_FILENAMES = ["desktop.ini", ".DS_Store", "Thumbs.db", ".Spotlight-V100", ".Trashes", "__MACOSX"]
JUNK_PREFIXES = ["._"]
MEDIA_EXTENSIONS = list(set(IMAGE_EXTENSIONS + VIDEO_EXTENSIONS + OTHER_EXTENSIONS))
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
    except Exception:
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
        for sidecar_path in [f"{base_path}{ext}", f"{base_path}{file_ext}{ext}"]:
            if os.path.exists(sidecar_path):
                try:
                    with open(sidecar_path, 'r') as f:
                        if ext == '.json':
                            try:
                                import json
                                sidecar_data = json.load(f)
                                if 'date' in sidecar_data:
                                    try:
                                        date_value = sidecar_data['date']
                                        parsed_date = datetime.datetime.fromisoformat(date_value)
                                        dates[f"Sidecar ({ext})"] = parsed_date
                                    except ValueError:
                                        pass
                            except Exception as e:
                                logging.warning(f"could not parse JSON sidecar file: {e}", extra={'target': os.path.basename(sidecar_path)})
                        else:
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
        (r"(\d{4})_(\d{2})_(\d{2})_(\d{2})_(\d{2})_(\d{2})", "%Y%m%d%H%M%S"),
        (r"(\d{4})(\d{2})(\d{2})[_-](\d{2})(\d{2})(\d{2})", "%Y%m%d%H%M%S"),
        (r"(\d{4})[._-](\d{2})[._-](\d{2})", "%Y%m%d"),
        (r"(\d{4})(\d{2})(\d{2})", "%Y%m%d"),
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
        if re.match(r"^\d{8}$", folder_name):
            parsed_date = datetime.datetime.strptime(folder_name, "%Y%m%d")
            dates["FolderDate"] = parsed_date
        elif re.match(r"^\d{4}$", folder_name):
            parsed_date = datetime.datetime.strptime(folder_name, "%Y")
            dates["FolderDate"] = parsed_date
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

# ========================================
# summary helpers (end-of-run reporting)
# ========================================
from collections import defaultdict
from datetime import timedelta

def human_bytes(num_bytes: int) -> str:
    """Return human friendly size (e.g., '31.7 GB')."""
    try:
        num = float(num_bytes)
    except Exception:
        return str(num_bytes)
    units = ['B','KB','MB','GB','TB','PB']
    for unit in units:
        if num < 1024.0 or unit == units[-1]:
            return f"{num:.1f} {unit}" if unit != 'B' else f"{int(num)} {unit}"
        num /= 1024.0

def format_duration(seconds: float) -> str:
    """Return HH:MM:SS for a duration in seconds."""
    if seconds is None:
        return "00:00:00"
    td = timedelta(seconds=int(round(seconds)))
    total_seconds = int(td.total_seconds())
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

class RunSummary:
    """
    Lightweight tracker for end-of-run summaries.

    Usage:
        s = RunSummary()
        s.inc('processed', 3)
        s.add_bytes('freed_bytes', 12_345_678)
        # ... do your work ...
        s.emit_lines([
            f"Processed {s['processed']} items in {s.duration_hms}.",
            f"Freed {s.hbytes('freed_bytes')}. Failures: {s['failed']}.",
        ], json_extra={'processed': s['processed'], 'failed': s['failed']})
    """
    def __init__(self):
        self._t0 = datetime.datetime.now()
        self._t1 = None
        self.counters = defaultdict(int)   # any numeric counters
        self.metrics  = {}                 # arbitrary other values
        self.notes = []                    # misc strings (e.g., sample failures)

    # timing
    @property
    def duration_s(self) -> float:
        end = self._t1 or datetime.datetime.now()
        return (end - self._t0).total_seconds()

    @property
    def duration_hms(self) -> str:
        return format_duration(self.duration_s)

    def stop(self):
        self._t1 = datetime.datetime.now()

    # counters & metrics
    def inc(self, key: str, n: int = 1):
        self.counters[key] += n

    def add_bytes(self, key: str, n: int):
        self.counters[key] += int(n)

    def set(self, key: str, value):
        self.metrics[key] = value

    def note(self, text: str):
        self.notes.append(text)

    def __getitem__(self, key: str):
        # convenience for counters/metrics
        if key in self.counters:
            return self.counters[key]
        return self.metrics.get(key)

    def hbytes(self, key: str) -> str:
        """human-readable bytes for a counter/metric name."""
        val = self[key]
        return human_bytes(int(val or 0))

    # emission
    def emit_lines(self, lines, level=logging.INFO, json_extra=None):
        """Log one or more human lines, then a compact JSON line at DEBUG."""
        self.stop()
        # Human-readable lines
        for line in lines:
            logging.log(level, line, extra={'target': 'SUMMARY'})
        # Optional JSON line for machines
        try:
            payload = {
                'duration_s': int(round(self.duration_s)),
                'counters': dict(self.counters),
                'metrics': self.metrics,
            }
            if self.notes:
                payload['notes'] = self.notes
            if json_extra:
                payload.update(json_extra)
            logging.debug("%s", payload, extra={'target': 'SUMMARY'})
        except Exception:
            # Never let summary logging crash the script
            pass
