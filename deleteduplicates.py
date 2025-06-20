import os
import sys
import hashlib
import logging
from collections import defaultdict
import mimetypes
import argparse
from archivetoolscore import __version__, get_dates_from_file, select_date, calculate_file_hash, MEDIA_EXTENSIONS

def prioritize_file(files, mode='default', verbose=False):
    if verbose:
        logging.debug(f"Prioritizing file out of: {files}", extra={'target': os.path.basename(files[0]) if files else '-'})
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
                if verbose:
                    logging.debug(f"Metadata-based tie break: keeping {metadata_dates[0][0]}", extra={'target': os.path.basename(metadata_dates[0][0])})
                return metadata_dates[0][0]
        if verbose:
            logging.debug(f"Keeping {files_with_dates[0][0]}", extra={'target': os.path.basename(files_with_dates[0][0])})
        return files_with_dates[0][0]
    return files[0]

def process_folder(folder_path, mode='default', verbose=False):
    hash_map = defaultdict(list)
    if verbose:
        logging.debug(f"Scanning folder: {folder_path}", extra={'target': os.path.basename(folder_path)})

    for root, _, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            if os.path.splitext(file_path)[1].lower() in MEDIA_EXTENSIONS:
                if verbose:
                    logging.debug(f"Calculating hash for: {file_path}", extra={'target': os.path.basename(file_path)})
                file_hash = calculate_file_hash(file_path)
                if file_hash:
                    hash_map[file_hash].append(file_path)

    for file_hash, file_list in hash_map.items():
        if len(file_list) > 1:
            if verbose:
                logging.debug(f"Duplicate set detected: {file_list}", extra={'target': os.path.basename(folder_path)})
            file_to_keep = prioritize_file(file_list, mode, verbose=verbose)
            deleted_files = []
            for file in file_list:
                if file != file_to_keep:
                    try:
                        if verbose:
                            logging.debug(f"Deleting duplicate: {file}", extra={'target': os.path.basename(file)})
                        os.remove(file)
                        deleted_files.append(os.path.basename(file))
                    except Exception as e:
                        logging.error(f"Error deleting file: {e}", extra={'target': os.path.basename(file)})
            logging.info(f"Kept: {os.path.basename(file_to_keep)}    |    Deleted: {', '.join(deleted_files)}", extra={'target': os.path.basename(folder_path)})

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scans a folder for duplicate image or video files based on file hash. Keeps the most relevant version based on metadata or timestamp and deletes the rest.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('-v', '--version', action='version', version=f'ArchiveTools {__version__}')
    parser.add_argument("-f", "--folder", required=True, help="Path to the folder to process")
    parser.add_argument("--mode", default='default', help="Date selection mode: default, oldest, exif, sidecar, metadata")
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    args = parser.parse_args()
    folder_path = args.folder
    mode = args.mode

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)

    if not os.path.isdir(folder_path):
        logging.error(f"The specified path is not a valid directory", extra={'target': os.path.basename(folder_path)})
        sys.exit(1)

    logging.info(f"Processing folder", extra={'target': os.path.basename(folder_path)})
    process_folder(folder_path, mode, verbose=args.verbose)
    logging.info("Processing complete.", extra={'target': os.path.basename(folder_path)})
