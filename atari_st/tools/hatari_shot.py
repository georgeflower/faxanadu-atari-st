#!/usr/bin/env python3
"""Run a .PRG headlessly in Hatari and render what it put on screen.

Hatari is driven through its debugger: a breakpoint on a VBL count dumps RAM and the video registers, and this script
decodes the four-bitplane framebuffer into a PNG. It prints the 16 palette words and a hash of the picture (every pixel's
palette index and the palette), which a golden check can compare.

    hatari_shot.py --tos etos512us.img --prg build/FAXANADU.PRG --out build/screen.png [--vbls 600] [--ram 0]

--ram is Hatari's --memsize: 0 is the 512 KB of a 520 STFM, 1 is 1 MB. Without --tos the TOS environment variable is used.
The EmuTOS image decides the frequency: the German one (etos512de.img) starts at 50 Hz like a PAL machine, the US one at 60 Hz.
--trace takes Hatari's trace flags, e.g. video_border_v (`detect remove bottom` when the bottom border opens) or video_sync (every write to
$FF820A with its line and cycle); the log is build/shots/hatari.log.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

SCREEN_BYTES = 32000
SCREEN_STRIDE = 160
SCREEN_WIDTH = 320
SCREEN_HEIGHT = 200
VBL_MARGIN = 60


def run_hatari(hatari: str, tos: Path, prg: Path, work: Path, vbls: int, ram: str, debug_script: str, trace: str | None) -> str:
    hd = work / "hd"
    if hd.exists():
        shutil.rmtree(hd)
    hd.mkdir(parents=True)
    shutil.copy(prg, hd / prg.name)
    # Data files of the same build sit beside the PRG, as on a disk.
    for data in sorted(prg.parent.glob("*.DAT")):
        shutil.copy(data, hd / data.name)
    script_path = work / "dbg.ini"
    script_path.write_text(debug_script, encoding="utf-8")
    command = [
        hatari, "--tos", str(tos), "--machine", "st", "--memsize", ram, "--cpu-exact", "true", "--compatible", "true",
        "--fast-boot", "true", "--fast-forward", "true", "--sound", "off", "--disable-video", "true",
        "--harddrive", str(hd), "--auto", f"C:\\{prg.name}", "--parse", str(script_path), "--log-level", "info",
        # Emulation has to outlive the last breakpoint, or it stops before the condition is ever evaluated.
        "--run-vbls", str(vbls + VBL_MARGIN),
    ]
    if trace:
        command += ["--trace", trace]
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    result = subprocess.run(command, capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL, timeout=600)
    return result.stdout + result.stderr


def video_base(log: str) -> int:
    """The video base out of the debugger's dump of $FF8200: the high byte is at $FF8201, the middle one at $FF8203."""
    match = re.search(r"^00FF8200: ([0-9a-fA-F]{2}) ([0-9a-fA-F]{2}) ([0-9a-fA-F]{2}) ([0-9a-fA-F]{2})", log, re.M)
    if not match:
        raise SystemExit("Could not read the video base registers from the Hatari log")
    return (int(match.group(2), 16) << 16) | (int(match.group(4), 16) << 8)


def read_palette(log: str) -> list[int]:
    values: list[int] = []
    for line_base in (0xFF8240, 0xFF8250):
        match = re.search(rf"^00{line_base:04X}: ((?:[0-9a-fA-F]{{2}} ){{16}})", log, re.M)
        if not match:
            raise SystemExit("Could not read the palette from the Hatari log")
        values += [int(token, 16) for token in match.group(1).split()]
    return [(values[i] << 8) | values[i + 1] for i in range(0, 32, 2)]


def decode_screen(ram: bytes, base: int, lines: int = SCREEN_HEIGHT) -> list[list[int]]:
    screen = ram[base : base + lines * SCREEN_STRIDE]
    if len(screen) < lines * SCREEN_STRIDE:
        raise SystemExit(f"Video base {base:#08x} is outside the RAM dump")
    rows = []
    for y in range(lines):
        offset = y * SCREEN_STRIDE
        row = []
        for group in range(SCREEN_WIDTH // 16):
            planes = struct.unpack(">4H", screen[offset + group * 8 : offset + group * 8 + 8])
            for bit in range(15, -1, -1):
                row.append(sum(((planes[p] >> bit) & 1) << p for p in range(4)))
        rows.append(row)
    return rows


def write_png(path: Path, rows: list[list[int]], palette_words: list[int]) -> None:
    palette = [(((w >> 8) & 7) * 36, ((w >> 4) & 7) * 36, (w & 7) * 36) for w in palette_words]
    raw = bytearray()
    for row in rows:
        raw.append(0)
        for index in row:
            raw.extend(palette[index])

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", len(rows[0]), len(rows), 8, 2, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
                     + chunk(b"IEND", b""))


def frame_hash(rows: list[list[int]], palette_words: list[int]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(bytes(row))
    for word in palette_words:
        digest.update(word.to_bytes(2, "big"))
    return digest.hexdigest()


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--prg", type=Path, default=project / "build" / "FAXANADU.PRG")
    parser.add_argument("--out", type=Path, default=project / "build" / "screen.png")
    parser.add_argument("--tos", type=Path, default=Path(os.environ.get("TOS", "")))
    parser.add_argument("--hatari", default=shutil.which("hatari") or "hatari")
    parser.add_argument("--vbls", type=int, default=600, help="the VBL to capture at (TOS takes about 300 to boot)")
    parser.add_argument("--ram", default="0", help="Hatari --memsize (0 = 512 KB)")
    parser.add_argument("--lines", type=int, default=SCREEN_HEIGHT, help="lines of video memory to draw (240 for the overscan screen)")
    parser.add_argument("--work", type=Path, default=project / "build" / "shots")
    parser.add_argument("--trace", default="", help="Hatari trace flags, e.g. os_base,cpu_exception")
    args = parser.parse_args()
    if not str(args.tos) or not args.tos.is_file():
        raise SystemExit("Pass --tos <tos.img> or set the TOS environment variable")

    args.work.mkdir(parents=True, exist_ok=True)
    ram_path = args.work / "ram.bin"
    capture = args.work / "capture.ini"
    capture.write_text(f"m $ff8200-$ff8260\nsavebin {ram_path} 0 $80000\ncont\n", encoding="utf-8")
    log = run_hatari(args.hatari, args.tos, args.prg, args.work, args.vbls, args.ram,
                     f"b VBL > {args.vbls - 1} :once :file {capture}\n", args.trace or None)
    (args.work / "hatari.log").write_text(log, encoding="utf-8")

    if "Pterm0()" in log:
        print("WARNING: the program terminated during the run", file=sys.stderr)
    faults = sorted({m.group(1) for m in re.finditer(r"^cpu exception [23] currpc (\w+)", log, re.M)
                     # $FC0EE2 is the TOS boot-time blitter probe, present on every boot.
                     if m.group(1) != "fc0ee2"})
    if faults:
        print(f"WARNING: bus/address errors at {', '.join(faults)}", file=sys.stderr)

    base = video_base(log)
    palette_words = read_palette(log)
    rows = decode_screen(ram_path.read_bytes(), base, args.lines)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_png(args.out, rows, palette_words)
    print("PALETTE " + " ".join(f"{w:03x}" for w in palette_words))
    print("FRAMEHASH " + frame_hash(rows, palette_words))
    print(f"video base {base:#08x}, wrote {args.out}")


if __name__ == "__main__":
    main()
