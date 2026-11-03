#!/usr/bin/env python3
"""Check the tables the code reaches through the a6 anchor.

`ltab sym, %aN` assembles to `move.l #(sym - table_anchor), %aN` and `adda.l %a6, %aN`: a 32-bit distance, so
the tables may sit anywhere in the image. (It used to be a `lea` with a 16-bit displacement, and a table more
than 32767 bytes from the anchor silently wrapped to the wrong address.) This reads the linked ELF's symbols,
fails the build when a symbol named in an `ltab` does not exist, and reports how far the tables spread; it
fails only if that spread could no longer be a 32-bit distance, and warns when the old 16-bit reach is passed.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

LTAB = re.compile(r"^\s*ltab\s+([A-Za-z_][A-Za-z0-9_]*)\s*,")


def symbol_addresses(nm: str, elf: Path) -> dict[str, int]:
    out = subprocess.run([nm, "-n", str(elf)], check=True, capture_output=True, text=True).stdout
    table = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 3:
            table[parts[2]] = int(parts[0], 16)
    return table


# One line of an `as -al` listing: line number, offset within the section, the bytes, then the source.
LISTING = re.compile(r"^\s*\d+\s+([0-9a-fA-F]{4,8})\s+(?:[0-9A-F]{2,4}\s+)*\t\s*(\S.*)$")
SECTION = re.compile(r"^\s*\d+\s+\.(?:section\s+(\S+?)[,\s]|section\s+(\S+)$|(text|data|bss)\b)")
BRANCH = re.compile(r"^(bsr|bra|b[a-z]{2})(?:\.([bswl]))?\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:\|.*)?$")
PC_OPERAND = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)(?:[+-]\d+)?\(%pc[,)]")


def check_displacements(listing: Path, symbols: dict[str, int]) -> tuple[list[str], int, list[tuple[int, str]]]:
    """The 68000 branches and PC-relative operands span a signed 16 bits (a short branch 8). GNU as does not
    complain when a displacement does not fit: it wraps, and the program jumps into the wrong place (it once sent
    the main loop's `bsr draw_hud` into low RAM and crashed at start). The listing gives every instruction's offset
    in .text, `game_start` is the link address of offset 0, and the symbols give the targets, so the real distance
    can be computed. Returns the failures, how many were checked, and the tightest few (slack, where)."""
    base = {"text": symbols["game_start"]}
    section = "text"
    failures: list[str] = []
    checked = 0
    tight: list[tuple[int, str]] = []
    for line in listing.read_text(encoding="utf-8", errors="replace").splitlines():
        found = SECTION.match(line)
        if found:
            name = (found.group(1) or found.group(2) or found.group(3)).lstrip(".")
            section = name if name in ("text", "data", "bss", "rodata", "text.late") else "other"
            continue
        match = LISTING.match(line)
        if not match or section != "text":
            continue
        offset, source = int(match.group(1), 16), match.group(2).strip()
        instruction = re.sub(r"^\w+:\s*", "", source)           # a label may share the line
        branch = BRANCH.match(instruction)
        if branch and branch.group(3) in symbols:
            limit = 127 if branch.group(2) in ("b", "s") else 32767
            distance = symbols[branch.group(3)] - (base["text"] + offset + 2)
            target = branch.group(3)
        else:
            pc = PC_OPERAND.search(instruction)
            if not pc or pc.group(1) not in symbols or instruction.startswith(("dc", ".")):
                continue
            # the displacement word follows the opcode, or an immediate / register mask that comes first
            extra = 2 if re.match(r"^(btst|bset|bclr|bchg|movem)\S*\s+(#|%|\{)", instruction) or \
                re.match(r"^(btst|bset|bclr|bchg)\S*\s+#", instruction) else 0
            distance = symbols[pc.group(1)] - (base["text"] + offset + 2 + extra)
            limit, target = 32767, pc.group(1)
        checked += 1
        room = limit - distance if distance >= 0 else limit + 1 + distance
        tight = sorted(tight + [(room, f"{instruction.split('|')[0].strip()} at .text+{offset:#x}")])[:3]
        if not -limit - 1 <= distance <= limit:
            failures.append(f"{source.split('|')[0].strip()} at .text+{offset:#x}: {target} is {distance} bytes away")
    return failures, checked, tight


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("elf", type=Path)
    parser.add_argument("sources", type=Path, nargs="+")
    parser.add_argument("--nm", default="m68k-linux-gnu-nm")
    parser.add_argument("--listing", type=Path, help="the assembler listing of main.s (as -al=FILE)")
    args = parser.parse_args()
    symbols = symbol_addresses(args.nm, args.elf)
    anchor = symbols.get("table_anchor")
    used: dict[str, str] = {}
    for source in args.sources:
        for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
            match = LTAB.match(line.split("|", 1)[0])
            if match:
                used.setdefault(match.group(1), f"{source.name}:{number}")
    if used and anchor is None:
        sys.exit("The code uses ltab but the image has no table_anchor symbol")
    bad = []
    far_back = far_ahead = 0
    for name, where in sorted(used.items()):
        if name not in symbols:
            bad.append(f"{name} ({where}) is not a symbol in the ELF")
            continue
        distance = symbols[name] - anchor
        far_back = min(far_back, distance)
        far_ahead = max(far_ahead, distance)
    if bad:
        sys.exit("Tables the code names but the image lacks:\n  " + "\n  ".join(bad))
    reach = ""
    if args.listing:
        failures, checked, tight = check_displacements(args.listing, symbols)
        if failures:
            sys.exit("Branches and PC-relative operands too far for 16 bits (route a branch through a *_far stub in "
                     "main.s):\n  " + "\n  ".join(failures))
        reach = (f"; {checked} branches and PC-relative operands fit 16 bits, the tightest left "
                 + ", ".join(f"{room} bytes ({where})" for room, where in tight))
    print(f"Tables ok: {len(used)} tables, furthest back {-far_back}, furthest ahead {far_ahead} bytes from table_anchor{reach}")


if __name__ == "__main__":
    main()
