#!/usr/bin/env python3
"""Time a routine on the ST (in Hatari, PAL): build the viewer with BENCH=<repeats>, which draws the hero that many times and
leaves the number of VBLs it took in `bench_result`, then print the cycles for one repeat.

    bench.py --tos etos512de.img [--repeats 100]

A PAL frame is 160,256 cycles (313 lines of 512), so the result is VBLs * 160256 / repeats, to within one VBL / repeats.
Use the German EmuTOS image (50 Hz); the US one runs at 60 Hz and the VBL count would not mean the same.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
PAL_FRAME_CYCLES = 160_256


def measure(tos: Path, repeats: int, symbol: str = "bench_result", extra_make: list[str] | None = None) -> int:
    import hatari_shot as hs

    subprocess.run(["make", "-C", str(ROOT), "viewer", f"VIEWER_DEFS=--defsym BENCH={repeats}", *(extra_make or [])], check=True, capture_output=True)
    nm = subprocess.run(["m68k-linux-gnu-nm", str(ROOT / "build" / "viewer.elf")], check=True, capture_output=True, text=True).stdout.split("\n")
    sym = {line.split()[2]: int(line.split()[0], 16) for line in nm if len(line.split()) == 3}
    image = (ROOT / "build" / "viewer.bin").read_bytes()
    work = ROOT / "build" / "shots_bench"
    work.mkdir(parents=True, exist_ok=True)
    vbl = 1500
    (work / "cap.ini").write_text(f"savebin {work / 'ram.bin'} 0 $80000\ncont\n", encoding="utf-8")
    hs.run_hatari(shutil.which("hatari") or "hatari", tos, ROOT / "build" / "VIEWER.PRG", work, vbl, "0", f"b VBL > {vbl - 1} :once :file {work / 'cap.ini'}\n", None)
    ram = (work / "ram.bin").read_bytes()
    base = ram.find(image[sym["start"]:sym["start"] + 48]) - sym["start"]
    if base <= 0:
        raise SystemExit("the program was not found in RAM")
    return int.from_bytes(ram[base + sym[symbol]:base + sym[symbol] + 4], "big")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tos", type=Path, default=Path(os.environ.get("TOS_PAL") or os.environ.get("TOS") or ""))
    parser.add_argument("--repeats", type=int, default=100)
    args = parser.parse_args()
    vbls = measure(args.tos, args.repeats)
    print(f"{vbls} VBLs for {args.repeats} repeats = {vbls * PAL_FRAME_CYCLES / args.repeats:,.0f} cycles each")


if __name__ == "__main__":
    main()
