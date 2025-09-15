import os
import shutil
import argparse
import pyzipper
import logging
from archivetools import __version__, calculate_file_hash, RunSummary, prompt_password


def verify_unzipped_contents(zip_file_path, extracted_folder_path, password=None, verbose=False):
    """
    Verify that the extracted folder matches the ZIP contents by comparing SHA-256 per file.
    Returns True on full match, False otherwise.
    """
    zip_name = os.path.basename(zip_file_path)
    if verbose:
        logging.debug(
            f"Verifying contents of {os.path.basename(extracted_folder_path)} against {zip_name}",
            extra={'target': zip_name},
        )
    try:
        with pyzipper.AESZipFile(zip_file_path, 'r') as zipf:
            if password:
                zipf.setpassword(str(password).encode())
            members = [m for m in zipf.namelist() if not m.endswith('/')]
            # ensure each zip member exists and matches the extracted counterpart
            for rel in members:
                extracted_path = os.path.join(extracted_folder_path, rel)
                if not os.path.exists(extracted_path):
                    logging.error("Verification failed: missing extracted file %s", rel, extra={'target': zip_name})
                    return False
                # hash extracted file
                try:
                    extracted_hash = calculate_file_hash(extracted_path)
                except Exception as e:
                    logging.error("Verification failed: cannot hash extracted %s (%s)", rel, e, extra={'target': zip_name})
                    return False
                # hash zip member bytes
                import hashlib
                h = hashlib.sha256()
                with zipf.open(rel, 'r') as zf:
                    for chunk in iter(lambda: zf.read(4096), b""):
                        h.update(chunk)
                if h.hexdigest() != extracted_hash:
                    logging.error("Verification failed: checksum mismatch for %s", rel, extra={'target': zip_name})
                    return False
    except RuntimeError as e:
        logging.error("Verification error (password/encryption): %s", e, extra={'target': zip_name})
        return False
    except Exception as e:
        logging.error("Error during verification: %s", e, extra={'target': zip_name})
        return False

    if verbose:
        logging.debug("Verification OK", extra={'target': zip_name})
    return True


