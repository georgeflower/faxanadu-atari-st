#!/usr/bin/env python3
"""Write the disassembly's RAM labels (zero page and $0100-$07FF) as JSON, for the ROM harness and the port.

    ram_labels.py [OUT.json]       (default atari_st/build/refnes/ram_labels.json)

It assembles the US disassembly in the repository root (needs cc65: ca65 and ld65) into a scratch folder and reads the label
file ld65 writes. Only names and addresses come out, no ROM data.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def ram_labels() -> dict[str, int]:
    with tempfile.TemporaryDirectory() as tmp:
        obj = Path(tmp) / "f.o"
        labels = Path(tmp) / "labels.txt"
        subprocess.run(["ca65", "-g", "src/faxanadu.asm", "-o", str(obj)], cwd=ROOT, check=True, capture_output=True)
        subprocess.run(["ld65", "-C", "src/ld65.cfg", "-o", str(Path(tmp) / "f.nes"), str(obj), "-Ln", str(labels)],
                       cwd=ROOT, check=True, capture_output=True)
        out = {}
        for line in labels.read_text().splitlines():
            m = re.match(r"al ([0-9A-F]+) \.(\S+)$", line)
            if m and not m.group(2).startswith("@") and int(m.group(1), 16) < 0x800:
                out[m.group(2)] = int(m.group(1), 16)
    return out


def main(argv: list[str]) -> int:
    out = Path(argv[1]) if len(argv) > 1 else ROOT / "atari_st" / "build" / "refnes" / "ram_labels.json"
    labels = ram_labels()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(sorted(labels.items(), key=lambda kv: (kv[1], kv[0]))), indent=0), encoding="utf-8")
    print(f"{len(labels)} RAM labels -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
