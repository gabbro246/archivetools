## ArchiveTools Flags

| Flag             | Description                                                                                 | Required |
| ---------------- | ------------------------------------------------------------------------------------------- | -------- |
| `-f`, `--folder` | Path to target folder to process files.                                                     | yes      |
| `--mode`         | Mode for date selection. One of `default` `oldest` `exif` `sidecar` `metadata` (see below). | no       |
| `--rename`       | Renames files with naming conflicts instead of skipping them.                               | no       |
| `--depth`        | Specifies the hierarchy level up to which the script should operate.                        | no       |
| `-d`, `--day`    | `YYYYMMDD` (e.g., 20250228)                                                                 | yes*     |
| `-w`, `--week`   | `YYYYMMDD-YYYYMMDD - KWww` (e.g., 20250223-20250301 - KW09)                                 | yes*     |
| `-m`, `--month`  | `YYYYMMDD-YYYYMMDD - [Month Name]` (e.g., 20250201-20250228 - Februar)                      | yes*     |
| `-y`, `--year`   | `YYYY` (e.g., 2025)                                                                         | yes*     |


| `--mode`    | Description                                           |
| ----------- | ----------------------------------------------------- |
| `default`   | Priority order: EXIF > Sidecar > Metadata.            |
| `oldest`    | Selects the oldest date from any source.              |
| `exif`      | Only uses EXIF dates, fallback to `default`.          |
| `sidecar`:  | Only uses sidecar file dates, fallback to `default`.  |
| `metadata`: | Only uses file metadata dates, fallback to `default`. | 
