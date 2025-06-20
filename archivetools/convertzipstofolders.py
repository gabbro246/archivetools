import os
import shutil
import argparse
import pyzipper
import hashlib
import getpass
import logging
import sys
from archivetools import __version__, calculate_file_hash

def verify_unzipped_contents(zip_file_path, extracted_folder_path, password=None, verbose=False):
    if verbose:
        logging.debug(f"Verifying contents of {extracted_folder_path} against {zip_file_path}", extra={'target': os.path.basename(zip_file_path)})
    try:
        with pyzipper.AESZipFile(zip_file_path, 'r') as zipf:
            if password:
                zipf.setpassword(password.encode())
            for zip_info in zipf.infolist():
                file_path = os.path.join(extracted_folder_path, zip_info.filename)
                if not os.path.exists(file_path):
                    logging.warning(f"Missing file in extracted folder", extra={'target': os.path.basename(zip_info.filename)})
                    return False
                original_hash = hashlib.sha256(zipf.read(zip_info.filename)).hexdigest()
                extracted_hash = calculate_file_hash(file_path)
                if original_hash != extracted_hash:
                    logging.warning(f"File hash mismatch", extra={'target': os.path.basename(zip_info.filename)})
                    return False
        if verbose:
            logging.debug("Verification passed.", extra={'target': os.path.basename(zip_file_path)})
        return True
    except PermissionError as e:
        logging.error(f"Permission error during verification: {e}", extra={'target': os.path.basename(zip_file_path)})
        return False
    except Exception as e:
        logging.error(f"Error during verification: {e}")
        return False

def unzip_and_verify(directory, verbose=False):
    global_password = None
    if args.aes256 and args.aes256 is not True:
        global_password = args.aes256

    zip_files = [f for f in os.listdir(directory) if f.endswith(".zip")]
    for zip_file in zip_files:
        zip_file_path = os.path.join(directory, zip_file)
        folder_name = zip_file[:-4]
        extracted_folder_path = os.path.join(directory, folder_name)

        if os.path.exists(extracted_folder_path):
            logging.warning(f"Folder already exists. Skipping.", extra={'target': os.path.basename(folder_name)})
            if verbose:
                logging.debug(f"Skipping existing folder: {extracted_folder_path}", extra={'target': os.path.basename(folder_name)})
            continue

        if verbose:
            logging.debug(f"Extracting ZIP: {zip_file_path} to folder: {extracted_folder_path}", extra={'target': os.path.basename(zip_file_path)})

        try:
            with pyzipper.AESZipFile(zip_file_path, 'r') as zipf:
                needs_password = any(info.flag_bits & 0x1 for info in zipf.infolist())
                if needs_password:
                    if not global_password:
                        global_password = getpass.getpass(f"Enter password for {os.path.basename(zip_file_path)}: ")
                    zipf.setpassword(global_password.encode())
                try:
                    if verbose:
                        logging.debug(f"Extracting files from ZIP: {zip_file_path}", extra={'target': os.path.basename(zip_file_path)})
                    zipf.extractall(extracted_folder_path)
                except RuntimeError as e:
                    if "Bad password" in str(e):
                        logging.warning(f"Wrong password. Asking again.", extra={'target': os.path.basename(zip_file_path)})
                        global_password = getpass.getpass(f"Re-enter password for {os.path.basename(zip_file_path)}: ")
                        zipf.setpassword(global_password.encode())
                        zipf.extractall(extracted_folder_path)
                    else:
                        raise

            if verbose:
                logging.debug(f"Starting verification for extracted folder: {extracted_folder_path}", extra={'target': os.path.basename(zip_file_path)})

            if verify_unzipped_contents(zip_file_path, extracted_folder_path, global_password, verbose=verbose):
                logging.info(f"Verification successful. Deleting zip file.", extra={'target': os.path.basename(zip_file)})
                if verbose:
                    logging.debug(f"Deleting zip file: {zip_file_path}", extra={'target': os.path.basename(zip_file)})
                os.remove(zip_file_path)
            else:
                logging.warning(f"Verification failed. Zip file not deleted.", extra={'target': os.path.basename(zip_file)})

        except PermissionError as e:
            logging.error(f"Permission error: {e}", extra={'target': os.path.basename(zip_file)})
            if verbose:
                logging.debug(f"Permission error on: {zip_file_path}", extra={'target': os.path.basename(zip_file)})
            if os.path.exists(extracted_folder_path):
                shutil.rmtree(extracted_folder_path)
        except Exception as e:
            logging.error(f"Error unzipping or verifying file: {e}", extra={'target': os.path.basename(zip_file)})
            if verbose:
                logging.debug(f"Error encountered. Removing folder: {extracted_folder_path}", extra={'target': os.path.basename(zip_file)})
            if os.path.exists(extracted_folder_path):
                shutil.rmtree(extracted_folder_path)

def main():
    parser = argparse.ArgumentParser(
        description="Extracts all ZIP archives in the target folder into folders with matching names. Verifies that all extracted files match the original content before deleting the ZIP file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('-v', '--version', action='version', version=f'ArchiveTools {__version__}')
    parser.add_argument('-f', '--folder', type=str, help='Path to the folder to process')
    parser.add_argument('--aes256', nargs='?', const=True, help='Password for AES-256 encrypted ZIPs. If omitted, you will be prompted when needed.')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)

    unzip_and_verify(args)

if __name__ == "__main__":
    main()
