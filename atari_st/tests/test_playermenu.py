"""The player menu's picture (src/menu.s) in Hatari: the PLAYER entry, the pictures in the lists and in the HUD's item box, and the places where Select does
nothing. The choosing itself is tests/test_menu.py and the viewer tests."""
from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"

import test_viewer as tv  # noqa: E402  (borrowed: the scene runner and the picture helpers; the class itself is not imported)

SCAN = {"TAB": 0x0F, "A": 0x39, "B": 0x38, "UP": 0x48, "DOWN": 0x50}
NAME_BASE = (0, 4, 8, 12, 17)
SPECIAL_IDS = (0x80, 0x81, 0x82, 0x83, 0x92, 0x8A, 0x93, 0x94)
ARGS = ["ALL=1", "AREA=0", "SCREEN=1", "HERO=144,144,0,255,0,0,1", "WORLD=1", "HUD=80,80,0,0,0"]


def keys_to_pokes(keys: list[str], first: int = 420) -> list[tuple[int, str, int]]:
    pokes, vbl = [], first
    for k in keys:
        pokes += [(vbl, "key", SCAN[k] << 8 | 1), (vbl + 4, "key", SCAN[k] << 8)]
        vbl += 16
    return pokes


def tile_pixels(tile: bytes) -> list[list[int]]:
    """An ST tile (8 lines of four plane bytes) as 8 rows of 8 slot numbers."""
    return [[sum(((tile[4 * y + p] >> (7 - x)) & 1) << p for p in range(4)) for x in range(8)] for y in range(8)]


@unittest.skipUnless(ROM.is_file() and shutil.which("hatari") and shutil.which("m68k-linux-gnu-as") and shutil.which("ca65") and tv.TOS.is_file(),
                     "needs the ROM, cc65, hatari, the m68k binutils and a TOS image (TOS or TOS_PAL)")
