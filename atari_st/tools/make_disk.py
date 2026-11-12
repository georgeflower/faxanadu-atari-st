#!/usr/bin/env python3
"""Make a 720 KB double-sided Atari ST floppy image (.st) holding the game: FAXANADU.PRG and its data files.

The image is plain FAT12 as TOS writes it (80 tracks, 2 sides, 9 sectors of 512 bytes, 2 sectors a cluster, one root
directory of 112 entries). A name with a folder, `AUTO/FAXANADU.PRG`, puts the file in that folder of the root (one level): TOS
runs the programs of A:\AUTO when it starts from the disk, with the root as the current folder, so the data files stay in the root.
A Gotek or HxC reads it as it is, and Hatari takes it as a floppy image.

    make_disk.py OUT.st FILE [FILE ...]        (each FILE is a path, stored under its upper-case 8.3 name; NAME=PATH stores PATH as NAME)

A .TXT file is stored with DOS line ends (TOS's text viewer wants them).
"""
from __future__ import annotations

import datetime
import struct
import sys
from pathlib import Path

SECTOR = 512
SECTORS_PER_TRACK = 9
SIDES = 2
TRACKS = 80
TOTAL_SECTORS = SECTORS_PER_TRACK * SIDES * TRACKS      # 1440
PER_CLUSTER = 2
RESERVED = 1
FATS = 2
PER_FAT = 5
ROOT_ENTRIES = 112
MEDIA = 0xF9


class DiskFull(Exception):
    pass


def short_name(name: str) -> bytes:
    base, _, ext = name.upper().partition(".")
    if not 0 < len(base) <= 8 or len(ext) > 3:
        raise ValueError(f"{name!r} is not an 8.3 name")
    return base.ljust(8).encode("ascii") + ext.ljust(3).encode("ascii")


