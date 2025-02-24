# ArchiveTools

ArchiveTools is a set of Python-based tools for managing and organizing files within a specified folder. It includes scripts for compressing and extracting folders, flattening directory structures, and organizing media files by date. The tools are designed with verification and error handling to ensure data integrity.

## 📦 Features
- **Convert All Folders to ZIP:** Compresses folders into ZIP files with verification and hash-based integrity checks.
- **Convert All ZIPs to Folders:** Extracts ZIP files to restore original folder structures while ensuring data consistency.
- **Flatten Folder Structure:** Moves all files to a single level, handling naming conflicts through optional renaming.
- **Organize Media by Date:** Sorts images and videos into date-based folders using EXIF data or file metadata, with sidecar file management.

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

## `organizemediabydate.py`

This script organizes media files into folders based on their creation date, using either EXIF data (for images) or standard file metadata. It supports organization by day, week, month, or year, and can handle renaming conflicts automatically. Additionally, it moves related sidecar files (.xmp, .json, .txt, .srt) to ensure associated metadata or subtitles remain in sync.

Possible Folder Naming Patterns:

- By Day: YYYYMMDD
- By Week: YYYYMMDD-YYYYMMDD - KWXX (e.g., 20240101-20240107 - KW01)
- By Month: YYYYMMDD-YYYYMMDD - MonthName (e.g., 20240101-20240131 - January)
- By Year: YYYY

**Usage:**
```
python organizemediabydate.py --folder [target_folder] --[day|week|month|year] [--rename]
```

**Options:**
| Flag             | Description                            | Required |
|------------------|----------------------------------------|----------|
| `--folder`, `-f` | Target folder for organizing files     | Yes      |
| `--day`, `-d`    | Organize files by individual days      | Yes*     |
| `--week`, `-w`   | Organize files by weeks                | Yes*     |
| `--month`, `-m`  | Organize files by months               | Yes*     |
| `--year`, `-y`   | Organize files by years                | Yes*     |
| `--rename`       | Rename files if a name conflict occurs | No       |

## `flattenfolder.py`
This script flattens complex directory structures by moving all files to the top-level directory. It provides an option to rename files to avoid conflicts when duplicate names are detected. You can also limit the depth of the flattening process to prevent unintended file relocations.

**Usage:**
```
python flattenfolder.py --folder [target_folder] [--rename] [--depth n]
```

**Options:**
| Flag             | Description                                 | Required |
|------------------|---------------------------------------------|----------|
| `--folder`, `-f` | Path to the folder to flatten               | Yes      |
| `--rename`, `-r` | Rename files to avoid naming conflicts      | No       |
| `--depth`, `-d`  | Depth to flatten. Flattens all levels if not set | No       |

## `convertallfoldertozip.py`
This script converts all folders within a specified directory into ZIP archives. It verifies the contents of each ZIP file by comparing file hashes to ensure data integrity. If the verification is successful, the original folder is deleted, freeing up space. Existing ZIP files are automatically skipped to prevent unnecessary processing.

**Usage:**
```
python convertallfoldertozip.py --folder [target_folder]
```

**Options:**
| Flag             | Description                                 | Required |
|------------------|---------------------------------------------|----------|
| `--folder`, `-f` | Target folder containing the folders to zip | Yes      |

## `convertallziptofolder.py`
This script extracts all ZIP files in a given directory, recreating the original folder structure. It includes a verification step to match file hashes between the ZIP and the extracted files. Successfully verified ZIP files are automatically deleted, keeping the directory clean and organized.

**Usage:**
```
python convertallziptofolder.py --folder [target_folder]
```

**Options:**
| Flag              | Description                                   | Required |
|-------------------|-----------------------------------------------|----------|
| `--folder`, `-f`  | Target folder containing zip files to convert | Yes      |