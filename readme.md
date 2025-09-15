# ArchiveTools

ArchiveTools is a suite of small, focused Python scripts for tidying large media archives:

* Convert folders ↔ ZIPs (with optional AES‑256)
* Organize photos/videos into dated folders
* Detect & delete exact duplicates
* Flatten nested folder structures
* Clean junk/empty files & folders
* Set file dates from metadata (EXIF/ffprobe/etc.)
* Check media for basic corruption

Each tool is standalone.

---

## Installation

See **[Installation](installation.md)**.

---

## Flags & Conventions

See **[Flags](flags.md)** for the full list.

**Important target selection (consistent across all tools):**

* `-f, --folder` → **Batch mode** — operate on the **contents of this folder**.
* `-s, --single` → **Single mode** — operate on **this exact path** (file *or* folder, depending on the tool).

> Exactly **one** of `-f/--folder` or `-s/--single` is required.

---

## Tools

### Organize Media by Date

Organize media into subfolders by **day / week / month / year** using EXIF, ffprobe, sidecars, filename, folder name, or timestamps. Matching sidecars move with the media. Optional `--midnight-shift` groups early hours into the previous day.

**Batch (inside folder):**

```bash
python organizebydate.py -f /media/2024/Phone --day [--rename] [--mode default] [--midnight-shift] [--verbose]
```

**Single (one file):**

```bash
python organizebydate.py -s /media/2024/Phone/IMG_0001.JPG --day [--rename] [--mode default] [--midnight-shift]
```

---

### Flatten Folder Structure

Move files from subfolders up; optionally limit depth; rename on conflict if requested.

**Batch (within the folder itself):**

```bash
python flattenfolder.py -f /media/Inbox [--rename] [--depth 2] [--verbose]
```

**Single (lift this folder’s contents to its parent):**

```bash
python flattenfolder.py -s /media/Inbox/ToMerge [--rename] [--depth 2]
```

---

### Convert Folders to ZIPs

Create a `.zip` per **immediate subfolder** (batch) or zip **this folder itself** (single). Supports **AES‑256**; verifies contents by hash and deletes source folders on success.

**Batch (zip each subfolder):**

```bash
python convertfolderstozips.py -f /archive/Albums [--aes256 [password]] [--verbose]
```

**Single (zip this folder):**

```bash
python convertfolderstozips.py -s /archive/Albums/ParisTrip [--aes256 [password]]
```

> If `--aes256` is passed without a value, you’ll be prompted for a password.

---

### Convert ZIPs to Folders

Extract all `.zip` files in a folder (batch) or extract **this one `.zip`** (single). Verifies contents by hash and deletes zips on success. AES‑256/password supported.

**Batch (all zips in folder):**

```bash
python convertzipstofolders.py -f /incoming/Zips [--aes256 [password]] [--verbose]
```

**Single (this one zip):**

```bash
python convertzipstofolders.py -s /incoming/Zips/ParisTrip.zip [--aes256 [password]]
```

---

### Delete Duplicate Media

Exact‑duplicate detection by **content hash** with a keeper chosen via `--mode` (default heuristic or by EXIF/ffprobe/filename/folder/metadata; oldest/newest also supported).

**Batch (whole folder tree):**

```bash
python deleteduplicates.py -f /media/Library [--mode default] [--dry-run] [--verbose]
```

**Single (anchor this file; act on its duplicate set):**

```bash
python deleteduplicates.py -s /media/Library/IMG_0001.JPG [--mode default] [--dry-run]
```

---

### Set File Dates

Set file OS timestamps (+ sidecars) and, when applicable, **EXIF** (JPEG) and **FFmpeg creation\_time** (MP4/MOV), based on the selected date source/mode. Supports `--dry-run` and `--force`.

**Batch (inside folder):**

```bash
python setdates.py -f /media/PhoneDump [--mode default] [--force] [--dry-run] [--verbose]
```

**Single (one file):**

```bash
python setdates.py -s /media/PhoneDump/IMG_0001.JPG [--mode default] [--force] [--dry-run]
```

---

### Clean up Junk & Empty

Delete empty sidecars, common junk files/folders (`.DS_Store`, `desktop.ini`, AppleDouble `._*`, `__MACOSX`, etc.), and empty folders.

**Batch (full tree):**

```bash
python cleanup.py -f /archive [--verbose]
```

**Single (one file decision):**

```bash
python cleanup.py -s /archive/._Thumbs.db
```

---

### Check Media for Corruption

Verify images (via PIL) and videos (via ffprobe) can be read.

**Batch (folder tree):**

```bash
python checkmediacorruption.py -f /archive [--verbose]
```

**Single (one file):**

```bash
python checkmediacorruption.py -s /archive/clip_031.mov
```

---

© 2025 gabbro246. All rights reserved.
