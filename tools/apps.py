#!/usr/bin/env python3
"""List the apps on the iPhone by how much storage each one uses."""
import sys

from mobiledevice import Device, usb_devices

ATTRIBUTES = [
    "CFBundleIdentifier",
    "CFBundleDisplayName",
    "CFBundleName",
    "StaticDiskUsage",
    "DynamicDiskUsage",
]


def gb(n):
    return f"{n / 1e9:6.2f} GB"


def app_rows(device):
    """Return (name, bundle id, app size, data size) for every user app."""
    rows = []
    for bundle_id, info in device.apps(ATTRIBUTES).items():
        name = info.get("CFBundleDisplayName") or info.get("CFBundleName") or bundle_id
        rows.append((name, bundle_id, info.get("StaticDiskUsage", 0), info.get("DynamicDiskUsage", 0)))
    return sorted(rows, key=lambda row: row[2] + row[3], reverse=True)


def main():
    handles = usb_devices()
    if not handles:
        sys.exit("No iPhone found over USB. Plug it in and unlock it.")
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    with Device(handles[0]) as device:
        rows = app_rows(device)
    total = sum(app + data for _, _, app, data in rows)
    print(f"{len(rows)} apps, {gb(total).strip()} in total\n")
    print(f"{'App':32} {'Total':>10} {'App itself':>10} {'Its data':>10}")
    for name, _, app, data in rows[:limit]:
        print(f"{name[:32]:32} {gb(app + data):>10} {gb(app):>10} {gb(data):>10}")


if __name__ == "__main__":
    main()
