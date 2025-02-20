# FolderContentsArchiver

ArchiveTools is a set of Python-based tools for managing data inside a specified folder.

## OrganizeMediaByDate
This script organizes media files into folders based on the date taken from EXIF data or file metadata within a specified directory.

`python organizemediabydate.py --folder [target_folder] --[day|week|month|year] [--rename]`

| Flag             | Description                            | Required |
|------------------|----------------------------------------|----------|
| `--folder`, `-f` | Target folder for organizing files     | Yes      |
| `--day`, `-d`    | Organize files by individual days      | Yes*     |
| `--week`, `-w`   | Organize files by weeks                | Yes*     |
| `--month`, `-m`  | Organize files by months               | Yes*     |
| `--year`, `-y`   | Organize files by years                | Yes*     |
| `--rename`       | Rename files if a name conflict occurs | No       |


## ConvertAllFolderToZip
This script converts all folders within a specified directory into ZIP archives and verifies their contents.

`python convertallfoldertozip.py --folder [target_folder]`

| Flag             | Description                                 | Required |
|------------------|---------------------------------------------|----------|
| `--folder`, `-f` | Target folder containing the folders to zip | Yes      |


## ConvertAllZipToFolder
 This script extracts all ZIP files within a given directory into folders and verifies the integrity of the extracted files.

 `python convertallziptofolder.py --folder [target_folder]`

| Flag              | Description                                   | Required |
|-------------------|-----------------------------------------------|----------|
| `--folder`, `-f`  | Target folder containing zip files to convert | Yes      |