def extract_zip(zip_file_path, target_folder, password=None, verbose=False, summary=None):
    """
    Extract the entire zip to target_folder. Returns True on success, False otherwise.
    Increments 'files_extracted' and 'bytes_out' counters on success.
    """
    s = summary
    zip_name = os.path.basename(zip_file_path)
    try:
        with pyzipper.AESZipFile(zip_file_path, 'r') as zipf:
            if password:
                zipf.setpassword(str(password).encode())
            infos = [i for i in zipf.infolist() if not i.is_dir()]
            for info in infos:
                dest_path = os.path.join(target_folder, info.filename)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                if verbose:
                    logging.debug(f"Extracting {info.filename}", extra={'target': zip_name})
                with zipf.open(info, 'r') as src, open(dest_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
                if s:
                    s.inc('files_extracted')
                    try:
                        s.add_bytes('bytes_out', os.path.getsize(dest_path))
                    except OSError:
                        pass
        return True
    except RuntimeError as e:
        # wrong/missing password most likely
        logging.error("Extraction error (password/encryption): %s", e, extra={'target': zip_name})
        if s:
            s.inc('errors')
        return False
    except Exception as e:
        logging.error("Error extracting zip: %s", e, extra={'target': zip_name})
        if s:
            s.inc('errors')
        return False


def unzip_and_verify(args):
    directory = args.folder
    verbose = args.verbose

    # Summary tracker
    s = RunSummary()
    # AES-256 flag might be provided with or without a password string
    provided_password = None
    if args.aes256 and args.aes256 is not True:
        provided_password = str(args.aes256)
    s.set('aes256', bool(args.aes256))

    # process .zip files in the given directory (non-recursive)
    zip_files = [f for f in os.listdir(directory) if f.lower().endswith(".zip")]
    total = len(zip_files)

    for zip_file in zip_files:
        zip_path = os.path.join(directory, zip_file)
        folder_name = os.path.splitext(zip_file)[0]
        target_folder = os.path.join(directory, folder_name)

        s.inc('zips_scanned')
        if verbose:
            logging.debug("Processing archive", extra={'target': zip_file})

        if os.path.exists(target_folder):
            logging.info("Folder already exists. Skipping.", extra={'target': folder_name})
            s.inc('skipped_exists')
            continue

        # choose password strategy
        password = provided_password

        # 1) extract
        ok = extract_zip(zip_path, target_folder, password=password, verbose=verbose, summary=s)
        if not ok and (args.aes256 is True or password is None):
            # If user passed --aes256 (no value) or no password was provided, prompt once and retry
            try:
                pw = prompt_password(confirm=False)
            except Exception as e:
                logging.error("Password input error: %s", e, extra={'target': zip_file})
                s.inc('password_failures')
                continue
            if pw:
                s.inc('password_prompts')
                ok = extract_zip(zip_path, target_folder, password=pw, verbose=verbose, summary=s)
                if not ok:
                    s.inc('password_failures')

        if not ok:
            s.inc('extract_failures')
            # tidy up empty partial folder
            try:
                if os.path.isdir(target_folder) and not os.listdir(target_folder):
                    os.rmdir(target_folder)
            except Exception:
                pass
            continue

        s.inc('extracted')

        # 2) verify
        verified = verify_unzipped_contents(zip_path, target_folder, password=password, verbose=verbose)
        if not verified:
            s.inc('verify_failures')
            logging.warning("Verification failed — keeping zip and extracted folder.", extra={'target': zip_file})
            continue

        s.inc('verified_ok')

        # 3) delete zip on success
        try:
            os.remove(zip_path)
            s.inc('zips_deleted')
            logging.info("Verification OK — deleted original zip.", extra={'target': zip_file})
        except Exception as e:
            logging.error("Failed to delete zip after verification: %s", e, extra={'target': zip_file})
            s.inc('errors')

    # Emit end-of-run summary
    zips_scanned = s['zips_scanned'] or 0
    extracted = s['extracted'] or 0
    skipped = s['skipped_exists'] or 0
    verified_ok = s['verified_ok'] or 0
    zips_deleted = s['zips_deleted'] or 0
    extract_failures = s['extract_failures'] or 0
    verify_failures = s['verify_failures'] or 0
    files_extracted = s['files_extracted'] or 0
    errors = s['errors'] or 0
    prompts = s['password_prompts'] or 0
    pfails = s['password_failures'] or 0

    line1 = f"Extracted {extracted}/{total} zips ({skipped} skipped: folder existed). {files_extracted} files unpacked in {s.duration_hms}."
    line2 = f"Verification OK for {verified_ok} archives — deleted {zips_deleted} zip files. AES-256: {'yes' if s['aes256'] else 'no'}."
    line3 = f"Failures — extract: {extract_failures}, verify: {verify_failures}, other errors: {errors}. Password prompts: {prompts}, failures: {pfails}."

    s.emit_lines([line1, line2, line3], json_extra={
        'zips_total': total,
        'zips_scanned': zips_scanned,
        'extracted': extracted,
        'skipped_exists': skipped,
        'verified_ok': verified_ok,
        'zips_deleted': zips_deleted,
        'extract_failures': extract_failures,
        'verify_failures': verify_failures,
        'files_extracted': files_extracted,
        'bytes_out': s['bytes_out'] or 0,
        'aes256': s['aes256'],
        'password_prompts': prompts,
        'password_failures': pfails,
        'errors': errors,
    })


def main():
    parser = argparse.ArgumentParser(
        description="Converts ZIP archives in a folder into extracted folders. Verifies integrity and deletes ZIP on success.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument('-v', '--version', action='version', version=f'ArchiveTools {__version__}')
    parser.add_argument('-f', '--folder', type=str, required=True, help='Path to the folder to process')
    parser.add_argument(
        '--aes256',
        nargs='?',
        const=True,
        help='If set, treat archives as AES-256 encrypted. Provide a password directly, or pass the flag alone to be prompted as needed.',
    )
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    args = parser.parse_args()

    logging.getLogger().setLevel(logging.DEBUG if args.verbose else logging.INFO)
    unzip_and_verify(args)


if __name__ == "__main__":
    main()
