"""The 68000 side of the title screen, the intro and the ending (src/splash68.s) in Hatari against the Python side (tools/splash.py, tools/splash_model.py).

The pictures must equal `splash.render_background` and `draw_sprites` of the pass the screen on show holds (the program records the pass of each of its two
screens: `sp_bufpass`; the video base says which one is on show, so a capture that falls in the middle of a pass is no problem); the palette must be the
base palette or the fade step of that pass (or the one before it: the palette follows the screen by a few cycles). The model's passes are the reference
(tests/test_splash.py checks them against jsnes). Needs the ROM, Hatari, the m68k binutils and a TOS image (TOS), like tests/test_viewer.py.
"""
from __future__ import annotations

import os
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
TOS = Path(os.environ.get("TOS") or os.environ.get("TOS_PAL") or "")

NEEDS = ROM.is_file() and shutil.which("hatari") and shutil.which("m68k-linux-gnu-as") and shutil.which("ca65") and TOS.is_file()

UP, DOWN, FIRE = 1, 2, 0x80


class Run:
    """One build and one Hatari run: pokes (joystick bytes) at given VBLs and RAM and screen captures at others."""

    def __init__(self, make_args: list[str], pokes: list[tuple[int, int]], captures: list[int], name: str):
        import hatari_shot as hs

        subprocess.run(["make", "-C", str(ROOT), "viewer", *make_args], check=True, capture_output=True)
        nm = subprocess.run(["m68k-linux-gnu-nm", str(ROOT / "build" / "viewer.elf")], check=True, capture_output=True, text=True).stdout.split("\n")
        self.sym = {line.split()[2]: int(line.split()[0], 16) for line in nm if len(line.split()) == 3}
        image = (ROOT / "build" / "viewer.bin").read_bytes()
        work = ROOT / "build" / name
        work.mkdir(parents=True, exist_ok=True)
        prg = ROOT / "build" / "VIEWER.PRG"
        hatari = shutil.which("hatari")
        (work / "c0.ini").write_text(f"savebin {work / 'ram0.bin'} 0 $80000\ncont\n", encoding="utf-8")
        hs.run_hatari(hatari, TOS, prg, work, 500, "0", f"b VBL > 499 :once :file {work / 'c0.ini'}\n", None)
        self.base = (work / "ram0.bin").read_bytes().find(image[self.sym["start"]:self.sym["start"] + 48]) - self.sym["start"]
        assert self.base > 0
        script = ""
        for i, (vbl, value) in enumerate(pokes):
            (work / f"poke{i}.ini").write_text(f"memwrite ${self.base + self.sym['input_state'] + 259:x} 0x{value:02x}\ncont\n", encoding="utf-8")
            script += f"b VBL > {vbl} :once :file {work / f'poke{i}.ini'}\n"
        for i, vbl in enumerate(captures):
            (work / f"cap{i}.ini").write_text(f"savebin {work / f'ram_{i}.bin'} 0 $80000\nm $ff8200-$ff8260\ncont\n", encoding="utf-8")
            script += f"b VBL > {vbl} :once :file {work / f'cap{i}.ini'}\n"
        log = hs.run_hatari(hatari, TOS, prg, work, max(captures) + 1, "0", script, None)
        chunks = re.split(r"(?m)^(?=00FF8200:)", log)[1:]
        assert len(chunks) == len(captures), "every capture's dump of the video registers is in the log"
        self.shots = []
        for i, chunk in enumerate(chunks):
            ram = (work / f"ram_{i}.bin").read_bytes()
            base = hs.video_base(chunk)
            self.shots.append(Shot(self, ram, hs.decode_screen(ram, base), base, hs.read_palette(chunk)))


class Shot:
    def __init__(self, run: Run, ram: bytes, rows: list[list[int]], video: int, palette: list[int]):
        self.run, self.ram, self.rows, self.video, self.palette = run, ram, rows, video, palette

    def at(self, name: str, offset: int = 0, size: int = 2, signed: bool = True) -> int:
        a = self.run.base + self.run.sym[name] + offset
        return int.from_bytes(self.ram[a:a + size], "big", signed=signed)

    def long(self, name: str, offset: int = 0) -> int:
        return self.at(name, offset, 4, False)

    @property
    def pass_shown(self) -> int:
        """The pass the screen on show holds (-1: it holds none)."""
        index = 0 if self.video == self.long("buf_a") else 1
        assert self.video == self.long("buf_a" if index == 0 else "buf_b"), "the screen on show is one of the two"
        return self.at("sp_bufpass", 2 * index)


def mismatch(rows, expected) -> list:
    return [(x, y) for y in range(200) for x in range(320) if rows[y][x] != expected[y][x]][:6]


def words(b: bytes) -> list[int]:
    return [int.from_bytes(b[i:i + 2], "big") for i in range(0, len(b), 2)]


