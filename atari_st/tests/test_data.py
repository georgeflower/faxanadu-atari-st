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

    def test_no_screen_depends_on_what_the_buffer_held_before(self) -> None:
        # The game decodes into one buffer; a screen that began by copying would read the screen decoded before it.
        for i in range(8):
            a = self.fm.area(self.rom, i)
            for s in range(self.fm.screen_count(self.rom, a)):
                self.assertEqual(self.fm.decode_screen(self.rom, a, s, bytes(256)),
                                 self.fm.decode_screen(self.rom, a, s, bytes([0xFF]) * 256), f"area {i} screen {s}")

    def test_neighbours_exist_and_nearly_all_link_back(self) -> None:
        # Seven links in the ROM's data are one-way (area 1 screen 27, area 2 screen 38, area 7 screens 1, 12 and 17); every
        # other link has the same screen on its far side pointing back.
        one_way = 0
        for i in range(8):
            a = self.fm.area(self.rom, i)
            n = self.fm.screen_count(self.rom, a)
            for s in range(n):
                links = self.fm.neighbours(self.rom, a, s)
                for direction, other in zip((0, 1, 2, 3), links):          # left, right, above, below
                    if other == 0xFF:
                        continue
                    self.assertLess(other, n, f"area {i} screen {s} -> {other}")
                    if self.fm.neighbours(self.rom, a, other)[direction ^ 1] != s:
                        one_way += 1
        self.assertEqual(one_way, 7)

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

    def shot(self, where: str):
        subprocess.run([sys.executable, str(ROOT / "tools" / "ram_labels.py")], check=True, capture_output=True)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        prefix = str(Path(tmp.name) / "shot")
        out = subprocess.run(["node", "refshot.mjs", where, prefix], cwd=ROOT / "tools" / "refnes", check=True,
                             capture_output=True, text=True, timeout=300).stdout
        return json.loads(out.strip().splitlines()[-1]), prefix

    def test_block_properties_equal_the_games_ram(self) -> None:
        import faxanadu_maps as fm
        import faxanadu_rom as fr

        state, prefix = self.shot("town")
        rom = fr.Rom(ROM)
        props = fm.block_properties(rom, fm.area(rom, state["area"]))
        packed = bytes((props[2 * k] & 15) | ((props[2 * k + 1] & 15) << 4) for k in range(128))
        self.assertEqual(packed, Path(prefix + ".props.bin").read_bytes())

    def test_neighbours_equal_the_games_ram(self) -> None:
        import faxanadu_maps as fm
        import faxanadu_rom as fr

        for where in ("town", "right"):
            state, _ = self.shot(where)
            rom = fr.Rom(ROM)
            self.assertEqual(list(fm.neighbours(rom, fm.area(rom, state["area"]), state["screen"])), state["neighbours"])

    def test_hud_tiles_equal_chr_ram_but_the_two_bar_tiles(self) -> None:
        import faxanadu_gfx as gfx  # noqa: F401
        import faxanadu_rom as fr

        _, prefix = self.shot("town")
        chr_ram = Path(prefix + ".chr.bin").read_bytes()
        rom = fr.Rom(ROM)
        raw = rom.at("HUD_TILES_START", 60 * 16)
        differ = [i for i in range(60) if raw[i * 16:(i + 1) * 16] != chr_ram[0x1000 + i * 16:0x1000 + (i + 1) * 16]]
        self.assertEqual(differ, [12, 13])      # the bar tiles, which the game draws into CHR RAM as the bars fill

    def test_the_castle_door_leads_to_screen_1_and_puts_the_hero_where_the_record_says(self) -> None:
        import faxanadu_maps as fm
        import faxanadu_rom as fr

        state, _ = self.shot("town")
        rom = fr.Rom(ROM)
        a = fm.area(rom, 0)
        door = fm.doors(rom, a)[0]
        self.assertEqual((door.screen, door.block), (0, 156))        # screen 0, row 9 column 12: x 192
        self.assertEqual(fm.door_destination(rom, a, door)[0], state["screen"])
        self.assertEqual(((door.start & 0x0F) << 4, door.start & 0xF0), (state["x"], state["y"]))

    def test_eolis_screen_1(self) -> None:
        self.check("town", 1)

    def test_eolis_screen_8(self) -> None:
        self.check("right", 8)


if __name__ == "__main__":
    unittest.main()
