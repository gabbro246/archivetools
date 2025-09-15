import os
import shutil
import argparse
import pyzipper
import logging
from archivetools import (
    __version__,
    calculate_file_hash,
    prompt_password,
    RunSummary,
    add_target_args,
    resolve_target,
)

def verify_zipped_contents(folder_path, zip_file_path, password=None, verbose=False):
    """
    Verify that every file in folder_path exists in the zip with identical SHA-256.
    Returns True on full match, False otherwise.
    """
    if verbose:
        logging.debug(
            f"Verifying {os.path.basename(zip_file_path)} against {os.path.basename(folder_path)}",
            extra={'target': os.path.basename(zip_file_path)},
        )

    # Map relative path -> sha256 from source folder
    expected = {}
    for root, _, files in os.walk(folder_path):
        for name in files:
            fpath = os.path.join(root, name)
            rel = os.path.relpath(fpath, folder_path).replace("\\", "/")
            try:
                expected[rel] = calculate_file_hash(fpath)
            except Exception as e:
                logging.error(
                    f"Failed to hash source file during verification: {e}",
                    extra={'target': name},
                )
                return False

    try:
        with pyzipper.AESZipFile(zip_file_path, 'r') as zipf:
            if password:
                zipf.setpassword(password.encode())
            names = [n for n in zipf.namelist() if not n.endswith("/")]
            if len(names) != len(expected):
                logging.error(
                    "Verification failed: file count differs (zip %d vs source %d)",
                    len(names), len(expected),
                    extra={'target': os.path.basename(zip_file_path)},
                )
                return False
            for rel in names:
                if rel not in expected:
                    logging.error(
                        "Verification failed: unexpected entry in zip: %s",
                        rel,
                        extra={'target': os.path.basename(zip_file_path)},
                    )
                    return False
                with zipf.open(rel, 'r') as f:
                    import hashlib
                    h = hashlib.sha256()
                    for chunk in iter(lambda: f.read(4096), b""):
                        h.update(chunk)
                    if h.hexdigest() != expected[rel]:
                        logging.error(
                            "Verification failed: checksum mismatch for %s",
                            rel,
                            extra={'target': os.path.basename(zip_file_path)},
                        )
                        return False
    except RuntimeError as e:
        logging.error(
            f"Verification error (password/encryption): {e}",
            extra={'target': os.path.basename(zip_file_path)},
        )
        return False
    except Exception as e:
        logging.error(
            f"Error during verification: {e}",
            extra={'target': os.path.basename(zip_file_path)},
        )
        return False

    if verbose:
        logging.debug("Verification OK", extra={'target': os.path.basename(zip_file_path)})
    return True


def zip_folder(folder_path, zip_file_path, password=None, verbose=False, summary=None):
    """
    Create (optionally AES-256) zip for folder_path at zip_file_path.
    """
    s = summary
    os.makedirs(os.path.dirname(zip_file_path), exist_ok=True)
    try:
        with pyzipper.AESZipFile(
            zip_file_path,
            'w',
            compression=pyzipper.ZIP_DEFLATED,
            compresslevel=6,
        ) as zipf:
            if password:
                zipf.setencryption(pyzipper.WZ_AES, nbits=256)
                zipf.setpassword(password.encode())
            for root, _, files in os.walk(folder_path):
                for name in files:
                    src = os.path.join(root, name)
                    arcname = os.path.relpath(src, folder_path).replace("\\", "/")
                    if verbose:
                        logging.debug(
                            f"Adding to zip: {arcname}",
                            extra={'target': os.path.basename(zip_file_path)},
                        )
                    try:
                        zipf.write(src, arcname)
                        if s:
                            s.inc('files_archived')
                            try:
                                s.add_bytes('bytes_in', os.path.getsize(src))
                            except OSError:
                                pass
                    except Exception as e:
                        logging.error(f"Failed to add to zip: {e}", extra={'target': name})
                        if s:
                            s.inc('errors')
        try:
            if s:
                s.add_bytes('bytes_zip', os.path.getsize(zip_file_path))
        except OSError:
            pass
        return True
    except PermissionError as e:
        logging.error(
            f"Permission error while zipping: {e}",
            extra={'target': os.path.basename(zip_file_path)},
        )
        if s:
            s.inc('errors')
        return False
    except Exception as e:
        logging.error(
            f"Error creating zip: {e}",
            extra={'target': os.path.basename(zip_file_path)},
        )
        if s:
            s.inc('errors')
        return False


def process_batch(directory, password, verbose, summary):
    """
    Batch mode (-f): zip each immediate subfolder inside directory.
    """
    s = summary
    entries = [d for d in os.listdir(directory)]
    folders = [
        os.path.join(directory, d)
        for d in entries
        if os.path.isdir(os.path.join(directory, d))
    ]
    total = len(folders)

    for folder_path in folders:
        folder_name = os.path.basename(folder_path)
        zip_file_path = os.path.join(directory, f"{folder_name}.zip")
        s.inc('folders_scanned')

        if os.path.exists(zip_file_path):
            logging.info("Zip already exists. Skipping.", extra={'target': os.path.basename(zip_file_path)})
            s.inc('skipped_exists')
            continue

        ok_zip = zip_folder(folder_path, zip_file_path, password=password, verbose=verbose, summary=s)
        if not ok_zip:
            s.inc('zip_failures')
            continue

        s.inc('zipped')
        if verbose:
            logging.debug(
                f"Created zip: {zip_file_path}",
                extra={'target': os.path.basename(zip_file_path)},
            )

        verified = verify_zipped_contents(folder_path, zip_file_path, password=password, verbose=verbose)
        if verified:
            s.inc('verified_ok')
            try:
                shutil.rmtree(folder_path)
                s.inc('sources_deleted')
                logging.info("Verification OK — deleted source folder.", extra={'target': folder_name})
            except Exception as e:
                logging.error(f"Failed to delete source folder after verify: {e}", extra={'target': folder_name})
                s.inc('errors')
        else:
            s.inc('verify_failures')
            logging.warning("Verification failed — keeping source folder and zip for inspection.", extra={'target': folder_name})

    return total


