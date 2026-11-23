# phone-storage-cleaner

Tools for finding what is eating an iPhone's storage, run from a Mac with the
phone plugged in over USB. No app is installed on the phone.

Everything here is read-only: the scripts list and copy, they never change or
delete anything on the phone.

## What it can see

| Data | How |
|---|---|
| Total / free space | lockdown `com.apple.disk_usage` |
| Per-app size (app and its data) | installation proxy lookup |
| Every file in the media area (camera roll, Photos data, music, books) | AFC file service |
| What each photo or video is (screenshot, screen recording, Live Photo, Recently Deleted, which app saved it) | the phone's `Photos.sqlite` index |

It cannot see inside other apps. WhatsApp's chat media, Messages attachments and
System Data are not reachable over the cable.

## Requirements

- macOS, phone unlocked and already trusted by this Mac ("Trust This Computer").
- The system Python at `/usr/bin/python3`. Nothing to install: the scripts call
  the MobileDevice framework that ships with macOS.

## Usage

Run from the `tools/` folder:

```bash
/usr/bin/python3 probe.py            # is the phone reachable, how full is it
/usr/bin/python3 apps.py 40          # top 40 apps by storage
/usr/bin/python3 inventory.py        # size every media file -> out/files.csv
/usr/bin/python3 pull_photos_db.py   # copy the Photos index -> out/Photos.sqlite
/usr/bin/python3 report.py           # cleanup report -> out/assets.csv
```

`out/` holds personal data from the phone and is ignored by git.

## Files

- `tools/mobiledevice.py` — bridge to the MobileDevice framework (sessions,
  values, app lookup, file listing and download).
- `tools/probe.py`, `apps.py`, `inventory.py`, `pull_photos_db.py`, `report.py`
  — the commands above.
- `docs/superpowers/specs/` — an earlier design for an on-phone app, superseded
  by this Mac-side approach.
