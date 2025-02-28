import os
import shutil
import argparse
from _atcore import logging


def get_new_name(base, extension, target_folder):
    counter = 1
    new_name = f"{base}({counter}){extension}"
    while os.path.exists(os.path.join(target_folder, new_name)):
        counter += 1
        new_name = f"{base}({counter}){extension}"
    return new_name


def flatten_folder(root_folder, rename_files, depth=None):
    if not os.path.isdir(root_folder):
        logging.error("The specified path is not a directory.", extra={'target': os.path.basename(root_folder)})
        return

    current_depth = 0
    prev_file_count = -1
    while True:
        any_folder_found = False
        current_file_count = sum([len(files) for _, _, files in os.walk(root_folder)])

        if current_file_count == prev_file_count:
            logging.warning("No progress detected, stopping to avoid an infinite loop.", extra={'target': os.path.basename(root_folder)})
            break
        prev_file_count = current_file_count

        for subdir in os.listdir(root_folder):
            subdir_path = os.path.join(root_folder, subdir)
            if os.path.isdir(subdir_path):
                any_folder_found = True
                for item in os.listdir(subdir_path):
                    item_path = os.path.join(subdir_path, item)
                    target_path = os.path.join(root_folder, item)

                    if os.path.exists(target_path):
                        if rename_files:
                            base, extension = os.path.splitext(item)
                            new_name = get_new_name(base, extension, root_folder)
                            target_path = os.path.join(root_folder, new_name)
                            logging.info("Renaming to avoid conflict.", extra={'target': os.path.basename(item_path)})
                        else:
                            logging.info("Skipping due to naming conflict.", extra={'target': os.path.basename(item_path)})
                            continue

                    try:
                        shutil.move(item_path, target_path)
                        logging.info("Moved file.", extra={'target': os.path.basename(item_path)})
                    except Exception as e:
                        logging.error(f"Error moving file: {e}", extra={'target': os.path.basename(item_path)})

                if not os.listdir(subdir_path):
                    try:
                        os.rmdir(subdir_path)
                        logging.info("Removed empty folder.", extra={'target': os.path.basename(subdir_path)})
                    except Exception as e:
                        logging.error(f"Could not remove folder: {e}", extra={'target': os.path.basename(subdir_path)})
                else:
                    logging.warning("Skipping deletion: folder is not empty.", extra={'target': os.path.basename(subdir_path)})

        current_depth += 1
        if not any_folder_found or (depth is not None and current_depth >= depth):
            break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Flatten folder structure by moving files up a specified depth.")
    parser.add_argument("-f", "--folder", required=True, help="Path to the folder to be flattened.")
    parser.add_argument("--rename", action="store_true", help="Rename files instead of skipping them.")
    parser.add_argument("--depth", type=int, help="Depth to flatten.")
    args = parser.parse_args()
    flatten_folder(args.folder, args.rename, args.depth)
