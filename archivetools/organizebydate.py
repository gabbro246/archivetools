import os
import shutil
import argparse
import datetime as dt
import logging

from archivetools import (
    __version__,
    configure_logging,
    add_target_args,
    resolve_target,
    iter_files,
    MEDIA_EXTENSIONS,
    get_dates_from_file,
    select_date,
    move_sidecar_files,
    unique_path,
    RunSummary,
    MONTH_NAMES,
    WEEK_PREFIX,
)

# ------------------------------------------------------------
# helpers
# ------------------------------------------------------------

def _format_duration_hms(seconds: float) -> str:
    seconds = int(round(seconds or 0))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _folder_name_day(d: dt.datetime) -> str:
    return d.strftime("%Y%m%d")


def _folder_name_week(d: dt.datetime) -> str:
    iso_year, iso_week, _ = d.isocalendar()
    start_date = dt.datetime.strptime(f"{iso_year}-W{iso_week}-1", "%G-W%V-%u").date()
    end_date = start_date + dt.timedelta(days=6)
    return f"{start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')} - {WEEK_PREFIX}{iso_week:02d}"


def _folder_name_month(d: dt.datetime) -> str:
    start_date = dt.datetime(d.year, d.month, 1)
    return f"{start_date.strftime('%Y%m')} - {MONTH_NAMES[d.month]} {d.year}"


def _folder_name_year(d: dt.datetime) -> str:
    return d.strftime("%Y")


def _resolve_folder_name(date_used: dt.datetime, granularity: str) -> str:
    if granularity == "day":
        return _folder_name_day(date_used)
    if granularity == "week":
        return _folder_name_week(date_used)
    if granularity == "month":
        return _folder_name_month(date_used)
    if granularity == "year":
        return _folder_name_year(date_used)
    return _folder_name_day(date_used)


def _apply_midnight_shift(date_used: dt.datetime, midnight_shift: int) -> dt.datetime:
    if midnight_shift and date_used.hour < midnight_shift:
        return date_used - dt.timedelta(days=1)
    return date_used


# ------------------------------------------------------------
# core logic
# ------------------------------------------------------------

def _handle_one_file(
    file_path: str,
    *,
    dest_root: str,
    granularity: str,
    mode: str,
    midnight_shift: int,
    rename_files: bool,
    dry_run: bool,
    verbose: bool,
    summary: RunSummary | None,
) -> None:
    name = os.path.basename(file_path)
    ext = os.path.splitext(name)[1].lower()

    if ext not in MEDIA_EXTENSIONS or not os.path.isfile(file_path):
        if verbose:
            logging.debug("Skipping non-media file: %s", file_path, extra={"target": name})
        return

    if summary:
        summary.inc("found")

    if verbose:
        logging.debug("Analyzing: %s", file_path, extra={"target": name})

    candidates = get_dates_from_file(file_path)
    sel = select_date(candidates, mode=mode)
    if not sel:
        logging.info("No valid date found. Skipping.", extra={"target": name})
        if summary:
            summary.inc("skipped_no_date")
        return

    label, date_used = sel
    date_used = _apply_midnight_shift(date_used, midnight_shift)
    if summary:
        summary.inc(f"source_{str(label).lower()}")

    folder_name = _resolve_folder_name(date_used, granularity)
    target_folder = os.path.join(dest_root, folder_name)

    if not os.path.exists(target_folder):
        if verbose:
            logging.debug("Creating folder: %s", target_folder, extra={"target": folder_name})
        if not dry_run:
            os.makedirs(target_folder, exist_ok=True)
        if summary:
            summary.inc("folders_created")

    target_path = os.path.join(target_folder, name)
    if os.path.abspath(file_path) == os.path.abspath(target_path):
        if verbose:
            logging.debug("Already in the correct folder: %s", file_path, extra={"target": name})
        return

    if os.path.exists(target_path):
        if rename_files:
            target_path = unique_path(target_path, style="paren")
            if summary:
                summary.inc("renamed")
            if verbose:
                logging.debug(
                    "Name conflict — using: %s",
                    os.path.basename(target_path),
                    extra={"target": name},
                )
        else:
            logging.warning("Skipping — same name exists in destination.", extra={"target": name})
            if summary:
                summary.inc("skipped_conflict")
            return

    try:
        if dry_run:
            if verbose:
                logging.debug("Would move -> %s", target_folder, extra={"target": name})
        else:
            shutil.move(file_path, target_path)
        if summary:
            summary.inc("moved")
        logging.info(
            "Placed in %s (%s: %s)",
            folder_name,
            label,
            date_used.strftime("%Y-%m-%d"),
            extra={"target": name},
        )
        move_sidecar_files(file_path, target_folder, dry_run=dry_run, verbose=verbose)
    except FileNotFoundError:
        logging.error("File could not be moved. Not found.", extra={"target": name})
        if summary:
            summary.inc("errors")


