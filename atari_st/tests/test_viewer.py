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
        subprocess.run(["make", "-C", str(ROOT), "viewer", f"AREA={area}", f"SCREEN={screen}", f"CAMERA={camera}", f"HERO={hero}", f"HUD={hud}", f"HUD2={hud2}"], check=True,
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
        """Hold the stick right (poked into the program's input state through Hatari's debugger) from VBL 600 to 650, let go, and
        capture at 700: he stands facing right at his limit, x = 224, in the first walk frame, and the rest of the picture is clean."""
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
        script = "".join(f"b VBL > {v} :once :file {work / f}\n" for v, f in ((599, "right.ini"), (649, "stop.ini"), (699, "cap.ini")))
        log = hs.run_hatari(hatari, TOS, prg, work, 700, "0", script, None)
        ram = (work / "ram1.bin").read_bytes()
        rows = hs.decode_screen(ram, hs.video_base(log))
        expected = sc.expected_screen(fr.Rom(ROM), 0, 1, 40, hero=sc.Hero(224, 144, 0, 255, 0, 0, False))
        bad = [(x, y) for y in range(200) for x in range(320) if rows[y][x] != expected[y][x]]
        self.assertEqual(bad[:5], [], f"{len(bad)} pixels differ")

    def test_a_hud_change_during_play_reaches_both_screens_and_the_background(self) -> None:
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
        for name in ("buf_a", "buf_b", "buf_bg"):
            address = int.from_bytes(ram[base + sym[name]:base + sym[name] + 4], "big")
            rows = hs.decode_screen(ram, address)
            bad = [(x, y) for y in range(32) for x in range(320) if rows[y][x] != expected[y][x]]
            self.assertEqual(bad[:5], [], f"{name}: {len(bad)} HUD pixels differ")


if __name__ == "__main__":
    unittest.main()
