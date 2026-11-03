#!/usr/bin/env python3
"""Compare the ROM you play (the port's data source) with the ROM the disassembly builds (the port's spec).

    rom_diff.py ../build/faxanadu.nes ../ext/Faxanadu_Europe.nes

Prints the iNES header facts of both and how many bytes of each 16 KB PRG bank differ. It prints counts only, nothing
from the ROMs, so its output can go into a pull request or the briefing.
"""
from __future__ import annotations

import sys
from pathlib import Path

BANK = 0x4000


def header_facts(rom: bytes) -> str:
    if rom[:4] != b"NES\x1a":
        return "not an iNES file"
    mapper = (rom[6] >> 4) | (rom[7] & 0xF0)
    nes2 = (rom[7] & 0x0C) == 0x08
    facts = [f"{rom[4]} PRG banks of 16 KB", f"{rom[5]} CHR banks", f"mapper {mapper}",
             ("vertical" if rom[6] & 1 else "horizontal") + " mirroring flag"]
    if nes2:
        facts.append("NES 2.0, timing " + {0: "NTSC", 1: "PAL", 2: "multi-region", 3: "Dendy"}.get(rom[12] & 3, "?"))
    return ", ".join(facts)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    a = Path(argv[1]).read_bytes()
    b = Path(argv[2]).read_bytes()
    print(f"{argv[1]}: {header_facts(a)}")
    print(f"{argv[2]}: {header_facts(b)}")
    pa, pb = a[16:], b[16:]
    if len(pa) != len(pb):
        print(f"PRG sizes differ: {len(pa)} and {len(pb)}")
        return 1
    total = 0
    for bank in range(len(pa) // BANK):
        x, y = pa[bank * BANK:(bank + 1) * BANK], pb[bank * BANK:(bank + 1) * BANK]
        count = sum(1 for i in range(BANK) if x[i] != y[i])
        total += count
        print(f"bank {bank:2d}: {count:5d} bytes differ" if count else f"bank {bank:2d}: identical")
    print(f"total {total} of {len(pa)} PRG bytes differ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
