import os
import zipfile
import hashlib
import logging
import shutil
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

def verify_unzipped_contents(zip_file_path, extracted_folder_path):
    """Verify that all files in zip_file_path match the files in extracted_folder_path."""
    try:
        with zipfile.ZipFile(zip_file_path, 'r') as zipf:
            for zip_info in zipf.infolist():
                file_path = os.path.join(extracted_folder_path, zip_info.filename)
                
                # Check if the file exists in the extracted folder
                if not os.path.exists(file_path):
                    logging.warning(f"Missing file in extracted folder: {zip_info.filename}")
                    return False

                # Verify file hash
                original_hash = hashlib.sha256(zipf.read(zip_info.filename)).hexdigest()
                extracted_hash = calculate_file_hash(file_path)
                
                if original_hash != extracted_hash:
                    logging.warning(f"File hash mismatch for {zip_info.filename}")
                    return False
        return True
    except PermissionError as e:
        logging.error(f"Permission error during verification for {zip_file_path}: {e}")
        return False
    except Exception as e:
        logging.error(f"Error during verification: {e}")
        return False

def unzip_and_verify(directory):
    zip_files = [f for f in os.listdir(directory) if f.endswith(".zip")]
    for zip_file in zip_files:
        zip_file_path = os.path.join(directory, zip_file)
        folder_name = zip_file[:-4]  # Remove '.zip' extension
        extracted_folder_path = os.path.join(directory, folder_name)
        
        # Skip if folder already exists
        if os.path.exists(extracted_folder_path):
            logging.warning(f"Folder already exists: {folder_name}. Skipping.")
            continue
        
        try:
            # Extract the zip file
            with zipfile.ZipFile(zip_file_path, 'r') as zipf:
                zipf.extractall(extracted_folder_path)
            
            # Verify and delete the zip file if verification is successful
            if verify_unzipped_contents(zip_file_path, extracted_folder_path):
                logging.info(f"Verification successful for {zip_file}. Deleting zip file.")
                os.remove(zip_file_path)
            else:
                logging.warning(f"Verification failed for {zip_file}. Zip file not deleted.")
        
        except PermissionError as e:
            logging.error(f"Permission error with {zip_file}: {e}")
            # Clean up partially extracted folder if necessary
            if os.path.exists(extracted_folder_path):
                shutil.rmtree(extracted_folder_path)
        
        except Exception as e:
            logging.error(f"Error unzipping or verifying file {zip_file}: {e}")
            # Remove the extracted folder if an error occurred
            if os.path.exists(extracted_folder_path):
                shutil.rmtree(extracted_folder_path)

if __name__ == "__main__":
    # Get directory from command line argument or default to current directory
    directory_to_unzip = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    unzip_and_verify(directory_to_unzip)
