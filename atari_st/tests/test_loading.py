"""The start-up's LOADING screen (src/viewer.s, `loading_show`, `loading_hide`) in Hatari.

TOWN.DAT is read into TOS's own screen memory (`town_buf` = `orig_screen`). Before, the word LOADING was drawn on that screen and TOS's colours were put back
before TOWN.DAT was read, so the author saw the file arrive as coloured noise on a white screen. Now the word is on the program's own screen (`buf_a`) and
that is the screen on show while TOWN.DAT is read: the entry of `town_load` is stopped on, and the screen on show must be `buf_a`, black with only the word."""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"

import test_viewer as tv  # noqa: E402  (the TOS image)

NEEDS = ROM.is_file() and shutil.which("hatari") and shutil.which("m68k-linux-gnu-as") and shutil.which("ca65") and tv.TOS.is_file()


@unittest.skipUnless(NEEDS, "needs the ROM, cc65, hatari, the m68k binutils and a TOS image (TOS or TOS_PAL)")
class LoadingTests(unittest.TestCase):
    def test_the_screen_on_show_while_town_dat_is_read_is_the_programs_own_black_one_with_the_word(self) -> None:
        import hatari_shot as hs

        subprocess.run(["make", "-C", str(ROOT), "viewer", "ALL=1", "AREA=0", "SCREEN=1",
                        "VIEWER_DEFS=--defsym NEWGAME=1 --defsym MENU=1 --defsym NPCS=1 --defsym SPLASH=1"], check=True, capture_output=True)
        nm = subprocess.run(["m68k-linux-gnu-nm", str(ROOT / "build" / "viewer.elf")], check=True, capture_output=True, text=True).stdout.split("\n")
        sym = {line.split()[2]: int(line.split()[0], 16) for line in nm if len(line.split()) == 3}
        image = (ROOT / "build" / "viewer.bin").read_bytes()
        work = ROOT / "build" / "shots_loading"
        work.mkdir(parents=True, exist_ok=True)
        prg = ROOT / "build" / "VIEWER.PRG"
        hatari = shutil.which("hatari")
        (work / "c0.ini").write_text(f"savebin {work / 'ram0.bin'} 0 $80000\ncont\n", encoding="utf-8")
        hs.run_hatari(hatari, tv.TOS, prg, work, 500, "0", f"b VBL > 499 :once :file {work / 'c0.ini'}\n", None)
        base = (work / "ram0.bin").read_bytes().find(image[sym["start"]:sym["start"] + 48]) - sym["start"]
        self.assertGreater(base, 0)
        (work / "cap.ini").write_text(f"savebin {work / 'ram1.bin'} 0 $80000\nm $ff8200-$ff8260\ncont\n", encoding="utf-8")
        log = hs.run_hatari(hatari, tv.TOS, prg, work, 600, "0", f"b pc = ${base + sym['town_load']:x} :once :file {work / 'cap.ini'}\n", None)
        chunks = re.split(r"(?m)^(?=00FF8200:)", log)[1:]
        self.assertEqual(len(chunks), 1, "the program reached town_load")
        ram = (work / "ram1.bin").read_bytes()
        video = hs.video_base(chunks[0])
        buf_a = int.from_bytes(ram[base + sym["buf_a"]:base + sym["buf_a"] + 4], "big")
        orig = int.from_bytes(ram[base + sym["orig_screen"]:base + sym["orig_screen"] + 4], "big")
        self.assertNotEqual(buf_a, orig)
        self.assertEqual(video, buf_a, "the program's own screen is on show while TOWN.DAT is read, not TOS's, which the file lands in")
        palette = hs.read_palette(chunks[0])
        self.assertEqual(palette[:15], [0] * 15, "black but for colour 15")
        self.assertEqual(palette[15], 0x777)
        rows = hs.decode_screen(ram, video)
        colours = {c for row in rows for c in row}
        self.assertEqual(colours, {0, 15}, "nothing on the screen but the word LOADING")
        self.assertGreater(sum(c == 15 for row in rows for c in row), 100, "the word is there")


if __name__ == "__main__":
    unittest.main()
