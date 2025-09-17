import os
import argparse
import datetime as dt
import logging
import subprocess

from PIL import Image  # noqa: F401
import piexif

from archivetools import (
    configure_logging,
    add_target_args,
    resolve_target,
    iter_files,
    MEDIA_EXTENSIONS,
    SIDECAR_EXTENSIONS,
    get_dates_from_file,
    select_date,
    RunSummary,
)

# -----------------------------
# low-level setters
# -----------------------------

def set_file_timestamp(file_path: str, selected_date: dt.datetime, *, dry_run: bool = False, verbose: bool = False) -> bool:
    if verbose:
        logging.debug(
            "%s OS timestamps for %s -> %s",
            "Would set" if dry_run else "Setting",
            os.path.basename(file_path),
            selected_date,
            extra={"target": os.path.basename(file_path)},
        )
    try:
        if not dry_run:
            ts = selected_date.timestamp()
            # atime, mtime
            os.utime(file_path, (ts, ts))
        return True
    except Exception as e:
        logging.error("Failed to set file timestamps: %s", e, extra={"target": os.path.basename(file_path)})
        return False


def set_sidecar_timestamps(file_path: str, selected_date: dt.datetime, *, dry_run: bool = False, verbose: bool = False) -> int:
    """
    Set timestamps on sidecar files that share the same basename.
    Returns how many sidecars were updated.
    """
    base, _ = os.path.splitext(file_path)
    count = 0
    for ext in SIDECAR_EXTENSIONS:
        sidecar = f"{base}{ext}"
        if not os.path.exists(sidecar):
            continue
        if verbose:
            logging.debug(
                "%s sidecar timestamps for %s -> %s",
                "Would set" if dry_run else "Setting",
                os.path.basename(sidecar),
                selected_date,
                extra={"target": os.path.basename(sidecar)},
            )
        try:
            if not dry_run:
                ts = selected_date.timestamp()
                os.utime(sidecar, (ts, ts))
            count += 1
        except Exception as e:
            logging.error("Failed to set sidecar timestamps: %s", e, extra={"target": os.path.basename(sidecar)})
    return count


