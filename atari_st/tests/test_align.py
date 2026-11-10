"""Alignment: on a 68000 a word or long access at an odd address is an address error ("three bombs"; TOS ends the program).

A table of words that follows a table of bytes with no `.even` between is odd or even by luck of the build: `key_hints` (the hint of a locked door) came after the three
bytes of `ring_masks`, was even in some builds and odd in others, and the gate of Eolis crashed the author's game. This builds the game's disk configuration (what
`make disk` assembles) and reads the listing: every instruction and every `.word`/`.long` must be at an even offset of its section, and every section must be
placed on an even address and have an even size (so the one behind it is even too)."""
from __future__ import annotations

import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"
NEEDS = ROM.is_file() and shutil.which("ca65") and shutil.which("m68k-linux-gnu-as")

DISK_DEFS = "--defsym MENU=1 --defsym SPLASH=1 --defsym NPCS=1 --defsym NEWGAME=1 --defsym JOYPAD=1"
DATA_WORDS = {".word", ".long", ".short", ".hword", ".int", ".2byte", ".4byte"}


def odd_places(listing: str) -> list[str]:
    """(file line, section, offset, source) of every instruction or word/long directive at an odd offset of its section."""
    section, bad = ".text", []
    for line in listing.split("\n"):
        source = line.split("\t", 1)[1] if "\t" in line else ""
        m = re.match(r"^\s*\.section\s+([^\s,]+)", source)
        if m:
            section = m.group(1)
            continue
        m = re.match(r"^\s*\.(text|data|bss)\b", source)
        if m:
            section = "." + m.group(1)
            continue
        m = re.match(r"^\s*(\d+) ([0-9a-f]{4,8}) ", line)
        if not m:
            continue
        code = re.sub(r"^\s*(?:[A-Za-z_.$][\w.$]*|\d+):\s*", "", source).split("|")[0].strip()
        if not code:
            continue
        op = code.split()[0]
        if op.startswith(".") and op not in DATA_WORDS:
            continue
        if int(m.group(2), 16) % 2:
            bad.append(f"line {m.group(1)} in {section} at {m.group(2)}: {code[:70]}")
    return bad


@unittest.skipUnless(NEEDS, "needs the ROM, cc65 and the m68k binutils")
class AlignmentTests(unittest.TestCase):
    def test_the_disks_program_has_no_instruction_or_word_at_an_odd_address(self) -> None:
        subprocess.run(["make", "-C", str(ROOT), "viewer", "ALL=1", "WORLD=1,2,3,5,6,7", f"VIEWER_DEFS={DISK_DEFS}"], check=True, capture_output=True)
        listing = (ROOT / "build" / "viewer.lst").read_text(encoding="utf-8", errors="replace")
        self.assertEqual(odd_places(listing), [])
        sections = subprocess.run(["m68k-linux-gnu-objdump", "-h", str(ROOT / "build" / "viewer.o")], check=True, capture_output=True, text=True).stdout
        for name, size, align in re.findall(r"^\s*\d+ (\S+)\s+([0-9a-f]{8})\s+\S+\s+\S+\s+\S+\s+2\*\*(\d+)$", sections, re.M):
            if name in (".text.boot", ".bss") or int(size, 16) == 0:
                continue                                       # (the boot jump is first, at 0)
            self.assertEqual(int(size, 16) % 2, 0, f"{name} has an odd size: the section behind it would start at an odd address")
            self.assertGreaterEqual(int(align), 1, f"{name} may be placed at an odd address: start it with .even")

    def test_the_checker_finds_the_bug_it_is_for(self) -> None:
        listing = "\n".join([
            " 880               \t    .section .rodata",
            " 881               \tring_masks:",
            " 882 0cc0 8020 10   \t    .byte 0x80, 0x20, 0x10",
            " 883               \tkey_hints:",
            " 884 0cc3 07A6 07D2 \t    .word TEXT_KEY_A, TEXT_KEY_K",
            " 885 0cc7 41FA 0000 \t    lea key_hints-2(%pc), %a0",
        ])
        self.assertEqual(len(odd_places(listing)), 2)
        self.assertEqual(odd_places(listing.replace("0cc3", "0cc4").replace("0cc7", "0cc8")), [])


if __name__ == "__main__":
    unittest.main()
