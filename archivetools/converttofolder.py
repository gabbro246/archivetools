import os
import argparse
import logging
import shutil
from pathlib import PurePosixPath
from typing import Dict, Iterable, List, Optional, Tuple

import pyzipper  # for reading (including AES-encrypted) zips

from archivetools import (
    configure_logging,
    add_target_args,
    resolve_target,
    iter_files,
    is_hidden,
    unique_path,
    map_relative_file_hashes,
    RunSummary,
)

# ------------------------------------------------------------
# Zip helpers
# ------------------------------------------------------------

def _zip_entry_is_hidden(rel: str) -> bool:
    """
    Determine if a zip entry path (posix-style) should be considered hidden:
    if ANY component starts with '.'.
    """
    parts = PurePosixPath(rel).parts
    return any(p.startswith(".") for p in parts if p not in (".", ".."))


def _zip_member_hashes(zip_path: str, *, password: Optional[str] = None, algo: str = "sha256",
                       include_hidden: bool = False) -> Dict[str, str]:
    """
    Return {'relative/posix/path': hexdigest} for all regular files in the zip.
    Selection-time policy: once a zip is chosen, include ALL nested entries.
    """
    import hashlib
    mapping: Dict[str, str] = {}
    with pyzipper.AESZipFile(zip_path, "r") as zf:
        if password:
            zf.setpassword(password.encode())
        for info in zf.infolist():
            name = info.filename
            if (not name) or name.endswith("/"):
                continue  # skip directories
            rel = str(PurePosixPath(name))
            h = hashlib.new(algo)
            with zf.open(name, "r") as fp:
                for chunk in iter(lambda: fp.read(1024 * 1024), b""):
                    h.update(chunk)
            mapping[rel] = h.hexdigest()
    return mapping



def _iter_zip_files(zip_path: str, *, include_hidden: bool, password: Optional[str]) -> Iterable[Tuple[str, int]]:
    """
    Yield (rel_path, uncompressed_size) for each file entry in the zip.
    """
    with pyzipper.AESZipFile(zip_path, "r") as zf:
        if password:
            zf.setpassword(password.encode())
        for info in zf.infolist():
            name = info.filename
            if (not name) or name.endswith("/"):
                continue
            rel = str(PurePosixPath(name))
            yield rel, int(getattr(info, "file_size", 0))



def _safe_join(base_dir: str, rel_posix: str) -> Optional[str]:
    """
    Join a zip entry relative path to base_dir safely (prevent zip-slip).
    Returns absolute path or None if the target would escape base_dir.
    """
    rel_native = rel_posix.replace("/", os.sep)
    target = os.path.abspath(os.path.join(base_dir, rel_native))
    base_abs = os.path.abspath(base_dir)
    if not target.startswith(base_abs + os.sep) and target != base_abs:
        return None
    return target


# ------------------------------------------------------------
# Extraction & verification
# ------------------------------------------------------------

def extract_zip_to_folder(
    zip_path: str,
    out_folder: str,
    *,
    include_hidden: bool,
    password: Optional[str],
    dry_run: bool,
    verbose: bool,
    summary: RunSummary | None,
) -> Tuple[int, int]:
    """
    Extract zip_path into out_folder. Returns (files_extracted, bytes_out).
    Honors include_hidden. Creates out_folder if needed.
    """
    files = list(_iter_zip_files(zip_path, include_hidden=include_hidden, password=password))
    files_extracted = 0
    bytes_out = 0

    if dry_run:
        files_extracted = len(files)
        bytes_out = sum(sz for _, sz in files)
        if verbose:
            logging.debug(
                "Would extract %d files from %s",
                files_extracted, os.path.basename(zip_path),
                extra={"target": os.path.basename(out_folder)},
            )
        return files_extracted, bytes_out

    os.makedirs(out_folder, exist_ok=True)
    with pyzipper.AESZipFile(zip_path, "r") as zf:
        if password:
            zf.setpassword(password.encode())
        for rel, sz in files:
            dest = _safe_join(out_folder, rel)
            if dest is None:
                logging.warning("Skipping unsafe entry path", extra={"target": rel})
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            try:
                with zf.open(rel, "r") as src, open(dest, "wb") as dst:
                    for chunk in iter(lambda: src.read(1024 * 1024), b""):
                        dst.write(chunk)
                files_extracted += 1
                bytes_out += sz
            except RuntimeError as e:
                # common for wrong password / encrypted entry
                logging.error("Failed to extract entry: %s", e, extra={"target": rel})
                if summary:
                    summary.inc("errors")
            except Exception as e:
                logging.error("Error extracting entry: %s", e, extra={"target": rel})
                if summary:
                    summary.inc("errors")

    if summary:
        summary.inc("folders_created")
    logging.info("Extracted zip", extra={"target": os.path.basename(zip_path)})
    return files_extracted, bytes_out


