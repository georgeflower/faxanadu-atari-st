"""The sides of a screen: knocked back or walked off them, the hero goes where the ROM sends him.

The ROM (`tools/refnes/knockedge.mjs`, jsnes): a knock-back moves him 8 pixels a frame with `Player_TryMoveLeft/Right`, the same moves as walking. Past
x $F0 (or under 0) he scrolls to the screen on that side when there is one, whatever the stick says, and the knock-back goes on there; with none he
stays at $F0 (or 0). He leaves an area only on the blocks of a way out (`Player_CheckSwitchScreen`: properties 12 and 13 at x and x + 15), never by
the side of the screen itself: Trunk screen 0 has a record in `AREA_TOWN_TRANSITIONS_DATA` (to the towns, screen 2) but no such blocks, so walking
left there ends at x 0 (the port used to take the record and put him in Forepaw, the author's report on Fax086). Each case runs in both; the port
in Hatari with the test keys H and G (a hit from the right, from the left) and no enemies.

Needs the ROM, node and the harness's packages, Hatari, the m68k binutils and a TOS image (TOS or TOS_PAL).
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
sys.path.insert(0, str(ROOT / "tests"))
import test_viewer as tv  # noqa: E402

# (case for the ROM, the port's pokes): "from" left is the G key (he is knocked to the right), right the H key
CASES = [
    ({"screen": 26, "x": 232, "y": 144, "from": "left"}, "onto the way into Forepaw: area 3, screen 2"),
    ({"screen": 1, "x": 232, "y": 160, "from": "left"}, "off the right side: scrolls to screen 2 and the knock-back goes on"),
    ({"screen": 1, "x": 8, "y": 160, "from": "right"}, "off the left side: scrolls to screen 0"),
    ({"screen": 26, "x": 8, "y": 144, "from": "right"}, "off the left side of screen 26: screen 25"),
    ({"screen": 8, "x": 16, "y": 160, "from": "right"}, "onto the way into Apolune on the left: area 3, screen 1"),
    ({"screen": 7, "x": 200, "y": 160, "walk": "right", "hold": 50}, "walking onto the way into Apolune: area 3, screen 0"),
    ({"screen": 0, "x": 32, "y": 160, "walk": "left", "hold": 150}, "walking left on Trunk's first screen: he stays at x 0"),
]


@unittest.skipUnless(tv.ROM.is_file() and shutil.which("hatari") and shutil.which("m68k-linux-gnu-as") and shutil.which("node") and tv.TOS.is_file()
                     and (ROOT / "tools" / "refnes" / "node_modules").exists(), "needs the ROM, node and the harness, hatari, the m68k binutils and a TOS image")
class KnockEdgeTests(unittest.TestCase):
    rom: list = []

    @classmethod
    def setUpClass(cls) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec, out = Path(tmp) / "cases.json", Path(tmp) / "out.json"
            spec.write_text(json.dumps([dict(area=1, region=1, **c) for c, _ in CASES]))
            subprocess.run(["node", "knockedge.mjs", str(spec), str(out)], cwd=ROOT / "tools" / "refnes", check=True, capture_output=True)
            cls.rom = json.loads(out.read_text())

    run_scenario = tv.ViewerTests.run_scenario
    assert_picture = tv.ViewerTests.assert_picture

    def rom_end(self, i: int) -> tuple[int, int, int, int, int]:
        f = self.rom[i]["frames"][-1]
        return f["area"], f["screen"], f["x"], f["y"], (f["flags"] >> 6) & 1

    def test_the_rom(self) -> None:
        """What the ROM does, in short (the port is compared with these runs below)."""
        ends = [self.rom_end(i)[:4] for i in range(len(CASES))]
        self.assertEqual(ends, [(3, 2, 48, 144), (1, 2, 16, 160), (1, 0, 232, 160), (1, 25, 232, 144), (3, 1, 216, 144), (3, 0, 32, 144), (1, 0, 0, 160)])
        right = self.rom[1]["frames"]
        self.assertIn(248, [f["x"] for f in right if f["scroll"] != 0xFF], "the scroll starts with him at 248 (240 + 8), not wrapped to the left")
        self.assertTrue(all(f["area"] == 1 and f["screen"] == 0 for f in self.rom[6]["frames"]), "Trunk's first screen: no way out on the left")

    def test_the_port_ends_where_the_rom_does(self) -> None:
        for i, (case, what) in enumerate(CASES):
            with self.subTest(what):
                args = ["ALL=1", "AREA=1", f"SCREEN={case['screen']}", f"HERO={case['x']},{case['y']},0,255,0,0,1", "WORLD=1,3",
                        "VIEWER_DEFS=--defsym NO_ENEMIES=1"]
                if "walk" in case:
                    stick = 8 if case["walk"] == "right" else 4
                    pokes = [(599, "joy", stick), (599 + case["hold"], "joy", 0)]
                else:
                    pokes = [(599, "g" if case["from"] == "left" else "h", 1), (600, "g" if case["from"] == "left" else "h", 0)]
                _, word, _ = self.run_scenario(args, pokes, 900, "shots_knockedge")
                area, screen, x, y, facing = self.rom_end(i)
                self.assertEqual((word("cur_area"), word("cur_screen"), word("hero_x"), word("hero_y")), (area, screen, x, y))
                if "walk" not in case:
                    self.assertEqual(word("hero_flip"), facing, "he faces the enemy again after the knock-back")


if __name__ == "__main__":
    unittest.main()