class PlayerMenuTests(unittest.TestCase):
    run_scenario = tv.ViewerTests.run_scenario
    assert_picture = tv.ViewerTests.assert_picture
    text_layer = staticmethod(tv.ViewerTests.text_layer)
    box_layer = staticmethod(tv.ViewerTests.box_layer)
    bright_slot = staticmethod(tv.ViewerTests.bright_slot)

    @classmethod
    def setUpClass(cls) -> None:
        import faxanadu_rom as fr
        import faxanadu_text as ft

        cls.rom = fr.Rom(ROM)
        font = bytearray(ft.font(cls.rom))
        font[8 * (ord('>') - 32):8 * (ord('>') - 32) + 8] = bytes([0x00, 0x10, 0x18, 0xFC, 0xFC, 0x18, 0x10, 0x00])      # build_assets.py: the menu's arrow
        cls.font = bytes(font)
        cls.names = ft.menu_strings(cls.rom)["names"]
        cls.status = ft.status_strings(cls.rom)

    def picture(self, rows, index: int, x: int, y: int, palette: int = 0) -> None:
        import itempics

        for n, tile in enumerate(itempics.st_tiles(self.rom, index, palette)):
            for dy, line in enumerate(tile_pixels(tile)):
                rows[y + 8 * (n >> 1) + dy][x + 8 * (n & 1):x + 8 * (n & 1) + 8] = line

    def same_in(self, got, want, x0: int, x1: int, y0: int, y1: int) -> None:
        bad = [(x, y) for y in range(y0, y1) for x in range(x0, x1) if got[y][x] != want[y][x]]
        self.assertEqual(bad[:5], [], f"{len(bad)} pixels differ")

    def blank(self):
        return [[0] * 320 for _ in range(200)]

    def test_the_player_entry_shows_the_rank_the_next_price_what_he_wears_and_the_special_items(self) -> None:
        """Select, the cursor down to PLAYER, A: the box of the ROM's PlayerMenu_ShowStatusMenu (the rank in force in capitals, the experience the earned rank
        needs, the name and picture of the weapon, armour, shield and spell, the pictures of the special items in their places)."""
        import hatari_shot as hs
        import st_convert as sc

        table = [self.rom.word("PLAYER_TITLE_EXP_NEEDED", i) for i in range(15)]
        special = 0x80 | 0x08 | 0x04 | 0x01                                  # Ring of Elf, Elixir, Magical Rod, Black Onyx
        pokes = [(380, "inv", 34 << 8 | 2), (381, "inv", 35 << 8 | 1), (382, "inv", 29 << 8 | special), (383, "weapon", 1), (384, "w:hero_magic", 3),
                 (385, "w:hero_title", 5), (386, "w:hero_next", 6)] + keys_to_pokes(["TAB"] + ["DOWN"] * 5 + ["A"])
        ram, word, log = self.run_scenario(ARGS, pokes, 700, "shots_status")
        got = hs.decode_screen(ram, hs.video_base(log))
        want = self.blank()
        slot = self.bright_slot(self.rom, 0)
        self.box_layer(want, slot, 4, 64, 13, 128)
        glyphs = [(80 + 8 * i, 80 + 16 * k, c, False) for k, label in enumerate(self.status["labels"]) for i, c in enumerate(label)]
        glyphs += [(152 + 8 * i, 80, c, False) for i, c in enumerate(self.status["titles"][5])]
        glyphs += [(152 + 8 * i, 96, c, False) for i, c in enumerate(f"{table[6]:05d}")]
        for cat, number in enumerate((1, 2, 1, 3)):                           # worn: Long Sword, Studded Mail, Large Shield, Death
            glyphs += [(152 + 8 * i, 112 + 16 * cat, c, False) for i, c in enumerate(self.names[NAME_BASE[cat] + number])]
        self.text_layer(want, self.font, slot, glyphs)                         # (the pictures come over the blanks at the end of the labels)
        for cat, number in enumerate((1, 2, 1, 3)):
            self.picture(want, NAME_BASE[cat] + number, 136, 104 + 16 * cat)
        for k, item in enumerate(SPECIAL_IDS):
            if special & (0x80 >> k):
                self.picture(want, 17 + (item & 31), 136 + 16 * k, 168)
        self.same_in(got, want, 64, 272, 64, 192)

    def test_the_player_entry_at_the_last_rank_with_nothing_worn_and_B_closes_the_menu(self) -> None:
        """Rank 15 has no price (the line stays blank), no weapon, shield or spell draws no name and no picture, A does nothing, and B ends the whole menu: the game
        goes on (the hero's step counter runs again)."""
        import hatari_shot as hs

        pokes = [(380, "inv", 34 << 8 | 0), (381, "inv", 35 << 8 | 255), (382, "weapon", 255), (383, "w:hero_magic", 0xFFFF), (384, "w:hero_title", 15),
                 (385, "w:hero_next", 15)] + keys_to_pokes(["TAB"] + ["DOWN"] * 5 + ["A", "A"])
        ram, word, log = self.run_scenario(ARGS, pokes, 700, "shots_status_last")
        got = hs.decode_screen(ram, hs.video_base(log))
        want = self.blank()
        slot = self.bright_slot(self.rom, 0)
        self.box_layer(want, slot, 4, 64, 13, 128)
        glyphs = [(80 + 8 * i, 80 + 16 * k, c, False) for k, label in enumerate(self.status["labels"]) for i, c in enumerate(label)]
        glyphs += [(152 + 8 * i, 80, c, False) for i, c in enumerate(self.status["titles"][15])]
        glyphs += [(152 + 8 * i, 128, c, False) for i, c in enumerate(self.names[4])]               # the armour is always worn: Leather Armor
        self.text_layer(want, self.font, slot, glyphs)
        self.picture(want, 4, 136, 120)
        self.same_in(got, want, 64, 272, 64, 192)
        held = word("step_clock")
        pokes += keys_to_pokes(["B"], 560)
        ram, word, _ = self.run_scenario(ARGS, pokes, 700, "shots_status_last")
        self.assertGreater(word("step_clock"), held + 60, "B closed the menu and the game runs")
        self.assertEqual(word.raw("inv", 38)[34:36], b"\x00\xff", "nothing was chosen")

    def list_scene(self, category: int, lists: list[tuple[int, int]], numbers: list[int], name: str) -> None:
        """Select, down to `category`, A: the box with the list; its pictures, names and the arrow on the first entry."""
        import hatari_shot as hs

        pokes = [(380 + i, "inv", o << 8 | v) for i, (o, v) in enumerate(lists)] + keys_to_pokes(["TAB"] + ["DOWN"] * category + ["A"])
        ram, word, log = self.run_scenario(ARGS, pokes, 700, name)
        got = hs.decode_screen(ram, hs.video_base(log))
        want = self.blank()
        slot = self.bright_slot(self.rom, 0)
        self.box_layer(want, slot, 4, 40, 10, 144)
        glyphs = [(72, 48, ">", False)]
        for i, number in enumerate(numbers):
            index = NAME_BASE[category] + number
            glyphs += [(96 + 8 * k, 48 + 16 * i, c, False) for k, c in enumerate(self.names[index])]
            self.picture(want, index, 80, 44 + 16 * i)
        self.text_layer(want, self.font, slot, glyphs)
        self.same_in(got, want, 64, 224, 40, 184)

    def test_a_list_has_a_picture_beside_each_name(self) -> None:
        self.list_scene(0, [(0, 1), (1, 2), (2, 3), (24, 3)], [1, 2, 3], "shots_list_w")
        self.list_scene(4, [(16, 9), (17, 15), (18, 16), (19, 0), (28, 4)], [9, 15, 16, 0], "shots_list_i")

    def test_the_item_box_of_the_hud_shows_the_item_in_hand(self) -> None:
        """The Mattock (item 9) in hand: Select and B (the menu's exit redraws the HUD) put its picture in the item box (tiles $3C-$3F), in the HUD's colours;
        no item: the box is empty."""
        import faxanadu_rom as fr
        import hatari_shot as hs
        import st_convert as sc

        for item, state in ((9, dict(item=9)), (21, dict(item=21)), (255, {})):
            with self.subTest(item=item):
                pokes = [(380, "inv", 36 << 8 | item)] + keys_to_pokes(["TAB", "B"])
                ram, word, log = self.run_scenario(ARGS, pokes, 640, "shots_hud_item")
                got = hs.decode_screen(ram, hs.video_base(log))
                plan = sc.plan_for_set(self.rom, 0)
                want = sc.hud_pixels(self.rom, 0, plan, dict(hp=80, mp=80, experience=0, gold=0, seconds=0, **state))
                self.same_in(got, [[0] * 32 + row + [0] * 32 for row in want] + [[0] * 320] * 168, 32, 288, 0, 32)

    def test_select_does_not_open_the_menu_on_eolis_first_screen_but_does_elsewhere(self) -> None:
        """The ROM's screen 0 of area 0 (outside the walls) has no menu. With the menu open the game stands still, so the hero's step counter stops (it reads about VBL - 185 while the game runs and stays near 415 from the VBL of the key on)."""
        pokes = [(599, "key", SCAN["TAB"] << 8 | 1), (603, "key", SCAN["TAB"] << 8)]
        _, word, _ = self.run_scenario(["ALL=1", "AREA=0", "SCREEN=0", "WORLD=1", "HUD=80,80,0,0,0"], pokes, 650, "shots_select")
        self.assertGreater(word("step_clock"), 440, "screen 0: the game goes on")
        _, word, _ = self.run_scenario(["ALL=1", "AREA=0", "SCREEN=1", "WORLD=1", "HUD=80,80,0,0,0"], pokes, 650, "shots_select")
        self.assertLess(word("step_clock"), 430, "screen 1: the menu is open and the game stands still")
        _, word, _ = self.run_scenario(["AREA=0", "SCREEN=1", "WORLD=1", "HUD=80,80,0,0,0"], pokes, 650, "shots_select")
        self.assertLess(word("step_clock"), 430, "a build without all the screens (table numbers are not the ROM's) too")
        _, word, _ = self.run_scenario(["AREA=0", "SCREEN=0", "WORLD=1", "HUD=80,80,0,0,0"], pokes, 650, "shots_select")
        self.assertGreater(word("step_clock"), 440, "screen 0 in a build of a few screens")


if __name__ == "__main__":
    unittest.main()
