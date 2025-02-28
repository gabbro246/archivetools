# ArchiveTools

ArchiveTools is a suite of Python-based tools for streamlining file management tasks. It includes utilities for converting folders to ZIP archives, extracting ZIPs, organizing media by date, detecting and deleting duplicate files, flattening folder structures, and setting file creation and modification dates using EXIF data, sidecar files, or metadata. The tools are designed to simplify managing large file collections and maintaining organized directories.

## Installation

- **Python 3.7+** is required.
- Required Python packages:

```bash
pip install pillow colorama
```

```bash
git clone https://github.com/gabbro246/ArchiveTools.git
cd ArchiveTools
```

## Usage

### Organize all Media by Date
This script organizes media files in a specified folder into subfolders based on their creation or modification dates. The date used for organization can be sourced from EXIF data, sidecar files, or file metadata. You can organize files by day, week, month, or year. The script also (intends to) handle sidecar files. The available grouping modes are: By Day: `YYYYMMDD` (e.g., 20250228); By Week: `YYYYMMDD-YYYYMMDD - KWww` (e.g., 20250223-20250301 - KW09); By Month: `YYYYMMDD-YYYYMMDD - [Month Name]` (e.g., 20250201-20250228 - Februar); By Year: `YYYY` (e.g., 2025);

```bash
python organizebydate.py --folder [target_folder] --[day|week|month|year] [--rename] [--mode mode]
```

### Flatten Folder Structure
This script flattens the folder structure of a specified directory by moving all files and subfolders up one hierarchy level to the top level of the directory. This operation can be performed iteratively to a specified depth. Optionally, the script can rename conflicting files instead of skipping them.

```bash
python flattenfolder.py --folder [target_folder] [--rename] [--depth n]
```

### Convert all Folders to ZIPs
This script compresses all folders within a specified directory into individual ZIP archives. It incorporates a verification step to ensure that all files are correctly included and that their hashes match those of the original files. Upon successful verification, the original folder is automatically deleted.

```bash
python convertallfoldertozip.py --folder [target_folder]
```

### Convert all ZIPs to Folders
This script extracts all ZIP files within a directory into folders. It includes an integrity verification step to ensure that the extracted files match the original files' hashes. If the verification is successful, the original ZIP files are automatically deleted.

```bash
python convertallziptofolder.py --folder [target_folder]
```

### Delete all Duplicate Files
This script scans a specified directory for duplicate media files by comparing their hash values. The preferred file to keep is determined based on metadata or EXIF date, and all detected duplicates are automatically deleted.

```bash
python deleteduplicates.py --folder [target_folder] [--mode mode]
```

### Set Files to Selected Date
This script sets the creation and modification dates of media files and their associated sidecar files to a selected date. The date can be chosen based on EXIF data, file metadata, sidecar files, or the oldest available date.

```bash
python setdates.py --folder [target_folder] [--mode mode]
```

## Flags

| Flag             | Description                                                            | 
| ---------------- | ---------------------------------------------------------------------- | 
| `-f`, `--folder` | Path to target folder to process files.                                | 
| `--mode`         | Mode for date selection `default` `oldest` `exif` `sidecar` `metadata` |  
| `--rename`       | Renames files with naming conflicts instead of skipping them.          |   
| `--depth`        | Specifies the hierarchy level up to which the script should operate.   |
| `-d`, `--day`; `-w`, `--week`; `-m`, `--month`; `-y`, `--year` |                          |

| `--mode`    | Description                                           |
| ----------- | ----------------------------------------------------- |
| `default`   | Priority order: EXIF > Sidecar > Metadata.            |
| `oldest`    | Selects the oldest date from any source.              |
| `exif`      | Only uses EXIF dates, fallback to `default`.          |
| `sidecar`:  | Only uses sidecar file dates, fallback to `default`.  |
| `metadata`: | Only uses file metadata dates, fallback to `default`. | 

© 2025 gabbro246. All rights reserved.
