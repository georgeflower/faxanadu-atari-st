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

        subprocess.run(["make", "-C", str(ROOT), "viewer"], check=True, capture_output=True)
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
            (work / f"cap{v}.ini").write_text(f"savebin {work / f'ram{v}.bin'} 0 $80000\ncont\n", encoding="utf-8")
            script += f"b VBL > {v} :once :file {work / f'cap{v}.ini'}\n"
        hs.run_hatari(hatari, TOS, prg, work, 701, "0", script, None)

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


if __name__ == "__main__":
    unittest.main()
