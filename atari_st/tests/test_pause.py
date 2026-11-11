"""The Start pause (`pause_key` in src/save.s, `sound_pause` in src/sound.s): the ROM's GameLoop_CheckPauseGame and Audio_HandlePaused.

What the ROM does (`tools/refnes/pauseprobe.mjs`, jsnes): Start, newly pressed in the main loop, stops everything after that frame's work until Start is newly pressed again;
the hero and the sprites stand, the picture stays. The sound engine keeps the song where it is and resets the channels (silence), but a sound effect that runs goes
on to its end. After the pause the song goes on from where it stood, and its channels stay silent until the song writes them again. There is no pause while he
dies or during a scroll (both are loops of their own in the ROM). Return is Start on the ST. Needs the ROM, Hatari, the m68k binutils and a TOS image (TOS).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"

import test_flow as tf  # noqa: E402  (the Run helper)
import test_viewer as tv  # noqa: E402

NEEDS = ROM.is_file() and shutil.which("hatari") and shutil.which("m68k-linux-gnu-as") and shutil.which("ca65") and tv.TOS.is_file()
NODE = shutil.which("node") and (ROOT / "tools" / "refnes" / "node_modules").is_dir()
RETURN, ESC = 0x1C, 0x01
IN_QUIT = "b:input_state+262"
SND_MPTR, SND_SLEFT, SND_PEND, SND_PAUSED, SND_MUTE = 4, 20, 52, 56, 57


def key(vbl: int, scan: int, up: int = 4) -> list:
    return [(vbl, "key", scan << 8 | 1), (vbl + up, "key", scan << 8)]


def snd(shot, offset: int, size: int = 1) -> int:
    return int.from_bytes(shot.raw("snd_state", offset + size)[offset:offset + size], "big")


@unittest.skipUnless(NEEDS, "needs the ROM, cc65, hatari, the m68k binutils and a TOS image (TOS or TOS_PAL)")
class PauseTests(unittest.TestCase):
    ARGS = ["ALL=1", "AREA=0", "SCREEN=4", "HERO=40,144,0,255,0,0,1", "HUD=80,80,0,0,0", "VIEWER_DEFS=--defsym FLOW=1"]

    def check_pause(self, args, name) -> None:
        """He walks right; a sound effect ($08) is asked for, then Return: everything stands (hero, enemies, the song's place), the song's channels are silent, the
        effect goes on; Return again: he walks on."""
        pokes = [(590, "joy", tf.RIGHT), (597, f"w:snd_state+{SND_PEND}", 8)] + key(600, RETURN) + key(700, RETURN)
        run = tf.Run(args, pokes, [596, 606, 612, 660, 698, 730], name)
        walking, p1, p2, p3, p4, after = run.shots
        self.assertEqual(snd(walking, SND_PAUSED), 0)
        for s in (p1, p2, p3, p4):
            self.assertEqual(s.raw("pause_on", 1)[0], 0xFF, "paused")
            self.assertEqual(snd(s, SND_PAUSED), 1)
            self.assertEqual((s.at("hero_x"), s.at("hero_y"), s.at("hero_tick")), (p1.at("hero_x"), p1.at("hero_y"), p1.at("hero_tick")), "he stands")
            self.assertEqual(s.raw("enemies", 240), p1.raw("enemies", 240), "the enemies stand")
            self.assertEqual(snd(s, SND_MPTR, 4), snd(p1, SND_MPTR, 4), "the song stands where it is")
            self.assertEqual(s.rows, p1.rows, "the picture stays")
        self.assertGreater(p1.at("hero_x"), walking.at("hero_x"), "he walked until the pause")
        self.assertGreater(snd(p1, SND_SLEFT, 2), snd(p2, SND_SLEFT, 2), "the sound effect goes on during the pause")
        self.assertGreater(snd(p2, SND_SLEFT, 2), 0)
        self.assertEqual(snd(p3, SND_MUTE), 7, "the song's channels are silent")
        self.assertEqual(snd(after, SND_PAUSED), 0)
        self.assertEqual(after.raw("pause_on", 1)[0], 0)
        self.assertGreater(after.at("hero_x"), p4.at("hero_x"), "Return again: the game goes on")
        self.assertNotEqual(snd(after, SND_MPTR, 4), snd(p4, SND_MPTR, 4), "and the song")

    def test_return_pauses_and_return_again_goes_on(self) -> None:
        self.check_pause(self.ARGS, "shots_pause")

    def test_the_disks_controls_pause_with_return_too(self) -> None:
        args = self.ARGS[:-1] + ["VIEWER_DEFS=--defsym FLOW=1 --defsym JOYPAD=1"]
        self.check_pause(args, "shots_pause_joy")

    def test_esc_in_the_pause_opens_the_esc_menu_and_continue_goes_on_unpaused(self) -> None:
        pokes = [(590, "joy", tf.RIGHT)] + key(600, RETURN) + [(640, "key", ESC << 8 | 1), (640, IN_QUIT, 255), (644, "key", ESC << 8)] + key(680, RETURN)
        run = tf.Run(self.ARGS, pokes, [630, 670, 730], "shots_pause_esc")
        paused, menu, after = run.shots
        self.assertEqual(paused.raw("pause_on", 1)[0], 0xFF)
        self.assertEqual(menu.raw("pause_on", 1)[0], 0, "Esc ends the pause")
        self.assertEqual(snd(menu, SND_PAUSED), 0)
        self.assertEqual(menu.at("hero_x"), paused.at("hero_x"), "the Esc menu is up: he still stands")
        self.assertGreater(after.at("hero_x"), menu.at("hero_x"), "Continue: the game goes on, not paused")
        self.assertEqual(after.raw("pause_on", 1)[0], 0)

    def test_no_pause_while_he_dies(self) -> None:
        """Power 1 and the H key's hit: the death runs; Return during it does nothing."""
        args = ["ALL=1", "AREA=0", "SCREEN=1", "HERO=40,144,0,255,0,0,1", "HUD=1,0,0,0,0", "VIEWER_DEFS=--defsym FLOW=1 --defsym NO_ENEMIES=1"]
        pokes = key(600, 0x23) + key(620, RETURN)
        run = tf.Run(args, pokes, [640], "shots_pause_dead")
        self.assertNotEqual(run.shots[0].at("hero_dead"), 0)
        self.assertEqual(run.shots[0].raw("pause_on", 1)[0], 0)


@unittest.skipUnless(NODE and ROM.is_file(), "needs node, the harness's node_modules and the ROM")
class PauseInTheRomTests(unittest.TestCase):
    def test_the_rom_freezes_the_game_silences_the_song_and_lets_an_effect_finish(self) -> None:
        out = subprocess.run(["node", "pauseprobe.mjs", "8"], cwd=ROOT / "tools" / "refnes", check=True, capture_output=True, text=True, timeout=300).stdout
        rows = json.loads(next(line for line in out.split("\n") if line.startswith("RESULT "))[7:])
        paused = [r for r in rows if 1 <= r[0] < 100]
        self.assertTrue(all(r[1] & 1 for r in paused), "Game_PausedState is set from the press to the second press")
        self.assertEqual({r[2] for r in paused}, {rows[0][2]}, "the hero stands")
        effect = [r[3][1][1] for r in paused]                   # pulse 2: the effect $08 goes on and fades
        self.assertGreater(effect[0], 0)
        self.assertTrue(all(r[3][0] == [0, 0] and r[3][2] == 0 for r in paused), "the song's channels are silent")
        self.assertEqual({r[4] for r in rows}, {rows[0][4]}, "the same song throughout (it is not started again)")
        self.assertGreater(rows[101][2], rows[99][2], "after the second press he walks on at once")


if __name__ == "__main__":
    unittest.main()
