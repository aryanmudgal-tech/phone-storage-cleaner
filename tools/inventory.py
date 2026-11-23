#!/usr/bin/env python3
"""Walk the phone's media area and record every file with its size.

Writes out/files.csv (path, bytes, modified) and prints the size of each
top-level folder. Read-only: nothing on the phone is changed.
"""
import csv
import os
import sys
import time

from mobiledevice import Device, Files, usb_devices

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")


def walk(files, root):
    """Yield (path, bytes, modified_seconds) for every file under root."""
    stack = [root]
    while stack:
        folder = stack.pop()
        for name in files.listdir(folder):
            path = folder.rstrip("/") + "/" + name
            info = files.info(path)
            if not info:
                continue
            kind = info.get("st_ifmt")
            if kind == "S_IFDIR":
                stack.append(path)
            elif kind == "S_IFREG":
                modified = int(info.get("st_mtime", "0")) // 1_000_000_000
                yield path, int(info.get("st_size", "0")), modified


def main():
    handles = usb_devices()
    if not handles:
        sys.exit("No iPhone found over USB. Plug it in and unlock it.")
    os.makedirs(OUT_DIR, exist_ok=True)
    totals = {}
    count = 0
    started = time.time()
    with Device(handles[0]) as device:
        files = Files(device)
        with open(os.path.join(OUT_DIR, "files.csv"), "w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["path", "bytes", "modified"])
            for path, size, modified in walk(files, "/"):
                writer.writerow([path, size, modified])
                top = path.split("/")[1]
                totals[top] = totals.get(top, 0) + size
                count += 1
                if count % 5000 == 0:
                    print(f"  {count} files scanned ({time.time() - started:.0f}s)", flush=True)
    print(f"\n{count} files, {sum(totals.values()) / 1e9:.2f} GB in the media area\n")
    for top, size in sorted(totals.items(), key=lambda item: item[1], reverse=True):
        print(f"{top:28} {size / 1e9:8.2f} GB")


if __name__ == "__main__":
    main()
