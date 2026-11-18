"""The screen on show is never the one being drawn (`present_swap` in src/viewer.s), and the hero is on the screen in every frame of a busy scene.

The author saw the hero vanish on Trunk screens 29, 38 and 30 (Fax086, with three Yuinarus about): the shifter takes a new screen address at the start of a
frame, and `present_swap` wrote it after the wait for the VBL, so the screen the next pass erased and drew into was the one on show for that whole frame. The
beam showed what was there when it passed: the hero, drawn last, was often still erased, most of all when many enemies were drawn before him. The NES does not
hide him there: in jsnes no line of those screens has more than six sprites (eight is the limit), so the ROM drops and flickers nothing.

Each test captures every VBL of a window (Hatari's VBL breakpoint: the screen address in the shifter's registers then is the screen shown in the frame that
starts) and checks that (1) the playfield (the HUD is in the side margins) of the screen on show at VBL n is the same at VBL n + 1, i.e. nothing drew into it while it was shown, (2) it holds every pixel
of the hero as his state at VBL n says (he is drawn after the enemies, so they cannot cover him), (3) no frame came late."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_mattock as tm  # noqa: E402


@unittest.skipUnless(tm.ROM.is_file() and tm.shutil.which("hatari") and tm.shutil.which("m68k-linux-gnu-as") and tm.shutil.which("ca65") and tm.tv.TOS.is_file(),
                     "needs the ROM, cc65, hatari, the m68k binutils and a TOS image (TOS or TOS_PAL)")
class PresentTests(unittest.TestCase):
    run_multi = tm.MattockTests.run_multi

    @classmethod
    def setUpClass(cls) -> None:
        import faxanadu_rom as fr

        cls.rom = fr.Rom(tm.ROM)

    def busy_scene(self, area: int, screen: int, hero: str, first: int, last: int, name: str) -> None:
        import faxanadu_maps as fm
        import hatari_shot as hs
        import st_convert as sc

        args = ["ALL=1", f"AREA={area}", f"SCREEN={screen}", f"HERO={hero},0,255,0,0,1", "WORLD=1", "HUD=80,80,0,0,0", "VIEWER_DEFS=--defsym JOYPAD=1 --defsym NPCS=1"]
        captures = list(range(first, last + 1))
        shots = self.run_multi(args, [], captures, name)
        rams, bases = self.last_rams, self.last_bases
        pal = fm.area(self.rom, area).palette_index
        plan = sc.plan_for_set(self.rom, pal)
        enemies = 0
        for n in range(len(captures) - 1):
            rows, word = shots[n]
            with self.subTest(vbl=captures[n]):
                after = hs.decode_screen(rams[n + 1], bases[n])
                changed = [(x, y) for y in range(sc.ST_TOP, 200) for x in range(sc.ST_LEFT, sc.ST_LEFT + 256) if after[y][x] != rows[y][x]]      # (the playfield: the HUD, in the side margins, is drawn into both screens right after the VBL, by design)
                self.assertEqual(changed[:5], [], f"{len(changed)} pixels of the screen on show were drawn while it was shown")
                camera = word("camera")
                layer = sc.hero_layer(self.rom, sc.Hero(word("hero_x"), word("hero_y"), 0, 255, 0, word("hero_frame"), bool(word("hero_flip"))), pal, plan)
                shown = [(x, line + sc.SPRITE_DY - camera) for (x, line) in layer if sc.ST_TOP <= line + sc.SPRITE_DY - camera < 200 and sc.ST_LEFT <= x < sc.ST_LEFT + 256]
                missing = [(x, y) for x, y in shown if rows[y][x] != layer[(x, y - sc.SPRITE_DY + camera)]]
                self.assertGreater(len(shown), 100, "he is in the window")
                self.assertEqual(missing[:5], [], f"{len(missing)} of his {len(shown)} pixels are not on the screen on show")
                enemies = max(enemies, sum(1 for i in range(8) if word.raw("enemies", 240)[i * 30] != 0xFF))
        self.assertGreaterEqual(enemies, 2, "a busy scene")
        late = [int.from_bytes(w.raw("late_frames", 4), "big") for _, w in shots]
        self.assertEqual(late[0], late[-1], "no late frame in the window")

    def test_trunk_29_with_three_yuinarus(self) -> None:
        self.busy_scene(1, 29, "16,144", 300, 340, "shots_present_29")

    def test_trunk_26_with_charron_and_his_fireball(self) -> None:
        self.busy_scene(1, 26, "64,144", 296, 316, "shots_present_26")


if __name__ == "__main__":
    unittest.main()
