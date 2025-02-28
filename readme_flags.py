## ArchiveTools Flags

| Flag             | Description                                                                                 | Required |
| ---------------- | ------------------------------------------------------------------------------------------- | -------- |
| `-f`, `--folder` | Path to target folder to process files.                                                     | yes      |
| `--mode`         | Mode for date selection. One of `default` `oldest` `exif` `sidecar` `metadata` (see below). | no       |
| `--rename`       | Renames files with naming conflicts instead of skipping them.                               | no       |
| `--depth`        | Specifies the hierarchy level up to which the script should operate.                        | no       |
| `-d`, `--day`    |                                                                                             | yes*     |
| `-w`, `--week`   |                                                                                             | yes*     |
| `-m`, `--month`  |                                                                                             | yes*     |
| `-y`, `--year`   |                                                                                             | yes*     |


| `--mode`    | Description                                           |
| ----------- | ----------------------------------------------------- |
| `default`   | Priority order: EXIF > Sidecar > Metadata.            |
| `oldest`    | Selects the oldest date from any source.              |
| `exif`      | Only uses EXIF dates, fallback to `default`.          |
| `sidecar`:  | Only uses sidecar file dates, fallback to `default`.  |
| `metadata`: | Only uses file metadata dates, fallback to `default`. | 
