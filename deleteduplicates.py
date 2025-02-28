import os
import sys
import hashlib
import logging
from collections import defaultdict
import mimetypes
import argparse
from _atcore import get_dates_from_file, select_date, calculate_file_hash


def prioritize_file(files, mode='default'):
    """Determine which file to keep based on date selection rules."""
    files_with_dates = []
    for file in files:
        dates = get_dates_from_file(file)
        selected_date = select_date(dates, mode)
        if selected_date:
            files_with_dates.append((file, selected_date[1]))

    if files_with_dates:
        files_with_dates.sort(key=lambda x: x[1])
        if len(files_with_dates) > 1 and files_with_dates[0][1] == files_with_dates[1][1]:
            metadata_dates = []
            for file in files:
                dates = get_dates_from_file(file)
                selected_metadata_date = select_date(dates, "metadata")
                if selected_metadata_date:
                    metadata_dates.append((file, selected_metadata_date[1]))

            if metadata_dates:
                metadata_dates.sort(key=lambda x: x[1])
                return metadata_dates[0][0]

        return files_with_dates[0][0]

    return files[0]  # Fallback if no dates found



def process_folder(folder_path, mode='default'):
    """Process folder to find and handle duplicate files."""
    hash_map = defaultdict(list)

    # Traverse directory
    for root, _, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            if mimetypes.guess_type(file_path)[0] in ["image/jpeg", "video/mp4"]:
                file_hash = calculate_file_hash(file_path)
                if file_hash:
                    hash_map[file_hash].append(file_path)

    # Process duplicates
    for file_hash, file_list in hash_map.items():
        if len(file_list) > 1:
            file_to_keep = prioritize_file(file_list, mode)
            deleted_files = []
            for file in file_list:
                if file != file_to_keep:
                    try:
                        os.remove(file)
                        deleted_files.append(os.path.basename(file))
                    except Exception as e:
                        logging.error(f"Error deleting file: {e}", extra={'target': os.path.basename(file)})
            logging.info(f"Kept: {os.path.basename(file_to_keep)}    |    Deleted: {', '.join(deleted_files)}", extra={'target': os.path.basename(folder_path)})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Delete duplicate files based on hash and metadata.")
    parser.add_argument("-f", "--folder", required=True, help="Path to the folder to process")
    parser.add_argument("--mode", default='default', help="Date selection mode: default, oldest, exif, sidecar, metadata")
    args = parser.parse_args()
    folder_path = args.folder
    mode = args.mode

    if not os.path.isdir(folder_path):
        logging.error(f"The specified path is not a valid directory", extra={'target': os.path.basename(folder_path)})
        sys.exit(1)

    logging.info(f"Processing folder", extra={'target': os.path.basename(folder_path)})
    process_folder(folder_path, mode)
    logging.info("Processing complete.", extra={'target': os.path.basename(folder_path)})
