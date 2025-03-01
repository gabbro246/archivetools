---
# ArchiveTools Installation

## Requirements

- **Python 3.7+**
- Installing Required Python packages:

```bash
pip install pillow colorama
```

## Clone Repository

```bash
git clone https://github.com/gabbro246/ArchiveTools.git
cd ArchiveTools
```

## Add to path (optional)
### Windows

To add a directory to the system `Path` using PowerShell, open PowerShell as Administrator and run:

```powershell
$envPath = [System.Environment]::GetEnvironmentVariable("Path", [System.EnvironmentVariableTarget]::Machine)
[System.Environment]::SetEnvironmentVariable("Path", $envPath + ";C:\Scripts", [System.EnvironmentVariableTarget]::Machine)
```

Replace `C:\Scripts` with the actual directory you want to add. Restart your terminal or PC for the changes to take effect.

Make Python scripts directly executable

By default, Python scripts require calling `python script.py`. To make `.py` files directly executable, follow these steps:

- Open PowerShell as Administrator and run:

```powershell
[System.Environment]::SetEnvironmentVariable("PATHEXT", $env:PATHEXT + ";.PY", [System.EnvironmentVariableTarget]::Machine)
```

- Restart your terminal or PC for the changes to take effect.

Now, you can run Python scripts directly by typing their name (e.g., `script.py`).

## Run ArchiveTools

Once installed, you can execute the main script:

```bash
python path/to/archive_tools.py
```

Or, if `.py` files are registered as executable and in your path:

```bash
archive_tools.py
```

