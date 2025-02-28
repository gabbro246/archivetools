# ArchiveTools

ArchiveTools is a suite of user-friendly Python-based tools designed to simplify file management and organization tasks. Whether you need to convert folders to ZIP archives, extract ZIP files back into folders, organize media files by date, clean up duplicate files, flatten folder structures, or set files to a specific date using advanced selection modes, ArchiveTools provides a reliable and efficient solution.

## 🚀 Installation
### Prerequisites
- **Python 3.7+**
- Required Python packages:
```
pip install pillow
```

### Clone the Repository
```
git clone https://github.com/gabbro246/ArchiveTools.git
cd ArchiveTools
```

## 📂 Usage

### Convert Folders to ZIP with `convertallfoldertozip.py`
Automatically compresses all folders within a specified directory into ZIP files, ensuring data integrity through hash-based verification.

**Usage:** `python convertallfoldertozip.py --folder [target_folder]`

**Flags:**
- `-f`, `--folder`: Specifies the target folder containing folders to convert into ZIP files.

### Convert ZIPs to Folders with `convertallziptofolder.py`
Extracts ZIP files to restore the original folder structure, including a verification process to maintain data consistency.

**Usage:** `python convertallziptofolder.py --folder [target_folder]`

**Flags:**
- `-f`, `--folder`: Specifies the target folder containing ZIP files to extract.

### Flatten Folder Structure with `flattenfolder.py`
Moves all files to a single directory level, with optional renaming to avoid file name conflicts.

**Usage:** `python flattenfolder.py --folder [target_folder] [--rename] [--depth n]`

**Flags:**
- `-f`, `--folder`: Specifies the folder to flatten.
- `-r`, `--rename`: Renames files to avoid conflicts.
- `-d`, `--depth`: Sets the depth to flatten. Flattens all levels if not set.

### Organize Media by Date with `organizemediabydate.py`
Sorts photos and videos into date-based folders using EXIF data or file metadata, with automatic handling of sidecar files (e.g., .xmp, .json, .txt, .srt).

**Usage:** `python organizemediabydate.py --folder [target_folder] --[day|week|month|year] [--rename]`

**Flags:**
- `-f`, `--folder`: Specifies the folder containing media files.
- `-d`, `--day`: Organizes files by individual days.
- `-w`, `--week`: Organizes files by weeks.
- `-m`, `--month`: Organizes files by months.
- `-y`, `--year`: Organizes files by years.
- `--rename`: Renames files if a conflict occurs.

### Delete Duplicate Files with `deleteallduplicate.py`
Scans a directory for duplicate files (images and videos) and retains only the preferred file based on EXIF or metadata information.

**Usage:** `python deleteallduplicate.py --folder [target_folder]`

**Flags:**
- `-f`, `--folder`: Specifies the folder to scan for duplicate files.

### Set Files to Selected Date with `setdates.py`
Sets the file creation and modification dates to a selected date based on various modes, including EXIF data, file metadata, sidecar files, or the oldest available date.

**Usage:** `python setdates.py --folder [target_folder] [--mode mode]`

**Flags:**
- `-f`, `--folder`: Specifies the target folder to process files.
- `-m`, `--mode`: Specifies the mode for date selection. Options are:
  - `default`: Prioritizes EXIF dates, then sidecar, then metadata.
  - `oldest`: Selects the oldest date available from any source.
  - `exif`: Selects the oldest EXIF date if available.
  - `sidecar`: Selects the oldest date from sidecar files.
  - `metadata`: Selects the oldest file creation or modification date.

---

## 💡 Tips
- Always back up important files before running batch operations.
- Consider running the scripts on a test directory to become familiar with their behavior.

© 2025 gabbro246. All rights reserved.