def set_exif_date(file_path: str, selected_date: dt.datetime, *, dry_run: bool = False, verbose: bool = False) -> bool:
    """
    Write EXIF dates for JPEG/TIFF files (DateTime, DateTimeOriginal, DateTimeDigitized).
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in (".jpg", ".jpeg", ".tif", ".tiff"):
        return False

    if verbose:
        logging.debug(
            "%s EXIF date for %s -> %s",
            "Would set" if dry_run else "Setting",
            os.path.basename(file_path),
            selected_date,
            extra={"target": os.path.basename(file_path)},
        )
    try:
        if dry_run:
            return True

        dt_str = selected_date.strftime("%Y:%m:%d %H:%M:%S")
        try:
            exif_dict = piexif.load(file_path)
        except Exception:
            # If no EXIF exists, start fresh
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

        exif_dict["0th"][piexif.ImageIFD.DateTime] = dt_str.encode()
        exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = dt_str.encode()
        exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = dt_str.encode()

        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, file_path)
        return True
    except Exception as e:
        logging.error("Failed to write EXIF date: %s", e, extra={"target": os.path.basename(file_path)})
        return False


def set_ffprobe_date(file_path: str, selected_date: dt.datetime, *, dry_run: bool = False, verbose: bool = False) -> bool:
    """
    For MP4/MOV, re-mux with creation_time metadata using ffmpeg (stream copy).
    """
    base, ext = os.path.splitext(file_path)
    ext = ext.lower()
    if ext not in (".mp4", ".mov", ".m4v"):
        return False


    if verbose:
        logging.debug(
            "%s FFprobe creation_time for %s -> %s",
            "Would set" if dry_run else "Setting",
            os.path.basename(file_path),
            selected_date,
            extra={"target": os.path.basename(file_path)},
        )
    try:
        if dry_run:
            return True
        # keep the container identical to the input
        temp_file = f"{base}.tmp{ext}"
        cmd = [
            "ffmpeg",
            "-y",
            "-i", file_path,
            "-map", "0",
            "-codec", "copy",
            "-metadata", f"creation_time={selected_date.isoformat()}",
            temp_file,
        ]

        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        os.replace(temp_file, file_path)
        return True
    except Exception as e:
        logging.error("Failed to write FFprobe creation_time: %s", e, extra={"target": os.path.basename(file_path)})
        # Clean up temp if present
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except Exception:
            pass
        return False


# -----------------------------
# per-file coordinator
# -----------------------------

def set_selected_date(
    file_path: str,
    selected_date_info: tuple[str, dt.datetime] | None,
    current_dates: list[tuple[str, dt.datetime]],
    *,
    force: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
    summary: RunSummary | None = None,
) -> None:
    """
    Apply the chosen date to file system timestamps, EXIF (jpg/tiff), ffprobe (mp4/mov), and sidecars.
    """
    name = os.path.basename(file_path)

    if not selected_date_info:
        logging.info("No usable date — skipping.", extra={"target": name})
        if summary:
            summary.inc("no_date")
        return

    date_source, selected_date = selected_date_info

    if summary:
        summary.inc("processed")
        summary.inc(f"source_{str(date_source).lower()}")

        # Track min/max
        earliest = summary.get("earliest_date")
        latest = summary.get("latest_date")
        try:
            if earliest is None or selected_date < earliest:
                summary.set("earliest_date", selected_date)
            if latest is None or selected_date > latest:
                summary.set("latest_date", selected_date)
        except Exception:
            pass

    if verbose:
        logging.debug(
            "Selected date for %s: %s (source: %s)",
            name, selected_date, date_source,
            extra={"target": name},
        )

    actions = []

    # Always set file timestamps (unless force=False and they already match to-the-second)
    try:
        mtime = dt.datetime.fromtimestamp(os.path.getmtime(file_path))
        already = (mtime.replace(microsecond=0) == selected_date.replace(microsecond=0))
    except Exception:
        already = False

    if force or not already:
        if set_file_timestamp(file_path, selected_date, dry_run=dry_run, verbose=verbose):
            actions.append("File timestamps")
            if summary:
                summary.inc("timestamps")

    # EXIF for JPEG/TIFF
    if set_exif_date(file_path, selected_date, dry_run=dry_run, verbose=verbose):
        actions.append("EXIF")
        if summary:
            summary.inc("exif")

    # FFprobe creation_time for MP4/MOV
    if set_ffprobe_date(file_path, selected_date, dry_run=dry_run, verbose=verbose):
        actions.append("FFprobe")
        if summary:
            summary.inc("ffprobe")

    # Sidecars (timestamps only)
    moved = set_sidecar_timestamps(file_path, selected_date, dry_run=dry_run, verbose=verbose)
    if moved:
        actions.append(f"Sidecars×{moved}")
        if summary:
            summary.inc("sidecars", moved)

    if summary and actions:
        summary.inc("updated")

    logging.info(
        "Updated (%s): %s (%s: %s)",
        ", ".join(actions) if actions else "Nothing",
        name,
        date_source,
        selected_date.strftime("%Y-%m-%d %H:%M:%S"),
        extra={"target": name},
    )


# -----------------------------
# CLI
# -----------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Set file timestamps (and embedded metadata where possible) from detected dates "
            "(EXIF for images, ffprobe for videos, filesystem times as fallback). "
            "Also updates timestamps on matching sidecar files."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    add_target_args(
        parser,
        folder_help="Batch mode: set dates on media inside this folder (non-recursive by default; use --recursive to include subfolders).",
        single_help="Single mode: set date on exactly this file.",
        required=True,
    )

    parser.add_argument("--force", action="store_true", help="Force overwriting even if current timestamps match")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without modifying files")
    parser.add_argument(
        "--mode",
        type=str,
        default="default",
        choices=["default", "oldest", "newest"],
        help="Date selection: 'default' prefers EXIF/ffprobe, otherwise file times; 'oldest'/'newest' pick extremes.",
    )

    args = parser.parse_args()
    configure_logging(getattr(args, "verbose", False))

    # Resolve target: single expects a FILE; batch expects a FOLDER
    mode_sel, target = resolve_target(args, single_expect="file", folder_expect="folder")

    s = RunSummary()
    s.set("mode", args.mode)
    s.set("dry_run", bool(getattr(args, "dry_run", False)))
    s.set("force", bool(getattr(args, "force", False)))
    s.set("recursive", bool(getattr(args, "recursive", False)))
    s.set("include_hidden", bool(getattr(args, "include_hidden", False)))
    s.set("earliest_date", None)
    s.set("latest_date", None)

    if mode_sel == "single":
        # Single file
        if getattr(args, "verbose", False):
            logging.debug("Analyzing file: %s", target, extra={"target": os.path.basename(target)})
        candidates = get_dates_from_file(target)
        if getattr(args, "verbose", False):
            logging.debug("Detected dates for %s: %s", os.path.basename(target), candidates, extra={"target": os.path.basename(target)})
        chosen = select_date(candidates, args.mode)
        set_selected_date(
            target,
            chosen,
            candidates,
            force=bool(args.force),
            dry_run=bool(args.dry_run),
            verbose=getattr(args, "verbose", False),
            summary=s,
        )
    else:
        # Batch over files in folder (non-recursive by default)
        for file_path in iter_files(
            target,
            recursive=bool(getattr(args, "recursive", False)),
            include_hidden=bool(getattr(args, "include_hidden", False)),
            ext_filter=set(MEDIA_EXTENSIONS),
        ):
            name = os.path.basename(file_path)
            if getattr(args, "verbose", False):
                logging.debug("Analyzing file: %s", file_path, extra={"target": name})
            candidates = get_dates_from_file(file_path)
            if getattr(args, "verbose", False):
                logging.debug("Detected dates for %s: %s", name, candidates, extra={"target": name})
            chosen = select_date(candidates, args.mode)
            set_selected_date(
                file_path,
                chosen,
                candidates,
                force=bool(args.force),
                dry_run=bool(args.dry_run),
                verbose=getattr(args, "verbose", False),
                summary=s,
            )

    # Summary
    processed = s.get("processed", 0) or 0
    updated = s.get("updated", 0) or 0
    no_date = s.get("no_date", 0) or 0
    timestamps = s.get("timestamps", 0) or 0
    exif = s.get("exif", 0) or 0
    sidecars = s.get("sidecars", 0) or 0
    ffprobe = s.get("ffprobe", 0) or 0
    earliest = s.get("earliest_date")
    latest = s.get("latest_date")

    line1 = f"Processed {processed} file(s): {updated} updated, {no_date} without a usable date."
    line2 = f"Applied updates — Timestamps {timestamps}, EXIF {exif}, Sidecars {sidecars}, FFprobe {ffprobe}."
    line3 = f"Date range — earliest: {earliest}, latest: {latest}."

    s.emit_lines(
        [line1, line2, line3],
        json_extra={
            "processed": processed,
            "updated": updated,
            "no_date": no_date,
            "timestamps": timestamps,
            "exif": exif,
            "sidecars": sidecars,
            "ffprobe": ffprobe,
            "earliest_date": str(earliest) if earliest else None,
            "latest_date": str(latest) if latest else None,
            "mode": s["mode"],
            "dry_run": s["dry_run"],
            "force": s["force"],
            "recursive": s["recursive"],
            "include_hidden": s["include_hidden"],
            "target_mode": mode_sel,
            "target": target,
        },
    )


if __name__ == "__main__":
    main()
