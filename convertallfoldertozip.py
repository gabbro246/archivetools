import os
import shutil
import argparse
import zipfile
import hashlib
import logging
import sys

# Set up logging to display logs in the terminal
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def calculate_file_hash(file_path):
    """Calculate SHA-256 hash of a file."""
    hash_sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
    except PermissionError as e:
        logging.error(f"Permission error while accessing {file_path}: {e}")
        raise
    return hash_sha256.hexdigest()

def verify_zipped_contents(folder_path, zip_file_path):
    """Verify that all files in folder_path match the files in zip_file_path."""
    try:
        with zipfile.ZipFile(zip_file_path, 'r') as zipf:
            for root, _, files in os.walk(folder_path):
                for file in files:
                    relative_path = os.path.relpath(os.path.join(root, file), folder_path)
                    
                    # Check if file exists in the zip
                    if relative_path not in zipf.namelist():
                        logging.warning(f"Missing file in zip: {relative_path}")
                        return False

                    # Verify file hash
                    original_hash = calculate_file_hash(os.path.join(root, file))
                    zipped_hash = hashlib.sha256(zipf.read(relative_path)).hexdigest()

                    if original_hash != zipped_hash:
                        logging.warning(f"File hash mismatch for {relative_path}")
                        return False
        return True
    except PermissionError as e:
        logging.error(f"Permission error during verification for {zip_file_path}: {e}")
        return False
    except Exception as e:
        logging.error(f"Error during verification: {e}")
        return False

def zip_and_verify(directory):
    folders = [f for f in os.listdir(directory) if os.path.isdir(os.path.join(directory, f))]
    for folder in folders:
        folder_path = os.path.join(directory, folder)
        zip_file_path = os.path.join(directory, f"{folder}.zip")

        # Skip if zip file already exists
        if os.path.exists(zip_file_path):
            logging.warning(f"Zip file already exists: {zip_file_path}. Skipping.")
            continue

        try:
            # Compress the folder into a zip file
            with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(folder_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        zipf.write(file_path, os.path.relpath(file_path, folder_path))

            # Verify and delete the original folder if verification is successful
            if verify_zipped_contents(folder_path, zip_file_path):
                logging.info(f"Verification successful for {zip_file_path}. Deleting original folder.")
                shutil.rmtree(folder_path)
            else:
                logging.warning(f"Verification failed for {zip_file_path}. Original folder not deleted.")

        except PermissionError as e:
            logging.error(f"Permission error with {folder_path}: {e}")

        except Exception as e:
            logging.error(f"Error zipping or verifying folder {folder}: {e}")
            # Remove the zip file if an error occurred
            if os.path.exists(zip_file_path):
                os.remove(zip_file_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Convert all folders to zip archives.')
    parser.add_argument('-f', '--folder', type=str, help='Target folder to convert')
    args = parser.parse_args()

    directory_to_zip = args.folder
    zip_and_verify(directory_to_zip)