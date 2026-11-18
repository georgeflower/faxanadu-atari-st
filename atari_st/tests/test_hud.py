"""The HUD in the side margins (src/hud.s, `st_convert.HUD_PLACES`): the playfield has all 200 lines of the screen, so the HUD's tiles stand in
the 32-pixel margins left and right of it. Pure Python, apart from the ROM for the tiles; the pictures in Hatari are in tests/test_viewer.py
(`test_the_hud_is_drawn_from_its_state...`, `test_a_hud_change_during_play_reaches_both_screens`) and tests/test_camera.py.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"

import faxanadu_gfx as gfx  # noqa: E402
import st_convert as sc  # noqa: E402


class LayoutTests(unittest.TestCase):
    def test_every_tile_of_the_hud_has_a_place_strictly_inside_a_margin(self) -> None:
        """Every non-blank tile the NES's HUD draws (its static symbols but the two colons of the bars, the bars, the digits, the item box) has
        a place, every place is in columns 0-3 (x 0-31) or 36-39 (x 288-319), and no two share one."""
        layout = sc.st_hud_layout(80, 80, 65535, 9999999, 99)
        layout[2][17:21] = layout[3][19:23] = [0x30] * 4                 # (every place of the values, a blank too)
        drawn = {(r, c) for r in (2, 3) for c in range(32) if layout[r][c]}
        self.assertEqual(drawn - set(sc.HUD_PLACES), {(2, 2), (3, 2)}, "only the colons after M and P are left out")
        places = list(sc.HUD_PLACES.values())
        self.assertEqual(len(places), len(set(places)))
        for col, row in places:
            self.assertTrue(col < 4 or col >= 36, (col, row))
            self.assertTrue(0 <= row < 25, (col, row))

    def test_the_bars_stand_upright_and_the_numbers_read_from_top_to_bottom(self) -> None:
        places = sc.HUD_PLACES
        for r, col in ((2, 0), (3, 2)):                                  # magic in column 0, power in column 2, the label on top
            self.assertEqual(places[(r, 1)], (col, 2))
            self.assertEqual([places[(r, 3 + k)] for k in range(11)], [(col, 13 - k) for k in range(11)], "the first tile at the bottom, the end on top")
        for label, first in ((2, 17), (3, 19)):                           # E: and G:, the value on one line of four tiles under its label
            row = places[(label, 14)][1]
            self.assertEqual((places[(label, 14)], places[(label, 15)]), ((36, row), (37, row)))
            self.assertEqual([places[(label, first + k)] for k in range(4)], [(36 + k, row + 1) for k in range(4)])
            self.assertNotIn((label, first - 1), places, "the other digit columns have no place")

    def test_experience_and_gold_are_four_characters_rounded_down(self) -> None:
        """The author asked for "99.9K" and "1.00M": five characters, one more than the four tiles of a line, so one decimal below 10 and none above."""
        cases = {0: "   0", 999: " 999", 1000: "1.0K", 1099: "1.0K", 1999: "1.9K", 9999: "9.9K", 10000: " 10K", 99999: " 99K", 999999: "999K",
                 1000000: "1.0M", 1099999: "1.0M", 9999999: "9.9M", 10000000: " 10M", 16777215: " 16M", 65535: " 65K"}
        for value, text in cases.items():
            self.assertEqual(sc.short_number(value), text, value)
        self.assertEqual(sc.short_tiles(1099), [0x31, sc.HUD_DOT, 0x30, sc.HUD_K])
        self.assertEqual(sc.short_tiles(1000000), [0x31, sc.HUD_DOT, 0x30, sc.HUD_M])
        self.assertEqual(sc.short_tiles(7), [0, 0, 0, 0x37])
        for value in range(0, 17_000_000, 997):                           # never more than he has: the number the text stands for is at most the value
            text = sc.short_number(value).strip()
            unit = {"K": 1000, "M": 1_000_000}.get(text[-1], 1)
            shown = float(text[:-1] if unit > 1 else text) * unit
            self.assertLessEqual(shown, value, (value, text))

    def test_the_trainer_words_do_not_touch_the_hud(self) -> None:
        hud_lines = {row * 8 + y for col, row in sc.HUD_PLACES.values() if col < 4 for y in range(8)}
        trainer = {line + y for line in sc.TRAINER_LINES for y in range(8)}
        self.assertFalse(hud_lines & trainer)

    def test_a_turned_bar_tile_is_the_tile_turned_a_quarter_left(self) -> None:
        img = bytearray(32)
        img[0] = 0x80                                                    # plane 0 of the top left pixel (x 0, y 0), and plane 1 of x 7, y 0
        img[1] = 0x01
        turned = sc.rotate_bar_tile(bytes(img))
        self.assertEqual(turned[7 * 4], 0x80, "top left goes to bottom left")
        self.assertEqual(turned[0 * 4 + 1], 0x80, "top right goes to top left")
        self.assertEqual(sum(turned), 0x100)

    def test_the_places_table_of_the_program_matches(self) -> None:
        import build_assets as ba

        table = ba.hud_places_bytes()
        self.assertEqual(len(table), 64 * 4)
        for n in range(64, 128):
            screen, margin = (int.from_bytes(table[4 * (n - 64) + k:4 * (n - 64) + k + 2], "big") for k in (0, 2))
            place = sc.HUD_PLACES.get((n >> 5, n & 31))
            if place is None:
                self.assertEqual((screen, margin), (0xFFFF, 0xFFFF))
                continue
            col, row = place
            self.assertEqual(screen, row * 8 * 160 + (col >> 1) * 8 + (col & 1))
            self.assertEqual(margin, row * 64 + (col & 1) if col in (36, 37) else 0xFFFF)

    def test_the_camera_is_0_to_8_and_the_window_200_lines(self) -> None:
        self.assertEqual((sc.WINDOW_LINES, sc.CAMERA_MAX, sc.ST_TOP), (200, 8, 0))
        self.assertEqual(sc.WINDOW_LINES + sc.CAMERA_MAX, 208, "camera 8 shows the playfield's last line")


@unittest.skipUnless(ROM.is_file(), "needs the ROM")
class PictureTests(unittest.TestCase):
    def test_the_expected_screen_has_the_whole_playfield_and_the_hud_only_in_the_margins(self) -> None:
        import faxanadu_rom as fr

        rom = fr.Rom(ROM)
        state = dict(hp=35, mp=13, experience=4242, gold=1234567, seconds=7)
        full = sc.expected_screen(rom, 0, 1, 0, state=state)
        window = sc.expected_window(rom, 0, 1, 0, 200)
        self.assertEqual([row[32:288] for row in full], window, "lines 0-199 of the playfield")
        low = sc.expected_screen(rom, 0, 1, 8, state=state)
        self.assertEqual([row[32:288] for row in low], sc.expected_window(rom, 0, 1, 8, 200), "camera 8: lines 8-207")
        margins = sc.hud_margins(rom, 0, sc.plan_for_set(rom, 0), state)
        self.assertEqual([row[:32] + row[288:] for row in full], [row[:32] + row[288:] for row in margins])
        self.assertTrue(any(margins[y][x] for y in range(16, 24) for x in range(0, 8)), "the M")
        self.assertTrue(any(margins[y][x] for y in range(96, 104) for x in range(0, 8)), "the magic bar's bottom tile")
        self.assertTrue(any(margins[y][x] for y in range(48, 56) for x in range(288, 320)), "the experience (4.2K)")

    def test_build_assets_refuses_a_camera_over_8(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run([sys.executable, str(ROOT / "tools" / "build_assets.py"), "--rom", str(ROM), "--camera", "9", "--out", tmp],
                               capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("0 to 8", r.stderr)


if __name__ == "__main__":
    unittest.main()
