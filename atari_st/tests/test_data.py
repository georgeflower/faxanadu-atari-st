"""The ROM data decoders (tools/faxanadu_rom.py, faxanadu_maps.py, render_screen.py) against the ROM and the harness.

Skipped without the ROM (ext/Faxanadu_Europe.nes) and cc65; the picture comparison also needs node and jsnes.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"

SCREENS_PER_AREA = [9, 64, 83, 14, 10, 40, 32, 20]


def have_rom() -> bool:
    return bool(ROM.is_file() and shutil.which("ca65") and shutil.which("ld65"))


def have_harness() -> bool:
    return bool(shutil.which("node") and (ROOT / "tools" / "refnes" / "node_modules" / "jsnes").is_dir())


@unittest.skipUnless(have_rom(), "needs ext/Faxanadu_Europe.nes and cc65")
class DecoderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import faxanadu_maps as fm
        import faxanadu_rom as fr
        import render_screen as rs

        cls.fm, cls.fr, cls.rs = fm, fr, rs
        cls.rom = fr.Rom(ROM)

    def test_the_eight_areas_have_the_screens_the_tables_say(self) -> None:
        counts = [self.fm.screen_count(self.rom, self.fm.area(self.rom, i)) for i in range(8)]
        self.assertEqual(counts, SCREENS_PER_AREA)

    def test_every_tile_a_screen_uses_is_in_the_areas_tileset_or_blank(self) -> None:
        for i in range(8):
            a = self.fm.area(self.rom, i)
            tiles = self.rs.tileset(self.rom, a.tiles_index)
            for s in range(self.fm.screen_count(self.rom, a)):
                blocks = self.fm.decode_screen(self.rom, a, s)
                self.assertEqual(len(blocks), 256)
                for block in set(blocks[:13 * 16]):
                    for tile in self.fm.block_tiles(self.rom, a, block):
                        self.assertTrue(tile == 0 or tile in tiles, f"area {i} screen {s} block {block} tile {tile}")

    def test_the_last_rows_of_the_screen_buffer_are_zero(self) -> None:
        a = self.fm.area(self.rom, 0)
        self.assertEqual(self.fm.decode_screen(self.rom, a, 1)[0xF0:], bytes(16))


@unittest.skipUnless(have_rom() and have_harness(), "needs the ROM, cc65, node and jsnes (npm install in tools/refnes)")
class PictureTests(unittest.TestCase):
    """A screen drawn from the ROM's tables alone equals what jsnes shows, apart from sprites and the blanked edges."""

    def check(self, where: str, screen: int) -> None:
        import faxanadu_rom as fr
        import render_screen as rs

        subprocess.run([sys.executable, str(ROOT / "tools" / "ram_labels.py")], check=True, capture_output=True)
        with tempfile.TemporaryDirectory() as tmp:
            prefix = str(Path(tmp) / "shot")
            out = subprocess.run(["node", "refshot.mjs", where, prefix], cwd=ROOT / "tools" / "refnes", check=True,
                                 capture_output=True, text=True, timeout=300).stdout
            state = json.loads(out.strip().splitlines()[-1])
            self.assertEqual((state["area"], state["screen"]), (0, screen))
            image = rs.render(fr.Rom(ROM), state["area"], state["screen"], state["palette"])
            oam = json.loads(Path(prefix + ".oam.json").read_text())
            count, box = rs.compare(image, rs.read_ppm(Path(prefix + ".ppm")), oam)
            self.assertEqual(count, 0, f"{count} pixels differ, in {box}")

    def test_eolis_screen_1(self) -> None:
        self.check("town", 1)

    def test_eolis_screen_8(self) -> None:
        self.check("right", 8)


if __name__ == "__main__":
    unittest.main()
