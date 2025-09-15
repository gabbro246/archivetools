## ArchiveTools Flags Overview

> For every script, **exactly one** of `-f/--folder` or `-s/--single` is required.

| Flag               | Description                                                                                                                                       | Required            | Scripts                                                   |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------- | --------------------------------------------------------- |
| `-v`, `--version`  | Display script version.                                                                                                                           |                     | All                                                       |
| `-f`, `--folder`   | **Batch mode** — operate on the **contents of this folder**.                                                                                      | one of `-f` or `-s` | All                                                       |
| `-s`, `--single`   | **Single mode** — operate on **this exact path** (file *or* folder, depends on the script; see notes below).                                      | one of `-f` or `-s` | All                                                       |
| `--mode`           | Date/priority strategy. One of `default`, `oldest`, `newest`, `exif`, `ffprobe`, `sidecar`, `filename`, `folder`, `metadata`.                     |                     | `organizebydate.py`, `setdates.py`, `deleteduplicates.py` |
| `--rename`         | Rename files instead of skipping on name conflicts.                                                                                               |                     | `organizebydate.py`, `flattenfolder.py`                   |
| `--depth`          | Flattening depth (relative to the selected folder). Level 1 = immediate children.                                                                 |                     | `flattenfolder.py`                                        |
| `-d`, `--day`      | Organize by day (e.g., `YYYYMMDD`).                                                                                                               | yes\*               | `organizebydate.py`                                       |
| `-w`, `--week`     | Organize by ISO week (e.g., `YYYYMMDD-YYYYMMDD - KWww`).                                                                                          | yes\*               | `organizebydate.py`                                       |
| `-m`, `--month`    | Organize by month (e.g., `YYYYMM - Month YYYY`).                                                                                                  | yes\*               | `organizebydate.py`                                       |
| `-y`, `--year`     | Organize by year (e.g., `YYYY`).                                                                                                                  | yes\*               | `organizebydate.py`                                       |
| `--force`          | Force overwrite of timestamps/metadata even if present.                                                                                           |                     | `setdates.py`                                             |
| `--dry-run`        | Preview changes without modifying files.                                                                                                          |                     | `setdates.py`, `deleteduplicates.py`                      |
| `--midnight-shift` | Treat early morning times (e.g., 00:00–03:00) as belonging to the previous day. Optional hours value; defaults to 3h if flag is used without one. |                     | `organizebydate.py`                                       |
| `--aes256`         | AES‑256 encryption/decryption. Provide a password, or pass the flag alone to be prompted as needed.                                               |                     | `convertfolderstozips.py`, `convertzipstofolders.py`      |
| `--verbose`        | Verbose output with detailed logs.                                                                                                                |                     | All                                                       |

\* one of `-d/--day`, `-w/--week`, `-m/--month`, or `-y/--year` is required for `organizebydate.py`.

---

### `--mode` Options

| Mode       | Description                                                                                   |
| ---------- | --------------------------------------------------------------------------------------------- |
| `default`  | Heuristic (combines ffprobe/EXIF/filename/folder/sidecar/timestamps; prefers best available). |
| `oldest`   | Select the oldest available date.                                                             |
| `newest`   | Select the newest available date.                                                             |
| `exif`     | Prefer EXIF dates.                                                                            |
| `ffprobe`  | Prefer container metadata via ffprobe/FFmpeg (video).                                         |
| `sidecar`  | Prefer sidecar file dates.                                                                    |
| `filename` | Parse date from filename.                                                                     |
| `folder`   | Parse date from parent folder name.                                                           |
| `metadata` | Use filesystem timestamps.                                                                    |

---

### What `-s/--single` expects per script

| Script                    | `-s` expects  | Behavior                                                                                  |
| ------------------------- | ------------- | ----------------------------------------------------------------------------------------- |
| `convertfolderstozips.py` | **Folder**    | Zip this folder itself into a sibling `<name>.zip`.                                       |
| `convertzipstofolders.py` | **.zip file** | Extract this one archive to a same‑named folder; verify; delete the zip on success.       |
| `setdates.py`             | **File**      | Set dates only on this file (OS timestamps, sidecars, and EXIF/FFmpeg where applicable).  |
| `organizebydate.py`       | **File**      | Move just this file into its correct dated subfolder (with sidecars).                     |
| `checkmediacorruption.py` | **File**      | Check only this file (PIL for images; ffprobe for videos).                                |
| `flattenfolder.py`        | **Folder**    | Move this folder’s contents up to its parent (ignore siblings); then clean empty subdirs. |
| `cleanup.py`              | **File**      | If junk or empty sidecar, delete; otherwise leave as‑is.                                  |
| `deleteduplicates.py`     | **File**      | Anchor on this file; find same‑hash matches in its parent tree; keep one per policy.      |
