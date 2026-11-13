"""The trainer (src/trainer.s): T turns it on and off; while it is on nothing takes power off the hero and the area and the screen are shown left of the HUD.

The scene is the one of test_viewer's `test_an_enemy_on_him_does_not_start_the_death_again`: the Snowman of Trunk screen 16 leaps on him at 3 power, which kills him
before VBL 900 without the trainer."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "tools"))

import test_flow as tf  # noqa: E402

T_KEY = 0x14
SCENE = ["ALL=1", "AREA=1", "SCREEN=16", "HERO=208,144,0,255,0,0,1", "WORLD=1", "HUD=3,0,0,0,0"]


def margin_pixels(shot: "tf.Shot") -> int:
    """Pixels that are not black in the margin left of the HUD (x 0 to 31, lines 8 to 27)."""
    return sum(1 for y in range(8, 28) for x in range(32) if shot.rows[y][x])


@unittest.skipUnless(tf.NEEDS, "needs the ROM, cc65, hatari, the m68k binutils and a TOS image")
class TrainerTests(unittest.TestCase):
    def test_t_makes_him_invincible_and_shows_the_area_and_screen_and_t_again_takes_both_away(self) -> None:
        pokes = [(290, "key", T_KEY << 8 | 1), (318, "key", T_KEY << 8), (910, "key", T_KEY << 8 | 1), (914, "key", T_KEY << 8)]   # (the Snowman lands on him about VBL 330)
        run = tf.Run(SCENE, pokes, [285, 900, 940], "shots_trainer")
        before, on, off = run.shots
        self.assertEqual(margin_pixels(before), 0, "nothing in the margin before T")
        self.assertEqual(on.at("hero_dead"), 0, "the Snowman did not kill him")
        self.assertEqual(on.raw("hud_state", 1)[0], 3, "his power is still 3")
        self.assertGreater(margin_pixels(on), 40, "A1 and S16 are written left of the HUD")
        slot = next(on.rows[y][x] for y in range(8, 28) for x in range(32) if on.rows[y][x])
        self.assertEqual(on.palette[slot] & 0x777, 0x777, "in white")
        self.assertEqual(margin_pixels(off), 0, "T again takes the words away")
        self.assertEqual(off.raw("input_state", 396)[395], 0, "and the trainer is off")


if __name__ == "__main__":
    unittest.main()
