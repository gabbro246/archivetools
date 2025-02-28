import os
import shutil
import argparse
import zipfile
import hashlib
import logging
import sys
from _atcore import calculate_file_hash

def verify_unzipped_contents(zip_file_path, extracted_folder_path):
    """Verify that all files in zip_file_path match the files in extracted_folder_path."""
    try:
        with zipfile.ZipFile(zip_file_path, 'r') as zipf:
            for zip_info in zipf.infolist():
                file_path = os.path.join(extracted_folder_path, zip_info.filename)
                
                # Check if the file exists in the extracted folder
                if not os.path.exists(file_path):
                    logging.warning(f"Missing file in extracted folder", extra={'target': os.path.basename(zip_info.filename)})
                    return False

                # Verify file hash
                original_hash = hashlib.sha256(zipf.read(zip_info.filename)).hexdigest()
                extracted_hash = calculate_file_hash(file_path)
                
                if original_hash != extracted_hash:
                    logging.warning(f"File hash mismatch", extra={'target': os.path.basename(zip_info.filename)})
                    return False
        return True
    except PermissionError as e:
        logging.error(f"Permission error during verification: {e}", extra={'target': os.path.basename(zip_file_path)})
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
            logging.warning(f"Folder already exists. Skipping.", extra={'target': os.path.basename(folder_name)})
            continue
        
        try:
            # Extract the zip file
            with zipfile.ZipFile(zip_file_path, 'r') as zipf:
                zipf.extractall(extracted_folder_path)
            
            # Verify and delete the zip file if verification is successful
            if verify_unzipped_contents(zip_file_path, extracted_folder_path):
                logging.info(f"Verification successful. Deleting zip file.", extra={'target': os.path.basename(zip_file)})
                os.remove(zip_file_path)
            else:
                logging.warning(f"Verification failed. Zip file not deleted.", extra={'target': os.path.basename(zip_file)})
        
        except PermissionError as e:
            logging.error(f"Permission error: {e}", extra={'target': os.path.basename(zip_file)})
            # Clean up partially extracted folder if necessary
            if os.path.exists(extracted_folder_path):
                shutil.rmtree(extracted_folder_path)
        
        except Exception as e:
            logging.error(f"Error unzipping or verifying file: {e}", extra={'target': os.path.basename(zip_file)})
            # Remove the extracted folder if an error occurred
            if os.path.exists(extracted_folder_path):
                shutil.rmtree(extracted_folder_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Convert all zip files to folders.')
    parser.add_argument('-f', '--folder', type=str, help='Target folder containing zip files')
    args = parser.parse_args()

    directory_to_unzip = args.folder
    unzip_and_verify(directory_to_unzip)