## ArchiveTools Flags Overview

| Flag               | Description                                                                                             | Required In              | Optional In                              |
|--------------------|---------------------------------------------------------------------------------------------------------|--------------------------|------------------------------------------|
| `-f`, `--folder`   | Path to target folder to process.                                                                       | All                      |                                          |
| `--mode`           | Mode for date selection. One of `default`, `oldest`, `newest`, `exif`, `ffprobe`, `sidecar`, `filename`, `folder`, `metadata`. | `organizebydate.py`, `setdates.py`, `deleteduplicates.py` |                                          |
| `--rename`         | Rename files instead of skipping them if duplicates exist.                                               |                          | `organizebydate.py`, `flattenfolder.py`  |
| `--depth`          | Specifies folder flattening depth.                                                                       |                          | `flattenfolder.py`                       |
| `-d`, `--day`      | Organize by day (e.g. `YYYYMMDD`).                                                                      | `organizebydate.py`      |                                          |
| `-w`, `--week`     | Organize by ISO week (e.g. `YYYYMMDD-YYYYMMDD - KWww`).                                                  | `organizebydate.py`      |                                          |
| `-m`, `--month`    | Organize by month (e.g. `YYYYMMDD-YYYYMMDD - Februar`).                                                 | `organizebydate.py`      |                                          |
| `-y`, `--year`     | Organize by year (e.g. `YYYY`).                                                                         | `organizebydate.py`      |                                          |
| `--force`          | Force overwrite of all timestamps, regardless of existing date values.                                 |                          | `setdates.py`                            |
| `--dry-run`        | Preview changes without modifying files.                                                                |                          | `setdates.py`                            |

### `--mode` Options

| Mode         | Description                                                                 |
|--------------|-----------------------------------------------------------------------------|
| `default`    | Heuristic: FFprobe > EXIF > Filename > Folder > Sidecar > Metadata.         |
| `oldest`     | Selects the oldest date from any source.                                    |
| `newest`     | Selects the newest date from any source.                                    |
| `exif`       | Uses EXIF dates only, fallback to `default`.                                |
| `ffprobe`    | Uses FFprobe metadata from video files, fallback to `default`.              |
| `sidecar`    | Uses sidecar file dates, fallback to `default`.                             |
| `filename`   | Extracts date from filename, fallback to `default`.                         |
| `folder`     | Extracts date from parent folder name, fallback to `default`.               |
| `metadata`   | Uses file timestamps (Created, Modified), fallback to `default`.            |

