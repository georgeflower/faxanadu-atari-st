"""The viewer (src/viewer.s) on the ST in Hatari draws the screen the converter says it should, pixel for pixel.

Needs the ROM (ext/Faxanadu_Europe.nes), cc65-free (the converter only needs Python), Hatari, the m68k binutils and a TOS image (TOS or TOS_PAL).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"


def ft_message(rom, number):
    import faxanadu_text as ft

    return ft.message(rom, number)
TOS = Path(os.environ.get("TOS") or os.environ.get("TOS_PAL") or "")


@unittest.skipUnless(ROM.is_file() and shutil.which("hatari") and shutil.which("m68k-linux-gnu-as") and shutil.which("ca65") and TOS.is_file(),
                     "needs the ROM, cc65, hatari, the m68k binutils and a TOS image (TOS or TOS_PAL)")
class ViewerTests(unittest.TestCase):
    def run_viewer(self, area: int, screen: int, camera: int, hero: str, hud: str, hud2: str) -> bytes:
        subprocess.run(["make", "-C", str(ROOT), "viewer", f"AREA={area}", f"SCREEN={screen}", f"CAMERA={camera}", f"HERO={hero}", f"HUD={hud}", f"HUD2={hud2}",
                        "VIEWER_DEFS=--defsym NO_PHYSICS=1"], check=True,
                       capture_output=True)
        rows = ROOT / "build" / "viewer_test.rows"
        subprocess.run([sys.executable, str(ROOT / "tools" / "hatari_shot.py"), "--tos", str(TOS), "--prg", str(ROOT / "build" / "VIEWER.PRG"),
                        "--out", str(ROOT / "build" / "viewer_test.png"), "--rows", str(rows)], check=True, capture_output=True, timeout=600)
        return rows.read_bytes()

    def check(self, area: int, screen: int, camera: int, hero: str = "144,144,0,255,0,0,1", hud: str = "16,0,0,0,0", hud2: str = "") -> None:
        import faxanadu_rom as fr
        import st_convert as sc

        got = self.run_viewer(area, screen, camera, hero, hud, hud2)
        keys = ('hp', 'mp', 'experience', 'gold', 'seconds')
        state = dict(zip(keys, (int(v) for v in (hud2 or hud).split(','))))
        expected = sc.expected_screen(fr.Rom(ROM), area, screen, camera, state=state, hero=sc.Hero(*[bool(v) if i == 6 else v for i, v in enumerate(int(t) for t in hero.split(','))]))
        bad = [(x, y) for y in range(200) for x in range(320) if got[y * 320 + x] != expected[y][x]]
        self.assertEqual(bad[:5], [], f"{len(bad)} pixels differ")

    def test_eolis_screen_1_at_the_bottom_of_the_playfield(self) -> None:
        self.check(0, 1, 40)

    def test_eolis_screen_8_from_the_top(self) -> None:
        self.check(0, 8, 0)

    def test_a_trunk_screen_part_way_down(self) -> None:
        self.check(1, 5, 17)

    def test_the_hero_in_other_equipment_and_at_every_pixel_phase_of_a_group(self) -> None:
        for x in (100, 101, 109, 117, 123):
            with self.subTest(x=x):
                self.check(0, 1, 40, f"{x},144,2,2,3,1,0")

    def test_the_hero_is_cut_under_the_hud_and_at_the_bottom_of_the_screen(self) -> None:
        self.check(0, 1, 40, "144,20,1,1,1,0,1")
        self.check(0, 1, 0, "144,170,3,3,3,0,0")

    def test_the_hud_is_drawn_from_its_state_and_updates_clear_what_was_there(self) -> None:
        states = ["16,0,0,0,0", "80,80,65535,16777215,99", "35,13,4242,1234567,7", "7,1,10000,100000,10", "0,79,9,655360,60", "81,200,1,1,5"]
        for first, second in zip(states, states[1:] + states[:1]):
            with self.subTest(first=first, second=second):
                self.check(0, 1, 40, hud=first, hud2=second)

    def test_the_hero_walks_when_the_stick_is_pushed_and_leaves_no_trail(self) -> None:
        """Hold the stick right (poked into the program's input state through Hatari's debugger) from VBL 600 to 640, let go, and
        capture at 700: he stands facing right (the sprite flip bit set) where the ROM's walking puts him after about 40 frames (acceleration from $C0), in the first walk frame, and the rest of the picture is clean."""
        import faxanadu_rom as fr
        import hatari_shot as hs
        import st_convert as sc

        subprocess.run(["make", "-C", str(ROOT), "viewer"], check=True, capture_output=True)
        nm = subprocess.run(["m68k-linux-gnu-nm", str(ROOT / "build" / "viewer.elf")], check=True, capture_output=True, text=True).stdout.split("\n")
        sym = {line.split()[2]: int(line.split()[0], 16) for line in nm if len(line.split()) == 3}
        image = (ROOT / "build" / "viewer.bin").read_bytes()
        work = ROOT / "build" / "shots_move"
        work.mkdir(parents=True, exist_ok=True)
        prg = ROOT / "build" / "VIEWER.PRG"
        hatari = shutil.which("hatari")
        (work / "c0.ini").write_text(f"savebin {work / 'ram0.bin'} 0 $80000\ncont\n", encoding="utf-8")
        hs.run_hatari(hatari, TOS, prg, work, 500, "0", f"b VBL > 499 :once :file {work / 'c0.ini'}\n", None)
        ram = (work / "ram0.bin").read_bytes()
        base = ram.find(image[sym["start"]:sym["start"] + 48]) - sym["start"]
        self.assertGreater(base, 0)
        joy = base + sym["input_state"] + 259                # IN_JOY: bits 0-3 up, down, left, right
        (work / "right.ini").write_text(f"memwrite ${joy:x} 0x08\ncont\n", encoding="utf-8")
        (work / "stop.ini").write_text(f"memwrite ${joy:x} 0x00\ncont\n", encoding="utf-8")
        (work / "cap.ini").write_text(f"savebin {work / 'ram1.bin'} 0 $80000\n" "m $ff8200-$ff8260\ncont\n", encoding="utf-8")
        script = "".join(f"b VBL > {v} :once :file {work / f}\n" for v, f in ((599, "right.ini"), (639, "stop.ini"), (699, "cap.ini")))
        log = hs.run_hatari(hatari, TOS, prg, work, 700, "0", script, None)
        ram = (work / "ram1.bin").read_bytes()
        rows = hs.decode_screen(ram, hs.video_base(log))
        word = lambda name: int.from_bytes(ram[base + sym[name]:base + sym[name] + 2], "big")
        x, frac = word("hero_x"), word("hero_frac")
        import hero_physics as hp
        h = hp.Hero(x=144, y=144)
        free = [0] * 208
        reached = []
        for _ in range(45):
            hp.walk_step(h, hp.JOY_RIGHT, free)
            reached.append((h.x, h.frac))
        self.assertIn((x, frac), reached[36:44], f"x {x} frac {frac}: not what the ROM's walking gives after about 40 frames")
        self.assertEqual(word("hero_flip"), 1)
        expected = sc.expected_screen(fr.Rom(ROM), 0, 1, 40, hero=sc.Hero(x, 144, 0, 255, 0, 0, True))
        bad = [(x, y) for y in range(200) for x in range(320) if rows[y][x] != expected[y][x]]
        self.assertEqual(bad[:5], [], f"{len(bad)} pixels differ")

    def test_the_walking_acceleration_steps_by_the_rank_group(self) -> None:
        """PlayerTitle 12 (rank group 3, Champion and up): the acceleration grows by 8 a frame instead of 2, as `hero_physics` (and the ROM)
        has it, so after 20 frames of walking he is much further than a novice."""
        import hero_physics as hp

        reached = {}
        for title in (0, 12):
            ram, word, _ = self.run_scenario(["VIEWER_DEFS=--defsym TITLE=%d" % title], [(599, "joy", 8), (618, "joy", 0)], 699, "shots_rank")
            h = hp.Hero(x=144, y=144, title=title)
            free = [0] * 208
            seen = []
            for _ in range(24):
                hp.walk_step(h, hp.JOY_RIGHT, free)
                seen.append((h.x, h.frac))
            self.assertIn((word("hero_x"), word("hero_frac")), seen[16:24], f"title {title}")
            reached[title] = word("hero_x")
        self.assertGreater(reached[12], reached[0])

    def test_a_wall_in_the_next_screens_edge_column_stops_him_at_the_edge(self) -> None:
        """Trunk screen 27 (rows 10-11 are open at both edges and the next screens, 62 on the right and 26 on the left, have a wall in their
        edge column at those rows): he walks to the edge and stays on the screen (x 240 on the right, 0 on the left) as in the ROM
        (`FirstColumnInRightScreen`, `LastColumnLeftScreen`) instead of scrolling."""
        make = ["ALL=1", "AREA=1", "SCREEN=27"]
        _, word, _ = self.run_scenario(make + ["HERO=200,160,0,255,0,0,1"], [(599, "joy", 8)], 799, "shots_edge_wall")
        self.assertEqual((word("cur_screen"), word("hero_x")), (27, 240))
        _, word, _ = self.run_scenario(make + ["HERO=40,160,0,255,0,0,1"], [(599, "joy", 4)], 799, "shots_edge_wall")
        self.assertEqual((word("cur_screen"), word("hero_x")), (27, 0))

    def test_a_jump_goes_on_after_the_scroll_to_the_next_screen(self) -> None:
        """He walks three frames and jumps right off the edge of Eolis screen 1 (`tools/refnes/airscroll.mjs`): the ROM scrolls in the middle of the
        jump and the jump stays where it was (curve index 18, y 112 for the whole scroll) and goes on when the screen has changed. Left: index 25, y 116."""
        for start, stick, jump, y in ((224, 0x08, 18, 112), (24, 0x04, 25, 116)):
            ram, word, _ = self.run_scenario(["ALL=1", "AREA=0", "SCREEN=1", f"HERO={start},144,0,255,0,0,1"],
                                             [(599, "joy", stick), (602, "space", 1), (603, "space", 0)], 650, "shots_air_scroll")
            self.assertEqual((word("hero_jump"), word("hero_y")), (jump, y), f"stick {stick}: the jump is frozen during the scroll")
        ram, word, _ = self.run_scenario(["ALL=1", "AREA=0", "SCREEN=1", "HERO=224,144,0,255,0,0,1"],
                                         [(599, "joy", 0x08), (602, "space", 1), (603, "space", 0), (900, "joy", 0)], 1000, "shots_air_scroll")
        self.assertEqual((word("cur_screen"), word("hero_y")), (8, 144), "on the next screen, landed")

    def test_wing_boots_fly_up_and_down_glide_and_steer_in_the_air(self) -> None:
        """With the boots on (WINGS=40 seconds) and A held (`tools/hero_physics.py` against the ROM in jsnes): up flies a pixel a frame, down a pixel
        and a half, with A alone he glides down a pixel a frame (8 without A) and steers left and right in the air; he is in the pose of the jump.
        Frames are counted with `wings_clock`, which counts the hero's steps."""
        args = ["ALL=1", "AREA=0", "SCREEN=1", "HERO=16,144,0,255,0,0,1", "VIEWER_DEFS=--defsym WINGS=40"]

        def span(pokes, stick):
            """(frames, dy, dx) from 1 VBL after the pokes to 40 VBLs after, the hero put at x 16 by the pokes."""
            first = self.run_scenario(args, pokes, 600, "shots_wings")
            last = self.run_scenario(args, pokes, 640, "shots_wings")
            return (last[1]("wings_clock") - first[1]("wings_clock"), last[1]("hero_y") - first[1]("hero_y"), last[1]("hero_x") - first[1]("hero_x"), last[1])

        frames, dy, _, word = span([(599, "joy", 1), (599, "space", 1)], 1)
        self.assertGreater(frames, 20)
        self.assertEqual(dy, -frames, "up with A: a pixel a frame")
        self.assertEqual(word("hero_frame"), 3, "the pose in the air")
        frames, dy, _, _ = span([(599, "y", 16), (599, "joy", 2), (599, "space", 1)], 2)
        self.assertIn(dy, (frames + frames // 2, frames + (frames + 1) // 2), "down with A: a pixel and a half a frame")
        frames, dy, _, _ = span([(599, "y", 16), (599, "space", 1)], 0)
        self.assertEqual(dy, frames, "A alone: gliding down a pixel a frame")
        frames, dy, dx, _ = span([(599, "y", 16), (599, "joy", 8), (599, "space", 1)], 8)
        self.assertEqual(dy, frames)
        self.assertGreater(dx, 20, "walking right in the air")
        frames, dy, dx, _ = span([(599, "y", 16), (599, "joy", 4), (599, "space", 1)], 4)
        self.assertEqual(dy, frames)
        self.assertLess(dx, -10, "and left (the hero stands at x 16: he stops at the edge of the screen)")
        _, dy, _, _ = span([(599, "y", 16)], 0)
        self.assertGreater(dy, 60, "without A he falls 8 pixels a frame")

    def test_the_w_key_puts_the_wing_boots_on_for_the_ranks_time_and_they_run_out(self) -> None:
        """No boots at the start; W gives the rank's time (title 0: 40 seconds, title 12: 10) and a second is 64 frames."""
        _, word, _ = self.run_scenario(["ALL=1", "AREA=0", "SCREEN=1"], [], 650, "shots_wings_key")
        self.assertEqual(word("hero_wings"), -1)
        _, word, _ = self.run_scenario(["ALL=1", "AREA=0", "SCREEN=1"], [(599, "w", 1)], 650, "shots_wings_key")
        self.assertIn(word("hero_wings"), (40, 39), "(the ROM too counts the second from the global frame counter)")
        _, word, _ = self.run_scenario(["ALL=1", "AREA=0", "SCREEN=1", "VIEWER_DEFS=--defsym TITLE=12"], [(599, "w", 1)], 650, "shots_wings_key")
        self.assertIn(word("hero_wings"), (10, 9))
        _, word, _ = self.run_scenario(["ALL=1", "AREA=0", "SCREEN=1", "VIEWER_DEFS=--defsym TITLE=12"], [(599, "w", 1)], 800, "shots_wings_key")
        self.assertIn(word("hero_wings"), (7, 6), "a second every 64 frames: 200 frames are 3 or 4 of them")

    def test_a_hit_knocks_him_back_and_takes_power_and_he_is_invincible_for_60_frames(self) -> None:
        """The H key (debug: something hits him from the right) as `tools/hero_physics.hit` does it, checked there against the ROM in jsnes: he
        turns to the enemy, goes 8 pixels a frame to the left for three frames (24 pixels), loses DAMAGE power and cannot be hurt again for 60 frames."""
        args = ["ALL=1", "AREA=0", "SCREEN=1", "HERO=128,144,0,255,0,0,1", "VIEWER_DEFS=--defsym DAMAGE=8"]
        _, base_word, _ = self.run_scenario(args, [], 700, "shots_hit")
        power = base_word("hud_state") >> 8
        ram, word, _ = self.run_scenario(args, [(599, "h", 1), (600, "h", 0)], 700, "shots_hit")
        self.assertEqual(word("hero_x"), 128 - 24)
        self.assertEqual(word("hero_flip"), 1, "he faces the enemy")
        self.assertEqual(word("hud_state") >> 8, power - 8)
        self.assertEqual((word("hero_invinc"), word("hero_knock")), (0, 0))
        ram, word, _ = self.run_scenario(args, [(599, "h", 1), (600, "h", 0), (610, "h", 1), (611, "h", 0)], 700, "shots_hit")
        self.assertEqual(word("hud_state") >> 8, power - 8, "the second hit 10 frames later does nothing: he is invincible")
        self.assertEqual(word("hero_x"), 128 - 24)
        ram, word, _ = self.run_scenario(args, [(599, "g", 1), (600, "g", 0)], 700, "shots_hit")
        self.assertEqual((word("hero_x"), word("hero_flip")), (128 + 24, 0), "hit from the left")

    def test_with_no_power_left_he_dissolves_and_starts_again(self) -> None:
        """DAMAGE=80: the first H takes all the power. Player_HandleDeath's loop: 16 passes standing, then 8 phases of 8 tiles (tools in the ROM:
        Player_DrawDeathAnimation), the fade from pass 80, and at pass 256 the screen is back with the death song and the ROM's message (\"Remember your mantra\") on a box, waiting for a button; then he is
        back at the start with all his power and magic and the gold and experience of a Battler (rank 2: 2200 and 800)."""
        args = ["ALL=1", "AREA=0", "SCREEN=1", "HERO=128,144,0,255,0,0,1", "VIEWER_DEFS=--defsym DAMAGE=80 --defsym TITLE=2"]
        hit = [(599, "h", 1), (600, "h", 0)]
        _, base_word, _ = self.run_scenario(args, [], 700, "shots_death")
        self.assertGreater(base_word("hud_state") >> 8, 0)
        _, word, _ = self.run_scenario(args, hit, 610, "shots_death")
        self.assertEqual((word("hero_dead"), word("hud_state") >> 8, word("death_state+2")), (1, 0, 0xFF), "dead, standing still for 16 passes")
        _, word, _ = self.run_scenario(args, hit, 660, "shots_death")
        self.assertTrue(0 <= word("death_state+2") < 8, "dissolving")
        self.assertEqual(word("hero_x"), 128, "he does not move (and not back: the start is where he stood)")
        _, word, _ = self.run_scenario(args, hit, 760, "shots_death")
        self.assertEqual(word("death_state+2"), 8, "dissolved")
        ram, word, log = self.run_scenario(args, hit + [(840, "joy", 0x80), (880, "joy", 0)], 900, "shots_death")
        self.assertEqual(word("hero_dead"), 2, "the song plays and he waits for a button (a button held through the end does not count)")
        import faxanadu_rom as fr
        import hatari_shot as hs
        import st_convert as sc

        rom = fr.Rom(ROM)
        state = dict(hp=word("hud_state") >> 8, mp=word("hud_state") & 255, experience=word("hud_state+2"), gold=word("hud_state+4") << 16 | (word("hud_state+6") & 0xFFFF),
                     seconds=(word("hud_state+8") >> 8) & 255)
        expected = sc.expected_screen(rom, 0, 1, word("camera"), state=state)
        self.text_box(expected, rom, 0, ft_message(rom, 0x24))
        self.assert_picture(hs.decode_screen(ram, hs.video_base(log)), expected)        # the ROM's message on a box, he is gone
        _, word, _ = self.run_scenario(args, hit, 1100, "shots_death")
        self.assertEqual(word("hero_dead"), 2, "no press: still waiting")
        _, word, _ = self.run_scenario(args, hit + [(1000, "joy", 0x80), (1010, "joy", 0)], 1100, "shots_death")
        self.assertEqual((word("hero_dead"), word("hero_x"), word("hero_y")), (0, 128, 144), "back at the start")
        self.assertEqual((word("hud_state"), word("hud_state+2"), word("hud_state+4"), word("hud_state+6")), (0x5050, 2200, 0, 800), "all power and magic, his rank's experience and gold")
        self.assertEqual(word("hero_invinc"), 0)

    def test_up_and_b_cast_a_spell_that_flies_is_drawn_costs_magic_and_leaves_no_trail(self) -> None:
        """Eolis screen 1 with 80 magic power and each spell chosen (MAGIC=n): Up and B cast it. A few frames later its place and state are those of
        `tools/magic_model.py` (checked against the ROM in tests/test_magic.py), the magic power is down by its cost, and the screen is the converter's
        with the spell's box the only difference; when it has gone off the screen the picture is the plain one again."""
        import faxanadu_maps as fm
        import faxanadu_rom as fr
        import hatari_shot as hs
        import hero_physics as hp
        import magic_model as mm
        import st_convert as sc

        rom = fr.Rom(ROM)
        a = fm.area(rom, 0)
        props = fm.block_properties(rom, a)
        impassable = [hp.IMPASSABLE[props[b] & 15] for b in fm.decode_screen(rom, a, 1)]
        for spell in range(5):
            args = ["AREA=0", "SCREEN=1", "CAMERA=40", "HERO=100,144,0,255,0,0,1", "HUD=16,80,0,0,0", f"VIEWER_DEFS=--defsym MAGIC={spell}"]
            ram, word, log = self.run_scenario(args, [(599, "joy", 0x81), (601, "joy", 0)], 616, "shots_magic")
            flags = word("spell_state+2")
            self.assertEqual(flags & 0x40, 0x40 if word("hero_flip") else 0, "it flies the way he faces")
            self.assertEqual(word("hud_state") & 0xFF, 80 - mm.COSTS[spell], f"spell {spell}: the cost")
            found = None
            for n in range(1, 20):                         # the model, n frames after the cast
                sp = mm.Spell()
                mm.cast(sp, word("hero_x"), word("hero_y"), 0x40 if word("hero_flip") else 0, 80, spell, hp.JOY_UP, hp.BUTTON_B)
                for _ in range(n):
                    mm.step(sp, impassable)
                if (sp.type, sp.flags, sp.x, sp.y, sp.counter, sp.phase) == tuple(word(f"spell_state+{o}") & 0xFFFF if o else word("spell_state") for o in (0, 2, 4, 8, 12, 14)):
                    found = n
                    break
            self.assertIsNotNone(found, f"spell {spell}: its state ({[word(f'spell_state+{o}') for o in range(0, 18, 2)]}) is one the model reaches")
            x, y = word("spell_state+4"), word("spell_state+8") + 32 - word("camera")     # (the sprites lie 32 lines, the HUD, below the game's y)
            rows = hs.decode_screen(ram, hs.video_base(log))
            expected = sc.expected_screen(rom, 0, 1, word("camera"), state=dict(hp=16, mp=word("hud_state") & 0xFF, experience=0, gold=0, seconds=0),
                                          hero=sc.Hero(word("hero_x"), word("hero_y"), 0, 255, 0, word("hero_frame"), bool(word("hero_flip"))))
            bad = [(px, py) for py in range(200) for px in range(320) if rows[py][px] != expected[py][px]]
            outside = [(px, py) for px, py in bad if not (x + 32 - 8 <= px < x + 32 + 40 and y - 8 <= py < y + 40)]
            self.assertEqual(outside[:5], [], f"spell {spell}: {len(outside)} pixels differ outside its box")
            if spell in (0, 3, 4):                         # (Thunder and Fire blink: not there in every frame)
                self.assertGreater(len(bad), 20, f"spell {spell}: it is drawn")
            ram, word, log = self.run_scenario(args, [(599, "joy", 0x81), (601, "joy", 0)], 780, "shots_magic")
            self.assertEqual(word("spell_state"), -1, f"spell {spell}: gone")
            rows = hs.decode_screen(ram, hs.video_base(log))
            self.assert_picture(rows, sc.expected_screen(rom, 0, 1, word("camera"), state=dict(hp=16, mp=word("hud_state") & 0xFF, experience=0, gold=0, seconds=0),
                                                         hero=sc.Hero(word("hero_x"), word("hero_y"), 0, 255, 0, word("hero_frame"), bool(word("hero_flip")))))

    def test_a_spell_needs_up_the_power_and_a_chosen_spell(self) -> None:
        """B alone (no Up), Up and B with too little magic power (Thunder costs 4), and Up and B with no spell chosen cast nothing and take no power;
        the M key chooses the first spell and fills the magic, and then Up and B cast."""
        base = ["AREA=0", "SCREEN=1", "CAMERA=40", "HERO=100,144,0,255,0,0,1"]
        _, word, _ = self.run_scenario(base + ["HUD=16,80,0,0,0", "VIEWER_DEFS=--defsym MAGIC=0"], [(599, "joy", 0x80), (601, "joy", 0)], 616, "shots_magic")
        self.assertEqual((word("spell_state"), word("hud_state") & 0xFF), (-1, 80), "no Up")
        _, word, _ = self.run_scenario(base + ["HUD=16,3,0,0,0", "VIEWER_DEFS=--defsym MAGIC=1"], [(599, "joy", 0x81), (601, "joy", 0)], 616, "shots_magic")
        self.assertEqual((word("spell_state"), word("hud_state") & 0xFF), (-1, 3), "too little power")
        _, word, _ = self.run_scenario(base + ["HUD=16,80,0,0,0"], [(599, "joy", 0x81), (601, "joy", 0)], 616, "shots_magic")
        self.assertEqual((word("spell_state"), word("hud_state") & 0xFF), (-1, 80), "no spell chosen")
        _, word, _ = self.run_scenario(base + ["HUD=16,0,0,0,0"], [(580, "m", 1), (584, "m", 0), (599, "joy", 0x81), (601, "joy", 0)], 616, "shots_magic")
        self.assertEqual((word("hero_magic"), word("spell_state"), word("hud_state") & 0xFF), (0, 0, 78), "the M key: Deluge, full power; cast")

    def test_the_weapons_place_and_reach_follow_the_pose(self) -> None:
        """`weapon_x`, `weapon_y`, `weapon_rx`, `weapon_ry` (Player_DrawWeapon's numbers, checked against the ROM in tests/test_hero_physics.py) for the
        pose he is in: standing, and in each phase of an attack (a dagger, no shield)."""
        import faxanadu_rom as fr
        import faxanadu_sprites as fs

        rom = fr.Rom(ROM)
        seen = set()
        for capture, stick in ((620, 0), (606, 0x80), (609, 0x80), (620, 0x80)):
            ram, word, _ = self.run_scenario(["ALL=1", "AREA=0", "SCREEN=1", "HERO=128,144,0,255,0,0,1"], [(599, "joy", stick), (601, "joy", 0)], capture, "shots_weapon")
            frame, flip = word("hero_frame"), word("hero_flip")
            seen.add(frame)
            dx, dy = fs.weapon_offset(rom, 0, 255, 0, frame, bool(flip))
            want = (word("hero_x") + dx, word("hero_y") + (dy - 256 if dy > 127 else dy), *fs.weapon_range(rom, 0))
            got = tuple(word(f"weapon_x+{2 * i}") for i in range(4))
            self.assertEqual(got, want, f"pose {frame}, flip {flip}")
        self.assertGreaterEqual(len(seen), 2)

    def test_a_hud_change_during_play_reaches_both_screens(self) -> None:
        """The program is told through the debugger (poke hud_state, then hud_dirty) that the HUD changed; the HUD lines of both screens
        and of the clean background must show the new state."""
        import faxanadu_rom as fr
        import hatari_shot as hs
        import st_convert as sc

        subprocess.run(["make", "-C", str(ROOT), "viewer"], check=True, capture_output=True)
        nm = subprocess.run(["m68k-linux-gnu-nm", str(ROOT / "build" / "viewer.elf")], check=True, capture_output=True, text=True).stdout.split("\n")
        sym = {line.split()[2]: int(line.split()[0], 16) for line in nm if len(line.split()) == 3}
        image = (ROOT / "build" / "viewer.bin").read_bytes()
        work = ROOT / "build" / "shots_hud"
        work.mkdir(parents=True, exist_ok=True)
        prg = ROOT / "build" / "VIEWER.PRG"
        hatari = shutil.which("hatari")
        (work / "c0.ini").write_text(f"savebin {work / 'ram0.bin'} 0 $80000\ncont\n", encoding="utf-8")
        hs.run_hatari(hatari, TOS, prg, work, 500, "0", f"b VBL > 499 :once :file {work / 'c0.ini'}\n", None)
        base = (work / "ram0.bin").read_bytes().find(image[sym["start"]:sym["start"] + 48]) - sym["start"]
        self.assertGreater(base, 0)
        state = dict(hp=35, mp=13, experience=4242, gold=1234567, seconds=7)
        values = " ".join(f"0x{b:02x}" for b in sc.hud_state_bytes(state))
        (work / "poke.ini").write_text(f"memwrite ${base + sym['hud_state']:x} {values}\nmemwrite ${base + sym['hud_dirty']:x} 0x01\ncont\n", encoding="utf-8")
        (work / "cap.ini").write_text(f"savebin {work / 'ram1.bin'} 0 $80000\ncont\n", encoding="utf-8")
        script = "".join(f"b VBL > {v} :once :file {work / f}\n" for v, f in ((599, "poke.ini"), (699, "cap.ini")))
        hs.run_hatari(hatari, TOS, prg, work, 700, "0", script, None)
        ram = (work / "ram1.bin").read_bytes()
        expected = sc.expected_screen(fr.Rom(ROM), 0, 1, 40, state=state, hero=sc.Hero())
        for name in ("buf_a", "buf_b"):
            address = int.from_bytes(ram[base + sym[name]:base + sym[name] + 4], "big")
            rows = hs.decode_screen(ram, address)
            bad = [(x, y) for y in range(32) for x in range(320) if rows[y][x] != expected[y][x]]
            self.assertEqual(bad[:5], [], f"{name}: {len(bad)} HUD pixels differ")

    def test_walking_off_the_right_edge_scrolls_to_the_next_screen_in_steps_of_16_pixels(self) -> None:
        self.scroll_test(True)

    def test_walking_off_the_left_edge_scrolls_to_the_next_screen_in_steps_of_16_pixels(self) -> None:
        self.scroll_test(False)

    def scroll_test(self, to_the_right: bool) -> None:
        """He stands at the right edge of Eolis screen 1 and the stick is pushed right (poked): the picture is captured at several moments
        of the scroll; each must be the two screens side by side moved by what the program says (shown_offset), the hero as the ROM
        places him (257 - offset), and at the end the new screen with the hero at its left edge."""
        import faxanadu_rom as fr
        import faxanadu_maps as fm
        import hatari_shot as hs
        import re
        import st_convert as sc

        subprocess.run(["make", "-C", str(ROOT), "viewer", "VIEWER_DEFS=--defsym NO_ENEMIES=1"], check=True, capture_output=True)
        nm = subprocess.run(["m68k-linux-gnu-nm", str(ROOT / "build" / "viewer.elf")], check=True, capture_output=True, text=True).stdout.split("\n")
        sym = {line.split()[2]: int(line.split()[0], 16) for line in nm if len(line.split()) == 3}
        image = (ROOT / "build" / "viewer.bin").read_bytes()
        work = ROOT / "build" / "shots_scroll"
        work.mkdir(parents=True, exist_ok=True)
        prg = ROOT / "build" / "VIEWER.PRG"
        hatari = shutil.which("hatari")
        (work / "c0.ini").write_text(f"savebin {work / 'ram0.bin'} 0 $80000\ncont\n", encoding="utf-8")
        hs.run_hatari(hatari, TOS, prg, work, 500, "0", f"b VBL > 499 :once :file {work / 'c0.ini'}\n", None)
        base = (work / "ram0.bin").read_bytes().find(image[sym["start"]:sym["start"] + 48]) - sym["start"]
        self.assertGreater(base, 0)
        joy, hero_x = base + sym["input_state"] + 259, base + sym["hero_x"]
        (work / "go.ini").write_text(f"memwrite ${hero_x:x} 0x00 {'0xf1' if to_the_right else '0x00'}\nmemwrite ${joy:x} {'0x08' if to_the_right else '0x04'}\ncont\n", encoding="utf-8")
        (work / "let_go.ini").write_text(f"memwrite ${joy:x} 0x00\ncont\n", encoding="utf-8")
        moments = [625, 640, 652, 665, 690, 705, 730, 760, 790, 820]
        for v in moments:
            (work / f"cap{v}.ini").write_text(f"savebin {work / f'ram{v}.bin'} 0 $80000\nm $ff8200-$ff8260\ncont\n", encoding="utf-8")
        script = f"b VBL > 599 :once :file {work / 'go.ini'}\nb VBL > 602 :once :file {work / 'let_go.ini'}\n"
        script += "".join(f"b VBL > {v} :once :file {work / f'cap{v}.ini'}\n" for v in moments)
        log = hs.run_hatari(hatari, TOS, prg, work, moments[-1] + 1, "0", script, None)
        bases = [(int(m.group(2), 16) << 16) | (int(m.group(4), 16) << 8)
                 for m in re.finditer(r"^00FF8200: ([0-9a-fA-F]{2}) ([0-9a-fA-F]{2}) ([0-9a-fA-F]{2}) ([0-9a-fA-F]{2})", log, re.M)]
        self.assertEqual(len(bases), len(moments))
        rom = fr.Rom(ROM)
        a = fm.area(rom, 0)
        left, right = fm.neighbours(rom, a, 1)[:2]
        target = right if to_the_right else left
        seen, late = set(), []
        for v, shown in zip(moments, bases):
            ram = (work / f"ram{v}.bin").read_bytes()
            word = lambda name: int.from_bytes(ram[base + sym[name]:base + sym[name] + 2], "big")
            offset, cur = word("shown_offset"), word("cur_screen")
            late.append(int.from_bytes(ram[base + sym["late_frames"]:base + sym["late_frames"] + 4], "big"))
            rows = hs.decode_screen(ram, shown)
            if cur == 0 and offset == 0:                          # not scrolling yet (or the hero still walks)
                continue
            seen.add(offset)
            if offset % 16:
                self.fail(f"offset {offset}")
            if cur == 0:
                step = offset // 16
                hero = sc.Hero(261 - offset if to_the_right else offset - 20, 144, 0, 255, 0, step & 1, to_the_right)
                expected = sc.expected_scroll_screen(rom, 0, 1, target, offset, to_the_right, 40, hero=hero)
            else:
                hero = sc.Hero(1 if to_the_right else 241, 144, 0, 255, 0, 0, to_the_right)
                expected = sc.expected_scroll_screen(rom, 0, target, target, 0, True, 40, hero=hero)
            bad = [(x, y) for y in range(200) for x in range(320) if rows[y][x] != expected[y][x]]
            if cur == 0 and offset == 16:
                # The ROM's 8-bit sprite arithmetic wraps or drops cells of a hero this close to the edge (a sword at the far
                # edge, the body gone); the port clips by position instead (AGENTS.md, deliberate differences): his lines are not compared.
                bad = [(x, y) for (x, y) in bad if not 120 <= y < 180]
            self.assertEqual(bad[:5], [], f"VBL {v}, offset {offset}, screen {cur}: {len(bad)} pixels differ")
        self.assertGreaterEqual(len(seen), 5, f"offsets seen: {sorted(seen)}")
        self.assertEqual(late[-1], late[0], f"frames that took longer than 20 ms during the scroll: {late}")

    def test_walking_off_the_top_scrolls_to_the_screen_above(self) -> None:
        self.vscroll_test(False)

    def test_walking_off_the_bottom_scrolls_to_the_screen_below(self) -> None:
        self.vscroll_test(True)

    def vscroll_test(self, down: bool) -> None:
        """Trunk (area 1): screen 3 has screen 4 above it (and 4 has 3 below). The hero stands at the top (or the bottom) and the stick is
        pushed (poked): the picture is captured at several moments; each must be the two playfields one above the other, the window
        from the line the program reports (shown_vtop), the hero fixed where the game puts him (y 192 going up, 0 going down), and
        at the end the new screen with the camera of its hero."""
        import faxanadu_rom as fr
        import hatari_shot as hs
        import re
        import st_convert as sc

        start, target = (4, 3) if down else (3, 4)
        hero_start = "144,192,0,255,0,0,1" if down else "144,0,0,255,0,0,1"
        subprocess.run(["make", "-C", str(ROOT), "viewer", "AREA=1", f"SCREEN={start}", f"CAMERA={40 if down else 0}", f"HERO={hero_start}",
                        "VIEWER_DEFS=--defsym NO_PHYSICS=1"], check=True, capture_output=True)
        nm = subprocess.run(["m68k-linux-gnu-nm", str(ROOT / "build" / "viewer.elf")], check=True, capture_output=True, text=True).stdout.split("\n")
        sym = {line.split()[2]: int(line.split()[0], 16) for line in nm if len(line.split()) == 3}
        image = (ROOT / "build" / "viewer.bin").read_bytes()
        work = ROOT / "build" / "shots_vscroll"
        work.mkdir(parents=True, exist_ok=True)
        prg = ROOT / "build" / "VIEWER.PRG"
        hatari = shutil.which("hatari")
        (work / "c0.ini").write_text(f"savebin {work / 'ram0.bin'} 0 $80000\ncont\n", encoding="utf-8")
        hs.run_hatari(hatari, TOS, prg, work, 500, "0", f"b VBL > 499 :once :file {work / 'c0.ini'}\n", None)
        base = (work / "ram0.bin").read_bytes().find(image[sym["start"]:sym["start"] + 48]) - sym["start"]
        self.assertGreater(base, 0)
        joy = base + sym["input_state"] + 259
        (work / "go.ini").write_text(f"memwrite ${joy:x} {'0x02' if down else '0x01'}\ncont\n", encoding="utf-8")
        (work / "let_go.ini").write_text(f"memwrite ${joy:x} 0x00\ncont\n", encoding="utf-8")
        moments = [610, 625, 640, 655, 670, 685, 700, 715, 730, 760]
        for v in moments:
            (work / f"cap{v}.ini").write_text(f"savebin {work / f'ram{v}.bin'} 0 $80000\nm $ff8200-$ff8260\ncont\n", encoding="utf-8")
        script = f"b VBL > 599 :once :file {work / 'go.ini'}\nb VBL > 602 :once :file {work / 'let_go.ini'}\n"
        script += "".join(f"b VBL > {v} :once :file {work / f'cap{v}.ini'}\n" for v in moments)
        log = hs.run_hatari(hatari, TOS, prg, work, moments[-1] + 1, "0", script, None)
        bases = [(int(m.group(2), 16) << 16) | (int(m.group(4), 16) << 8)
                 for m in re.finditer(r"^00FF8200: ([0-9a-fA-F]{2}) ([0-9a-fA-F]{2}) ([0-9a-fA-F]{2}) ([0-9a-fA-F]{2})", log, re.M)]
        self.assertEqual(len(bases), len(moments))
        rom = fr.Rom(ROM)
        state = dict(hp=16, mp=0, experience=0, gold=0, seconds=0)
        seen, late = [], []
        for v, shown in zip(moments, bases):
            ram = (work / f"ram{v}.bin").read_bytes()
            word = lambda name: int.from_bytes(ram[base + sym[name]:base + sym[name] + 2], "big", signed=True)
            top, cur = word("shown_vtop"), word("cur_screen")
            late.append(int.from_bytes(ram[base + sym["late_frames"]:base + sym["late_frames"] + 4], "big"))
            rows = hs.decode_screen(ram, shown)
            if top == -1 and cur == 0:
                continue                                           # not started yet
            seen.append(top)
            if top != -1:
                hero = sc.Hero(144, 0 if down else 192, 0, 255, 0, 0, True)
                expected = sc.expected_vscroll_screen(rom, 1, start, target, down, top, 0 if down else 40, state=state, hero=hero)
            else:
                hero = sc.Hero(144, 0 if down else 192, 0, 255, 0, 0, True)
                expected = sc.expected_screen(rom, 1, target, 0 if down else 40, state=state, hero=hero)
            bad = [(x, y) for y in range(200) for x in range(320) if rows[y][x] != expected[y][x]]
            self.assertEqual(bad[:5], [], f"VBL {v}, top {top}, screen {cur}: {len(bad)} pixels differ")
        self.assertGreaterEqual(len(seen), 5, f"tops seen: {seen}")
        self.assertEqual(seen[-1], -1, f"tops seen: {seen}")
        self.assertEqual(late[-1], late[0], f"frames that took longer than 20 ms during the scroll: {late}")

    def test_the_window_follows_the_hero_up_the_screen(self) -> None:
        """He starts low (camera 40) and the stick is pushed up (poked): once his y is below 56 the window moves to camera 0 (both screens
        are redrawn) and the picture is the converter's, with him where he stands."""
        import faxanadu_rom as fr
        import hatari_shot as hs
        import st_convert as sc

        subprocess.run(["make", "-C", str(ROOT), "viewer", "AREA=0", "SCREEN=1", "CAMERA=40", "HERO=144,100,0,255,0,0,1",
                        "VIEWER_DEFS=--defsym NO_PHYSICS=1"], check=True, capture_output=True)
        nm = subprocess.run(["m68k-linux-gnu-nm", str(ROOT / "build" / "viewer.elf")], check=True, capture_output=True, text=True).stdout.split("\n")
        sym = {line.split()[2]: int(line.split()[0], 16) for line in nm if len(line.split()) == 3}
        image = (ROOT / "build" / "viewer.bin").read_bytes()
        work = ROOT / "build" / "shots_camera"
        work.mkdir(parents=True, exist_ok=True)
        prg = ROOT / "build" / "VIEWER.PRG"
        hatari = shutil.which("hatari")
        (work / "c0.ini").write_text(f"savebin {work / 'ram0.bin'} 0 $80000\ncont\n", encoding="utf-8")
        hs.run_hatari(hatari, TOS, prg, work, 500, "0", f"b VBL > 499 :once :file {work / 'c0.ini'}\n", None)
        base = (work / "ram0.bin").read_bytes().find(image[sym["start"]:sym["start"] + 48]) - sym["start"]
        self.assertGreater(base, 0)
        joy = base + sym["input_state"] + 259
        (work / "go.ini").write_text(f"memwrite ${joy:x} 0x01\ncont\n", encoding="utf-8")
        (work / "let_go.ini").write_text(f"memwrite ${joy:x} 0x00\ncont\n", encoding="utf-8")
        (work / "cap.ini").write_text(f"savebin {work / 'ram1.bin'} 0 $80000\nm $ff8200-$ff8260\ncont\n", encoding="utf-8")
        script = f"b VBL > 599 :once :file {work / 'go.ini'}\nb VBL > 650 :once :file {work / 'let_go.ini'}\nb VBL > 720 :once :file {work / 'cap.ini'}\n"
        log = hs.run_hatari(hatari, TOS, prg, work, 721, "0", script, None)
        import re
        m = re.search(r"^00FF8200: ([0-9a-fA-F]{2}) ([0-9a-fA-F]{2}) ([0-9a-fA-F]{2}) ([0-9a-fA-F]{2})", log, re.M)
        shown = (int(m.group(2), 16) << 16) | (int(m.group(4), 16) << 8)
        ram = (work / "ram1.bin").read_bytes()
        word = lambda name: int.from_bytes(ram[base + sym[name]:base + sym[name] + 2], "big", signed=True)
        self.assertEqual(word("camera"), 0)
        self.assertLess(word("hero_y"), 56)
        hero = sc.Hero(word("hero_x"), word("hero_y"), 0, 255, 0, word("hero_frame"), bool(word("hero_flip")))
        expected = sc.expected_screen(fr.Rom(ROM), 0, 1, 0, state=dict(hp=16, mp=0, experience=0, gold=0, seconds=0), hero=hero)
        rows = hs.decode_screen(ram, shown)
        bad = [(x, y) for y in range(200) for x in range(320) if rows[y][x] != expected[y][x]]
        self.assertEqual(bad[:5], [], f"{len(bad)} pixels differ")

    def test_he_falls_to_the_floor_and_jumps_when_a_is_pressed(self) -> None:
        """He starts in the air (y 40) in Eolis screen 1 and falls to the floor (y 144); a key held down (Space, the jump button: poked into the key table)
        starts a jump, in the air his y is above the floor with the jumping bit set, and he lands on the floor again."""
        import hatari_shot as hs

        subprocess.run(["make", "-C", str(ROOT), "viewer", "AREA=0", "SCREEN=1", "CAMERA=40", "HERO=144,40,0,255,0,0,1"], check=True, capture_output=True)
        nm = subprocess.run(["m68k-linux-gnu-nm", str(ROOT / "build" / "viewer.elf")], check=True, capture_output=True, text=True).stdout.split("\n")
        sym = {line.split()[2]: int(line.split()[0], 16) for line in nm if len(line.split()) == 3}
        image = (ROOT / "build" / "viewer.bin").read_bytes()
        work = ROOT / "build" / "shots_jump"
        work.mkdir(parents=True, exist_ok=True)
        prg = ROOT / "build" / "VIEWER.PRG"
        hatari = shutil.which("hatari")
        (work / "c0.ini").write_text(f"savebin {work / 'ram0.bin'} 0 $80000\ncont\n", encoding="utf-8")
        hs.run_hatari(hatari, TOS, prg, work, 500, "0", f"b VBL > 499 :once :file {work / 'c0.ini'}\n", None)
        base = (work / "ram0.bin").read_bytes().find(image[sym["start"]:sym["start"] + 48]) - sym["start"]
        self.assertGreater(base, 0)
        space = base + sym["input_state"] + 264 + 0x39
        (work / "press.ini").write_text(f"memwrite ${space:x} 0x01\ncont\n", encoding="utf-8")
        (work / "release.ini").write_text(f"memwrite ${space:x} 0x00\ncont\n", encoding="utf-8")
        script = ""
        moments = ((599, "press.ini"), (700, "release.ini"))
        for v, f in moments:
            script += f"b VBL > {v} :once :file {work / f}\n"
        for v in (590, 610, 800):
            (work / f"cap{v}.ini").write_text(f"savebin {work / f'ram{v}.bin'} 0 $80000\ncont\n", encoding="utf-8")
            script += f"b VBL > {v} :once :file {work / f'cap{v}.ini'}\n"
        hs.run_hatari(hatari, TOS, prg, work, 801, "0", script, None)

        def state(v: int) -> tuple[int, int]:
            ram = (work / f"ram{v}.bin").read_bytes()
            word = lambda name: int.from_bytes(ram[base + sym[name]:base + sym[name] + 2], "big", signed=True)
            if v == 610:
                self.assertEqual(word("hero_frame"), 3, "the pose in the air")
            return word("hero_y"), word("hero_air")

        self.assertEqual(state(590), (144, 0), "fallen to the floor")
        y, air = state(610)
        self.assertLess(y, 144)
        self.assertTrue(air & 1, "jumping")
        self.assertEqual(state(800), (144, 0), "landed again")

    def test_he_climbs_a_ladder_as_the_rom_does(self) -> None:
        """Mist screen 0 has a ladder in column 2 (rows 10 to 12). He hangs on it without falling; the stick held up (poked) from VBL 600 to 640
        lifts him 5/8 of a pixel a frame, which is where the Python model puts him after about 40 frames."""
        import faxanadu_maps as fm
        import faxanadu_rom as fr
        import hatari_shot as hs
        import hero_physics as hp

        subprocess.run(["make", "-C", str(ROOT), "viewer", "AREA=2", "SCREEN=0", "CAMERA=40", "HERO=32,170,0,255,0,0,1"], check=True, capture_output=True)
        nm = subprocess.run(["m68k-linux-gnu-nm", str(ROOT / "build" / "viewer.elf")], check=True, capture_output=True, text=True).stdout.split("\n")
        sym = {line.split()[2]: int(line.split()[0], 16) for line in nm if len(line.split()) == 3}
        image = (ROOT / "build" / "viewer.bin").read_bytes()
        work = ROOT / "build" / "shots_ladder"
        work.mkdir(parents=True, exist_ok=True)
        prg = ROOT / "build" / "VIEWER.PRG"
        hatari = shutil.which("hatari")
        (work / "c0.ini").write_text(f"savebin {work / 'ram0.bin'} 0 $80000\ncont\n", encoding="utf-8")
        hs.run_hatari(hatari, TOS, prg, work, 500, "0", f"b VBL > 499 :once :file {work / 'c0.ini'}\n", None)
        base = (work / "ram0.bin").read_bytes().find(image[sym["start"]:sym["start"] + 48]) - sym["start"]
        self.assertGreater(base, 0)
        joy = base + sym["input_state"] + 259
        (work / "up.ini").write_text(f"memwrite ${joy:x} 0x01\ncont\n", encoding="utf-8")
        (work / "stop.ini").write_text(f"memwrite ${joy:x} 0x00\ncont\n", encoding="utf-8")
        script = ""
        for v, f in ((599, "up.ini"), (639, "stop.ini")):
            script += f"b VBL > {v} :once :file {work / f}\n"
        for v in (590, 700):
            (work / f"cap{v}.ini").write_text(f"savebin {work / f'ram{v}.bin'} 0 $80000\nm $ff8200-$ff8260\ncont\n", encoding="utf-8")
            script += f"b VBL > {v} :once :file {work / f'cap{v}.ini'}\n"
        log = hs.run_hatari(hatari, TOS, prg, work, 701, "0", script, None)

        def word(v: int, name: str) -> int:
            ram = (work / f"ram{v}.bin").read_bytes()
            return int.from_bytes(ram[base + sym[name]:base + sym[name] + 2], "big", signed=True)

        self.assertEqual((word(590, "hero_x"), word(590, "hero_y")), (32, 170), "hangs on the ladder")
        rom = fr.Rom(ROM)
        a = fm.area(rom, 2)
        props = fm.block_properties(rom, a)
        blocks = fm.decode_screen(rom, a, 0)
        impassable = [hp.IMPASSABLE[props[b] & 15] for b in blocks]
        ladder = [hp.CLIMBABLE[props[b] & 15] for b in blocks]
        h = hp.Hero(x=32, y=170, flags=0x40)
        reached = []
        for _ in range(45):
            hp.step(h, hp.JOY_UP, 0, impassable, ladder=ladder)
            reached.append(h.y)
        self.assertIn(word(700, "hero_y"), reached[36:44], f"y {word(700, 'hero_y')}: not what the ROM's climbing gives after about 40 frames")
        self.assertLess(word(700, "hero_y"), 170)
        # hanging on the ladder after the climb: the climbing pose (the ROM's frame 7), mirrored every 16 movement ticks
        import re
        import st_convert as sc
        self.assertEqual(word(700, "hero_frame"), 7)
        m = re.findall(r"^00FF8200: ([0-9a-fA-F]{2}) ([0-9a-fA-F]{2}) ([0-9a-fA-F]{2}) ([0-9a-fA-F]{2})", log, re.M)[-1]
        shown = (int(m[1], 16) << 16) | (int(m[3], 16) << 8)
        flip = word(700, "hero_flip") ^ ((word(700, "hero_mtick") >> 4) & 1)
        expected = sc.expected_screen(rom, 2, 0, 40, state=dict(hp=16, mp=0, experience=0, gold=0, seconds=0),
                                      hero=sc.Hero(word(700, "hero_x"), word(700, "hero_y"), 0, 255, 0, 7, bool(flip)))
        rows = hs.decode_screen((work / "ram700.bin").read_bytes(), shown)
        bad = [(x, y) for y in range(200) for x in range(320) if rows[y][x] != expected[y][x]]
        self.assertEqual(bad[:5], [], f"{len(bad)} pixels differ")

    def test_the_sword_is_swung_in_three_phases(self) -> None:
        """B (Alternate, poked into the key table) held from VBL 600: the attack frames 4, 5 and 6 follow one another (8, 3 and 8 frames) and the
        picture in each is the converter's, with the sword; afterwards he stands again."""
        import re
        import faxanadu_rom as fr
        import hatari_shot as hs
        import st_convert as sc

        subprocess.run(["make", "-C", str(ROOT), "viewer", "AREA=0", "SCREEN=1", "CAMERA=40", "HERO=144,144,0,255,0,0,1"], check=True, capture_output=True)
        nm = subprocess.run(["m68k-linux-gnu-nm", str(ROOT / "build" / "viewer.elf")], check=True, capture_output=True, text=True).stdout.split("\n")
        sym = {line.split()[2]: int(line.split()[0], 16) for line in nm if len(line.split()) == 3}
        image = (ROOT / "build" / "viewer.bin").read_bytes()
        work = ROOT / "build" / "shots_attack"
        work.mkdir(parents=True, exist_ok=True)
        prg = ROOT / "build" / "VIEWER.PRG"
        hatari = shutil.which("hatari")
        (work / "c0.ini").write_text(f"savebin {work / 'ram0.bin'} 0 $80000\ncont\n", encoding="utf-8")
        hs.run_hatari(hatari, TOS, prg, work, 500, "0", f"b VBL > 499 :once :file {work / 'c0.ini'}\n", None)
        base = (work / "ram0.bin").read_bytes().find(image[sym["start"]:sym["start"] + 48]) - sym["start"]
        self.assertGreater(base, 0)
        key = base + sym["input_state"] + 264 + 0x38
        (work / "press.ini").write_text(f"memwrite ${key:x} 0x01\ncont\n", encoding="utf-8")
        (work / "release.ini").write_text(f"memwrite ${key:x} 0x00\ncont\n", encoding="utf-8")
        script = f"b VBL > 599 :once :file {work / 'press.ini'}\nb VBL > 640 :once :file {work / 'release.ini'}\n"
        moments = (604, 609, 614, 626, 700)
        for v in moments:
            (work / f"cap{v}.ini").write_text(f"savebin {work / f'ram{v}.bin'} 0 $80000\nm $ff8200-$ff8260\ncont\n", encoding="utf-8")
            script += f"b VBL > {v} :once :file {work / f'cap{v}.ini'}\n"
        log = hs.run_hatari(hatari, TOS, prg, work, 701, "0", script, None)
        shots = re.findall(r"^00FF8200: ([0-9a-fA-F]{2}) ([0-9a-fA-F]{2}) ([0-9a-fA-F]{2}) ([0-9a-fA-F]{2})", log, re.M)
        rom = fr.Rom(ROM)
        frames = []
        for v, m in zip(moments, shots[-len(moments):]):
            ram = (work / f"ram{v}.bin").read_bytes()
            word = lambda name: int.from_bytes(ram[base + sym[name]:base + sym[name] + 2], "big", signed=True)
            frames.append(word("hero_frame"))
            shown = (int(m[1], 16) << 16) | (int(m[3], 16) << 8)
            expected = sc.expected_screen(rom, 0, 1, 40, state=dict(hp=16, mp=0, experience=0, gold=0, seconds=0),
                                          hero=sc.Hero(word("hero_x"), word("hero_y"), 0, 255, 0, word("hero_frame"), bool(word("hero_flip"))))
            rows = hs.decode_screen(ram, shown)
            bad = [(x, y) for y in range(200) for x in range(320) if rows[y][x] != expected[y][x]]
            self.assertEqual(bad[:5], [], f"VBL {v}, frame {frames[-1]}: {len(bad)} pixels differ")
        self.assertEqual(frames[0], 4, frames)
        self.assertIn(5, frames, frames)
        self.assertIn(6, frames, frames)
        self.assertEqual(frames[-1], 0, frames)

    def test_up_at_the_castle_door_leads_to_screen_1_of_eolis(self) -> None:
        """The viewer has every screen of Eolis (ALL=1) and the hero stands at the castle door of screen 0 (block 156); Up (poked into the
        stick for one frame) takes him through, as the ROM does (verified there: screen 1, hero at x 144, y 144): the picture is screen 1
        with the hero there, the door's own palette and the camera of a hero who stands low."""
        import faxanadu_rom as fr
        import hatari_shot as hs
        import st_convert as sc

        subprocess.run(["make", "-C", str(ROOT), "viewer", "ALL=1", "SCREEN=0", "HERO=192,144,0,255,0,0,1"], check=True, capture_output=True)
        nm = subprocess.run(["m68k-linux-gnu-nm", str(ROOT / "build" / "viewer.elf")], check=True, capture_output=True, text=True).stdout.split("\n")
        sym = {line.split()[2]: int(line.split()[0], 16) for line in nm if len(line.split()) == 3}
        image = (ROOT / "build" / "viewer.bin").read_bytes()
        work = ROOT / "build" / "shots_door"
        work.mkdir(parents=True, exist_ok=True)
        prg = ROOT / "build" / "VIEWER.PRG"
        hatari = shutil.which("hatari")
        (work / "c0.ini").write_text(f"savebin {work / 'ram0.bin'} 0 $80000\ncont\n", encoding="utf-8")
        hs.run_hatari(hatari, TOS, prg, work, 500, "0", f"b VBL > 499 :once :file {work / 'c0.ini'}\n", None)
        ram = (work / "ram0.bin").read_bytes()
        base = ram.find(image[sym["start"]:sym["start"] + 48]) - sym["start"]
        self.assertGreater(base, 0)
        word = lambda data, name: int.from_bytes(data[base + sym[name]:base + sym[name] + 2], "big", signed=True)
        self.assertEqual(word(ram, "cur_screen"), 0)
        joy = base + sym["input_state"] + 259
        (work / "up.ini").write_text(f"memwrite ${joy:x} 0x01\ncont\n", encoding="utf-8")
        (work / "stop.ini").write_text(f"memwrite ${joy:x} 0x00\ncont\n", encoding="utf-8")
        (work / "cap.ini").write_text(f"savebin {work / 'ram1.bin'} 0 $80000\nm $ff8200-$ff8260\ncont\n", encoding="utf-8")
        script = "".join(f"b VBL > {v} :once :file {work / f}\n" for v, f in ((599, "up.ini"), (602, "stop.ini"), (699, "cap.ini")))
        log = hs.run_hatari(hatari, TOS, prg, work, 700, "0", script, None)
        ram = (work / "ram1.bin").read_bytes()
        self.assertEqual(word(ram, "cur_screen"), 1)
        self.assertEqual((word(ram, "hero_x"), word(ram, "hero_y")), (144, 144))
        self.assertEqual(word(ram, "camera"), 40)
        rows = hs.decode_screen(ram, hs.video_base(log))
        expected = sc.expected_screen(fr.Rom(ROM), 0, 1, 40, hero=sc.Hero(144, 144, 0, 255, 0, 0, True))
        bad = [(x, y) for y in range(200) for x in range(320) if rows[y][x] != expected[y][x]]
        self.assertEqual(bad[:5], [], f"{len(bad)} pixels differ")

    def test_up_at_a_palette_door_loads_the_other_package(self) -> None:
        """Area 6 (palette 12): the door of screen 12 (block 72) leads to screen 16 in palette 13, which is another package, A6P13.DAT, read from
        the disk while the picture is black. The picture afterwards is screen 16 in palette 13 with the hero at the door's other end (x 16,
        y 144) and the HUD in the colours of the new palette."""
        import faxanadu_rom as fr
        import hatari_shot as hs
        import st_convert as sc

        subprocess.run(["make", "-C", str(ROOT), "viewer", "ALL=1", "AREA=6", "SCREEN=12", "HERO=128,64,0,255,0,0,1", "VIEWER_DEFS=--defsym NO_ENEMIES=1"],
                       check=True, capture_output=True)
        self.assertTrue((ROOT / "build" / "A6P13.DAT").is_file())
        nm = subprocess.run(["m68k-linux-gnu-nm", str(ROOT / "build" / "viewer.elf")], check=True, capture_output=True, text=True).stdout.split("\n")
        sym = {line.split()[2]: int(line.split()[0], 16) for line in nm if len(line.split()) == 3}
        image = (ROOT / "build" / "viewer.bin").read_bytes()
        work = ROOT / "build" / "shots_palette_door"
        work.mkdir(parents=True, exist_ok=True)
        prg = ROOT / "build" / "VIEWER.PRG"
        hatari = shutil.which("hatari")
        (work / "c0.ini").write_text(f"savebin {work / 'ram0.bin'} 0 $80000\ncont\n", encoding="utf-8")
        hs.run_hatari(hatari, TOS, prg, work, 500, "0", f"b VBL > 499 :once :file {work / 'c0.ini'}\n", None)
        ram = (work / "ram0.bin").read_bytes()
        base = ram.find(image[sym["start"]:sym["start"] + 48]) - sym["start"]
        self.assertGreater(base, 0)
        word = lambda data, name: int.from_bytes(data[base + sym[name]:base + sym[name] + 2], "big", signed=True)
        self.assertEqual(word(ram, "cur_screen"), 12)
        joy = base + sym["input_state"] + 259
        (work / "up.ini").write_text(f"memwrite ${joy:x} 0x01\ncont\n", encoding="utf-8")
        (work / "stop.ini").write_text(f"memwrite ${joy:x} 0x00\ncont\n", encoding="utf-8")
        (work / "cap.ini").write_text(f"savebin {work / 'ram1.bin'} 0 $80000\nm $ff8200-$ff8260\ncont\n", encoding="utf-8")
        script = "".join(f"b VBL > {v} :once :file {work / f}\n" for v, f in ((599, "up.ini"), (602, "stop.ini"), (799, "cap.ini")))
        log = hs.run_hatari(hatari, TOS, prg, work, 800, "0", script, None)
        ram = (work / "ram1.bin").read_bytes()
        self.assertEqual(word(ram, "cur_screen"), 16)
        self.assertEqual((word(ram, "hero_x"), word(ram, "hero_y")), (16, 144))
        rows = hs.decode_screen(ram, hs.video_base(log))
        expected = sc.expected_screen(fr.Rom(ROM), 6, 16, word(ram, "camera"), palette_index=13, hero=sc.Hero(16, 144, 0, 255, 0, 0, True))
        bad = [(x, y) for y in range(200) for x in range(320) if rows[y][x] != expected[y][x]]
        self.assertEqual(bad[:5], [], f"{len(bad)} pixels differ")

    def run_scenario(self, make_args: list[str], pokes: list[tuple[int, str, int]], capture: int, name: str):
        """Builds the viewer, runs it in Hatari and pokes the stick (`joy`, a byte: 1 up, 2 down, 4 left, 8 right) or the hero's x (`x`, a word) at
        the given VBLs; returns (RAM at the capture VBL, a reader for words by symbol, the Hatari log)."""
        import hatari_shot as hs

        subprocess.run(["make", "-C", str(ROOT), "viewer", *make_args], check=True, capture_output=True)
        nm = subprocess.run(["m68k-linux-gnu-nm", str(ROOT / "build" / "viewer.elf")], check=True, capture_output=True, text=True).stdout.split("\n")
        sym = {line.split()[2]: int(line.split()[0], 16) for line in nm if len(line.split()) == 3}
        image = (ROOT / "build" / "viewer.bin").read_bytes()
        work = ROOT / "build" / name
        work.mkdir(parents=True, exist_ok=True)
        prg = ROOT / "build" / "VIEWER.PRG"
        hatari = shutil.which("hatari")
        (work / "c0.ini").write_text(f"savebin {work / 'ram0.bin'} 0 $80000\ncont\n", encoding="utf-8")
        hs.run_hatari(hatari, TOS, prg, work, 500, "0", f"b VBL > 499 :once :file {work / 'c0.ini'}\n", None)
        base = (work / "ram0.bin").read_bytes().find(image[sym["start"]:sym["start"] + 48]) - sym["start"]
        self.assertGreater(base, 0)
        script = ""
        for i, (vbl, what, value) in enumerate(pokes):
            if what == "joy":
                text = f"memwrite ${base + sym['input_state'] + 259:x} 0x{value:02x}\ncont\n"
            elif what == "space":                                      # the jump key
                text = f"memwrite ${base + sym['input_state'] + 264 + 0x39:x} 0x{value:02x}\ncont\n"
            elif what == "w":                                          # the W key (wing boots)
                text = f"memwrite ${base + sym['input_state'] + 264 + 0x11:x} 0x{value:02x}\ncont\n"
            elif what == "b":                                          # B (Alternate): the sword
                text = f"memwrite ${base + sym['input_state'] + 264 + 0x38:x} 0x{value:02x}\ncont\n"
            elif what == "m":                                          # the M key (debug: the next spell, full magic)
                text = f"memwrite ${base + sym['input_state'] + 264 + 0x32:x} 0x{value:02x}\ncont\n"
            elif what == "p":                                          # the P key (debug: shows the mantra)
                text = f"memwrite ${base + sym['input_state'] + 264 + 0x19:x} 0x{value:02x}\ncont\n"
            elif what in ("h", "g"):                                   # the H and G keys (debug: hit from the right / from the left)
                text = f"memwrite ${base + sym['input_state'] + 264 + (0x23 if what == 'h' else 0x22):x} 0x{value:02x}\ncont\n"
            elif what == "y":                                          # the hero's y (a word)
                text = f"memwrite ${base + sym['hero_y']:x} 0x{value >> 8:02x} 0x{value & 255:02x}\ncont\n"
            else:
                text = f"memwrite ${base + sym['hero_x']:x} 0x{value >> 8:02x} 0x{value & 255:02x}\ncont\n"
            (work / f"poke{i}.ini").write_text(text, encoding="utf-8")
            script += f"b VBL > {vbl} :once :file {work / f'poke{i}.ini'}\n"
        (work / "cap.ini").write_text(f"savebin {work / 'ram1.bin'} 0 $80000\nm $ff8200-$ff8260\ncont\n", encoding="utf-8")
        script += f"b VBL > {capture} :once :file {work / 'cap.ini'}\n"
        log = hs.run_hatari(hatari, TOS, prg, work, capture + 1, "0", script, None)
        ram = (work / "ram1.bin").read_bytes()
        def word(name: str) -> int:                                    # a word by symbol ("symbol+2": at an offset)
            symbol, _, offset = name.partition("+")
            at = base + sym[symbol] + int(offset or 0)
            return int.from_bytes(ram[at:at + 2], "big", signed=True)
        word.raw = lambda name, n: ram[base + sym[name]:base + sym[name] + n]              # bytes by symbol
        return ram, word, log

    def assert_picture(self, rows, expected) -> None:
        bad = [(x, y) for y in range(200) for x in range(320) if rows[y][x] != expected[y][x]]
        self.assertEqual(bad[:5], [], f"{len(bad)} pixels differ")

    ENEMY_SCENES = ((0, 8, "16,144", 360), (0, 4, "240,144", 260), (0, 5, "240,144", 260), (1, 16, "16,144", 240),
                    (1, 7, "240,144", 260), (1, 31, "240,144", 260), (1, 22, "16,144", 240),
                    (1, 29, "16,144", 260), (1, 45, "64,144", 260), (1, 60, "208,144", 260))    # area, screen, hero, the capture's VBL

    def enemy_engine(self, rom, area_index: int, screen: int, word):
        """The model with the enemies of a screen as they are placed, the hero where the viewer has him."""
        import enemy_data as ed
        import enemy_model as em
        import faxanadu_maps as fm

        area = fm.area(rom, area_index)
        props = fm.block_properties(rom, area)
        free = next(b for b in range(256) if em.IMPASSABLE[props[b] & 15] == 0 and props[b] & 15 != em.LADDER)
        eng = em.Engine(rom.prg(14), ed.random_table(rom), bytes(fm.decode_screen(rom, area, screen)[:208]) + bytes([free]) * 48, props)
        eng.hero_x, eng.hero_y = word("hero_x"), word("hero_y")
        for i, (ent, x, y) in enumerate(p for p in ed.placements(rom, area_index, screen) if p[0] in ed.ENEMIES):
            s = eng.sprites[7 - i]
            s.ent, s.x, s.y, s.beh, s.hbox = ent, x, y, 0xFF, ed.entity(rom, ent)["hitbox"]
            s.script = rom.word("SPRITE_BSCRIPTS", ent)
        return eng

    def test_the_enemies_are_drawn_where_the_model_has_them(self) -> None:
        """The picture is the background, the hero and the enemies' pictures from the ROM's own frames (`enemy_model.appearance_offset`, mirrored when
        they face right), for the state the model has after the updates the viewer made (or the one before: the capture can fall between a frame's update
        and its show)."""
        import copy

        import enemy_data as ed
        import enemy_model as em
        import faxanadu_maps as fm
        import faxanadu_rom as fr
        import faxanadu_sprites as fs
        import hatari_shot as hs
        import st_convert as sc

        rom = fr.Rom(ROM)
        for area, screen, hero, vbl in self.ENEMY_SCENES:
            with self.subTest(area=area, screen=screen):
                pal = fm.area(rom, area).palette_index
                plan = sc.plan_for_set(rom, pal)
                palettes = sc.sprite_palettes(rom, pal)
                ram, word, log = self.run_scenario(["ALL=1", f"AREA={area}", f"SCREEN={screen}", f"HERO={hero},0,255,0,0,1", "WORLD=1", "HUD=80,80,0,0,0"], [], vbl, "shots_enemy")
                n = word("en_counter")
                rows = hs.decode_screen(ram, hs.video_base(log))
                eng = self.enemy_engine(rom, area, screen, word)
                states = []
                for k in range(1, n + 1):
                    eng.update_all()
                    if k >= n - 1:
                        states.append((copy.deepcopy(eng.sprites), k))
                worst = []
                for sprites, counter in states:
                    expected = sc.expected_screen(rom, area, screen, word("camera"), state=dict(hp=80, mp=80, experience=0, gold=0, seconds=0),
                                                  hero=sc.Hero(word("hero_x"), word("hero_y"), 0, 255, 0, word("hero_frame"), bool(word("hero_flip"))))
                    for sp in sprites:
                        if sp.ent == em.NONE:
                            continue
                        app = fs.appearance(rom, ed.entity(rom, sp.ent)["appearance"] + em.appearance_offset(sp.ent, sp.phase, counter), "TILEINFO_ENTITY_ADDRS")
                        layer = fs.sprite_layer(fs.place(app, sp.x, sp.y, em.flip_mask(sp.flags)), fs.entity_tiles(rom, sp.ent), palettes)
                        for (x, line), c in layer.items():
                            y = line - word("camera")
                            if sc.ST_TOP <= y < 200 and sc.ST_LEFT <= x + sc.ST_LEFT < sc.ST_LEFT + 256:
                                expected[y][x + sc.ST_LEFT] = plan.slot[c & 0x3F]
                    hx, hy = word("hero_x") + sc.ST_LEFT, word("hero_y") + 32 - word("camera")        # (his own picture is tested elsewhere: not the box round him, nor what of it the NES wraps round to the left edge)
                    bad = [(px, py) for py in range(200) for px in range(320) if rows[py][px] != expected[py][px] and not ((hx - 24 <= px < hx + 40 or hx - 280 <= px < hx - 216) and hy - 8 <= py < hy + 40)]
                    worst.append(bad)
                self.assertTrue(any(not bad for bad in worst), f"area {area} screen {screen}: {[len(b) for b in worst]} pixels differ, e.g. {worst[0][:5]}")

    def test_the_enemies_move_as_the_model_does(self) -> None:
        """Eolis screens 4 and 5 (two Zozuras each) and 8 (a Monodron): the hero stands still far from them (on 4 and 5 the capture is early, before a Zozura reaches him); after n updates (en_counter) every slot is
        where `enemy_model.py` (checked against the game in tests/test_enemy.py) says it is, the hops and the random turns included."""
        import enemy_data as ed
        import enemy_model as em
        import faxanadu_maps as fm
        import faxanadu_rom as fr

        rom = fr.Rom(ROM)
        for area, screen, hero, vbl in self.ENEMY_SCENES:
            with self.subTest(area=area, screen=screen):
                ram, word, _ = self.run_scenario(["ALL=1", f"AREA={area}", f"SCREEN={screen}", f"HERO={hero},0,255,0,0,1", "WORLD=1", "HUD=80,80,0,0,0"], [], vbl, "shots_enemy")
                n = word("en_counter")
                self.assertGreater(n, 60)
                eng = self.enemy_engine(rom, area, screen, word)
                for _ in range(n):
                    eng.update_all()
                raw = word.raw("enemies", 8 * 28)
                for i, s in enumerate(eng.sprites):
                    r = raw[i * 28:(i + 1) * 28]
                    got = (r[0], r[2], r[3], r[4], r[5], r[1], r[6], r[7], r[8], r[10], r[11], r[9], r[13], r[12])
                    want = (s.ent, s.x, s.xf, s.y, s.yf, s.flags, s.phase, s.beh, s.arg1, s.d3, s.d2, s.internal, s.bxf, s.bxfull)
                    self.assertEqual(got, want, f"slot {i} after {n} updates")

    def test_the_sword_kills_the_zozuras_and_they_hurt_him(self) -> None:
        """Eolis screen 4, a Long Sword (it reaches a Zozura, the dagger does not), the hero faces left and swings every 24 frames while two Zozuras walk
        up: each dies of one blow and gives 30 experience (`ENEMY_EXPERIENCE`); a touch takes the damage (7) off the power, and nothing while he is
        invincible (tests/test_enemy.py checks the rules against the game frame by frame)."""
        pokes = []
        for v in range(400, 1100, 24):
            pokes += [(v, "b", 1), (v + 3, "b", 0)]
        ram, word, _ = self.run_scenario(["ALL=1", "AREA=0", "SCREEN=4", "HERO=200,144,0,255,1,0,1", "WORLD=1", "HUD=80,80,0,0,0"], pokes, 1100, "shots_fight")
        state = word.raw("hud_state", 10)
        power, exp = state[0], int.from_bytes(state[2:4], "big")
        self.assertGreater(exp, 0)
        self.assertEqual(exp % 30, 0, exp)
        self.assertEqual((80 - power) % 7, 0, power)

    def test_a_snowman_that_hops_into_him_takes_four_power_a_touch(self) -> None:
        """Area 1 screen 16 (a wall cuts off its left half, so the hero stands at 208): the Snowman leaps at him, and each touch takes its 4 off the power."""
        ram, word, _ = self.run_scenario(["ALL=1", "AREA=1", "SCREEN=16", "HERO=208,144,0,255,0,0,1", "WORLD=1", "HUD=80,80,0,0,0"], [], 600, "shots_touch")
        power = word.raw("hud_state", 1)[0]
        self.assertLess(power, 80)
        self.assertEqual((80 - power) % 4, 0, power)

    def test_a_zozura_that_walks_into_him_takes_seven_power_and_he_is_invincible_for_a_while(self) -> None:
        ram, word, _ = self.run_scenario(["ALL=1", "AREA=0", "SCREEN=4", "HERO=200,144,0,255,0,0,1", "WORLD=1", "HUD=80,80,0,0,0"], [], 700, "shots_touch")
        state = word.raw("hud_state", 10)
        self.assertLess(state[0], 80)
        self.assertEqual((80 - state[0]) % 7, 0, state[0])

    def test_up_at_a_building_door_goes_in_and_walking_off_the_side_comes_out(self) -> None:
        """Eolis screen 1, the hero at the first door (x 48, block 147): a building (the ROM, in jsnes: area 4, screen 7's layout, palette 24,
        tileset 7, hero at 224 and falling to 128 with no sword, facing left). Then he is put at x 240 and walks right off the side: he is back
        in Eolis, at the block of the door (48,144) facing right, in Eolis's colours."""
        import faxanadu_rom as fr
        import hatari_shot as hs
        import st_convert as sc

        rom = fr.Rom(ROM)
        args = ["ALL=1", "AREA=0", "SCREEN=1", "HERO=48,144,0,255,0,0,1", "WORLD=1"]
        ram, word, log = self.run_scenario(args, [(599, "joy", 1), (602, "joy", 0)], 799, "shots_building")
        self.assertEqual((word("cur_area"), word("cur_pal"), word("cur_screen")), (4, 24, 0))
        self.assertEqual((word("hero_x"), word("hero_y"), word("hero_flip")), (224, 128, 0))
        self.assertEqual(word("cur_music"), 15)                # BUILDING_MUSIC: the shop song
        rows = hs.decode_screen(ram, hs.video_base(log))
        self.assert_picture(rows, sc.expected_screen(rom, 4, 7, word("camera"), palette_index=24, tiles_index=7,
                                                     hero=sc.Hero(224, 128, 0, 255, 255, 0, False)))
        ram, word, log = self.run_scenario(args, [(599, "joy", 1), (602, "joy", 0), (699, "x", 240), (700, "joy", 8), (703, "joy", 0)], 899,
                                           "shots_building_out")
        self.assertEqual((word("cur_area"), word("cur_pal"), word("cur_screen")), (0, 0, 1))
        self.assertEqual((word("hero_x"), word("hero_y"), word("hero_flip")), (48, 144, 1))
        self.assertEqual(word("cur_music"), 7)                 # Eolis's song again
        rows = hs.decode_screen(ram, hs.video_base(log))
        self.assert_picture(rows, sc.expected_screen(rom, 0, 1, word("camera"), hero=sc.Hero(48, 144, 0, 255, 0, 0, True)))

    def test_up_at_the_gate_of_eolis_leads_to_trunk(self) -> None:
        """Eolis screen 8, the door at block 156 (a J key is needed: the viewer has all keys): the ROM (jsnes) puts him in Trunk screen 0 at
        16,160 in Trunk's own palette."""
        import faxanadu_rom as fr
        import hatari_shot as hs
        import st_convert as sc

        rom = fr.Rom(ROM)
        ram, word, log = self.run_scenario(["ALL=1", "AREA=0", "SCREEN=8", "HERO=192,144,0,255,0,0,1", "WORLD=1", "VIEWER_DEFS=--defsym NO_ENEMIES=1"],
                                           [(599, "joy", 1), (602, "joy", 0)], 799, "shots_outside")
        self.assertEqual((word("cur_area"), word("cur_pal"), word("cur_screen")), (1, 6, 0))
        self.assertEqual((word("hero_x"), word("hero_y")), (16, 160))
        self.assertEqual(word("cur_music"), 3)                 # AREA_TO_MUSIC_TABLE: Trunk's song
        rows = hs.decode_screen(ram, hs.video_base(log))
        self.assert_picture(rows, sc.expected_screen(rom, 1, 0, word("camera"), hero=sc.Hero(16, 160, 0, 255, 0, 0, True)))

    def test_walking_off_the_side_of_trunk_screen_7_leads_to_apolune(self) -> None:
        """Trunk screen 7 has no screen to its right: the ROM's town table (AREA_TOWN_TRANSITIONS_DATA) sends him to area 3 (the towns) screen 0
        at 32,144 in palette 27. (He is held at y 112 without physics, so that only the edge is tested.)"""
        import faxanadu_rom as fr
        import hatari_shot as hs
        import st_convert as sc

        rom = fr.Rom(ROM)
        ram, word, log = self.run_scenario(["ALL=1", "AREA=1", "SCREEN=7", "HERO=240,112,0,255,0,0,1", "WORLD=3", "VIEWER_DEFS=--defsym NO_PHYSICS=1"],
                                           [(599, "joy", 8), (602, "joy", 0)], 799, "shots_edge")
        self.assertEqual((word("cur_area"), word("cur_pal"), word("cur_screen")), (3, 27, 0))
        self.assertEqual((word("hero_x"), word("hero_y")), (32, 144))
        rows = hs.decode_screen(ram, hs.video_base(log))
        self.assert_picture(rows, sc.expected_screen(rom, 3, 0, word("camera"), hero=sc.Hero(32, 144, 0, 255, 0, 0, True)))

    def test_a_door_that_needs_a_key_stays_shut_without_it(self) -> None:
        """The gate of Eolis needs the J key (door requirement 4): with no keys (KEYS=0) Up does nothing."""
        ram, word, log = self.run_scenario(["ALL=1", "AREA=0", "SCREEN=8", "HERO=192,144,0,255,0,0,1", "WORLD=1", "VIEWER_DEFS=--defsym KEYS=0"],
                                           [(599, "joy", 1), (602, "joy", 0)], 799, "shots_locked")
        self.assertEqual((word("cur_area"), word("cur_screen")), (0, 8))


    # ------------------------------------------------------------------------------------------------------------------ text and the mantra
    @staticmethod
    def text_layer(rows, font, slot, glyphs):
        """Draws text on the expected picture: glyphs = [(x, y, char, inverted)]; the ROM's font, one bit a pixel, light on black (or the other way)."""
        for x, y, char, inverted in glyphs:
            g = font[8 * (ord(char) - 32):8 * (ord(char) - 32) + 8] if 32 <= ord(char) < 128 else bytes(8)
            for dy in range(8):
                for dx in range(8):
                    lit = bool(g[dy] >> (7 - dx) & 1) != inverted
                    rows[y + dy][x + dx] = slot if lit else 0

    @staticmethod
    def box_layer(rows, slot, group0, y0, groups, lines):
        """A two-pixel frame round black, as draw_box makes it."""
        for y in range(y0, y0 + lines):
            for x in range(16 * group0, 16 * (group0 + groups)):
                edge = y - y0 < 2 or y - y0 >= lines - 2 or x - 16 * group0 < 2 or x >= 16 * (group0 + groups) - 2
                rows[y][x] = slot if edge else 0

    @staticmethod
    def bright_slot(rom, palette_index):
        """The palette's brightest colour (the first of them): the colour the text is drawn in."""
        import st_convert as sc

        colours = sc.plan_for_set(rom, palette_index).colours
        colours = colours + [(0, 0, 0)] * (16 - len(colours))
        best = 1
        for i in range(1, 16):
            if sum(colours[i]) > sum(colours[best]):
                best = i
        return best

    def text_box(self, rows, rom, palette_index, text):
        """The picture with a message box on it, as draw_text_box lays it out."""
        import faxanadu_text as ft

        slot, font = self.bright_slot(rom, palette_index), ft.font(rom)
        lines = text.split("\n")
        height = 10 * len(lines) + 8
        y0 = 32 + (168 - height) // 2
        self.box_layer(rows, slot, 5, y0, 10, height)
        self.text_layer(rows, font, slot, [(96 + 8 * i, y0 + 4 + 10 * n, c, False) for n, line in enumerate(lines) for i, c in enumerate(line)])

    def test_the_p_key_shows_the_mantra_in_a_box_and_a_button_takes_it_away(self) -> None:
        """The ROM's password of the state the game has (a Novice with a dagger and leather armour, no spell), 16 characters to a line, in a box over
        the window; a button takes it away and the picture is the game's again."""
        import faxanadu_rom as fr
        import password_model as pm
        import st_convert as sc

        rom = fr.Rom(ROM)
        mantra = pm.password(pm.State(0, 0, 0, 0, 0, 0, pm.UNSET, pm.UNSET, pm.UNSET, weapons=[0], armors=[0]))
        self.assertEqual(len(mantra), 11)
        ram, word, log = self.run_scenario([], [(599, "p", 1), (602, "p", 0)], 699, "shots_mantra")
        import hatari_shot as hs
        rows = hs.decode_screen(ram, hs.video_base(log))
        expected = sc.expected_screen(rom, 0, 1, word("camera"), hero=sc.Hero(144, 144, 0, 255, 0, 0, True))
        self.text_box(expected, rom, 0, mantra)
        self.assert_picture(rows, expected)
        self.assertEqual(word.raw("pw_text", 12), mantra.encode() + b"\0")
        ram, word, log = self.run_scenario([], [(599, "p", 1), (602, "p", 0), (699, "joy", 0x80), (702, "joy", 0)], 799, "shots_mantra_gone")
        rows = hs.decode_screen(ram, hs.video_base(log))
        self.assert_picture(rows, sc.expected_screen(rom, 0, 1, word("camera"), hero=sc.Hero(144, 144, 0, 255, 0, 0, True)))

    def test_the_mantra_holds_the_rank_and_the_chosen_spell(self) -> None:
        """Rank 12 and the Fire spell chosen: a longer mantra, the one the ROM makes for that state."""
        import faxanadu_rom as fr
        import hatari_shot as hs
        import password_model as pm
        import st_convert as sc

        rom = fr.Rom(ROM)
        mantra = pm.password(pm.State(0, 12, 0, 0, 0, 0, pm.UNSET, 2, pm.UNSET, weapons=[0], armors=[0], spells=[2]))
        ram, word, log = self.run_scenario(["VIEWER_DEFS=--defsym TITLE=12 --defsym MAGIC=2"], [(599, "p", 1), (602, "p", 0)], 699, "shots_mantra_2")
        rows = hs.decode_screen(ram, hs.video_base(log))
        expected = sc.expected_screen(rom, 0, 1, word("camera"), hero=sc.Hero(144, 144, 0, 255, 0, 0, True), state=dict(hp=16, mp=0, experience=0, gold=0, seconds=0))
        self.text_box(expected, rom, 0, mantra)
        self.assert_picture(rows, expected)


    # ------------------------------------------------------------------------------------------------------------------ the menu and the entry
    CELLS = 66
    UP, DOWN, LEFT, RIGHT, FIRE = 1, 2, 4, 8, 0x80

    @classmethod
    def cell_after(cls, cell: int, move: int) -> int:
        """The cursor in the grid of 64 characters, DEL and END (mantra_entry)."""
        if move == cls.UP:
            cell -= 8
            if cell < 0:
                cell += 64
                if cell >= cls.CELLS:
                    cell -= 8
            return cell
        if move == cls.DOWN:
            cell += 8
            return cell if cell < cls.CELLS else cell & 7
        if move == cls.LEFT:
            return cell - 1 if cell else cls.CELLS - 1
        return cell + 1 if cell < cls.CELLS - 1 else 0

    @classmethod
    def moves(cls, start: int, goal: int) -> list[int]:
        """The shortest way between two cells."""
        seen, queue = {start: []}, [start]
        for cell in queue:
            if cell == goal:
                return seen[cell]
            for move in (cls.UP, cls.DOWN, cls.LEFT, cls.RIGHT):
                nxt = cls.cell_after(cell, move)
                if nxt not in seen:
                    seen[nxt] = seen[cell] + [move]
                    queue.append(nxt)
        raise AssertionError("unreachable")

    @classmethod
    def typing(cls, text: str, first_vbl: int, end: bool = True) -> tuple[list[tuple[int, str, int]], int]:
        """Pokes that move the cursor to each character of `text` and take it, then (end) to END and take that: (pokes, the VBL after the last)."""
        import password_model as pm

        pokes, vbl, cell = [], first_vbl, 0
        for target in [pm.CHARS.index(c) for c in text] + ([65] if end else []):
            for move in cls.moves(cell, target) + [cls.FIRE]:
                pokes += [(vbl, "joy", move), (vbl + 2, "joy", 0)]
                vbl += 4
            cell = target
        return pokes, vbl

    def entry_box(self, rows, rom, palette_index, text, cell, wrong=False):
        """mantra_entry's screen as it is laid out."""
        import faxanadu_text as ft
        import password_model as pm

        slot, font = self.bright_slot(rom, palette_index), ft.font(rom)
        self.box_layer(rows, slot, 2, 36, 16, 160)
        glyphs = [(88 + 8 * i, 44, c, False) for i, c in enumerate(ft.password_lines(rom)[1])]
        for n in range(66):
            x, y = (96 + 16 * (n & 7), 98 + 10 * (n >> 3)) if n < 64 else (96 if n == 64 else 136, 178)
            for i, c in enumerate(pm.CHARS[n] if n < 64 else ("DEL" if n == 64 else "END")):
                glyphs.append((x + 8 * i, y, c, n == cell))
        for i in range(pm.MAX_CHARS):
            c = text[i] if i < len(text) else "_" if i == len(text) else " "
            glyphs.append((96 + 8 * (i & 15), 62 + 10 * (i >> 4), c, False))
        if wrong:
            glyphs += [(64 + 8 * i, 84, c, False) for i, c in enumerate(ft.password_lines(rom)[0])]
        self.text_layer(rows, font, slot, glyphs)

    def menu_box(self, rows, rom, palette_index, selected):
        import faxanadu_text as ft

        slot, font = self.bright_slot(rom, palette_index), ft.font(rom)
        self.box_layer(rows, slot, 5, 88, 10, 56)
        self.text_layer(rows, font, slot, [(104 + 8 * i, 96, c, selected == 0) for i, c in enumerate("Start")]
                        + [(104 + 8 * i, 114, c, selected == 1) for i, c in enumerate("Enter mantra")])

    def test_the_menu_starts_the_game_or_goes_to_the_entry_of_a_mantra(self) -> None:
        import faxanadu_rom as fr
        import hatari_shot as hs
        import st_convert as sc

        rom = fr.Rom(ROM)
        args = ["VIEWER_DEFS=--defsym MENU=1"]
        for pokes, selected in (([], 0), ([(599, "joy", self.DOWN), (602, "joy", 0)], 1)):
            ram, word, log = self.run_scenario(args, pokes, 699, "shots_menu")
            expected = sc.expected_screen(rom, 0, 1, word("camera"))                      # (the hero is not on it yet)
            self.menu_box(expected, rom, 0, selected)
            self.assert_picture(hs.decode_screen(ram, hs.video_base(log)), expected)
        ram, word, log = self.run_scenario(args, [(599, "joy", self.FIRE), (602, "joy", 0)], 799, "shots_menu")
        self.assertEqual((word("hero_dead"), word("menu_sel")), (0, 0))
        self.assert_picture(hs.decode_screen(ram, hs.video_base(log)), sc.expected_screen(rom, 0, 1, word("camera"), hero=sc.Hero(144, 144, 0, 255, 0, 0, True)))

    def test_a_mantra_is_typed_in_a_grid_and_the_game_starts_with_what_it_holds(self) -> None:
        """Down and fire take 'Enter mantra'; the stick moves over the grid and fire takes a character; END asks the game to read it. The mantra
        of a Chevalier (rank 5) with the Thunder spell (the ROM's, from the model) starts the game with that rank (its experience and gold), the
        spell, full power and magic. Before that: the picture of the entry screen, and a wrong mantra shows the ROM's message."""
        import faxanadu_rom as fr
        import hatari_shot as hs
        import password_model as pm
        import st_convert as sc

        rom = fr.Rom(ROM)
        args = ["VIEWER_DEFS=--defsym MENU=1"]
        start = [(599, "joy", self.DOWN), (602, "joy", 0), (610, "joy", self.FIRE), (613, "joy", 0)]
        mantra = pm.password(pm.State(0, 5, 0, 0, 0, 0, pm.UNSET, 1, pm.UNSET, weapons=[0], armors=[0], spells=[1]))
        pokes, end = self.typing(mantra[:3], 620, end=False)
        ram, word, log = self.run_scenario(args, start + pokes, end + 10, "shots_entry")
        cell = pm.CHARS.index(mantra[2])
        expected = sc.expected_screen(rom, 0, 1, word("camera"))
        self.entry_box(expected, rom, 0, mantra[:3], cell)
        self.assert_picture(hs.decode_screen(ram, hs.video_base(log)), expected)
        self.assertEqual(word.raw("ent_text", 4), mantra[:3].encode() + b"\0")
        pokes, end = self.typing("AAAA", 620)                                              # (a wrong one)
        ram, word, log = self.run_scenario(args, start + pokes, end + 10, "shots_entry_wrong")
        expected = sc.expected_screen(rom, 0, 1, word("camera"))
        self.entry_box(expected, rom, 0, "AAAA", 65, wrong=True)
        self.assert_picture(hs.decode_screen(ram, hs.video_base(log)), expected)
        pokes, end = self.typing(mantra, 620)
        ram, word, log = self.run_scenario(args, start + pokes, end + 200, "shots_entry_ok")
        self.assertEqual((word("hero_title"), word("hero_magic"), word("hero_dead")), (5, 1, 0))
        self.assertEqual((word("hud_state"), word("hud_state+2"), word("hud_state+4"), word("hud_state+6")),
                         (0x5050, rom.word("PLAYER_TITLE_EXP_NEEDED", 4), 0, rom.word("PLAYER_TITLE_GOLD", 4)), "full power and magic, the rank's experience and gold")
        expected = sc.expected_screen(rom, 0, 1, word("camera"), hero=sc.Hero(144, 144, 0, 255, 0, 0, True),
                                      state=dict(hp=80, mp=80, experience=word("hud_state+2"), gold=word("hud_state+6"), seconds=0))
        self.assert_picture(hs.decode_screen(ram, hs.video_base(log)), expected)

    def test_end_with_nothing_written_goes_back_to_the_menu(self) -> None:
        import faxanadu_rom as fr
        import hatari_shot as hs
        import st_convert as sc

        rom = fr.Rom(ROM)
        start = [(599, "joy", self.DOWN), (602, "joy", 0), (610, "joy", self.FIRE), (613, "joy", 0)]
        pokes, end = self.typing("", 620)
        ram, word, log = self.run_scenario(["VIEWER_DEFS=--defsym MENU=1"], start + pokes, end + 100, "shots_entry_back")
        expected = sc.expected_screen(rom, 0, 1, word("camera"), hero=sc.Hero(144, 144, 0, 255, 0, 0, True))       # (the screens were made again: he is on it)
        self.menu_box(expected, rom, 0, 1)
        self.assert_picture(hs.decode_screen(ram, hs.video_base(log)), expected)


if __name__ == "__main__":
    unittest.main()
