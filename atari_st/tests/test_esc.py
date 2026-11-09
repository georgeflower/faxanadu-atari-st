"""The Esc menu (src/save.s `esc_key`, `esc_menu`): Esc in the running game opens a box of three lines, Save, Continue and Exit to GEMDOS.

The game stands still while it is up; Continue (or Esc again, or B) closes it and the game goes on as it was (the screens are made again, IN_QUIT is cleared and the key waited
for); Save writes SAVE.SAV as the Guru's "Save to disk" does and comes back to the menu; Exit to GEMDOS leaves as Esc used to. The title, the intro and the ending keep Esc as
it was (they leave). Esc is the byte IN_QUIT, which the keyboard code sets: the tests write it (and the key's own flag, `key` pokes) through the debugger, as
tests/test_flow.py does. Needs the ROM, Hatari, the m68k binutils and a TOS image (TOS).
"""
from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"

import test_flow as tf  # noqa: E402  (the Run helper)
import test_save as ts  # noqa: E402  (the drive with a SAVE.SAV, the picture of a message box)
import test_viewer as tv  # noqa: E402  (the boxes of text)

import password_model as pm  # noqa: E402

NEEDS = ROM.is_file() and shutil.which("hatari") and shutil.which("m68k-linux-gnu-as") and shutil.which("ca65") and tv.TOS.is_file()
ESC, UP_KEY, DOWN_KEY, RETURN, TAB = 0x01, 0x48, 0x50, 0x1C, 0x0F
IN_QUIT = "b:input_state+262"


def key(vbl: int, scan: int, up: int = 4) -> list:
    return [(vbl, "key", scan << 8 | 1), (vbl + up, "key", scan << 8)]


def esc(vbl: int) -> list:
    """Esc pressed at `vbl`: the key's flag, the byte the keyboard code sets, and the key let go four frames later."""
    return [(vbl, "key", ESC << 8 | 1), (vbl, IN_QUIT, 255), (vbl + 4, "key", ESC << 8)]


