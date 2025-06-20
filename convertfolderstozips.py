import os
import shutil
import argparse
import pyzipper
import hashlib
import logging
import sys
from _atcore import __version__, calculate_file_hash, prompt_password

def verify_zipped_contents(folder_path, zip_file_path, password=None, verbose=False):
    if verbose:
        logging.debug(f"Verifying contents of {zip_file_path} against {folder_path}", extra={'target': os.path.basename(zip_file_path)})
    try:
        with pyzipper.AESZipFile(zip_file_path, 'r') as zipf:
            if password:
                zipf.setpassword(password.encode())
            for root, _, files in os.walk(folder_path):
                for file in files:
                    relative_path = os.path.relpath(os.path.join(root, file), folder_path)
                    
                    if relative_path not in zipf.namelist():
                        logging.warning(f"Missing file in zip", extra={'target': os.path.basename(relative_path)})
                        return False

                    original_hash = calculate_file_hash(os.path.join(root, file))
                    zipped_hash = hashlib.sha256(zipf.read(relative_path)).hexdigest()

                    if original_hash != zipped_hash:
                        logging.warning(f"File hash mismatch", extra={'target': os.path.basename(relative_path)})
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

def zip_and_verify(directory, verbose=False):
    if args.aes256:
        if args.aes256 is True:
            try:
                password = prompt_password(confirm=True)
            except ValueError as e:
                logging.error(str(e))
                sys.exit(1)
        else:
            password = args.aes256
    else:
        password = None
    folders = [f for f in os.listdir(directory) if os.path.isdir(os.path.join(directory, f))]
    for folder in folders:
        folder_path = os.path.join(directory, folder)
        zip_file_path = os.path.join(directory, f"{folder}.zip")

        if os.path.exists(zip_file_path):
            logging.warning(f"Zip file already exists. Skipping.", extra={'target': os.path.basename(zip_file_path)})
            if verbose:
                logging.debug(f"Skipping existing zip: {zip_file_path}", extra={'target': os.path.basename(zip_file_path)})
            continue

        if verbose:
            logging.debug(f"Creating ZIP: {zip_file_path} from folder: {folder_path}", extra={'target': os.path.basename(folder_path)})

        try:
            if password:
                with pyzipper.AESZipFile(zip_file_path, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zipf:
                    zipf.setpassword(password.encode())
                    zipf.setencryption(pyzipper.WZ_AES, nbits=256)
                    for root, _, files in os.walk(folder_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, folder_path)
                            if verbose:
                                logging.debug(f"Adding file to ZIP: {arcname}", extra={'target': os.path.basename(file_path)})
                            try:
                                zipf.write(file_path, arcname)
                            except Exception as e:
                                logging.error(f"Failed to write file to zip: {e}", extra={'target': file_path})
                                raise
            else:
                with pyzipper.AESZipFile(zip_file_path, 'w', compression=pyzipper.ZIP_DEFLATED) as zipf:
                    for root, _, files in os.walk(folder_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, folder_path)
                            if verbose:
                                logging.debug(f"Adding file to ZIP: {arcname}", extra={'target': os.path.basename(file_path)})
                            try:
                                zipf.write(file_path, arcname)
                            except Exception as e:
                                logging.error(f"Failed to write file to zip: {e}", extra={'target': file_path})
                                raise

            if verbose:
                logging.debug(f"Starting verification for ZIP: {zip_file_path}", extra={'target': os.path.basename(zip_file_path)})

            if verify_zipped_contents(folder_path, zip_file_path, password, verbose=verbose):
                logging.info(f"Verification successful. Deleting original folder.", extra={'target': os.path.basename(zip_file_path)})
                if verbose:
                    logging.debug(f"Deleting folder: {folder_path}", extra={'target': os.path.basename(folder_path)})
                shutil.rmtree(folder_path)
            else:
                logging.warning(f"Verification failed. Original folder not deleted.", extra={'target': os.path.basename(zip_file_path)})

        except PermissionError as e:
            logging.error(f"Permission error: {e}", extra={'target': os.path.basename(folder_path)})
            if verbose:
                logging.debug(f"Permission error on: {folder_path}", extra={'target': os.path.basename(folder_path)})

        except Exception as e:
            logging.error(f"Error zipping or verifying folder: {e}", extra={'target': os.path.basename(folder)})
            if os.path.exists(zip_file_path):
                if verbose:
                    logging.debug(f"Removing incomplete zip: {zip_file_path}", extra={'target': os.path.basename(zip_file_path)})
                os.remove(zip_file_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compresses each folder in the target directory into a separate ZIP archive. Verifies the integrity of each archive before deleting the original folder.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('-v', '--version', action='version', version=f'ArchiveTools {__version__}')
    parser.add_argument('-f', '--folder', type=str, help='Path to the folder to process')
    parser.add_argument('--aes256', nargs='?', const=True, help='Enable AES-256 encryption. If no password is given, you will be prompted securely.')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)

    directory_to_zip = args.folder
    zip_and_verify(directory_to_zip, verbose=args.verbose)
