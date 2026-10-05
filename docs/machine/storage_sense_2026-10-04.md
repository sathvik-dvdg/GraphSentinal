# Storage Sense change on the development machine (2026-10-04)

A change made to the project owner's Windows machine during this work. Recorded
here so it can be reverted, and so the unexplained disk losses it relates to are
not forgotten.

## Why

On 2026-10-03 drive C: reached 1.3 GB free. That evening three large deletions
happened that no command in this work made:

- about 52 GB freed beyond two approved cache cleans (npm, uv; about 13.7 GB);
- the Claude Code scratchpad under `%TEMP%` deleted;
- Docker Desktop's data disk, `%LOCALAPPDATA%\Docker\wsl\disk\docker_data.vhdx`,
  gone (its folder last modified 20:00:47).

Storage Sense was on, set to run when free space is low, and its registry
records its last run at **2026-10-03 19:53:12** (a failure entry at 19:54:10).
That fits the first two. **The Docker disk loss is unexplained**: deleting
application data is not a documented Storage Sense action, and Docker's logs for
that afternoon no longer exist, so whether "Reset to factory defaults" was used
cannot be determined. It is recorded as unexplained, not attributed.

The CICIDS2017 dataset was never at risk: it exists only on Google Drive, and its
file sizes are recorded in the Cell A audit verdict that Cell B checks on every
run.

## What was changed

`HKCU\Software\Microsoft\Windows\CurrentVersion\StorageSense\Parameters\StoragePolicy`

The record taken before the change, verbatim:

```
StoragePolicy before change (HKCU\...\StorageSense\Parameters\StoragePolicy): 01=1 02=1 04=1 08=1 32=0 128=0 256=30 512=0 1024=1 2048=0
```

After: `02=0 04=0 1024=0`, all else unchanged. Storage Sense stays on (`01=1`),
still runs when space is low (`2048=0`), and now only empties the Recycle Bin of
files older than 30 days (`08=1`, `256=30`). Downloads cleanup was already off
(`32=0`, `512=0`). `04` is temporary-file cleanup; `1024` and `02` were set to 0
as further deletion categories whose exact meaning is not documented here.

## How to revert

In PowerShell:

```powershell
$k = "HKCU:\Software\Microsoft\Windows\CurrentVersion\StorageSense\Parameters\StoragePolicy"
foreach ($n in "02","04","1024") { Set-ItemProperty -Path $k -Name $n -Value 1 -Type DWord }
```

or Settings → System → Storage → Storage Sense.
