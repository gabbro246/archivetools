## ArchiveTools Flags Overview

| Flag               | Description                                                                                                                                      | Required | Scripts                                                   |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ | -------- | --------------------------------------------------------- |
| `-v`, `--version`  | Display script version.                                                                                                                          |          | All                                                       |
| `-f`, `--folder`   | Path to target folder to process.                                                                                                                | yes      | All                                                       |
| `--mode`           | Mode for date selection. One of `default`, `oldest`, `newest`, `exif`, `ffprobe`, `sidecar`, `filename`, `folder`, `metadata`.                   |          | `organizebydate.py`, `setdates.py`, `deleteduplicates.py` |
| `--rename`         | Rename files instead of skipping them if duplicates exist or conflicts occur.                                                                    |          | `organizebydate.py`, `flattenfolder.py`                   |
| `--depth`          | Specifies folder flattening depth.                                                                                                               |          | `flattenfolder.py`                                        |
| `-d`, `--day`      | Organize by day (e.g., `YYYYMMDD`).                                                                                                              | yes\*    | `organizebydate.py`                                       |
| `-w`, `--week`     | Organize by ISO week (e.g., `YYYYMMDD-YYYYMMDD - KWww`).                                                                                         | yes\*    | `organizebydate.py`                                       |
| `-m`, `--month`    | Organize by month (e.g., `YYYYMMDD-YYYYMMDD - Februar`).                                                                                         | yes\*    | `organizebydate.py`                                       |
| `-y`, `--year`     | Organize by year (e.g., `YYYY`).                                                                                                                 | yes\*    | `organizebydate.py`                                       |
| `--force`          | Force overwrite of all timestamps, even if they already exist.                                                                                   |          | `setdates.py`                                             |
| `--dry-run`        | Preview changes without modifying files or metadata.                                                                                             |          | `setdates.py`                                             |
| `--midnight-shift` | Treat early morning times (e.g., 00:00–03:00) as belonging to the previous day. Optional value in hours. Defaults to 3h if used without a value. |          | `organizebydate.py`                                       |
| `--aes256`         | Enable AES-256 encryption or decryption. Optionally supply a password directly. If omitted, you will be prompted.                                |          | `convertfolderstozips.py`, `convertzipstofolders.py`      |
| `--verbose`        | Enable verbose output with detailed logs for each processing step.                                                                               |          | All                                                       |


### `--mode` Options

| Mode       | Description                                                         |
| ---------- | ------------------------------------------------------------------- |
| `default`  | Heuristic: FFprobe > EXIF > Filename > Folder > Sidecar > Metadata. |
| `oldest`   | Selects the oldest date from any source.                            |
| `newest`   | Selects the newest date from any source.                            |
| `exif`     | Uses EXIF dates only, fallback to `default`.                        |
| `ffprobe`  | Uses FFprobe metadata from video files, fallback to `default`.      |
| `sidecar`  | Uses sidecar file dates, fallback to `default`.                     |
| `filename` | Extracts date from filename, fallback to `default`.                 |
| `folder`   | Extracts date from parent folder name, fallback to `default`.       |
| `metadata` | Uses file timestamps (Created, Modified), fallback to `default`.    |
