import os
import sys
import argparse
import logging
import subprocess

from PIL import Image, UnidentifiedImageError

# Try to enable HEIF/HEIC support if available
_HEIF_SUPPORTED = False
try:
    import pillow_heif  # type: ignore

    pillow_heif.register_heif_opener()
    _HEIF_SUPPORTED = True
except Exception:
    _HEIF_SUPPORTED = False

from archivetools import (
    configure_logging,
    add_target_args,
    resolve_target,
    iter_files,
    MEDIA_EXTENSIONS,
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
    RunSummary,
)

# ------------------------------------------------------------
# Checking helpers
# ------------------------------------------------------------

def check_image_file(path: str, *, strict: bool = True) -> tuple[bool, str]:
    """
    Return (ok, reason). reason is 'ok', 'unsupported', or error message.
    If strict=True, we attempt to fully load after verify to catch truncated data.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext in (".heic", ".heif") and not _HEIF_SUPPORTED:
        return False, "unsupported"

    try:
        with Image.open(path) as im:
            im.verify()  # quick structural check
        if strict:
            # reopen to ensure data can be read (verify invalidates the parser)
            with Image.open(path) as im2:
                _ = im2.size  # force read headers
                im2.load()    # read the whole file
        return True, "ok"
    except UnidentifiedImageError:
        return False, "unidentified"
    except (OSError, ValueError) as e:
        # OSError includes truncated files, decoder errors, etc.
        return False, f"image-error:{e.__class__.__name__}"
    except Exception as e:
        return False, f"exception:{e.__class__.__name__}"


def _run_ffprobe_duration(path: str) -> tuple[bool, float | None, str]:
    """
    Try to extract duration (seconds) using ffprobe.
    Returns (ran, duration, stderr_excerpt).
    - ran=False indicates ffprobe not available or execution failure without result.
    """
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "format=duration",
        "-of",
        "default=nw=1:nk=1",
        path,
    ]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, encoding="utf-8").strip()
        if not out:
            return True, None, ""
        try:
            dur = float(out.splitlines()[0])
            return True, dur, ""
        except Exception:
            return True, None, out[:200]
    except FileNotFoundError:
        return False, None, "ffprobe-not-found"
    except subprocess.CalledProcessError as e:
        # ffprobe ran but file likely invalid/unreadable
        return True, None, (e.output or "")[:200]
    except Exception as e:
        return False, None, f"exception:{e.__class__.__name__}"


def check_video_file(path: str, *, min_duration: float | None = 0.0) -> tuple[bool, str]:
    """
    Return (ok, reason). ok=True if ffprobe runs and returns a numeric duration
    (and, if min_duration is set, duration >= min_duration).
    """
    ran, duration, info = _run_ffprobe_duration(path)
    if not ran:
        return False, info or "ffprobe-failed"
    if duration is None:
        return False, "no-duration"
    if min_duration is not None and duration < float(min_duration):
        return False, f"short:{duration:.3f}"
    return True, "ok"


# ------------------------------------------------------------
# Processing
# ------------------------------------------------------------

def _handle_one_file(path: str, *, check_images: bool, check_videos: bool, min_video_duration: float | None,
                     verbose: bool, summary: RunSummary | None) -> None:
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()

    if ext in IMAGE_EXTENSIONS and check_images:
        ok, reason = check_image_file(path, strict=True)
        if ok:
            if summary: summary.inc("images_ok")
            if verbose: logging.debug("Image OK", extra={"target": name})
        else:
            # treat unsupported HEIF as skipped, not corrupt
            if reason == "unsupported":
                logging.warning("Skipped (HEIF/HEIC unsupported)", extra={"target": name})
                if summary: summary.inc("images_unsupported")
            else:
                logging.error("Corrupted image (%s)", reason, extra={"target": name})
                if summary:
                    summary.inc("images_corrupt")
                    summary.inc("corrupt_total")
        if summary: summary.inc("images_checked")
        return

    if ext in VIDEO_EXTENSIONS and check_videos:
        ok, reason = check_video_file(path, min_duration=min_video_duration)
        if ok:
            if summary: summary.inc("videos_ok")
            if verbose: logging.debug("Video OK", extra={"target": name})
        else:
            if reason == "ffprobe-not-found":
                logging.warning("Skipped (ffprobe not found)", extra={"target": name})
                if summary: summary.inc("videos_ffprobe_missing")
            else:
                logging.error("Corrupted video (%s)", reason, extra={"target": name})
                if summary:
                    summary.inc("videos_corrupt")
                    summary.inc("corrupt_total")
        if summary: summary.inc("videos_checked")
        return

    # Non-media or filtered out by type
    if summary: summary.inc("skipped_nonmedia")
    if verbose:
        logging.debug("Skipping non-target file", extra={"target": name})


def _batch_mode(root: str, *, recursive: bool, include_hidden: bool, check_images: bool, check_videos: bool,
                min_video_duration: float | None, verbose: bool, summary: RunSummary | None) -> None:
    # Determine filter set
    if check_images and check_videos:
        ext_filter = set(MEDIA_EXTENSIONS)
    elif check_images:
        ext_filter = set(IMAGE_EXTENSIONS)
    elif check_videos:
        ext_filter = set(VIDEO_EXTENSIONS)
    else:
        ext_filter = set(MEDIA_EXTENSIONS)

    paths = list(
        iter_files(
            root,
            recursive=recursive,
            include_hidden=include_hidden,
            ext_filter=ext_filter,
        )
    )
    if summary:
        summary.set("files_seen", len(paths))
    for p in paths:
        _handle_one_file(
            p,
            check_images=check_images,
            check_videos=check_videos,
            min_video_duration=min_video_duration,
            verbose=verbose,
            summary=summary,
        )


def _single_mode(path: str, *, check_images: bool, check_videos: bool, min_video_duration: float | None,
                 verbose: bool, summary: RunSummary | None) -> None:
    _handle_one_file(
        path,
        check_images=check_images,
        check_videos=check_videos,
        min_video_duration=min_video_duration,
        verbose=verbose,
        summary=summary,
    )


# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Scan media files for corruption. Images are verified with Pillow; videos are probed with ffprobe. "
            "Non-recursive by default — use --recursive to include subfolders."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    add_target_args(
        parser,
        folder_help="Batch mode: check media in this folder (non-recursive by default; use --recursive to include subfolders).",
        single_help="Single mode: check exactly this file.",
        required=True,
    )

    typ = parser.add_mutually_exclusive_group()
    typ.add_argument("--images-only", action="store_true", help="Only check images")
    typ.add_argument("--videos-only", action="store_true", help="Only check videos")

    parser.add_argument(
        "--min-video-duration",
        type=float,
        default=0.0,
        help="Treat videos shorter than this many seconds as corrupt (0 disables the check).",
    )
    parser.add_argument(
        "--zero-exit",
        action="store_true",
        help="Always exit with code 0 even if corrupted files are found.",
    )

    args = parser.parse_args()
    configure_logging(getattr(args, "verbose", False))

    # Resolve target: single expects file; batch expects folder
    mode_sel, target = resolve_target(args, single_expect="file", folder_expect="folder")

    check_images = not args.videos_only
    check_videos = not args.images_only
    min_video_duration = None if (args.min_video_duration or 0) <= 0 else float(args.min_video_duration)

    s = RunSummary()
    s.set("recursive", bool(getattr(args, "recursive", False)))
    s.set("include_hidden", bool(getattr(args, "include_hidden", False)))
    s.set("check_images", check_images)
    s.set("check_videos", check_videos)
    s.set("heif_supported", _HEIF_SUPPORTED)

    if mode_sel == "single":
        _single_mode(
            target,
            check_images=check_images,
            check_videos=check_videos,
            min_video_duration=min_video_duration,
            verbose=getattr(args, "verbose", False),
            summary=s,
        )
    else:
        _batch_mode(
            target,
            recursive=bool(getattr(args, "recursive", False)),
            include_hidden=bool(getattr(args, "include_hidden", False)),
            check_images=check_images,
            check_videos=check_videos,
            min_video_duration=min_video_duration,
            verbose=getattr(args, "verbose", False),
            summary=s,
        )

    # Summary
    images_checked = s.get("images_checked", 0)
    videos_checked = s.get("videos_checked", 0)
    images_ok = s.get("images_ok", 0)
    videos_ok = s.get("videos_ok", 0)
    images_corrupt = s.get("images_corrupt", 0)
    videos_corrupt = s.get("videos_corrupt", 0)
    images_unsupported = s.get("images_unsupported", 0)
    videos_ffprobe_missing = s.get("videos_ffprobe_missing", 0)
    corrupt_total = s.get("corrupt_total", 0)
    files_seen = s.get("files_seen", 0)

    line1 = (
        f"Checked {files_seen or (images_checked + videos_checked)} file(s): "
        f"{images_checked} images, {videos_checked} videos."
    )
    line2 = (
        f"OK — images {images_ok}, videos {videos_ok}. "
        f"Corrupt — images {images_corrupt}, videos {videos_corrupt}."
    )
    notes = []
    if images_unsupported:
        notes.append(f"{images_unsupported} HEIF/HEIC skipped (no decoder)")
    if videos_ffprobe_missing:
        notes.append("ffprobe not found (videos skipped)")
    line3 = "Notes: " + "; ".join(notes) if notes else "Notes: none."

    s.emit_lines(
        [line1, line2, line3],
        json_extra={
            "files_seen": files_seen,
            "images_checked": images_checked,
            "images_ok": images_ok,
            "images_corrupt": images_corrupt,
            "images_unsupported": images_unsupported,
            "videos_checked": videos_checked,
            "videos_ok": videos_ok,
            "videos_corrupt": videos_corrupt,
            "videos_ffprobe_missing": videos_ffprobe_missing,
            "corrupt_total": corrupt_total,
            "recursive": s["recursive"],
            "include_hidden": s["include_hidden"],
            "check_images": s["check_images"],
            "check_videos": s["check_videos"],
            "heif_supported": s["heif_supported"],
            "target_mode": mode_sel,
            "target": target,
        },
    )

    if corrupt_total and not args.zero_exit:
        sys.exit(1)


if __name__ == "__main__":
    main()
