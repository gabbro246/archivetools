import os
import argparse
import logging
import shutil
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Optional, Tuple

import pyzipper  # AES-256 capable

from archivetools import (
    configure_logging,
    add_target_args,
    resolve_target,
    iter_dirs,
    is_hidden,
    calculate_file_hash,
    map_relative_file_hashes,
    prompt_password,
    RunSummary,
)

# ------------------------------------------------------------
# Hash helpers
# ------------------------------------------------------------

def zip_member_hashes(zip_path: str, *, password: Optional[str] = None, algo: str = "sha256") -> Dict[str, str]:
    """
    Return {'relative/posix/path': hexdigest} for all regular files in the zip.
    Paths use '/' separators.
    """
    mapping: Dict[str, str] = {}
    with pyzipper.AESZipFile(zip_path, "r") as zf:
        if password:
            zf.setpassword(password.encode())
        for info in zf.infolist():
            name = info.filename
            if not name or name.endswith("/"):
                continue  # skip directories
            rel = str(PurePosixPath(name))  # normalize to posix
            h = _hash_fileobj(lambda chunk_size: _zip_reader_iter(zf, name, chunk_size), algo=algo)
            mapping[rel] = h
    return mapping


def _zip_reader_iter(zf: pyzipper.AESZipFile, name: str, chunk_size: int):
    with zf.open(name, "r") as fp:
        while True:
            chunk = fp.read(chunk_size)
            if not chunk:
                break
            yield chunk


def _hash_fileobj(reader_iter_factory, *, algo: str = "sha256", chunk_size: int = 1024 * 1024) -> str:
    import hashlib
    h = hashlib.new(algo)
    for chunk in reader_iter_factory(chunk_size):
        h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------
# Zip creation & verification
# ------------------------------------------------------------

def _iter_files_for_zip(root: str, *, include_hidden: bool) -> Iterable[Tuple[str, str]]:
    """
    Yield (abs_path, archive_rel_path) for all files beneath root.
    Selection-time policy: once we've chosen this folder, include ALL contents.
    """
    root = os.path.abspath(root)
    for curr, _dirs, files in os.walk(root):
        for name in files:
            abs_path = os.path.join(curr, name)
            rel_path = os.path.relpath(abs_path, root).replace("\\", "/")
            yield abs_path, rel_path



def create_zip_from_folder(
    folder_path: str,
    zip_path: str,
    *,
    include_hidden: bool,
    aes256: bool,
    password: Optional[str],
    dry_run: bool,
    verbose: bool,
    summary: RunSummary | None,
) -> Tuple[int, int]:
    """
    Create a zip file at zip_path containing the folder contents.
    Returns (files_added, bytes_in).
    """
    files_added = 0
    bytes_in = 0

    if dry_run:
        # Count what would be added
        for abs_path, _rel in _iter_files_for_zip(folder_path, include_hidden=include_hidden):
            files_added += 1
            try:
                bytes_in += os.path.getsize(abs_path)
            except OSError:
                pass
        if verbose:
            logging.debug(
                "Would create zip with %d files from %s",
                files_added,
                folder_path,
                extra={"target": os.path.basename(zip_path)},
            )
        return files_added, bytes_in

    # Create parent dirs for the zip file
    os.makedirs(os.path.dirname(zip_path) or ".", exist_ok=True)

    mode = "w"
    with pyzipper.AESZipFile(zip_path, mode, compression=pyzipper.ZIP_DEFLATED) as zf:
        if aes256:
            # pyzipper uses AES encryption when a password is set and encryption is configured
            zf.setencryption(pyzipper.WZ_AES, nbits=256)
            if password:
                zf.setpassword(password.encode())
        for abs_path, rel in _iter_files_for_zip(folder_path, include_hidden=include_hidden):
            # Add file to zip
            zf.write(abs_path, arcname=rel)
            files_added += 1
            try:
                bytes_in += os.path.getsize(abs_path)
            except OSError:
                pass

    if summary:
        summary.inc("zips_created")
    logging.info("Created zip", extra={"target": os.path.basename(zip_path)})
    return files_added, bytes_in


def verify_zipped_contents(
    folder_path: str,
    zip_file_path: str,
    *,
    include_hidden: bool,
    password: Optional[str],
    verbose: bool,
) -> bool:
    """
    Compare content hashes between folder and zip without extracting.
    """
    expected = map_relative_file_hashes(folder_path)


    try:
        actual = zip_member_hashes(zip_file_path, password=password)
    except RuntimeError as e:
        logging.error("Failed to read zip: %s", e, extra={"target": os.path.basename(zip_file_path)})
        return False
    except Exception as e:
        logging.error("Unexpected error reading zip: %s", e, extra={"target": os.path.basename(zip_file_path)})
        return False

    if len(actual) != len(expected):
        if verbose:
            logging.debug("Verification mismatch: counts zip=%d vs src=%d", len(actual), len(expected))
        return False

    for rel, hv in expected.items():
        if rel not in actual or actual[rel] != hv:
            if verbose:
                logging.debug("Verification mismatch on %s", rel)
            return False

    return True