def verify_unzipped_contents(
    zip_path: str,
    out_folder: str,
    *,
    include_hidden: bool,
    password: Optional[str],
    verbose: bool,
) -> bool:
    """
    Compare content hashes between the zip and the extracted folder.
    """
    try:
        actual = _zip_member_hashes(zip_path, password=password, include_hidden=include_hidden)
    except RuntimeError as e:
        logging.error("Failed to read zip for verification: %s", e, extra={"target": os.path.basename(zip_path)})
        return False
    except Exception as e:
        logging.error("Unexpected error reading zip: %s", e, extra={"target": os.path.basename(zip_path)})
        return False

    expected = map_relative_file_hashes(out_folder)


    if len(actual) != len(expected):
        if verbose:
            logging.debug("Verification mismatch: counts extracted=%d vs zip=%d", len(expected), len(actual))
        return False

    for rel, hv in actual.items():
        if rel not in expected or expected[rel] != hv:
            if verbose:
                logging.debug("Verification mismatch on %s", rel)
            return False

    return True


# ------------------------------------------------------------
# Workflows
# ------------------------------------------------------------

def _extract_one_zip(
    zip_path: str,
    *,
    include_hidden: bool,
    password: Optional[str],
    rename_folder: bool,
    keep_source: bool,
    verify: bool,
    dry_run: bool,
    verbose: bool,
    summary: RunSummary | None,
) -> None:
    """
    Extract a single zip into a sibling folder named <zip_basename>/ (without .zip).
    """
    zip_path = os.path.abspath(zip_path)
    if not os.path.isfile(zip_path) or not zip_path.lower().endswith(".zip"):
        logging.warning("Skipping non-zip", extra={"target": os.path.basename(zip_path)})
        return

    parent = os.path.dirname(zip_path)
    base = os.path.splitext(os.path.basename(zip_path))[0]
    out_folder = os.path.join(parent, base)

    if os.path.exists(out_folder):
        if rename_folder:
            out_folder = unique_path(out_folder, style="paren")
            if verbose:
                logging.debug("Folder exists — using %s", os.path.basename(out_folder), extra={"target": base})
        else:
            logging.warning("Destination folder exists — skipping", extra={"target": os.path.basename(out_folder)})
            if summary:
                summary.inc("skipped_conflict")
            return

    try:
        files_out, bytes_out = extract_zip_to_folder(
            zip_path,
            out_folder,
            include_hidden=include_hidden,
            password=password,
            dry_run=dry_run,
            verbose=verbose,
            summary=summary,
        )
    except RuntimeError as e:
        logging.error("Failed to read zip (password?) %s", e, extra={"target": os.path.basename(zip_path)})
        if summary:
            summary.inc("errors")
        return
    except Exception as e:
        logging.error("Error during extraction: %s", e, extra={"target": os.path.basename(zip_path)})
        if summary:
            summary.inc("errors")
        return

    bytes_zip = 0
    if not dry_run:
        try:
            bytes_zip = os.path.getsize(zip_path)
        except OSError:
            bytes_zip = 0

    if verify and not dry_run:
        ok = verify_unzipped_contents(
            zip_path,
            out_folder,
            include_hidden=include_hidden,
            password=password,
            verbose=verbose,
        )
        if not ok:
            logging.error("Verification failed", extra={"target": os.path.basename(zip_path)})
            if summary:
                summary.inc("verify_failures")
            # Cleanup the extracted folder to avoid leaving potentially inconsistent data
            try:
                shutil.rmtree(out_folder)
            except Exception:
                pass
            return
        else:
            if summary:
                summary.inc("verified_ok")
            if verbose:
                logging.debug("Verified OK", extra={"target": os.path.basename(zip_path)})

    # Delete source zip after successful (or skipped) verification
    if not dry_run and not keep_source:
        try:
            os.remove(zip_path)
            if summary:
                summary.inc("sources_deleted")
            logging.info("Deleted source zip", extra={"target": os.path.basename(zip_path)})
        except Exception as e:
            logging.error("Failed to delete source zip: %s", e, extra={"target": os.path.basename(zip_path)})
            if summary:
                summary.inc("errors")

    if summary:
        summary.inc("zips_extracted")
        summary.inc("files_extracted", files_out)
        summary.inc("bytes_out", bytes_out)
        summary.inc("bytes_zip", bytes_zip)


