"""The Mattock (src/items.s `use_mattock`) in Hatari. The ROM's rules are in the spec the code quotes: one block in front of the top of the hero, matched
against USE_MATTOCK_BLOCK_TRANSITIONS, message $AB, four steps of four frames, nothing kept when the screen is left."""
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

TRUNK = ["ALL=1", "AREA=1", "SCREEN=12", "HERO=40,160,0,255,0,0,1", "WORLD=1", "HUD=80,80,0,0,0", "VIEWER_DEFS=--defsym NO_ENEMIES=1"]
WALL = {10 * 16 + 3: 0x63, 11 * 16 + 3: 0x63}


@unittest.skipUnless(ROM.is_file() and shutil.which("hatari") and shutil.which("m68k-linux-gnu-as") and shutil.which("ca65") and tv.TOS.is_file(),
                     "needs the ROM, cc65, hatari, the m68k binutils and a TOS image (TOS or TOS_PAL)")
class MattockTests(unittest.TestCase):
    run_scenario = tv.ViewerTests.run_scenario
    assert_picture = tv.ViewerTests.assert_picture
    use_pokes = staticmethod(tv.ViewerTests.use_pokes)

    @classmethod
    def setUpClass(cls) -> None:
        import faxanadu_rom as fr

        cls.rom = fr.Rom(ROM)

    def picture(self, ram, log, word, patch, hero=(40, 160)):
        import hatari_shot as hs
        import faxanadu_maps as fm
        import st_convert as sc

        rows = hs.decode_screen(ram, hs.video_base(log))
        want = sc.expected_screen(self.rom, 1, 12, word("camera"), hero=sc.Hero(hero[0], hero[1], 0, 255, 0, 0, True), state=dict(hp=80, mp=80, experience=0, gold=0, seconds=0),
                                  patch=patch)
        self.assert_picture(rows, want)

    def test_the_tables_are_the_roms(self) -> None:
        import itempics
        import faxanadu_maps as fm

        table = itempics.mattock_table(self.rom)
        self.assertEqual(table.hex(), "00000000" "63858642" + "00000000" * 6)
        self.assertEqual(bytes(self.rom.at("USE_MATTOCK_BLOCK_DISTANCES", 2)), b"\xff\x10")
        a = fm.area(self.rom, 1)
        blocks = fm.decode_screen(self.rom, a, 12)
        self.assertEqual({i: blocks[i] for i in WALL}, WALL)

    def test_the_wall_crumbles_in_four_steps_and_he_can_walk_through(self) -> None:
        """Trunk screen 12, hero at x 40 facing the wall (rows 10 and 11, column 3): Down and B, the message ($AB), then the Mattock is gone, the wall
        goes in steps ($63, $85, $86, $42 in both cells) and he walks on through the gap. Without the Mattock nothing happens and the wall stops him."""
        item = [(380, "inv", 36 << 8 | 9)]
        ram, word, log = self.run_scenario(TRUNK, item + self.use_pokes(599) + [(700, "joy", 8)], 600, "shots_mattock")
        self.assertEqual(word.raw("inv", 37)[36], 9, "the message is up, the Mattock still there")
        ram, word, log = self.run_scenario(TRUNK, item + self.use_pokes(599), 720, "shots_mattock")       # (the B press is a sword swing too: wait for it to end)
        self.assertEqual(word.raw("inv", 37)[36], 255, "used up")
        self.picture(ram, log, word, {i: 0x42 for i in WALL})
        pokes = item + self.use_pokes(599) + [(660, "joy", 8)]
        ram, word, log = self.run_scenario(TRUNK, pokes, 760, "shots_mattock")
        self.assertGreater(word("hero_x"), 70, "through the gap")
        ram, word, log = self.run_scenario(TRUNK, [(660, "joy", 8)], 760, "shots_mattock")
        self.assertLess(word("hero_x"), 48, "the wall stops him")

    def test_the_enemies_stay_on_the_screen_while_the_wall_crumbles(self) -> None:
        """The game stands still during the crumble and the ROM's sprites stay on the screen (the OAM is not touched). A Trunk Hornet is put on the wall (x 56, y 168: over the
        two cells that change, half of it outside them) and the Hour Glass holds it still. The picture of the screen before the Mattock is used gives the sprite's pixels (the
        Hornet's: whatever differs from the converter's plain screen, right of the hero); in four captures between the first change and the end of the crumble the picture is the
        plain screen with the wall at one of its four stages and those pixels over it. (Before, the two blocks were copied back from the playfield and everything of the sprites
        in them, and in the 16-pixel groups they touch, was gone until the next frame of the game.)"""
        import hatari_shot as hs
        import faxanadu_maps as fm
        import st_convert as sc

        args = ["ALL=1", "AREA=1", "SCREEN=12", "HERO=40,160,0,255,255,0,1", "WORLD=1", "HUD=80,80,0,0,0"]
        pokes = [(380, "inv", 36 << 8 | 9), (560, "w:hourglass", 3000), (560, "mem:enemies+182", 56), (560, "mem:enemies+184", 168)] + self.use_pokes(599)
        state = dict(hp=80, mp=80, experience=0, gold=0, seconds=0)

        def screen(vbl):
            ram, word, log = self.run_scenario(args, pokes, vbl, "shots_mattock_enemy")
            return hs.decode_screen(ram, hs.video_base(log)), word

        before, word = screen(596)
        raw = word.raw("enemies", 8 * 30)
        self.assertEqual((raw[180], raw[182], raw[184]), (42, 56, 168), "the Hornet is on the wall")
        camera = word("camera")
        hero0 = sc.Hero(40, 160, 0, 255, 255, 0, True)
        plain = sc.expected_screen(self.rom, 1, 12, camera, hero=hero0, state=state)
        sprites = {(x, y): before[y][x] for y in range(sc.ST_TOP, 200) for x in range(88, 288) if before[y][x] != plain[y][x]}      # (the Hornet's: the hero's lie left of x 88)
        self.assertGreater(sum(1 for (x, y) in sprites if x < 96), 20, "the Hornet's pixels over the cells that change")
        pal = fm.area(self.rom, 1).palette_index
        stages = [{}, {i: 0x85 for i in WALL}, {i: 0x86 for i in WALL}, {i: 0x42 for i in WALL}]
        seen = set()
        for vbl in (626, 633, 637, 641):
            rows, word = screen(vbl)
            hero = sc.hero_layer(self.rom, sc.Hero(40, 160, 0, 255, 255, word("hero_frame"), True), pal, sc.plan_for_set(self.rom, pal))
            for n, patch in enumerate(stages):
                want = sc.expected_screen(self.rom, 1, 12, camera, state=state, patch=patch)
                for (x, y), c in sprites.items():
                    want[y][x] = c                          # (the enemies are under the hero)
                for (x, line), slot in hero.items():
                    want[line - camera][x] = slot
                bad = [(x, y) for y in range(200) for x in range(320) if rows[y][x] != want[y][x] and not (88 <= x < 104 and 160 <= y < 192 and rows[y][x] == before[y][x])]      # (a sprite pixel of the colour of the old background is not in `sprites`)
                if not bad:
                    seen.add(n)
                    break
            else:
                self.fail(f"VBL {vbl}: the picture is none of the four stages with the sprites over it ({len(bad)} pixels differ from the last)")
        self.assertGreaterEqual(len(seen), 2, f"the stages seen: {sorted(seen)}")

    def test_nothing_happens_when_the_block_in_front_is_not_the_one(self) -> None:
        """Hero at x 100: the block in front of his head is not $63: no message, the Mattock stays in hand."""
        ram, word, log = self.run_scenario([a.replace("HERO=40", "HERO=100") for a in TRUNK], [(380, "inv", 36 << 8 | 9)] + self.use_pokes(599), 640, "shots_mattock_miss")
        self.assertEqual(word.raw("inv", 37)[36], 9)

    def test_the_screen_is_whole_again_when_he_comes_back(self) -> None:
        """Nothing is kept (the ROM makes the screen from its data each time): after the wall is broken he walks off the left edge and back, and the wall stands."""
        pokes = [(380, "inv", 36 << 8 | 9)] + self.use_pokes(599) + [(650, "joy", 4), (740, "joy", 0), (1000, "joy", 8), (1100, "joy", 0)]
        ram, word, log = self.run_scenario(TRUNK, pokes, 1300, "shots_mattock_back")
        self.assertEqual(word("cur_screen"), 12)
        self.picture(ram, log, word, {}, hero=(word("hero_x"), word("hero_y")))


if __name__ == "__main__":
    unittest.main()
