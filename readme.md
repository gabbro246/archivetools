# ArchiveTools

ArchiveTools is a suite of Python-based tools for streamlining file management tasks. It includes utilities for converting folders to ZIP archives (optionally with AES-256 encryption), extracting ZIPs with password handling, organizing media by date, detecting and deleting duplicate files, flattening folder structures, and setting file creation and modification dates using EXIF data, sidecar files, or metadata. The tools are designed to simplify managing large file collections and maintaining organized directories.

## Usage
- for installation see: [Installation](readme_installation.md)
- for more details about flags see: [Flags](readme_flags.md)

### Organize all Media by Date
This script organizes media files in a specified folder into subfolders based on their creation or modification dates. The date used for organization can be sourced from EXIF data, sidecar files, filenames, metadata, or folder names. You can organize files by day, week, month, or year. The script also automatically handles sidecar files. Optionally, early morning times (e.g., up to 03:00) can be treated as belonging to the previous day (`--midnight-shift`).

```bash
python organizebydate.py --folder [target_folder] --[day|week|month|year] [--rename] [--mode mode] [--midnight-shift]
```

### Flatten Folder Structure
This script flattens the folder structure of a specified directory by moving all files from subfolders into the root folder. This operation can be repeated iteratively to a specified depth. Optionally, the script can rename conflicting files instead of skipping them.

```bash
python flattenfolder.py --folder [target_folder] [--rename] [--depth n]
```

### Convert all Folders to ZIPs
This script compresses each folder within a specified directory into an individual ZIP archive. It supports optional AES-256 encryption. After creating each archive, it verifies that all files are included and match the original files' hashes. Upon successful verification, the original folder is automatically deleted.

```bash
python convertfolderstozips.py --folder [target_folder] [--aes256 [password]]
```

If no password is specified with `--aes256`, you will be prompted securely.

### Convert all ZIPs to Folders
This script extracts all ZIP files within a directory into folders. It supports extraction of AES-256 encrypted ZIPs and password handling. After extraction, it verifies that the extracted files match the original content. Upon successful verification, the original ZIP files are automatically deleted.

```bash
python convertzipstofolders.py --folder [target_folder] [--aes256 [password]]
```

If no password is specified with `--aes256`, you will be prompted securely when needed.

### Delete all Duplicate Files
This script scans a specified directory for duplicate media files by comparing their hash values. The preferred file to keep is determined based on a selectable strategy: EXIF data, sidecar files, filenames, metadata, or a heuristic. All detected duplicates are automatically deleted.

```bash
python deleteduplicates.py --folder [target_folder] [--mode mode]
```

### Set Files to Selected Date
This script sets the creation and modification dates of media files and their associated sidecar files to a selected date. The date can be chosen based on EXIF data, ffprobe metadata, sidecar files, filenames, folder names, or file timestamps. It also updates EXIF metadata (for JPEGs) and FFprobe metadata (for MP4/MOV files) where possible.

Supports dry-run mode and force-overwrite mode.

```bash
python setdates.py --folder [target_folder] [--mode mode] [--force] [--dry-run]
```

---
© 2025 gabbro246. All rights reserved.

