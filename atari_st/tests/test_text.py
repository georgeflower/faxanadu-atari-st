"""The text the port takes from the ROM (tools/faxanadu_text.py): the font and the messages."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"


@unittest.skipUnless(ROM.is_file(), "needs the ROM")
class TextTests(unittest.TestCase):
    def setUp(self) -> None:
        import faxanadu_rom as fr

        self.rom = fr.Rom(ROM)

    def test_the_font_is_96_glyphs_of_8_bytes_and_the_letters_are_drawn(self) -> None:
        import faxanadu_text as ft

        font = ft.font(self.rom)
        self.assertEqual(len(font), 96 * 8)
        self.assertEqual(font[:8], bytes(8), "the space is blank")
        glyph = lambda c: font[8 * (ord(c) - 32):8 * (ord(c) - 32) + 8]
        self.assertTrue(all(any(glyph(c)) for c in "AZaz09,?"))
        self.assertEqual(len({glyph(c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"}), 62, "every letter and digit has its own")

    def test_the_death_message_has_five_lines_that_fit_the_box(self) -> None:
        import faxanadu_text as ft

        text = ft.message(self.rom, ft.MESSAGE_DEATH)
        lines = text.split("\n")
        self.assertEqual(len(lines), 5)
        self.assertTrue(all(0 < len(line) <= 16 for line in lines))
        self.assertIn("mantra", text)
        self.assertTrue(all(32 <= ord(c) < 128 for c in text.replace("\n", "")))

    def test_the_password_screen_has_its_two_lines(self) -> None:
        import faxanadu_text as ft

        wrong, ask = ft.password_lines(self.rom)
        self.assertIn("mantra", wrong.lower())
        self.assertIn("mantra", ask.lower())
        self.assertLessEqual(max(len(wrong), len(ask)), 23)


if __name__ == "__main__":
    unittest.main()
