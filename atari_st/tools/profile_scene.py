#!/usr/bin/env python3
"""Cycles of the per-frame routines in a scene: runs a build of the viewer in Hatari (PAL timing needs a 50 Hz TOS image, the German EmuTOS)
with the debugger's profiler on for a window of VBLs, and prints what each routine costs a pass of the frame loop.

    profile_scene.py [--tos IMG] [--window 500,550] [--step 10] [--poke VBL:KIND:VALUE ...] -- MAKE_ARGS...

MAKE_ARGS are the arguments of `make viewer` (ALL=1 AREA=7 SCREEN=15 HERO=208,144,0,255,0,0,1 WORLD=1 HUD=80,80,0,0,0 ...). A poke is a joystick
byte (`joy`: 1 up, 2 down, 4 left, 8 right, 0x80 fire), the hero's x or y (`x`, `y`), a key (`key`: scan code << 8 | 1 down, 0 up) or a word of
the program's by its symbol (`hourglass:60` keeps the enemies still).
The window is in VBLs from the start of Hatari (TOS takes about 300 to boot, the title is not in these builds).

Hatari's profiler counts the cycles of every instruction (--cpu-exact); with the program's symbols loaded it also has the cycles of every
subroutine, inclusive of what it calls. A pass of the frame loop costs the program's total minus what `wait_vbl` spends waiting; the window is
cut into pieces of --step VBLs so the busiest piece shows. A frame is 160,256 cycles (313 lines of 512). A pass that costs more makes the next
VBL late: `late_frames` (read from RAM) counts those.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
FRAME = 160_256


def build(make_args: list[str]) -> dict[str, int]:
    subprocess.run(["make", "-C", str(ROOT), "viewer", *make_args], check=True, capture_output=True)
    nm = subprocess.run(["m68k-linux-gnu-nm", "-n", str(ROOT / "build" / "viewer.elf")], check=True, capture_output=True, text=True).stdout.splitlines()
    return {line.split()[2]: int(line.split()[0], 16) for line in nm if len(line.split()) == 3}


def run(tos: Path, sym: dict[str, int], start: int, end: int, step: int, pokes: list[tuple[int, str, int]], work: Path) -> tuple[list[dict], list[int]]:
    import hatari_shot as hs

    work.mkdir(parents=True, exist_ok=True)
    image = (ROOT / "build" / "viewer.bin").read_bytes()
    prg = ROOT / "build" / "VIEWER.PRG"
    hatari = shutil.which("hatari")
    (work / "c0.ini").write_text(f"savebin {work / 'ram0.bin'} 0 $80000\ncont\n", encoding="utf-8")
    hs.run_hatari(hatari, tos, prg, work, 500, "0", f"b VBL > 499 :once :file {work / 'c0.ini'}\n", None)
    ram0 = (work / "ram0.bin").read_bytes()
    base = ram0.find(image[sym["start"]:sym["start"] + 48]) - sym["start"]
    if base <= 0:
        raise SystemExit("the program was not found in RAM")
    with open(work / "syms.txt", "w", encoding="ascii") as f:
        for name, addr in sym.items():
            if addr < sym["image_size"]:
                f.write(f"{addr:08x} T {name}\n")
    script = ""
    for i, (vbl, what, value) in enumerate(pokes):
        if what == "joy":
            text = f"memwrite ${base + sym['input_state'] + 259:x} 0x{value:02x}\ncont\n"
        elif what == "key":
            text = f"memwrite ${base + sym['input_state'] + 264 + (value >> 8):x} 0x{value & 255:02x}\ncont\n"
        elif what in ("x", "y"):
            text = f"memwrite ${base + sym['hero_' + what]:x} 0x{value >> 8:02x} 0x{value & 255:02x}\ncont\n"
        else:                                           # the word at the program's symbol of that name (`hourglass`: the enemies stand still, the scene stays the same)
            text = f"memwrite ${base + sym[what]:x} 0x{value >> 8:02x} 0x{value & 255:02x}\ncont\n"
        (work / f"poke{i}.ini").write_text(text, encoding="utf-8")
        script += f"b VBL > {vbl} :once :file {work / f'poke{i}.ini'}\n"
    cuts = list(range(start, end, step)) + [end]
    for i, vbl in enumerate(cuts):
        text = f"savebin {work / f'late{i}.bin'} {base + sym['late_frames']:#x} 4\n"
        if i > 0:
            text += "profile stats\nprofile callers\nprofile off\n"
        if i < len(cuts) - 1:
            text += f"symbols {work / 'syms.txt'} {base:#x}\nprofile on\n"
        (work / f"cut{i}.ini").write_text(text + "cont\n", encoding="utf-8")
        script += f"b VBL > {vbl} :once :file {work / f'cut{i}.ini'}\n"
    log = hs.run_hatari(hatari, tos, prg, work, end + 2, "0", script, None)
    (work / "hatari.log").write_text(log, encoding="utf-8")
    pieces = []
    for chunk in re.split(r"(?m)^> profile stats$", log)[1:]:
        pieces.append(parse_piece(chunk, sym))
    late = [int.from_bytes((work / f"late{i}.bin").read_bytes(), "big") for i in range(len(cuts))]
    return pieces, late


def parse_piece(chunk: str, sym: dict[str, int]) -> dict:
    """The totals of one profile window and its subroutines: name -> (calls, inclusive cycles, exclusive cycles)."""
    total = sum(int(m.group(1)) for m in re.finditer(r"- used cycles:\s*\n\s*(\d+) ", chunk.split("> profile callers")[0]))
    routines: dict[str, list[int]] = {}
    for line in chunk.splitlines():
        m = re.match(r"^0x[0-9a-f]+: (.*), (\w+)$", line)
        if not m:
            continue
        entry = routines.setdefault(m.group(2), [0, 0, 0])
        for caller in m.group(1).split(", "):
            c = re.match(r"0x[0-9a-f]+ = (\d+) \w+(?: (\d+)/(\d+)/(\d+)(?:/\d+/\d+)?(?: (\d+)/(\d+)/(\d+)(?:/\d+/\d+)?)?)?$", caller)
            if not c:
                continue
            entry[0] += int(c.group(1))
            if c.group(4):
                entry[1] += int(c.group(4))
            if c.group(7):
                entry[2] += int(c.group(7))
    return {"total": total, "routines": routines}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tos", type=Path, default=Path(os.environ.get("TOS_PAL") or os.environ.get("TOS") or ""))
    parser.add_argument("--window", default="500,550")
    parser.add_argument("--step", type=int, default=10)
    parser.add_argument("--poke", action="append", default=[], help="VBL:KIND:VALUE")
    parser.add_argument("--top", type=int, default=14)
    parser.add_argument("--per-call", action="store_true", help="a table of the cost of one call (for a scroll, which has no passes of the frame loop)")
    parser.add_argument("--name", default="shots_profile")
    parser.add_argument("make_args", nargs="*")
    args = parser.parse_args()
    start, end = (int(v) for v in args.window.split(","))
    pokes = [(int(a), b, int(c, 0)) for a, b, c in (p.split(":") for p in args.poke)]
    sym = build(args.make_args)
    pieces, late = run(args.tos, sym, start, end, args.step, pokes, ROOT / "build" / args.name)
    sums: dict[str, list[int]] = {}
    busy_per_pass = []
    passes_total = busy_total = 0
    for p in pieces:
        r = p["routines"]
        passes = r.get("input_poll", [0])[0]
        waiting = r.get("wait_vbl", [0, 0, 0])[2]
        busy = p["total"] - waiting
        if passes:
            busy_per_pass.append(busy / passes)
        passes_total += passes
        busy_total += busy
        for name, (calls, inc, exc) in r.items():
            s = sums.setdefault(name, [0, 0, 0])
            s[0] += calls
            s[1] += inc
            s[2] += exc
    print(f"passes {passes_total} in {end - start} VBLs, late frames {late[-1] - late[0]}")
    if busy_per_pass:
        mean = busy_total / max(passes_total, 1)
        print(f"busy cycles a pass over the window: {mean:,.0f} ({mean / FRAME * 100:.0f}% of a frame of {FRAME:,}); over {args.step} VBLs at a time: " + " ".join(f"{b:,.0f}" for b in busy_per_pass))
        print("  (a pass that takes longer than a frame never waits, so the pieces are only as exact as the count of passes in them: trust the mean)")
    if args.per_call:
        print(f"{'routine':<24}{'calls':>8}{'cycles/call':>13}{'total':>12}  (inclusive)")
        for name, v in sorted(sums.items(), key=lambda kv: -kv[1][1])[:args.top]:
            print(f"{name:<24}{v[0]:>8}{v[1] // max(v[0], 1):>13,}{v[1]:>12,}")
        return
    print(f"{'routine':<24}{'calls/pass':>11}{'cycles/pass':>13}  (inclusive: with what it calls)")
    rows = sorted(((v[1] / max(passes_total, 1), k, v[0] / max(passes_total, 1)) for k, v in sums.items() if v[1]), reverse=True)
    for cycles, name, calls in rows[:args.top]:
        print(f"{name:<24}{calls:>11.1f}{cycles:>13,.0f}")


if __name__ == "__main__":
    main()
