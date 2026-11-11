"""The death box has no portrait, in the ROM as on the ST.

`Player_HandleDeath` ends by running script $FF, which `IScripts_Begin` maps to $1F: entity byte $00 (no portrait), MSG_UNSKIPPABLE $24, END. The port's death message
(`message_box` with message $24) has no portrait either, so nothing is to be added (an earlier note in AGENTS.md said a portrait was missing: wrong). Checked in the
script data and in jsnes (`tools/refnes/deathboxprobe.mjs`: while each page of the box is up, the only sprite is the box's cursor, not the 6x8 cells of a portrait)."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"
REFNES = ROOT / "tools" / "refnes"


@unittest.skipUnless(ROM.is_file(), "needs the ROM")
class DeathBoxTests(unittest.TestCase):
    def test_the_death_script_has_no_portrait(self) -> None:
        import faxanadu_rom as fr
        import iscripts as isc

        rom = fr.Rom(ROM)
        blob, offsets = isc.script_blob(rom), isc.script_offsets(rom)
        start = offsets[0x1F]
        self.assertEqual(blob[start], 0x00, "entity byte $00: no portrait")
        self.assertEqual(blob[start + 1:start + 4], bytes([1, 0x24, 0]), "MSG_UNSKIPPABLE $24, END")

    @unittest.skipUnless(shutil.which("node") and (REFNES / "node_modules").is_dir(), "needs node and the harness")
    def test_the_rom_shows_no_portrait_sprites_in_the_death_box(self) -> None:
        subprocess.run([sys.executable, str(ROOT / "tools" / "ram_labels.py")], check=True, capture_output=True, cwd=ROOT)
        out = subprocess.run(["node", "deathboxprobe.mjs"], cwd=REFNES, check=True, capture_output=True, text=True).stdout
        pages = json.loads(out.strip().split("\n")[-1])["pages"]
        self.assertEqual(len(pages), 3)
        for sprites in pages:
            self.assertLessEqual(len(sprites), 2, "at most the box's cursor (a portrait is 48 cells)")


if __name__ == "__main__":
    unittest.main()
