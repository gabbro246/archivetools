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
Automatically compresses all folders within a specified directory, including a verification process to maintain data consistency.

**Usage:**
```bash
python convertallfoldertozip.py --folder [target_folder]
```

**Flags:**
- `-f`, `--folder`: Specifies the target folder containing folders to convert into ZIP files.

### Convert ZIPs to Folders with `convertallziptofolder.py`
Automatically extracts all ZIP files within a specified directory, including a verification process to maintain data consistency.

**Usage:**
```bash
python convertallziptofolder.py --folder [target_folder]
```

**Flags:**
- `-f`, `--folder`: Specifies the target folder containing ZIP files to extract.

### Flatten Folder Structure with `flattenfolder.py`
Moves all files and folders up one level, with an optional depth argument to iterate through nested folders. Skips files with name conflicts or optionally renames them.

**Usage:**
```bash
python flattenfolder.py --folder [target_folder] [--rename] [--depth n]
```

**Flags:**
- `-f`, `--folder`: Specifies the folder to flatten.
- `--rename`: Renames files to avoid conflicts.
- `--depth`: Sets the depth to flatten.

### Organize Media by Date with `organizebydate.py`
Sorts media files into date-based folders using EXIF data, file metadata, or sidecar files. Automatically handles sidecar files and offers several date selection modes.

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
Scans a directory for duplicate files and retains only the preferred file based on EXIF or metadata information.

**Usage:**
```bash
python deleteallduplicate.py --folder [target_folder]
```

**Flags:**
- `-f`, `--folder`: Specifies the folder to scan for duplicate files.

### Set Files to Selected Date with `setdates.py`
Sets the file creation and modification dates of media files to a selected date based on various modes, including EXIF data, file metadata, sidecar files, or the oldest available date.

**Usage:**
```bash
python setdates.py --folder [target_folder] [--mode mode]
```

**Flags:**
- `-f`, `--folder`: Specifies the target folder to process media files.
- `--mode`: Specifies the mode for date selection. Options are the same as in the `organizebydate.py` script.

---

## 💡 Tips
- Always back up important files before running batch operations.
- Consider running the scripts on a test directory to become familiar with their behavior.

© 2025 gabbro246. All rights reserved.

