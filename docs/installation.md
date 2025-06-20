# ArchiveTools Installation

## Requirements

- **Python 3.7+**
- Installing Required Python packages:

```bash
pip install -r requirements.txt
```

## Clone Repository

```bash
git clone https://github.com/gabbro246/ArchiveTools.git
cd ArchiveTools
```

## Add to Path - Windows (optional)

To add a directory to the system `Path` using PowerShell, open PowerShell as Administrator and run:

```powershell
$envPath = [System.Environment]::GetEnvironmentVariable("Path", [System.EnvironmentVariableTarget]::Machine)
[System.Environment]::SetEnvironmentVariable("Path", $envPath + ";C:\Scripts", [System.EnvironmentVariableTarget]::Machine)
```

Replace `C:\Scripts` with the actual directory you want to add.

Make Python scripts directly executable:

```powershell
[System.Environment]::SetEnvironmentVariable("PATHEXT", $env:PATHEXT + ";.PY", [System.EnvironmentVariableTarget]::Machine)
```

- Restart your terminal or PC for the changes to take effect.

## Run ArchiveTools

Once installed and optionally added to your path, you can execute the scripts like this:

```bash
python scriptname.py --folder [target_folder] [options]
```

For example:

```bash
python organizebydate.py --folder "C:\Users\User\Pictures" --month
```

---
© 2025 gabbro246. All rights reserved.