def build_disk(files: list[tuple[str, bytes]], label: str = "FAXANADU", when: datetime.datetime | None = None) -> bytes:
    """The image of a disk with `files` (name, contents) in its root directory, in the given order; `FOLDER/NAME` puts a file in a folder of the root."""
    when = when or datetime.datetime(2026, 1, 1)
    root_sectors = ROOT_ENTRIES * 32 // SECTOR
    data_start = RESERVED + FATS * PER_FAT + root_sectors
    clusters = (TOTAL_SECTORS - data_start) // PER_CLUSTER
    cluster_bytes = PER_CLUSTER * SECTOR
    image = bytearray(TOTAL_SECTORS * SECTOR)

    boot = bytearray(SECTOR)
    boot[0:3] = b"\xeb\x3c\x90"
    boot[3:8] = b"FAXAN"
    struct.pack_into("<HBHBHHBHHHL", boot, 11, SECTOR, PER_CLUSTER, RESERVED, FATS, ROOT_ENTRIES, TOTAL_SECTORS,
                     MEDIA, PER_FAT, SECTORS_PER_TRACK, SIDES, 0)
    boot[8:11] = b"\x46\x41\x58"          # the serial number TOS looks at to see a disk change
    image[:SECTOR] = boot

    fat = bytearray(PER_FAT * SECTOR)

    def set_fat(n: int, value: int) -> None:
        at = n * 3 // 2
        if n & 1:
            fat[at] = (fat[at] & 0x0F) | ((value & 0x0F) << 4)
            fat[at + 1] = (value >> 4) & 0xFF
        else:
            fat[at] = value & 0xFF
            fat[at + 1] = (fat[at + 1] & 0xF0) | ((value >> 8) & 0x0F)

    set_fat(0, 0xF00 | MEDIA)
    set_fat(1, 0xFFF)
    stamp_time = (when.hour << 11) | (when.minute << 5) | (when.second // 2)
    stamp_date = ((when.year - 1980) << 9) | (when.month << 5) | when.day
    root = (RESERVED + FATS * PER_FAT) * SECTOR
    folders: dict[str, list[tuple[str, bytes]]] = {}
    plain = []
    for name, data in files:
        folder, _, leaf = name.rpartition("/")
        if folder:
            if "/" in folder:
                raise ValueError(f"{name!r}: one level of folders only")
            folders.setdefault(folder.upper(), []).append((leaf, data))
        else:
            plain.append((name, data))
    if len(plain) + len(folders) + 1 > ROOT_ENTRIES:
        raise DiskFull("too many files")
    image[root : root + 32] = (label.upper().ljust(11).encode("ascii")[:11] + b"\x08" + bytes(10)
                               + struct.pack("<HH", stamp_time, stamp_date) + bytes(6))
    next_cluster = 2

    def entry_bytes(name: bytes, attr: int, cluster: int, size: int) -> bytes:
        return name + bytes([attr]) + bytes(10) + struct.pack("<HHHL", stamp_time, stamp_date, cluster, size)

    def store(name: str, data: bytes) -> int:
        nonlocal next_cluster
        need = max(1, -(-len(data) // cluster_bytes))
        if next_cluster + need > clusters + 2:
            raise DiskFull(f"{name} does not fit: {next_cluster - 2 + need} of {clusters} clusters")
        first = next_cluster
        for k in range(need):
            set_fat(first + k, first + k + 1 if k < need - 1 else 0xFFF)
            at = (data_start + (first + k - 2) * PER_CLUSTER) * SECTOR
            chunk = data[k * cluster_bytes : (k + 1) * cluster_bytes]
            image[at : at + len(chunk)] = chunk
        next_cluster += need
        return first

    entries = []
    for folder, inside in folders.items():                          # a folder: ".", ".." and its files, in clusters of its own (32 entries a cluster)
        size = (2 + len(inside)) * 32
        own = next_cluster
        next_cluster += max(1, -(-size // cluster_bytes))
        if next_cluster > clusters + 2:
            raise DiskFull(f"{folder} does not fit")
        listing = entry_bytes(b".".ljust(11), 0x10, own, 0) + entry_bytes(b"..".ljust(11), 0x10, 0, 0)
        for leaf, data in inside:
            listing += entry_bytes(short_name(leaf), 0x20, store(f"{folder}/{leaf}", data), len(data))
        listing = listing.ljust(-(-size // cluster_bytes) * cluster_bytes, b"\0")
        for k in range(len(listing) // cluster_bytes):
            set_fat(own + k, own + k + 1 if k < len(listing) // cluster_bytes - 1 else 0xFFF)
        at = (data_start + (own - 2) * PER_CLUSTER) * SECTOR
        image[at : at + len(listing)] = listing
        entries.append(entry_bytes(short_name(folder), 0x10, own, 0))
    for name, data in plain:
        entries.append(entry_bytes(short_name(name), 0x20, store(name, data), len(data)))
    for entry, raw in enumerate(entries, 1):
        image[root + entry * 32 : root + entry * 32 + 32] = raw
    for f in range(FATS):
        at = (RESERVED + f * PER_FAT) * SECTOR
        image[at : at + len(fat)] = fat
    return bytes(image)


def read_disk(image: bytes) -> dict[str, bytes]:
    """The files of an image made by `build_disk`, a file in a folder as `FOLDER/NAME` (for the tests and for a look inside)."""
    if len(image) != TOTAL_SECTORS * SECTOR:
        raise ValueError("not a 720 KB image")
    fat_at = RESERVED * SECTOR
    root = (RESERVED + FATS * PER_FAT) * SECTOR
    data_start = RESERVED + FATS * PER_FAT + ROOT_ENTRIES * 32 // SECTOR

    def next_of(n: int) -> int:
        at = fat_at + n * 3 // 2
        pair = image[at] | (image[at + 1] << 8)
        return (pair >> 4) if n & 1 else (pair & 0xFFF)

    def chain(cluster: int, size: int | None) -> bytes:
        out = bytearray()
        while 2 <= cluster < 0xFF8 and (size is None or len(out) < size):
            at = (data_start + (cluster - 2) * PER_CLUSTER) * SECTOR
            out.extend(image[at : at + PER_CLUSTER * SECTOR])
            cluster = next_of(cluster)
        return bytes(out if size is None else out[:size])

    def listing(raw_dir: bytes, prefix: str, files: dict[str, bytes]) -> None:
        for entry in range(len(raw_dir) // 32):
            raw = raw_dir[entry * 32 : entry * 32 + 32]
            if raw[0] == 0:
                break
            if raw[11] & 0x08 or raw[0] == ord("."):
                continue
            base, ext = raw[:8].decode("ascii").rstrip(), raw[8:11].decode("ascii").rstrip()
            cluster, size = struct.unpack_from("<HL", raw, 26)
            if raw[11] & 0x10:
                listing(chain(cluster, None), prefix + base + "/", files)
            else:
                files[prefix + base + "." + ext] = chain(cluster, size)

    files: dict[str, bytes] = {}
    listing(image[root : root + ROOT_ENTRIES * 32], "", files)
    return files


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    out = Path(argv[1])
    files = []
    for arg in argv[2:]:
        name, _, path = arg.partition("=")
        if not path:
            name, path = Path(arg).name, arg
        data = Path(path).read_bytes()
        if name.upper().endswith(".TXT"):
            data = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        files.append((name, data))
    image = build_disk(files, when=datetime.datetime.now())
    out.write_bytes(image)
    used = sum(-(-len(d) // (PER_CLUSTER * SECTOR)) * PER_CLUSTER * SECTOR for _, d in files) + PER_CLUSTER * SECTOR * len({n.rpartition("/")[0] for n, _ in files} - {""})
    print(f"Wrote {out}: {len(files)} files, {used // 1024} KB of {TOTAL_SECTORS * SECTOR // 1024} KB used")
    for name, data in sorted(files, key=lambda f: -len(f[1])):
        print(f"  {name:<13}{len(data):>8} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
