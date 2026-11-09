"""The item pictures (tools/itempics.py, items.bin): the tile numbers of the ROM's lists (bank 10) and the tiles themselves."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"

# the tile numbers by picture index (0 weapons, 4 armour, 8 shields, 12 spells, 17 items), from the disassembly's lists (spec: ITEM_TILEMAP_INDEXES and its three neighbours)
NUMBERS = {0: (0x4A, 0x4B, 0x8F, 0x4C), 1: (0x47, 0x48, 0x8F, 0x49), 2: (0x44, 0x45, 0x8F, 0x46), 3: (0x4D, 0x4E, 0x4F, 0x50),
           4: (0x51, 0x52, 0x53, 0x54), 7: (0x5D, 0x5E, 0x5F, 0x60), 8: (0x61, 0x62, 0x63, 0x64), 11: (0x6D, 0x6E, 0x6F, 0x70),
           12: (0x7F, 0x80, 0x81, 0x82), 15: (0x7B, 0x7C, 0x7D, 0x7E), 16: (0x77, 0x78, 0x79, 0x7A),
           17 + 0: (0x06, 0x07, 0x0C, 0x0D), 17 + 4: (0x26, 0x27, 0x28, 0x29), 17 + 5: (0x2A, 0x27, 0x2B, 0x29), 17 + 9: (0x00, 0x01, 0x02, 0x03),
           17 + 10: (0x0E, 0x0F, 0x10, 0x11), 17 + 16: (0x2C, 0x2D, 0x2E, 0x2F), 17 + 18: (0x34, 0x35, 0x36, 0x37), 17 + 21: (0x40, 0x41, 0x42, 0x43)}


@unittest.skipUnless(ROM.is_file(), "needs the ROM")
class ItemPictureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import faxanadu_rom as fr
        import itempics

        cls.rom = fr.Rom(ROM)
        cls.data = itempics.item_file(cls.rom)
        cls.parsed = itempics.parse(cls.data)
        cls.itempics = itempics

    def test_the_file_has_the_layout_the_program_reads(self) -> None:
        ip = self.itempics
        self.assertEqual((ip.COLOURS_AT, ip.PICTURES_AT, ip.MATTOCK_AT, ip.TILES_AT), (0, 112, 268, 300), "src/menu.s ITEMS_PICTURES, ITEMS_MATTOCK and ITEMS_TILES")
        self.assertEqual((len(self.parsed["colours"]), len(self.parsed["pictures"])), (28, 39))
        self.assertEqual(len(self.data) - ip.TILES_AT, 16 * len(self.parsed["tiles"]))
        self.assertEqual(len(self.data) % 2, 0)

    def test_every_picture_is_the_four_tiles_of_the_roms_list(self) -> None:
        for index, numbers in NUMBERS.items():
            with self.subTest(index=index):
                tiles = [self.parsed["tiles"][t] for t in self.parsed["pictures"][index]]
                want = [bytes(self.rom.cpu(10, 0x8500 + 16 * n, 16)) for n in numbers]
                self.assertEqual(tiles, want)

    def test_the_hud_colours_of_each_set_are_the_slots_of_its_hud_palette(self) -> None:
        import st_convert as sc

        for pal in (0, 4, 14, 16, 27):
            plan = sc.plan_for_set(self.rom, pal)
            bg, _ = sc.palette_set(self.rom, pal)
            self.assertEqual(self.parsed["colours"][pal], [plan.slot[c & 0x3F] for c in bg[sc.ui_palette_row(self.rom, pal)]])

    def test_an_item_id_maps_to_its_picture(self) -> None:
        ip = self.itempics
        self.assertEqual([ip.picture_index(i) for i in (0x00, 0x23, 0x42, 0x63, 0x89, 0x94)], [0, 7, 10, 15, 17 + 9, 17 + 20])


if __name__ == "__main__":
    unittest.main()