def _batch_mode(
    target_dir: str,
    *,
    granularity: str,
    mode: str,
    midnight_shift: int,
    rename_files: bool,
    recursive: bool,
    include_hidden: bool,
    dry_run: bool,
    verbose: bool,
    summary: RunSummary | None,
) -> None:
    for path in iter_files(
        target_dir,
        recursive=recursive,
        include_hidden=include_hidden,
        ext_filter=set(MEDIA_EXTENSIONS),
    ):
        _handle_one_file(
            path,
            dest_root=target_dir,
            granularity=granularity,
            mode=mode,
            midnight_shift=midnight_shift,
            rename_files=rename_files,
            dry_run=dry_run,
            verbose=verbose,
            summary=summary,
        )


def _single_mode(
    file_path: str,
    *,
    granularity: str,
    mode: str,
    midnight_shift: int,
    rename_files: bool,
    dry_run: bool,
    verbose: bool,
    summary: RunSummary | None,
) -> None:
    parent = os.path.dirname(file_path)
    _handle_one_file(
        file_path,
        dest_root=parent,
        granularity=granularity,
        mode=mode,
        midnight_shift=midnight_shift,
        rename_files=rename_files,
        dry_run=dry_run,
        verbose=verbose,
        summary=summary,
    )


# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Organize media into subfolders by date (day/week/month/year). "
            "Uses EXIF/ffprobe/filename/folder timestamps when available. "
            "Automatically moves matching sidecar files."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    add_target_args(
        parser,
        folder_help="Batch mode: organize the media in this folder (non-recursive by default; use --recursive to include subfolders).",
        single_help="Single mode: move exactly this file into its dated subfolder (created under its current directory).",
        required=True,
    )

    parser.add_argument("--rename", action="store_true", help="Rename on conflict instead of skipping")
    parser.add_argument("--dry-run", action="store_true", help="Show what would move without changing files")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-d", "--day", action="store_true", help="Organize into YYYYMMDD folders")
    group.add_argument("-w", "--week", action="store_true", help="Organize into YYYYMMDD-YYYYMMDD - Week NN folders")
    group.add_argument("-m", "--month", action="store_true", help="Organize into YYYYMM - Month YYYY folders")
    group.add_argument("-y", "--year", action="store_true", help="Organize into YYYY folders")

    parser.add_argument(
        "--mode",
        type=str,
        default="default",
        choices=["default", "oldest", "newest"],
        help="Date selection strategy: 'default' prefers EXIF/ffprobe over file times; 'oldest'/'newest' choose extremal dates.",
    )
    parser.add_argument(
        "--midnight-shift",
        nargs="?",
        const=3,
        type=int,
        default=0,
        help="Shift early-hours (e.g. 00:00–02:59) back to the previous day. If provided without a value, uses 3.",
    )

    args = parser.parse_args()

    configure_logging(getattr(args, "verbose", False))

    mode_sel, target = resolve_target(args, single_expect="file", folder_expect="folder")

    s = RunSummary()
    t0 = dt.datetime.now()

    s.set("mode", args.mode)
    s.set("rename", bool(args.rename))
    s.set("dry_run", bool(args.dry_run))
    s.set("midnight_shift_h", int(args.midnight_shift or 0))
    s.set("recursive", bool(getattr(args, "recursive", False)))
    s.set("include_hidden", bool(getattr(args, "include_hidden", False)))

    granularity = "day" if args.day else "week" if args.week else "month" if args.month else "year"
    s.set("granularity", granularity)

    if getattr(args, "verbose", False):
        logging.debug(
            "Target %s in %s mode — granularity=%s, recursive=%s, include_hidden=%s, dry_run=%s",
            target,
            mode_sel,
            granularity,
            bool(getattr(args, "recursive", False)),
            bool(getattr(args, "include_hidden", False)),
            bool(args.dry_run),
            extra={"target": os.path.basename(target)},
        )

    if mode_sel == "single":
        _single_mode(
            target,
            granularity=granularity,
            mode=args.mode,
            midnight_shift=args.midnight_shift or 0,
            rename_files=args.rename,
            dry_run=args.dry_run,
            verbose=getattr(args, "verbose", False),
            summary=s,
        )
    else:
        _batch_mode(
            target,
            granularity=granularity,
            mode=args.mode,
            midnight_shift=args.midnight_shift or 0,
            rename_files=args.rename,
            recursive=bool(getattr(args, "recursive", False)),
            include_hidden=bool(getattr(args, "include_hidden", False)),
            dry_run=args.dry_run,
            verbose=getattr(args, "verbose", False),
            summary=s,
        )

    duration = (dt.datetime.now() - t0).total_seconds()
    duration_hms = _format_duration_hms(duration)

    found = s.get("found", 0)
    moved = s.get("moved", 0)
    skipped_no_date = s.get("skipped_no_date", 0)
    skipped_conflict = s.get("skipped_conflict", 0)
    folders_created = s.get("folders_created", 0)
    renamed = s.get("renamed", 0)
    errors = s.get("errors", 0)
    skipped_total = skipped_no_date + skipped_conflict

    line1 = (
        f"Moved {moved}/{found} files ({skipped_total} skipped: "
        f"{skipped_no_date} no date, {skipped_conflict} name conflict). "
        f"Created {folders_created} folders in {duration_hms}."
    )

    src_counts = {k.replace("source_", ""): v for k, v in s.items() if k.startswith("source_")}
    line2 = None
    total_src = sum(src_counts.values())
    if total_src:
        def _label(k: str) -> str:
            mapping = {"ffprobe:creation_time": "FFprobe", "exif:datetimeoriginal": "EXIF"}
            return mapping.get(k, k.replace("_", " ").title())
        parts = [f"{_label(k)} {int(round(100.0 * v / total_src))}%" for k, v in sorted(src_counts.items(), key=lambda kv: -kv[1])]
        line2 = "Date sources — " + ", ".join(parts) + "."

    line3 = f"Renames: {renamed}. Mode: {s['mode']}. Midnight-shift: {s['midnight_shift_h']}h. Errors: {errors}."

    lines = [line1]
    if line2:
        lines.append(line2)
    lines.append(line3)

    s.emit_lines(
        lines,
        json_extra={
            "found": found,
            "moved": moved,
            "skipped_no_date": skipped_no_date,
            "skipped_conflict": skipped_conflict,
            "folders_created": folders_created,
            "renamed": renamed,
            "errors": errors,
            "mode": s["mode"],
            "granularity": s["granularity"],
            "midnight_shift_h": s["midnight_shift_h"],
            "sources": src_counts,
            "target_mode": mode_sel,
            "duration_hms": duration_hms,
            "recursive": s["recursive"],
            "include_hidden": s["include_hidden"],
            "dry_run": s["dry_run"],
        },
    )


if __name__ == "__main__":
    main()