def _gather_zip_targets(root: str, *, recursive: bool, include_hidden: bool) -> List[str]:
    """
    Batch mode: non-recursive -> immediate *.zip files; recursive -> all descendant zips.
    Hidden zip files are ignored unless include_hidden=True.
    """
    zips = list(iter_files(root, recursive=recursive, include_hidden=include_hidden, ext_filter={".zip"}))
    return zips


# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Extract .zip archives into folders. "
            "Batch mode extracts each zip in the target directory (non-recursive by default; use --recursive for subfolders). "
            "Single mode extracts the specified zip into a sibling folder."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    add_target_args(
        parser,
        folder_help="Batch mode: extract .zip files in this directory (non-recursive by default; use --recursive to include subfolders).",
        single_help="Single mode: extract exactly this .zip into a sibling folder.",
        required=True,
    )

    parser.add_argument("--dry-run", action="store_true", help="Show what would be extracted without writing files")
    parser.add_argument("--rename", action="store_true", help="Rename destination folder if it already exists (instead of skipping)")
    parser.add_argument("--keep-source", action="store_true", help="Keep the .zip file after successful extraction/verification")
    parser.add_argument("--no-verify", dest="verify", action="store_false", help="Skip content verification after extraction")
    parser.set_defaults(verify=True)

    parser.add_argument("--password", type=str, default=None, help="Password for encrypted zips (if omitted and required, extraction will fail)")

    args = parser.parse_args()
    configure_logging(getattr(args, "verbose", False))

    # Resolve target: single expects a .zip file; batch expects a folder
    mode_sel, target = resolve_target(args, single_expect="zip", folder_expect="folder")

    s = RunSummary()
    s.set("recursive", bool(getattr(args, "recursive", False)))
    s.set("include_hidden", bool(getattr(args, "include_hidden", False)))
    s.set("dry_run", bool(getattr(args, "dry_run", False)))
    s.set("rename", bool(getattr(args, "rename", False)))
    s.set("keep_source", bool(getattr(args, "keep_source", False)))
    s.set("verify", bool(getattr(args, "verify", True)))

    if mode_sel == "single":
        _extract_one_zip(
            target,
            include_hidden=s["include_hidden"],
            password=args.password,
            rename_folder=s["rename"],
            keep_source=s["keep_source"],
            verify=s["verify"],
            dry_run=s["dry_run"],
            verbose=getattr(args, "verbose", False),
            summary=s,
        )
    else:
        targets = _gather_zip_targets(target, recursive=s["recursive"], include_hidden=s["include_hidden"])
        for zp in targets:
            _extract_one_zip(
                zp,
                include_hidden=s["include_hidden"],
                password=args.password,
                rename_folder=s["rename"],
                keep_source=s["keep_source"],
                verify=s["verify"],
                dry_run=s["dry_run"],
                verbose=getattr(args, "verbose", False),
                summary=s,
            )

    # Summaries
    zips_extracted = s.get("zips_extracted", 0) or 0
    files_extracted = s.get("files_extracted", 0) or 0
    verify_ok = s.get("verified_ok", 0) or 0
    verify_fail = s.get("verify_failures", 0) or 0
    sources_deleted = s.get("sources_deleted", 0) or 0
    bytes_out = s.get("bytes_out", 0) or 0
    bytes_zip = s.get("bytes_zip", 0) or 0
    overhead_pct = int(round((bytes_out / bytes_zip - 1.0) * 100)) if bytes_zip and bytes_out else 0
    errors = s.get("errors", 0) or 0

    line1 = (
        f"Extracted {zips_extracted} zip(s) "
        f"into folders with {files_extracted} files total. Verified OK: {verify_ok}, failed: {verify_fail}."
    )
    line2 = (
        f"Sizes — zip {bytes_zip} bytes → files {bytes_out} bytes "
        f"(~{overhead_pct}% larger than zip). Sources deleted: {sources_deleted}. Errors: {errors}."
    )
    line3 = (
        f"Recursive: {s['recursive']}. Include hidden: {s['include_hidden']}. "
        f"Dry-run: {s['dry_run']}. Verify: {s['verify']}."
    )

    s.emit_lines(
        [line1, line2, line3],
        json_extra={
            "zips_extracted": zips_extracted,
            "files_extracted": files_extracted,
            "verified_ok": verify_ok,
            "verify_failures": verify_fail,
            "sources_deleted": sources_deleted,
            "bytes_out": bytes_out,
            "bytes_zip": bytes_zip,
            "overhead_pct": overhead_pct,
            "errors": errors,
            "recursive": s["recursive"],
            "include_hidden": s["include_hidden"],
            "dry_run": s["dry_run"],
            "verify": s["verify"],
            "rename": s["rename"],
            "keep_source": s["keep_source"],
            "target_mode": mode_sel,
            "target": target,
        },
    )


if __name__ == "__main__":
    main()
