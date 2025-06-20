import os
import shutil
import argparse
from archivetools import __version__, logging

def get_new_name(base, extension, target_folder, verbose=False):
    counter = 1
    new_name = f"{base}({counter}){extension}"
    while os.path.exists(os.path.join(target_folder, new_name)):
        counter += 1
        new_name = f"{base}({counter}){extension}"
    if verbose:
        logging.debug(f"Generated new filename to avoid conflict: {new_name}", extra={'target': new_name})
    return new_name

def flatten_folder(root_folder, rename_files, depth=None, verbose=False):
    if not os.path.isdir(root_folder):
        logging.error("The specified path is not a directory.", extra={'target': os.path.basename(root_folder)})
        return

    if verbose:
        logging.debug(f"Starting to flatten folder: {root_folder}", extra={'target': os.path.basename(root_folder)})

    current_depth = 0
    prev_file_count = -1
    while True:
        any_folder_found = False
        current_file_count = sum([len(files) for _, _, files in os.walk(root_folder)])

        if current_file_count == prev_file_count:
            if verbose:
                logging.warning("No progress detected, stopping to avoid an infinite loop.", extra={'target': os.path.basename(root_folder)})
            break
        prev_file_count = current_file_count

        for subdir in os.listdir(root_folder):
            subdir_path = os.path.join(root_folder, subdir)
            if os.path.isdir(subdir_path):
                any_folder_found = True
                if verbose:
                    logging.debug(f"Processing subdirectory: {subdir_path}", extra={'target': subdir})
                for item in os.listdir(subdir_path):
                    item_path = os.path.join(subdir_path, item)
                    target_path = os.path.join(root_folder, item)

                    if os.path.exists(target_path):
                        if rename_files:
                            base, extension = os.path.splitext(item)
                            new_name = get_new_name(base, extension, root_folder, verbose=verbose)
                            target_path = os.path.join(root_folder, new_name)
                            logging.info("Renaming to avoid conflict.", extra={'target': os.path.basename(item_path)})
                            if verbose:
                                logging.debug(f"Renamed {item} to {new_name}", extra={'target': new_name})
                        else:
                            logging.info("Skipping due to naming conflict.", extra={'target': os.path.basename(item_path)})
                            if verbose:
                                logging.debug(f"Conflict found for {item}, skipping move.", extra={'target': item})
                            continue

                    try:
                        if verbose:
                            logging.debug(f"Moving file: {item_path} -> {target_path}", extra={'target': os.path.basename(item_path)})
                        shutil.move(item_path, target_path)
                        logging.info("Moved file.", extra={'target': os.path.basename(item_path)})
                    except Exception as e:
                        logging.error(f"Error moving file: {e}", extra={'target': os.path.basename(item_path)})

                if not os.listdir(subdir_path):
                    try:
                        if verbose:
                            logging.debug(f"Removing empty folder: {subdir_path}", extra={'target': subdir})
                        os.rmdir(subdir_path)
                        logging.info("Removed empty folder.", extra={'target': os.path.basename(subdir_path)})
                    except Exception as e:
                        logging.error(f"Could not remove folder: {e}", extra={'target': os.path.basename(subdir_path)})
                else:
                    logging.warning("Skipping deletion: folder is not empty.", extra={'target': os.path.basename(subdir_path)})

        current_depth += 1
        if not any_folder_found or (depth is not None and current_depth >= depth):
            if verbose:
                logging.debug(f"Stopping at depth {current_depth}", extra={'target': os.path.basename(root_folder)})
            break

    if verbose:
        logging.debug(f"Flattening complete for: {root_folder}", extra={'target': os.path.basename(root_folder)})

def main():
    parser = argparse.ArgumentParser(
        description="Flattens a folder structure by moving all files from subfolders into the root folder. Can optionally rename conflicting files and limit the operation by depth.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('-v', '--version', action='version', version=f'ArchiveTools {__version__}')
    parser.add_argument("-f", "--folder", required=True, help="Path to the folder to process")
    parser.add_argument("--rename", action="store_true", help="Rename files instead of skipping them")
    parser.add_argument("--depth", type=int, help="Depth to flatten")
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)
    
    flatten_folder(args.folder, args.rename, args.depth, verbose=args.verbose)

if __name__ == "__main__":
    main()