def process_single(folder_path, password, verbose, summary):
    """
    Single mode (-s): zip this folder itself to a sibling <name>.zip.
    """
    s = summary
    parent = os.path.dirname(os.path.abspath(folder_path))
    folder_name = os.path.basename(os.path.abspath(folder_path))
    zip_file_path = os.path.join(parent, f"{folder_name}.zip")
    s.inc('folders_scanned')

    if os.path.exists(zip_file_path):
        logging.info("Zip already exists. Skipping.", extra={'target': os.path.basename(zip_file_path)})
        s.inc('skipped_exists')
        return 1  # total considered = 1

    ok_zip = zip_folder(folder_path, zip_file_path, password=password, verbose=verbose, summary=s)
    if not ok_zip:
        s.inc('zip_failures')
        return 1

    s.inc('zipped')
    if verbose:
        logging.debug(
            f"Created zip: {zip_file_path}",
            extra={'target': os.path.basename(zip_file_path)},
        )

    verified = verify_zipped_contents(folder_path, zip_file_path, password=password, verbose=verbose)
    if verified:
        s.inc('verified_ok')
        try:
            shutil.rmtree(folder_path)
            s.inc('sources_deleted')
            logging.info("Verification OK — deleted source folder.", extra={'target': folder_name})
        except Exception as e:
            logging.error(f"Failed to delete source folder after verify: {e}", extra={'target': folder_name})
            s.inc('errors')
    else:
        s.inc('verify_failures')
        logging.warning("Verification failed — keeping source folder and zip for inspection.", extra={'target': folder_name})

    return 1  # total considered = 1


def main():
    parser = argparse.ArgumentParser(
        description="Converts folders into ZIP archives (optional AES-256). In -f mode, zips each subfolder; in -s mode, zips the folder itself.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument('-v', '--version', action='version', version=f'ArchiveTools {__version__}')
    add_target_args(
        parser,
        folder_help="Batch mode: zip each immediate subfolder inside this folder",
        single_help="Single mode: zip this folder itself (creates a sibling <name>.zip)",
        required=True,
    )
    parser.add_argument(
        '--aes256',
        nargs='?',
        const=True,
        help='Enable AES-256 encryption. Provide a password directly, or pass the flag alone to be prompted.',
    )
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    args = parser.parse_args()

    logging.getLogger().setLevel(logging.DEBUG if args.verbose else logging.INFO)

    # Resolve target: both -f and -s expect a folder path here
    mode_sel, target = resolve_target(args, single_expect='folder', folder_expect='folder')

    # Determine password behavior
    password = None
    if args.aes256:
        if args.aes256 is True:
            try:
                password = prompt_password(confirm=True)
            except Exception as e:
                logging.error(
                    f"Password input error: {e}",
                    extra={'target': os.path.basename(target)},
                )
                raise SystemExit(2)
        else:
            password = str(args.aes256)

    s = RunSummary()
    s.set('aes256', bool(password))

    if mode_sel == 'single':
        total = process_single(target, password=password, verbose=args.verbose, summary=s)
    else:
        total = process_batch(target, password=password, verbose=args.verbose, summary=s)

    # emit end-of-run summary
    zipped = s['zipped'] or 0
    skipped = s['skipped_exists'] or 0
    files_archived = s['files_archived'] or 0
    verified_ok = s['verified_ok'] or 0
    sources_deleted = s['sources_deleted'] or 0
    verify_fail = s['verify_failures'] or 0
    errors = s['errors'] or 0

    bytes_in = s['bytes_in'] or 0
    bytes_zip = s['bytes_zip'] or 0
    saved_pct = int(round(100.0 * (bytes_in - bytes_zip) / bytes_in)) if bytes_in else 0

    if mode_sel == 'single':
        head = f"Zipped 1 folder"
    else:
        head = f"Zipped {zipped}/{total} folders ({skipped} skipped: zip existed)"

    line1 = f"{head}. {files_archived} files archived in {s.duration_hms}."
    line2 = f"Verification OK for {verified_ok} archives — deleted {sources_deleted} source folders. AES-256: {'enabled' if s['aes256'] else 'disabled'}."
    line3 = f"Size {s.hbytes('bytes_in')} → {s.hbytes('bytes_zip')} ({saved_pct}% saved). Failures: {verify_fail + errors}."

    s.emit_lines(
        [line1, line2, line3],
        json_extra={
            'target_mode': mode_sel,
            'folders_total': total,
            'zipped': zipped,
            'skipped_exists': skipped,
            'files_archived': files_archived,
            'verified_ok': verified_ok,
            'verify_failures': verify_fail,
            'sources_deleted': sources_deleted,
            'bytes_in': bytes_in,
            'bytes_zip': bytes_zip,
            'saved_pct': saved_pct,
            'aes256': s['aes256'],
            'errors': errors,
        },
    )


if __name__ == "__main__":
    main()
