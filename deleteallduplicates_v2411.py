import os
import sys
import hashlib
import logging
from collections import defaultdict
from PIL import Image, ExifTags
import mimetypes
import time

def get_file_hash(file_path):
    """Calculate SHA-256 hash of a file."""
    hash_sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception as e:
        logging.error(f"Error hashing file {file_path}: {e}")
        return None

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
        logging.error(f"Error reading Exif data from {file_path}: {e}")
    return None

def get_file_metadata(file_path):
    """Get file creation or modification date as fallback."""
    try:
        creation_time = os.path.getctime(file_path)
        modification_time = os.path.getmtime(file_path)
        return time.gmtime(min(creation_time, modification_time))
    except Exception as e:
        logging.error(f"Error getting metadata for {file_path}: {e}")
        return None

def prioritize_file(files):
    """Determine which file to keep based on rules."""
    files_with_metadata = []
    for file in files:
        exif_date = get_exif_date(file)
        if exif_date:
            files_with_metadata.append((file, exif_date))
    
    if files_with_metadata:
        # Keep the oldest based on Exif Date Taken
        files_with_metadata.sort(key=lambda x: x[1])
        return files_with_metadata[0][0]
    
    # Fallback: Use file creation/modification date
    files_with_dates = [(file, get_file_metadata(file)) for file in files]
    files_with_dates.sort(key=lambda x: x[1])
    return files_with_dates[0][0] if files_with_dates[0][1] else files[0]

def process_folder(folder_path):
    """Process folder to find and handle duplicate files."""
    hash_map = defaultdict(list)
    
    # Traverse directory
    for root, _, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            if mimetypes.guess_type(file_path)[0] in ["image/jpeg", "video/mp4"]:
                file_hash = get_file_hash(file_path)
                if file_hash:
                    hash_map[file_hash].append(file_path)
    
    # Process duplicates
    for file_hash, file_list in hash_map.items():
        if len(file_list) > 1:
            logging.info(f"Duplicate files detected: {file_list}")
            file_to_keep = prioritize_file(file_list)
            logging.info(f"Keeping file: {file_to_keep}")
            for file in file_list:
                if file != file_to_keep:
                    try:
                        os.remove(file)
                        logging.info(f"Deleted file: {file}")
                    except Exception as e:
                        logging.error(f"Error deleting file {file}: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    if len(sys.argv) != 2:
        logging.error("Usage: python script.py path/to/folder")
        sys.exit(1)
    
    folder_path = sys.argv[1]
    
    if not os.path.isdir(folder_path):
        logging.error(f"The specified path is not a valid directory: {folder_path}")
        sys.exit(1)
    
    logging.info(f"Processing folder: {folder_path}")
    process_folder(folder_path)
    logging.info("Processing complete.")
