"""The cycle budget (AGENTS.md 5i, G4): the dearest frames stay under a frame of 160,256 cycles (PAL, 50 Hz) with no late frame.

tools/profile_scene.py runs the program in Hatari with the profiler on (--cpu-exact) and gives the busy cycles of every VBL and the late frames. Pinned here:
a scroll to the side with enemies (Eolis 4 to 5: the pass that starts it drew the whole next screen in one go, 673,000 cycles and three late frames, and
each 16-pixel step shifted the playfield in place, 141,000 cycles in one frame), a door (Eolis's castle door: the screen drawn while the picture is black)
and the dearest of the enemy scenes (Mist screen 64, two big enemies). Needs a 50 Hz TOS image: TOS_PAL, or the German EmuTOS beside the one in TOS."""
from __future__ import annotations

import os
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import profile_scene as ps  # noqa: E402

ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"


def pal_tos() -> Path | None:
    if os.environ.get("TOS_PAL") and Path(os.environ["TOS_PAL"]).is_file():
        return Path(os.environ["TOS_PAL"])
    tos = Path(os.environ.get("TOS", ""))
    if tos.is_file() and tos.name.startswith("etos") and (tos.parent / (tos.name[:-6] + "de.img")).is_file():
        return tos.parent / (tos.name[:-6] + "de.img")
    return None


TOS = pal_tos()


@unittest.skipUnless(ROM.is_file() and shutil.which("hatari") and shutil.which("m68k-linux-gnu-as") and shutil.which("ca65") and TOS,
                     "needs the ROM, cc65, hatari, the m68k binutils and a 50 Hz TOS image (TOS_PAL, or etos...de.img beside TOS)")
class CycleTests(unittest.TestCase):
    def frames(self, make_args: list[str], start: int, end: int, pokes: list[tuple[int, str, int]], name: str) -> tuple[list[int], int, list[int]]:
        """The busy cycles of every VBL from start to end, the late frames, and those of the VBLs that hold one pass of the frame loop."""
        sym = ps.build(make_args)
        pieces, late = ps.run(TOS, sym, start, end, 1, pokes, ROOT / "build" / name)
        busy = [p["total"] - p["routines"].get("wait_vbl", [0, 0, 0])[2] for p in pieces]
        passes = [p["routines"].get("input_poll", [0])[0] + p["routines"].get("input_poll_game", [0])[0] for p in pieces]
        return busy, late[-1] - late[0], [b for b, n in zip(busy, passes) if n == 1]

    def test_a_scroll_with_enemies_has_no_late_frame_and_no_frame_over_65_percent(self) -> None:
        # Eolis 4, two Zozuras; he stands at x 236 facing right and walks off the right edge by himself (the scroll starts about VBL 376, its steps end about 450).
        busy, late, _ = self.frames(["ALL=1", "AREA=0", "SCREEN=4", "HERO=236,144,0,255,0,0,1", "WORLD=1", "HUD=80,80,0,0,0"], 370, 470, [], "shots_cycles_scroll")
        self.assertEqual(late, 0)
        self.assertLess(max(busy), 0.65 * ps.FRAME, busy)

    def test_a_door_has_no_late_frame(self) -> None:
        busy, late, _ = self.frames(["ALL=1", "AREA=0", "SCREEN=0", "HERO=192,144,0,255,0,0,1", "WORLD=1", "HUD=80,80,0,0,0"], 395, 440,
                                    [(400, "joy", 1), (403, "joy", 0)], "shots_cycles_door")
        self.assertEqual(late, 0, busy)

    def test_the_dearest_enemy_scene_has_no_late_frame(self) -> None:
        busy, late, passes = self.frames(["ALL=1", "AREA=2", "SCREEN=64", "HERO=64,144,0,255,0,0,1", "WORLD=1", "HUD=80,80,0,0,0"], 420, 470, [], "shots_cycles_mist64")
        self.assertEqual(late, 0)
        self.assertGreaterEqual(len(passes), 30)
        self.assertLess(max(passes), ps.FRAME, passes)


if __name__ == "__main__":
    unittest.main()
