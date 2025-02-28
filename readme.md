# ArchiveTools

ArchiveTools is a suite of user-friendly Python-based tools designed to simplify file management and organization tasks. Whether you need to convert folders to ZIP archives, extract ZIP files back into folders, organize media files by date, clean up duplicate files, flatten folder structures, or set files to a specific date using advanced selection modes, ArchiveTools provides a reliable and efficient solution.

## 🚀 Installation
### Prerequisites
- **Python 3.7+**
- Required Python packages:
```bash
pip install pillow colorama
```

### Clone the Repository
```bash
git clone https://github.com/gabbro246/ArchiveTools.git
cd ArchiveTools
```

## 📂 Usage

### Convert Folders to ZIP with `convertallfoldertozip.py`
This script is designed to compress all folders in a specified directory into ZIP archives. It includes a verification step to ensure that all files in the folder are properly included and match the hashes of the original files. If the verification succeeds, the original folder is deleted.

**Usage:**
```bash
python convertallfoldertozip.py --folder [target_folder]
```

**Flags:**
- `-f`, `--folder`: Specifies the target folder containing folders to convert into ZIP files.

### Convert ZIPs to Folders with `convertallziptofolder.py`
This script extracts all ZIP files in a directory back into folders. It verifies the integrity of the extraction by checking that the extracted files match the original files' hashes. If verification is successful, the ZIP files are deleted.

**Usage:**
```bash
python convertallziptofolder.py --folder [target_folder]
```

**Flags:**
- `-f`, `--folder`: Specifies the target folder containing ZIP files to extract.

### Flatten Folder Structure with `flattenfolder.py`
This script flattens the folder structure of a specified directory by moving all files and folders one hierarchy level up to the top level of the directory. This can be done iteratively to a certain depth. Optionally, it renames conflicting files instead of skipping them.

**Usage:**
```bash
python flattenfolder.py --folder [target_folder] [--rename] [--depth n]
```

**Flags:**
- `-f`, `--folder`: Specifies the folder to flatten.
- `--rename`: Renames files to avoid conflicts.
- `--depth`: Sets the depth to flatten.

### Organize Media by Date with `organizebydate.py`
This script organizes media files in a specified folder into subfolders based on their creation or modification dates. The date used for organization can come from EXIF data, sidecar files, or file metadata. You can organize by day, week, month, or year. It also (should) handle sidecar files.

Folder naming conventions:

- By Day: `YYYYMMDD` (e.g., 20250228)
- By Week: `YYYYMMDD-YYYYMMDD - KWww` (e.g., 20250223-20250301 - KW09)
- By Month: `YYYYMMDD-YYYYMMDD - [German Month Name]` (e.g., 20250201-20250228 - Februar)
- By Year: `YYYY` (e.g., 2025)


**Usage:**
```bash
python organizebydate.py --folder [target_folder] --[day|week|month|year] [--rename] [--mode mode]
```

**Flags:**
- `-f`, `--folder`: Specifies the folder containing media files.
- `-d`, `--day`: Organizes files by individual days.
- `-w`, `--week`: Organizes files by weeks.
- `-m`, `--month`: Organizes files by months.
- `-y`, `--year`: Organizes files by years.
- `--rename`: Renames files instead of skipping.
- `--mode`: Specifies the mode for date selection. Options are:
  - `default`: EXIF > Sidecar > Metadata.
  - `oldest`: Selects the oldest date from any source.
  - `exif`: Only uses EXIF dates.
  - `sidecar`: Only uses sidecar file dates.
  - `metadata`: Only uses file metadata dates.

### Delete Duplicate Files with `deleteallduplicate.py`
This script scans a specified directory for duplicate media files (JPEG images and MP4 videos) by comparing their hash values. The preferred file to keep is selected based on metadata or EXIF date, and the duplicates are deleted.

**Usage:**
```bash
python deleteallduplicate.py --folder [target_folder]
```

**Flags:**
- `-f`, `--folder`: Specifies the folder to scan for duplicate files.
- `--mode`: Specifies the mode for date selection of the kept file. Options are:
  - `default`: EXIF > Sidecar > Metadata.
  - `oldest`: Selects the oldest date from any source.
  - `exif`: Only uses EXIF dates.
  - `sidecar`: Only uses sidecar file dates.
  - `metadata`: Only uses file metadata dates.

### Set Files to Selected Date with `setdates.py`
This script sets the creation and modification dates of media files and their associated sidecar files to a selected date, which can be chosen based on EXIF data, file metadata, sidecar files, or the oldest available date.

**Usage:**
```bash
python setdates.py --folder [target_folder] [--mode mode]
```

**Flags:**
- `-f`, `--folder`: Specifies the target folder to process media files.
- `--mode`: Specifies the mode for date selection of the kept file. Options are:
  - `default`: EXIF > Sidecar > Metadata.
  - `oldest`: Selects the oldest date from any source.
  - `exif`: Only uses EXIF dates.
  - `sidecar`: Only uses sidecar file dates.
  - `metadata`: Only uses file metadata dates.


## 💡 Tips
- Always back up important files before running batch operations.
- Consider running the scripts on a test directory to become familiar with their behavior.

© 2025 gabbro246. All rights reserved.

