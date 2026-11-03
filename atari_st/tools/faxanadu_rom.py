"""Read the Faxanadu ROM the way the game's own banks lay it out.

The disassembly (the US ROM, built with cc65) names every table. This module takes those names and addresses from ld65's debug
file, and reads the bytes from the ROM you supply (ext/Faxanadu_Europe.nes). Banks 0-4, 6-11 and 14 are identical in the two
ROMs, so a label in one of them is at the same file offset in both; for banks 5, 12 and 13 and the fixed bank 15, check the
Europe ROM itself (`Rom.differs`).

Only names, addresses and offsets are cached (build/refnes/rom_labels.json), never ROM data.
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "atari_st" / "build" / "refnes" / "rom_labels.json"
DEFAULT_ROM = ROOT / "ext" / "Faxanadu_Europe.nes"
BANK = 0x4000
HEADER = 16


@dataclass(frozen=True)
class Label:
    name: str
    addr: int        # CPU address ($8000.. for a switchable bank, $C000.. in the fixed bank)
    bank: int        # 0-14, or 15 for the fixed bank
    offset: int      # file offset in an iNES file


def build_labels() -> dict[str, Label]:
    """Assemble the US disassembly in a scratch folder and read ld65's debug file."""
    with tempfile.TemporaryDirectory() as tmp:
        obj, dbg = Path(tmp) / "f.o", Path(tmp) / "f.dbg"
        subprocess.run(["ca65", "-g", "src/faxanadu.asm", "-o", str(obj)], cwd=ROOT, check=True, capture_output=True)
        subprocess.run(["ld65", "-C", "src/ld65.cfg", "-o", str(Path(tmp) / "f.nes"), str(obj), "--dbgfile", str(dbg)],
                       cwd=ROOT, check=True, capture_output=True)
        text = dbg.read_text()
    segs = {}
    for m in re.finditer(r'^seg\tid=(\d+),name="(PRG\d+)(?:_MIRROR)?",start=0x([0-9A-F]+),size=0x[0-9A-F]+,.*ooffs=(\d+)', text, re.M):
        segs[int(m.group(1))] = (int(m.group(2)[3:]), int(m.group(3), 16), int(m.group(4)))
    out = {}
    for m in re.finditer(r'^sym\tid=\d+,name="([^"]+)",addrsize=\w+,scope=0,.*?val=0x([0-9A-F]+),seg=(\d+),type=lab', text, re.M):
        seg = segs.get(int(m.group(3)))
        if seg is None or m.group(1).startswith("@"):
            continue
        bank, start, ooffs = seg
        addr = int(m.group(2), 16)
        out[m.group(1)] = Label(m.group(1), addr, bank, ooffs + addr - start)
    return out


def labels(refresh: bool = False) -> dict[str, Label]:
    if CACHE.exists() and not refresh:
        return {k: Label(k, *v) for k, v in json.loads(CACHE.read_text()).items()}
    found = build_labels()
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps({k: [v.addr, v.bank, v.offset] for k, v in sorted(found.items())}), encoding="utf-8")
    return found


class Rom:
    def __init__(self, path: Path = DEFAULT_ROM, us_build: Path | None = None):
        self.data = Path(path).read_bytes()
        if self.data[:4] != b"NES\x1a":
            raise SystemExit(f"{path} is not an iNES file")
        self.labels = labels()
        self.us = Path(us_build).read_bytes() if us_build else None

    def prg(self, bank: int) -> bytes:
        return self.data[HEADER + bank * BANK: HEADER + (bank + 1) * BANK]

    def label(self, name: str) -> Label:
        return self.labels[name]

    def at(self, name: str, length: int, skip: int = 0) -> bytes:
        o = self.labels[name].offset + skip
        return self.data[o:o + length]

    def byte(self, name: str, index: int = 0) -> int:
        return self.data[self.labels[name].offset + index]

    def word(self, name: str, index: int = 0) -> int:
        o = self.labels[name].offset + 2 * index
        return self.data[o] | (self.data[o + 1] << 8)

    def cpu(self, bank: int, addr: int, length: int) -> bytes:
        """Bytes at a CPU address as seen with `bank` mapped at $8000 (the fixed bank 15 is at $C000)."""
        if addr >= 0xC000:
            return self.data[HEADER + 15 * BANK + addr - 0xC000:][:length]
        return self.data[HEADER + bank * BANK + addr - 0x8000:][:length]

    def differs(self, name: str, length: int = 1) -> bool:
        """True when these bytes are not the same in the US build (needs `us_build`). Without it, False."""
        if self.us is None:
            return False
        o = self.labels[name].offset
        return self.data[o:o + length] != self.us[o:o + length]
