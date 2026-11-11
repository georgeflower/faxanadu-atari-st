"""The enemies stay on the screen when a box goes (`box_leave` in src/text.s sets `box_keep`, so `refresh_screens` draws them on both screens it makes again).

The ROM does not touch its sprites while the game stands for a message or a script (jsnes, `tools/refnes/boxsprites.mjs`: the OAM keeps every sprite through an item's message;
its player menu is different, it takes every sprite off, the hero's too, while it is up, and they are back three frames after it closes). Here the enemies were off the screen for
the frames a box took to go (about three), whatever the box; only the boxes of used-up items kept them (`use_spent`). Each test puts a Trunk Hornet on screen 12 (the Hour Glass
holds it still), opens a box, takes it away, and captures every VBL from before the box goes: the box, then at every VBL the plain screen with the Hornet's pixels (from a capture
before the box) and the hero, no VBL without it. The Mattock tests' scene runner and checks (`tests/test_mattock.py`) do the work."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_mattock as tm  # noqa: E402

K_TAB, K_P, K_ESC = 0x0F, 0x19, 0x01
HORNET = [(560, "w:hourglass", 3000), (560, "mem:enemies+182", 120), (560, "mem:enemies+184", 168)]
ARGS = ["ALL=1", "AREA=1", "SCREEN=12", "HERO=40,160,0,255,255,0,1", "WORLD=1", "HUD=80,80,0,0,0", "VIEWER_DEFS=--defsym JOYPAD=1"]
# (the disk's controls: there the B that takes a box away is no sword stroke afterwards (JOY_SETTLE); in the raw test mapping it is, and the swing would be in the pictures)


def key(at: int, scan: int, hold: int = 3) -> list:
    return [(at, "key", scan << 8 | 1), (at + hold, "key", scan << 8)]


def alternate(at: int) -> list:
    """B (Alternate) pressed and let go: it takes a message, the player menu and the Esc menu away."""
    return [(at, "b", 1), (at + 3, "b", 0)]


@unittest.skipUnless(tm.ROM.is_file() and tm.shutil.which("hatari") and tm.shutil.which("m68k-linux-gnu-as") and tm.shutil.which("ca65") and tm.tv.TOS.is_file(),
                     "needs the ROM, cc65, hatari, the m68k binutils and a TOS image (TOS or TOS_PAL)")
class BoxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import faxanadu_rom as fr

        cls.rom = fr.Rom(tm.ROM)

    run_multi = tm.MattockTests.run_multi                              # (the helpers, not the tests, of the Mattock's class)
    crumble = tm.MattockTests.crumble
    assert_sequence = tm.MattockTests.assert_sequence
    STATE = tm.MattockTests.STATE
    STAGES = tm.MattockTests.STAGES

    def keeps_the_hornet(self, args, pokes, name, first=612, last=630, changing=False):
        """`changing`: the box's own picture changes while it is up (a script's box: the arrow blinks, the portrait's eyes move), so a capture before the plain screen comes
        counts as the box when the box's place differs from the plain screen with the Hornet in most pixels."""
        sprites, stages, shots, _ = self.crumble(args, pokes + HORNET, 596, first, last, name, patches=[{}])
        self.assertGreater(len(sprites), 60, "the Hornet is drawn")
        if changing and 0 in stages:
            end = shots[stages.index(0)][0]
            for i in range(stages.index(0)):
                rows = shots[i][0]
                differ = sum(rows[y][x] != end[y][x] for y in range(40, 88) for x in range(112, 272))
                if stages[i] is None and differ > 2000:
                    stages[i] = "box"
        self.assert_sequence(stages, first, 1)

    def test_a_message_box_keeps_the_enemies_on_the_screen_when_it_goes(self) -> None:
        """A plain message box (`message_box`, the one of every item picked up and of a locked door's hint): the mantra's box, the test build's P key, dismissed with B."""
        self.keeps_the_hornet(ARGS, key(599, K_P) + alternate(615), "shots_box_message")

    def test_the_player_menu_keeps_the_enemies_on_the_screen_when_it_goes(self) -> None:
        """Tab opens the player menu, B closes it."""
        self.keeps_the_hornet(ARGS, key(599, K_TAB) + alternate(615), "shots_box_menu")

    def test_the_esc_menu_keeps_the_enemies_on_the_screen_when_it_goes(self) -> None:
        """Esc opens the Esc menu, B is Continue."""
        self.keeps_the_hornet(ARGS, key(599, K_ESC) + [(599, "mem:input_state+262", 255)] + alternate(615), "shots_box_esc")

    def test_a_persons_script_keeps_the_enemies_on_the_screen_when_it_goes(self) -> None:
        """The test build's man ($37, script 2: one message, with his portrait) where the hero stands; Up starts the script; B, once the message is written, ends it and the script's END takes the box away."""
        args = ARGS[:-1] + ["VIEWER_DEFS=--defsym JOYPAD=1 --defsym NPCS=1 --defsym NPC_EXTRA=0x37 --defsym NPC_EXTRA_X=40 --defsym NPC_EXTRA_Y=160 --defsym NPC_EXTRA_SCRIPT=2"]
        self.keeps_the_hornet(args, [(599, "joy", 1), (603, "joy", 0)] + alternate(900), "shots_box_person", first=890, last=920, changing=True)


if __name__ == "__main__":
    unittest.main()