@unittest.skipUnless(NEEDS, "needs the ROM, cc65, hatari, the m68k binutils and a TOS image (TOS or TOS_PAL)")
class EscMenuTests(unittest.TestCase):
    text_layer = staticmethod(tv.ViewerTests.text_layer)
    box_layer = staticmethod(tv.ViewerTests.box_layer)
    bright_slot = staticmethod(tv.ViewerTests.bright_slot)
    message_box = ts.SaveSceneTests.message_box
    ARGS = ["ALL=1", "AREA=0", "SCREEN=1", "HERO=40,144,0,255,0,0,1", "VIEWER_DEFS=--defsym FLOW=1 --defsym NO_ENEMIES=1"]
    LINES = ["Save", "Continue", "Exit to GEMDOS"]

    @classmethod
    def setUpClass(cls) -> None:
        import faxanadu_rom as fr

        cls.rom = fr.Rom(ROM)

    def menu_box(self, selected: int):
        """The box: groups 5 to 14, from line 88, 74 lines (20 and 18 a line); the line the cursor is on light on dark turned round."""
        import faxanadu_text as ft

        rows = [[0] * 320 for _ in range(200)]
        slot, font = self.bright_slot(self.rom, 0), ft.font(self.rom)
        self.box_layer(rows, slot, 5, 88, 10, 74)
        self.text_layer(rows, font, slot, [(104 + 8 * i, 96 + 18 * n, c, selected == n) for n, line in enumerate(self.LINES) for i, c in enumerate(line)])
        return [row[80:240] for row in rows[88:162]]

    @staticmethod
    def box_of(shot):
        return [row[80:240] for row in shot.rows[88:162]]

    def scene(self, pokes, captures, name, files=None, extra=None):
        with ts.drive(files, extra):
            return tf.Run(self.ARGS, pokes, captures, name)

    def test_esc_opens_the_menu_with_three_lines_and_the_game_stands_still(self) -> None:
        """He walks right (the stick is held all the time); Esc: the box with Save, Continue and Exit to GEMDOS, the cursor on Continue, and he does not move while it is up."""
        run = self.scene([(590, "joy", tf.RIGHT)] + esc(600), [595, 625, 665], "shots_esc_open")
        walking, menu, later = run.shots
        self.assertEqual(menu.raw("input_state", 263)[262], 0, "IN_QUIT is cleared: the menu is not the key being seen again")
        self.assertEqual(self.box_of(menu), self.menu_box(1), "the three lines, Continue on the cursor")
        self.assertGreater(menu.at("hero_x"), walking.at("hero_x"), "he was walking when Esc came")
        self.assertEqual((later.at("hero_x"), later.at("hero_y"), later.at("hero_tick")), (menu.at("hero_x"), menu.at("hero_y"), menu.at("hero_tick")), "frozen while it is up")
        self.assertEqual(self.box_of(later), self.menu_box(1), "and the box is still there")
        self.assertEqual(menu.raw("hud_state", 10), walking.raw("hud_state", 10))

    def test_continue_closes_the_menu_and_the_game_goes_on_with_the_same_picture(self) -> None:
        """Return on Continue: the screen is made again (the same picture, the same state), Esc does not come back, and he walks when the stick is pushed."""
        run = self.scene(esc(600) + key(640, RETURN) + [(700, "joy", tf.RIGHT)], [590, 625, 690, 740], "shots_esc_continue")
        before, menu, after, walked = run.shots
        self.assertEqual(self.box_of(menu), self.menu_box(1))
        self.assertEqual(after.rows, before.rows, "the picture as it was before Esc")
        self.assertEqual(after.palette, before.palette)
        self.assertEqual(tf.diag(after), tf.diag(before), "no state lost")
        self.assertEqual(after.raw("input_state", 263)[262], 0)
        self.assertGreater(walked.at("hero_x"), before.at("hero_x"), "the game runs")
        self.assertEqual(self.box_of(walked) == self.menu_box(1), False)

    def test_esc_again_closes_the_menu_and_the_key_is_waited_for(self) -> None:
        """A second Esc is Continue. While that key is still down (it goes up at 660) the box stays and the game does not run on; afterwards the menu does not open again."""
        run = self.scene(esc(600) + [(640, "key", ESC << 8 | 1), (640, IN_QUIT, 255), (660, "key", ESC << 8), (665, "joy", tf.RIGHT)], [650, 700, 750], "shots_esc_again")
        waiting, running, later = run.shots
        self.assertEqual(self.box_of(waiting), self.menu_box(1), "the key is still down: nothing has changed")
        self.assertNotEqual(self.box_of(running), self.menu_box(1))
        self.assertEqual(later.raw("input_state", 263)[262], 0)
        self.assertGreater(later.at("hero_x"), running.at("hero_x"), "the game goes on and the menu did not open again")

    def test_exit_to_gemdos_leaves_the_program(self) -> None:
        """Down, Return: the program ends as Esc used to end it (TOS's own screen on show at the second capture)."""
        run = self.scene(esc(600) + key(620, DOWN_KEY) + key(640, RETURN), [590, 650], "shots_esc_exit")
        before, gone = run.shots
        self.assertNotEqual(before.video, before.at("orig_screen", 0, 4, False))
        self.assertEqual(gone.video, gone.at("orig_screen", 0, 4, False), "TOS's own screen is on show again")

    def test_save_writes_save_sav_as_the_guru_does_and_comes_back_to_the_menu(self) -> None:
        """Up (to Save), Return: SAVE.SAV is the mantra of the state (and a line end), the box says "Game saved."; a button dismisses it and the menu is there again; Continue goes on."""
        pokes = [(580, "w:hero_title", 3), (580, "w:hero_next", 3)] + esc(600) + key(620, UP_KEY) + key(640, RETURN)
        run = self.scene(pokes, [660], "shots_esc_save")
        (saved_box,) = run.shots
        self.assertEqual([row[80:240] for row in saved_box.rows[107:125]], self.message_box("Game saved."), "the box that says so")
        data = ts.saved("shots_esc_save")
        self.assertIsNotNone(data, "SAVE.SAV is on the drive")
        self.assertEqual(data, saved_box.raw("pw_text", len(data) - 2) + b"\r\n", "the text pw_encode made from the state")
        state = pm.read_save(data)
        self.assertIsNotNone(state, "a file the loader takes")
        self.assertEqual(state.title, 3)
        self.assertEqual(saved_box.at("sv_status"), 0)
        pokes = esc(600) + key(620, UP_KEY) + key(640, RETURN) + [(670, "joy", tf.FIRE), (674, "joy", 0)] + key(730, RETURN) + [(750, "joy", tf.RIGHT)]
        run = self.scene(pokes, [720, 790], "shots_esc_save2")
        menu, going = run.shots
        self.assertEqual(self.box_of(menu), self.menu_box(1), "back at the menu, on Continue")
        self.assertIsNotNone(ts.saved("shots_esc_save2"))
        self.assertGreater(going.at("hero_x"), menu.at("hero_x"), "Continue: the game goes on")
        self.assertEqual(going.raw("input_state", 263)[262], 0)

    def test_a_write_protected_drive_says_so_and_writes_nothing(self) -> None:
        run = self.scene(esc(600) + key(620, UP_KEY) + key(640, RETURN), [660], "shots_esc_protected", extra=["--protect-hd", "on"])
        (shot,) = run.shots
        self.assertEqual([row[80:240] for row in shot.rows[107:125]], self.message_box("Could not save."))
        self.assertEqual(shot.at("sv_status"), -1)
        self.assertIsNone(ts.saved("shots_esc_protected"))

    def test_esc_in_the_player_menu_closes_it_and_opens_the_esc_menu(self) -> None:
        """Tab opens the player menu, which Esc closes (it always did); the Esc menu follows."""
        run = self.scene(key(600, TAB) + [(620, IN_QUIT, 255)], [610, 660], "shots_esc_player")
        player, menu = run.shots
        self.assertNotEqual(self.box_of(player), self.menu_box(1))
        self.assertEqual(self.box_of(menu), self.menu_box(1))

    def test_esc_on_the_title_still_leaves(self) -> None:
        """The title keeps Esc as it was: the program ends (the Esc menu is for the running game)."""
        args = ["ALL=1", "AREA=0", "SCREEN=1", "VIEWER_DEFS=--defsym NEWGAME=1 --defsym MENU=1 --defsym NPCS=1 --defsym TITLE=3 --defsym HERO_X=1"]
        run = tf.Run(args, [(480, IN_QUIT, 255)], [470, 700], "shots_esc_title")
        title, gone = run.shots
        self.assertNotEqual(title.video, title.at("orig_screen", 0, 4, False))
        self.assertEqual(gone.video, gone.at("orig_screen", 0, 4, False))


if __name__ == "__main__":
    unittest.main()
