#!/usr/bin/env python3
"""Copy the phone's Photos index (a SQLite database) to out/ for analysis.

The index says what each camera roll file is: screenshot, screen recording,
Live Photo, in Recently Deleted, saved by which app, and so on. The copy stays
on this Mac in out/, which git ignores.
"""
import os
import sys
import time

from mobiledevice import Device, Files, usb_devices

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")
NAMES = ["Photos.sqlite", "Photos.sqlite-wal", "Photos.sqlite-shm"]


def main():
    handles = usb_devices()
    if not handles:
        sys.exit("No iPhone found over USB. Plug it in and unlock it.")
    os.makedirs(OUT_DIR, exist_ok=True)
    with Device(handles[0]) as device:
        files = Files(device)
        for name in NAMES:
            started = time.time()
            try:
                size = files.pull("/PhotoData/" + name, os.path.join(OUT_DIR, name))
            except FileNotFoundError:
                print(f"{name}: not present")
                continue
            print(f"{name}: {size / 1e6:.1f} MB in {time.time() - started:.1f}s")


if __name__ == "__main__":
    main()