# ------------------------------------------------------------
# Workflows
# ------------------------------------------------------------

def _zip_one_folder(
    folder_path: str,
    *,
    include_hidden: bool,
    aes256: bool,
    password: Optional[str],
    rename_zip: bool,
    keep_source: bool,
    verify: bool,
    dry_run: bool,
    verbose: bool,
    summary: RunSummary | None,
) -> None:
    """
    Zip a single folder to a sibling zip file named <folder>.zip
    """
    folder_path = os.path.abspath(folder_path)
    if not os.path.isdir(folder_path):
        logging.warning("Skipping non-folder", extra={"target": os.path.basename(folder_path)})
        return

    parent = os.path.dirname(folder_path)
    base = os.path.basename(folder_path)
    zip_path = os.path.join(parent, f"{base}.zip")

    if os.path.exists(zip_path):
        if rename_zip:
            zip_path = _unique_zip_path(zip_path)
            if verbose:
                logging.debug("Zip exists — using %s", os.path.basename(zip_path), extra={"target": base})
        else:
            logging.warning("Zip already exists — skipping", extra={"target": os.path.basename(zip_path)})
            if summary:
                summary.inc("skipped_conflict")
            return

    files_added, bytes_in = create_zip_from_folder(
        folder_path,
        zip_path,
        include_hidden=include_hidden,
        aes256=aes256,
        password=password,
        dry_run=dry_run,
        verbose=verbose,
        summary=summary,
    )

    bytes_zip = 0
    if not dry_run:
        try:
            bytes_zip = os.path.getsize(zip_path)
        except OSError:
            bytes_zip = 0

    if verify and not dry_run:
        ok = verify_zipped_contents(
            folder_path,
            zip_path,
            include_hidden=include_hidden,
            password=password if aes256 else None,
            verbose=verbose,
        )
        if not ok:
            logging.error("Verification failed", extra={"target": os.path.basename(zip_path)})
            if summary:
                summary.inc("verify_failures")
            # If verification fails and we created the zip, remove it to avoid confusion
            try:
                os.remove(zip_path)
            except Exception:
                pass
            return
        else:
            if summary:
                summary.inc("verified_ok")
            if verbose:
                logging.debug("Verified OK", extra={"target": os.path.basename(zip_path)})

    # Delete source only after successful (or skipped) verification
    if not dry_run and not keep_source:
        try:
            shutil.rmtree(folder_path)
            if summary:
                summary.inc("sources_deleted")
            logging.info("Deleted source folder", extra={"target": base})
        except Exception as e:
            logging.error("Failed to delete source folder: %s", e, extra={"target": base})
            if summary:
                summary.inc("errors")

    if summary:
        summary.inc("folders_zipped")
        summary.inc("files_zipped", files_added)
        summary.inc("bytes_in", bytes_in)
        summary.inc("bytes_zip", bytes_zip)


def _unique_zip_path(path: str) -> str:
    base, ext = os.path.splitext(path)
    counter = 1
    candidate = f"{base}({counter}){ext}"
    while os.path.exists(candidate):
        counter += 1
        candidate = f"{base}({counter}){ext}"
    return candidate


def _gather_batch_targets(root: str, *, recursive: bool, include_hidden: bool) -> List[str]:
    """
    Batch mode: non-recursive -> immediate subfolders; recursive -> all descendants.
    Returns a list sorted deepest-first to avoid parent/child conflicts when deleting.
    """
    if not recursive:
        targets = list(iter_dirs(root, recursive=False, include_hidden=include_hidden))
    else:
        targets = list(iter_dirs(root, recursive=True, include_hidden=include_hidden))
    # Sort deepest-first
    targets.sort(key=lambda p: p.count(os.sep), reverse=True)
    # Skip empty folders (optional: zip only if files exist)
    out = []
    for d in targets:
        has_files = any(True for _ in _iter_files_for_zip(d, include_hidden=include_hidden))
        if has_files:
            out.append(d)
    return out


# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Zip folders to .zip files. "
            "Batch mode zips each subfolder of the target directory (non-recursive by default; use --recursive for all descendants). "
            "Single mode zips the specified folder itself. Hidden items are ignored by default."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    add_target_args(
        parser,
        folder_help="Batch mode: zip each subfolder in this directory (non-recursive by default; use --recursive to include subfolders).",
        single_help="Single mode: zip exactly this folder.",
        required=True,
    )

    parser.add_argument("--dry-run", action="store_true", help="Show what would be zipped without writing files")
    parser.add_argument("--rename", action="store_true", help="Rename zip if target name already exists (instead of skipping)")
    parser.add_argument("--keep-source", action="store_true", help="Keep the source folder after successful zip/verification")
    parser.add_argument("--no-verify", dest="verify", action="store_false", help="Skip content verification after creating zip")
    parser.set_defaults(verify=True)

    # Encryption options
    parser.add_argument("--aes256", action="store_true", help="Use AES-256 encryption for the zip")
    parser.add_argument("--password", type=str, default=None, help="Password to use when --aes256 is set (will prompt if omitted)")

    args = parser.parse_args()
    configure_logging(getattr(args, "verbose", False))

    # Resolve target: both single and batch expect a folder
    mode_sel, target = resolve_target(args, single_expect="folder", folder_expect="folder")

    # Determine password if encryption requested
    password = args.password
    if args.aes256 and password is None and not getattr(args, "dry_run", False):
        password = prompt_password("Password for AES-256 zip: ")

    s = RunSummary()
    s.set("recursive", bool(getattr(args, "recursive", False)))
    s.set("include_hidden", bool(getattr(args, "include_hidden", False)))
    s.set("dry_run", bool(getattr(args, "dry_run", False)))
    s.set("rename", bool(getattr(args, "rename", False)))
    s.set("keep_source", bool(getattr(args, "keep_source", False)))
    s.set("verify", bool(getattr(args, "verify", True)))
    s.set("aes256", bool(getattr(args, "aes256", False)))

    if mode_sel == "single":
        _zip_one_folder(
            target,
            include_hidden=s["include_hidden"],
            aes256=s["aes256"],
            password=password,
            rename_zip=s["rename"],
            keep_source=s["keep_source"],
            verify=s["verify"],
            dry_run=s["dry_run"],
            verbose=getattr(args, "verbose", False),
            summary=s,
        )
    else:
        targets = _gather_batch_targets(target, recursive=s["recursive"], include_hidden=s["include_hidden"])
        for d in targets:
            _zip_one_folder(
                d,
                include_hidden=s["include_hidden"],
                aes256=s["aes256"],
                password=password,
                rename_zip=s["rename"],
                keep_source=s["keep_source"],
                verify=s["verify"],
                dry_run=s["dry_run"],
                verbose=getattr(args, "verbose", False),
                summary=s,
            )

    # Summaries
    folders_zipped = s.get("folders_zipped", 0) or 0
    files_zipped = s.get("files_zipped", 0) or 0
    zips_created = s.get("zips_created", 0) or 0
    verify_ok = s.get("verified_ok", 0) or 0
    verify_fail = s.get("verify_failures", 0) or 0
    sources_deleted = s.get("sources_deleted", 0) or 0
    bytes_in = s.get("bytes_in", 0) or 0
    bytes_zip = s.get("bytes_zip", 0) or 0
    saved_pct = int(round((1.0 - (bytes_zip / bytes_in)) * 100)) if bytes_in and bytes_zip else 0
    errors = s.get("errors", 0) or 0

    line1 = (
        f"Created {zips_created} zip(s) from {folders_zipped} folder(s) "
        f"({files_zipped} files). Verified OK: {verify_ok}, failed: {verify_fail}."
    )
    line2 = (
        f"Sizes — input {bytes_in} bytes → zip {bytes_zip} bytes "
        f"({saved_pct}% smaller). Sources deleted: {sources_deleted}. Errors: {errors}."
    )
    line3 = (
        f"Recursive: {s['recursive']}. Include hidden: {s['include_hidden']}. "
        f"Dry-run: {s['dry_run']}. Verify: {s['verify']}. AES-256: {s['aes256']}."
    )

    s.emit_lines(
        [line1, line2, line3],
        json_extra={
            "folders_zipped": folders_zipped,
            "files_zipped": files_zipped,
            "zips_created": zips_created,
            "verified_ok": verify_ok,
            "verify_failures": verify_fail,
            "sources_deleted": sources_deleted,
            "bytes_in": bytes_in,
            "bytes_zip": bytes_zip,
            "saved_pct": saved_pct,
            "aes256": s["aes256"],
            "errors": errors,
            "recursive": s["recursive"],
            "include_hidden": s["include_hidden"],
            "dry_run": s["dry_run"],
            "verify": s["verify"],
            "keep_source": s["keep_source"],
            "rename": s["rename"],
            "target_mode": mode_sel,
            "target": target,
        },
    )


if __name__ == "__main__":
    main()
