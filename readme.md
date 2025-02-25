# ArchiveTools

ArchiveTools is a suite of user-friendly Python-based tools designed to simplify file management and organization tasks. Whether you need to convert folders to ZIP archives, extract ZIP files back into folders, organize media files by date, or clean up duplicate files, ArchiveTools provides a reliable and efficient solution.

## 📦 Features
- **Convert Folders to ZIP:** Automatically compresses all folders within a specified directory into ZIP files, ensuring data integrity through hash-based verification.
- **Convert ZIPs to Folders:** Extracts ZIP files to restore the original folder structure, including a verification process to maintain data consistency.
- **Flatten Folder Structure:** Moves all files to a single directory level, with optional renaming to avoid file name conflicts.
- **Organize Media by Date:** Sorts photos and videos into date-based folders using EXIF data or file metadata, with automatic handling of sidecar files (e.g., .xmp, .json, .txt, .srt).
- **Delete Duplicate Files:** Scans a directory for duplicate files (images and videos) and retains only the preferred file based on EXIF or metadata information.

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

---

## `convertallfoldertozip.py`
This script scans a specified directory, converts all subfolders into ZIP files, and verifies the conversion using file hashes. If the ZIP file is confirmed to match the original files, the original folder is deleted to save space.

**Usage:**
```
python convertallfoldertozip.py --folder [target_folder]
```

### Flags
- `-f`, `--folder`: Specifies the target folder containing folders to convert into ZIP files.

## `convertallziptofolder.py`
This script takes all ZIP files in a specified directory, extracts their contents back into folders, and verifies data integrity by comparing file hashes. If verification is successful, the ZIP file is automatically deleted.

**Usage:**
```
python convertallziptofolder.py --folder [target_folder]
```

### Flags
- `-f`, `--folder`: Specifies the target folder containing ZIP files to extract.

## `flattenfolder.py`
Simplifies directory structures by moving all files to the top level of a specified folder. Can optionally rename files to avoid conflicts and control the depth of flattening.

**Usage:**
```
python flattenfolder.py --folder [target_folder] [--rename] [--depth n]
```

### Flags
- `-f`, `--folder`: Specifies the folder to flatten.
- `-r`, `--rename`: Renames files to avoid conflicts.
- `-d`, `--depth`: Sets the depth to flatten. Flattens all levels if not set.

## `organizemediabydate.py`
Organizes media files into date-based folders using either EXIF data or file metadata. Supports organization by day, week, month, or year, and manages sidecar files associated with images and videos.

**Usage:**
```
python organizemediabydate.py --folder [target_folder] --[day|week|month|year] [--rename]
```

### Flags
- `-f`, `--folder`: Specifies the folder containing media files.
- `-d`, `--day`: Organizes files by individual days.
- `-w`, `--week`: Organizes files by weeks.
- `-m`, `--month`: Organizes files by months.
- `-y`, `--year`: Organizes files by years.
- `--rename`: Renames files if a conflict occurs.

## `deleteallduplicate.py`
This script scans a directory for duplicate images and videos. It evaluates files based on their hashes and metadata, keeping the most relevant file (e.g., oldest photo based on EXIF data) and automatically deleting the rest.

**Usage:**
```
python deleteallduplicate.py --folder [target_folder]
```

### Flags
- `-f`, `--folder`: Specifies the folder to scan for duplicate files.

---

## 💡 Tips
- Always back up important files before running batch operations.
- Consider running the scripts on a test directory to become familiar with their behavior.

## 🛠️ Support
For help, please refer to the documentation or open an issue on the GitHub repository.