@unittest.skipUnless(NEEDS, "needs the ROM, cc65, hatari, the m68k binutils and a TOS image (TOS)")
class SplashTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import test_splash as ts
        import test_viewer as tv

        cls.ts = ts
        cls.vt = tv.ViewerTests("test_eolis_screen_1_at_the_bottom_of_the_playfield")     # (its helpers: the boxes of text)
        import faxanadu_rom as fr
        cls.rom = fr.Rom(ROM)

    # ------------------------------------------------------------------------------------------------------ the pictures
    def scene(self, name: str):
        import splash

        parts, wd = self.ts.unpacked(name)
        return parts, wd, splash.render_background(parts, wd)

    def scene_picture(self, name: str, drawn: list) -> list[list[int]]:
        import splash

        parts, wd, bg = self.scene(name)
        images = [parts["images"][40 * i:40 * i + 40] for i in range(wd["image_count"])]
        screen = [row[:] for row in bg]
        triples = [t for frame, x, y in drawn for t in splash.pose_triples(parts["poses"], frame, x, y)]
        splash.draw_sprites(screen, triples[::-1], images)
        return screen

    def title_picture(self, cursor: int) -> tuple[list[list[int]], list[int]]:
        import splash

        parts, wd = self.ts.unpacked("TITLE")
        screen = splash.render_background(parts, wd)
        x, y = (int.from_bytes(parts["cursor"][4 * cursor + 2 * i:][:2], "big") for i in (0, 1))
        splash.draw_sprites(screen, [(x, y, 0)], [parts["arrow"][:40]])
        return screen, words(parts["palette"])

    def check_title(self, shot: Shot, cursor: int) -> None:
        screen, palette = self.title_picture(cursor)
        self.assertEqual((shot.at("sp_phase"), shot.at("sp_cursor")), (1, cursor))
        self.assertEqual(mismatch(shot.rows, screen), [], f"the title, the cursor at {cursor}")
        self.assertEqual(shot.palette, palette)

    def intro_states(self):
        import splash_model as sm

        m = sm.Intro(sm.Data(self.ts.rom()))
        out = {}
        for k in range(1, 660):
            m.tick()
            out[k] = (list(m.drawn), m.fades)
        return out

    def check_intro(self, shot: Shot, states: dict) -> int:
        k = shot.pass_shown
        self.assertIn(k, states, "a pass of the intro is on show")
        parts, wd = self.ts.unpacked("INTRO")
        self.assertEqual(shot.at("sp_phase"), 2)
        self.assertEqual(mismatch(shot.rows, self.scene_picture("INTRO", states[k][0])), [], f"pass {k}")
        steps = (states[k - 1][1] if k > 1 else 0, states[k][1])
        palettes = [words(parts["palette"])] + [words(parts["fade"][32 * i:32 * i + 32]) for i in range(4)]
        self.assertIn(shot.palette, [palettes[s] for s in steps], f"pass {k}: the palette of fade step {steps}")
        return states[k][1]

    # ------------------------------------------------------------------------------------------------------ tests
    def test_the_title_the_cursor_and_the_flow_to_the_intro_and_the_game(self) -> None:
        """The disk's build (MENU=1 SPLASH=1): the title equals the Python picture with the arrow at START; down moves it to CONTINUE (sound $0B), up back,
        Select... (Tab is the same key as on the NES); fire starts the intro, whose pass 1.. pictures equal the model's; when the 659 passes are over the
        game is there: Eolis with the HUD and the hero, as after the plain menu's Start."""
        import st_convert as sc

        states = self.intro_states()
        run = Run(["VIEWER_DEFS=--defsym SPLASH=1 --defsym MENU=1"],
                  [(360, DOWN), (364, 0), (420, UP), (424, 0), (480, FIRE), (484, 0)],
                  [340, 400, 460, 540, 700, 1000, 1500, 1800], "shots_splash_flow")
        title, down, up, early, mid, late, game_early, game = run.shots
        self.check_title(title, 0)
        self.check_title(down, 1)
        self.check_title(up, 0)
        passes = []
        for shot in (early, mid, late):
            self.check_intro(shot, states)
            passes.append(shot.pass_shown)
        self.assertEqual(passes, sorted(passes))
        self.assertLess(passes[0], 100)
        self.assertGreater(passes[2], 400, "(the intro is on its way)")
        for shot in (game_early, game):
            self.assertEqual(shot.at("sp_phase"), 2)
            expected = sc.expected_screen(self.rom, 0, 1, shot.at("camera"), hero=sc.Hero(144, 144, 0, 255, 0, 0, True))
            self.assertEqual(mismatch(shot.rows, expected), [], "the game after the intro")
        self.assertEqual(game.palette, game_early.palette)

    def test_start_cuts_the_title_song_and_the_intro_plays_four_or_five_frames_of_song_8_before_it_sets_0(self) -> None:
        """The ROM's Start press sets Music_Current to 8 and the intro's first passes set it to 0 five frames later (jsnes: song 8's first note is heard for four frames,
        then silence: tools/refnes/musicprobe.mjs); the intro plays no song. Every VBL from the end of the intro's loading is captured: the title's song stops, song 8 is
        in the player for 3 to 6 VBLs in a row (SND_MLEFT of its record, over 2600), and then it is silent for good."""
        caps = list(range(484, 520))
        run = Run(["VIEWER_DEFS=--defsym SPLASH=1 --defsym MENU=1"], [(480, FIRE), (484, 0)], caps, "shots_splash_blip")
        left = [shot.at("snd_state", 16) for shot in run.shots]
        title_off = next(i for i, shot in enumerate(run.shots) if shot.at("sp_phase") == 2)
        song8 = [i for i, n in enumerate(left) if i > title_off and n > 2600]
        self.assertTrue(3 <= len(song8) <= 6, f"song 8 for 3 to 6 VBLs: {left}")
        self.assertEqual(song8, list(range(song8[0], song8[0] + len(song8))), "in a row")
        self.assertEqual(left[song8[-1] + 1:], [0] * (len(left) - song8[-1] - 1), "and silent afterwards")
        self.assertEqual([left[i] for i in range(title_off, song8[0])], [0] * (song8[0] - title_off), "the title's song is cut when the intro starts")

    def test_continue_goes_to_the_entry_of_a_mantra_and_end_with_nothing_written_goes_back_to_the_title(self) -> None:
        """Down and fire on the title: the mantra's entry on the game's picture (the plain menu's entry; hero and HUD are on it); END with nothing written
        gives up and the title is there again, the arrow at START."""
        import st_convert as sc

        moves, last = self.vt.typing("", 660, end=True)
        pokes = [(360, DOWN), (364, 0), (420, FIRE), (424, 0)] + [(vbl, value) for vbl, _, value in moves]
        run = Run(["VIEWER_DEFS=--defsym SPLASH=1 --defsym MENU=1"], pokes, [340, 650, last + 200], "shots_splash_continue")
        title, entry, again = run.shots
        self.check_title(title, 0)
        expected = sc.expected_screen(self.rom, 0, 1, entry.at("camera"), hero=sc.Hero(144, 144, 0, 255, 0, 0, True))
        self.vt.entry_box(expected, self.rom, 0, "", 0)
        self.assertEqual(mismatch(entry.rows, expected), [], "the entry on the game's picture")
        self.assertEqual(entry.at("sp_phase"), 1, "(the title's phase: the entry came from it)")
        self.check_title(again, 0)

    def test_the_intro_equals_the_model_pass_for_pass_in_the_pictures_and_the_fade(self) -> None:
        """INTRO=1: captures at passes spread over the walk and at every fade step. The sound effect of a footstep is $15 14 times (the model's passes)."""
        states = self.intro_states()
        # (pass p is on show at about VBL p+225: the start-up unpacks TOWN.DAT first, 9 VBLs, and the hero's data, 4; the fade steps come at passes 635, 643, 651 and 659, the last pass is on show for one VBL only)
        caps = [313, 343, 433, 533, 653, 773, 830, 864, 872, 880]
        run = Run(["VIEWER_DEFS=--defsym INTRO=1"], [], caps, "shots_splash_intro")
        steps = set()
        for vbl, shot in zip(caps, run.shots):
            with self.subTest(vbl=vbl, pass_shown=shot.pass_shown):
                steps.add(self.check_intro(shot, states))
        self.assertEqual(steps, {0, 1, 2, 3}, "the pictures were checked before the fade and at its first three steps")
        last = run.shots[-1]
        self.assertLessEqual(last.long("late_frames") - last.long("sp_late0"), 15, "a pass is one VBL: a few late ones at most")

    def test_the_ending_equals_the_model_and_ends_with_the_title(self) -> None:
        """ENDING=1: the hero's walk, the sparkles and the waterfall at several passes (loop 1, loop 2 until song 12 has ended, loop 3), and afterwards the title.
        The pass loop 3 began at (`sp_st+24`) is the one the song's end gave."""
        import splash_model as sm

        caps = [300, 500, 800, 1000, 1300, 2000, 2560, 2640, 2740, 3500]
        run = Run(["VIEWER_DEFS=--defsym ENDING=1"], [], caps, "shots_splash_ending")
        last = run.shots[-1]
        l3 = last.at("sp_st", 24)
        self.assertGreater(l3, 2200, "loop 3 began when the song ended (about 2310 passes)")
        self.assertLess(l3, 2331)
        self.assertEqual(last.at("sp_phase"), 1, "back at the title")
        self.check_title(last, 0)
        m = sm.Outro(sm.Data(self.ts.rom()), l3)
        drawn = {}
        loops = {}
        while not m.done:
            loop = m.loop
            m.tick()
            drawn[m.n] = list(m.drawn)
            loops[m.n] = loop
        self.assertEqual(max(drawn) - l3, 240)
        seen = set()
        for shot in run.shots[:-1]:
            k = shot.pass_shown
            self.assertEqual(shot.at("sp_phase"), 3)
            self.assertIn(k, drawn)
            self.assertEqual(mismatch(shot.rows, self.scene_picture("OUTRO", drawn[k])), [], f"pass {k}")
            self.assertEqual(shot.palette, words(self.ts.unpacked("OUTRO")[0]["palette"]))
            seen.add(loops[k])
        self.assertEqual(seen, {1, 2, 3}, "all three loops were compared")
        self.assertLessEqual(last.long("late_frames") - last.long("sp_late0"), 40)


if __name__ == "__main__":
    unittest.main()
