#!/usr/bin/env python3
"""Combine the file inventory and the Photos index into a cleanup report.

Reads out/files.csv and out/Photos.sqlite (run inventory.py and
pull_photos_db.py first). Writes out/assets.csv, one row per photo or video
with its real on-disk size and what kind of item it is, then prints totals for
each cleanup category.
"""
import collections
import csv
import datetime
import os
import sqlite3

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")
COCOA_EPOCH = 978307200  # seconds between 1970 and 2001

QUERY = """
SELECT a.Z_PK, a.ZDIRECTORY, a.ZFILENAME, a.ZKIND, a.ZKINDSUBTYPE, a.ZTRASHEDSTATE,
       a.ZFAVORITE, a.ZHIDDEN, a.ZDURATION, a.ZWIDTH, a.ZHEIGHT, a.ZDATECREATED,
       a.ZISDETECTEDSCREENSHOT, a.ZAVALANCHEUUID, a.ZAVALANCHEPICKTYPE,
       a.ZDUPLICATEMETADATAMATCHINGALBUM, a.ZDUPLICATEPERCEPTUALMATCHINGALBUM,
       a.ZADJUSTMENTSSTATE,
       x.ZIMPORTEDBYBUNDLEIDENTIFIER, x.ZIMPORTEDBYDISPLAYNAME, x.ZORIGINALFILENAME,
       e.ZFPS, e.ZCODEC, e.ZBITRATE
FROM ZASSET a
LEFT JOIN ZADDITIONALASSETATTRIBUTES x ON x.ZASSET = a.Z_PK
LEFT JOIN ZEXTENDEDATTRIBUTES e ON e.ZASSET = a.Z_PK
"""


def load_disk_sizes():
    """Map 'DCIM/110APPLE/IMG_0001' to the bytes of every file sharing that stem."""
    originals = collections.Counter()
    edits = collections.Counter()
    with open(os.path.join(OUT_DIR, "files.csv")) as handle:
        for row in csv.DictReader(handle):
            path, size = row["path"], int(row["bytes"])
            if path.startswith("/DCIM/"):
                originals[os.path.splitext(path[1:])[0]] += size
            elif path.startswith("/PhotoData/Mutations/DCIM/"):
                parts = path.split("/")
                if len(parts) > 6:
                    edits["/".join(parts[3:6])] += size
    return originals, edits


def classify(row):
    """Name the cleanup category an asset belongs to."""
    if row["trashed"]:
        return "recently_deleted"
    if row["kind"] == 1:
        return "screen_recording" if row["subtype"] == 103 else "video"
    if row["screenshot"]:
        return "screenshot"
    if row["subtype"] == 2:
        return "live_photo"
    return "photo"


def load_assets():
    originals, edits = load_disk_sizes()
    db = sqlite3.connect(os.path.join(OUT_DIR, "Photos.sqlite"))
    assets = []
    for r in db.execute(QUERY):
        stem = f"{r[1]}/{os.path.splitext(r[2] or '')[0]}"
        created = datetime.datetime.fromtimestamp((r[11] or 0) + COCOA_EPOCH)
        row = {
            "id": r[0],
            "path": f"{r[1]}/{r[2]}",
            "kind": r[3],
            "subtype": r[4],
            "trashed": bool(r[5]),
            "favorite": bool(r[6]),
            "hidden": bool(r[7]),
            "duration": round(r[8] or 0, 1),
            "width": r[9],
            "height": r[10],
            "created": created.strftime("%Y-%m-%d"),
            "screenshot": bool(r[12]) or r[4] == 10,
            "burst": r[13] or "",
            "burst_pick": r[14] or 0,
            "duplicate_group": r[15] or r[16] or "",
            "edited": bool(r[17]),
            "source_app": r[19] or r[18] or "",
            "original_name": r[20] or "",
            "fps": round(r[21] or 0),
            "codec": r[22] or "",
            "bitrate": round(r[23] or 0),
            "bytes": originals.get(stem, 0) + edits.get(stem, 0),
        }
        row["category"] = classify(row)
        assets.append(row)
    return assets


def gb(n):
    return f"{n / 1e9:6.2f} GB"


def total(rows):
    return sum(r["bytes"] for r in rows)


def main():
    assets = load_assets()
    with open(os.path.join(OUT_DIR, "assets.csv"), "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(assets[0].keys()))
        writer.writeheader()
        writer.writerows(assets)

    live = [a for a in assets if not a["trashed"]]
    print(f"{len(assets)} items in the library, {gb(total(assets)).strip()} on disk\n")

    print("By category")
    groups = collections.defaultdict(list)
    for a in assets:
        groups[a["category"]].append(a)
    for name, rows in sorted(groups.items(), key=lambda kv: -total(kv[1])):
        print(f"  {name:18} {len(rows):5} items {gb(total(rows))}")

    videos = sorted((a for a in live if a["kind"] == 1), key=lambda a: -a["bytes"])
    print("\nVideos by size")
    for floor in (200, 100, 50, 20):
        rows = [v for v in videos if v["bytes"] >= floor * 1e6]
        print(f"  {floor:4} MB or more: {len(rows):4} videos {gb(total(rows))}")
    uhd = [v for v in videos if max(v["width"] or 0, v["height"] or 0) >= 3000]
    print(f"  4K videos:       {len(uhd):4} videos {gb(total(uhd))}")
    long_ones = [v for v in videos if v["duration"] >= 60]
    print(f"  1 minute or longer: {len(long_ones):3} videos {gb(total(long_ones))}")

    print("\nSaved into Photos by app")
    apps = collections.defaultdict(list)
    for a in live:
        apps[a["source_app"] or "(unknown)"].append(a)
    for name, rows in sorted(apps.items(), key=lambda kv: -total(kv[1]))[:12]:
        print(f"  {name[:28]:28} {len(rows):5} items {gb(total(rows))}")

    dupes = collections.defaultdict(list)
    for a in live:
        if a["duplicate_group"]:
            dupes[a["duplicate_group"]].append(a)
    extra = [a for rows in dupes.values() for a in sorted(rows, key=lambda r: -r["bytes"])[1:]]
    print(f"\nDuplicates found by iOS: {len(dupes)} groups, {len(extra)} spare copies {gb(total(extra))}")

    bursts = collections.defaultdict(list)
    for a in live:
        if a["burst"]:
            bursts[a["burst"]].append(a)
    print(f"Bursts: {len(bursts)} groups, {sum(len(v) for v in bursts.values())} frames")
    print(f"Favorites: {sum(a['favorite'] for a in live)}   Hidden: {sum(a['hidden'] for a in live)}")


if __name__ == "__main__":
    main()
