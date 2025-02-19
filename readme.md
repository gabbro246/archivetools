# FolderContentsArchiver

FolderContentsArchiver is a simple Python-based tool for compressing all folders in a given directory into ZIP archives and extracting ZIP archives back into folders. The tool ensures data integrity by verifying the file contents using SHA-256 hashing before deleting the original files.

## Features
- Batch Folder Compression: Converts all folders in a directory into ZIP files.
- Batch ZIP Extraction: Extracts all ZIP files in a directory back into folders.
- Integrity Verification: Uses SHA-256 checksums to verify data integrity before deletion.
- Logging Support: Provides detailed logs for process tracking.

## Installation
- Requirements: Python 3.x
- Clone this repository and navigate to the folder:
  ```sh
  git clone https://github.com/yourusername/FolderContentsArchiver.git
  cd FolderContentsArchiver
  ```

## Usage

### Convert All Folders to ZIP
Run the following command in the directory where you want to zip all folders:
```sh
python convertallfoldertozip.py [directory_path]
```
- If no directory path is provided, the current working directory is used.
- The script will skip already existing ZIP files.
- Original folders are deleted only if verification is successful.

### Convert All ZIPs to Folders
Run the following command in the directory where you want to extract all ZIPs:
```sh
python convertallziptofolder.py [directory_path]
```
- If no directory path is provided, the current working directory is used.
- The script will skip extraction if a folder with the same name already exists.
- ZIP files are deleted only if verification is successful.
