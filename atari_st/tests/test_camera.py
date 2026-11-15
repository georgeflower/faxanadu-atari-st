"""The camera (`camera_follow` in src/viewer.s, AGENTS.md 5d): the window of 168 lines moves only when the hero would leave it (to 0 when
his top is above its first line, to 40 when his feet are below its last), and then 8 lines at a time, each step a whole picture, while the
game stands still. Entering a screen picks the camera from his height.

Needs the ROM, Hatari, the m68k binutils and a TOS image (TOS or TOS_PAL).
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
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"
TOS = Path(os.environ.get("TOS") or os.environ.get("TOS_PAL") or "")
JOY = 259                  # input_state + 259: the stick (bits 0-3 up, down, left, right)
KEYS = 264                 # input_state + 264 + scan code: a key held
SPACE = 0x39               # A (the jump; with the wing boots, A held flies)
UP, DOWN, RIGHT = 0x01, 0x02, 0x08


@unittest.skipUnless(ROM.is_file() and shutil.which("hatari") and shutil.which("m68k-linux-gnu-as") and shutil.which("ca65") and TOS.is_file(),
                     "needs the ROM, cc65, hatari, the m68k binutils and a TOS image (TOS or TOS_PAL)")
class CameraTests(unittest.TestCase):
    def run_scene(self, args: list[str], pokes: list[tuple[int, int, int]], captures: list[int], name: str):
        """Builds the viewer with `args`, writes `pokes` (VBL, offset in input_state, value) and takes the RAM and the screen on show at each
        VBL of `captures`. Returns (base, sym, [(vbl, ram, video base)])."""
        import hatari_shot as hs

        subprocess.run(["make", "-C", str(ROOT), "viewer", *args], check=True, capture_output=True)
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
        for i, (v, offset, value) in enumerate(pokes):
            (work / f"poke{i}.ini").write_text(f"memwrite ${base + sym['input_state'] + offset:x} {value:#04x}\ncont\n", encoding="utf-8")
            script += f"b VBL > {v} :once :file {work / f'poke{i}.ini'}\n"
        for v in captures:
            (work / f"cap{v}.ini").write_text(f"savebin {work / f'ram{v}.bin'} 0 $80000\nm $ff8200-$ff8204\ncont\n", encoding="utf-8")
            script += f"b VBL > {v} :once :file {work / f'cap{v}.ini'}\n"
        log = hs.run_hatari(hatari, TOS, prg, work, max(captures) + 1, "0", script, None)
        bases = [(int(m.group(2), 16) << 16) | (int(m.group(4), 16) << 8)
                 for m in re.finditer(r"^00FF8200: ([0-9a-fA-F]{2}) ([0-9a-fA-F]{2}) ([0-9a-fA-F]{2}) ([0-9a-fA-F]{2})", log, re.M)]
        self.assertEqual(len(bases), len(captures))
        return base, sym, [(v, (work / f"ram{v}.bin").read_bytes(), shown) for v, shown in zip(captures, bases)]

    @staticmethod
    def reader(ram: bytes, base: int, sym: dict):
        def word(name: str, offset: int = 0) -> int:
            return int.from_bytes(ram[base + sym[name] + offset:base + sym[name] + offset + 2], "big", signed=True)
        return word

    def cameras_shown(self, area: int, screen: int, base: int, sym: dict, shots, cameras) -> list:
        """For each shot: the camera of `cameras` whose picture (the converter's, with the hero as the RAM has him and the HUD's state) equals
        the screen on show, or None."""
        import faxanadu_rom as fr
        import hatari_shot as hs
        import st_convert as sc

        rom = fr.Rom(ROM)
        cache = {}
        seen = []
        for v, ram, shown in shots:
            word = self.reader(ram, base, sym)
            hud = ram[base + sym["hud_state"]:base + sym["hud_state"] + 10]
            state = dict(hp=hud[0], mp=hud[1], experience=int.from_bytes(hud[2:4], "big"), gold=int.from_bytes(hud[4:8], "big"), seconds=hud[8])
            hero = (word("hero_x"), word("hero_y"), 0, 255, 0, word("hero_frame"), bool(word("hero_flip")))
            rows = hs.decode_screen(ram, shown)
            found = None
            for c in cameras:
                key = (c, hero, tuple(state.items()))
                if key not in cache:
                    cache[key] = self.expected(rom, area, screen, c, state, hero)
                if rows == cache[key]:
                    found = c
                    break
            seen.append((v, found, word("camera"), hero[1]))
        return seen

    @staticmethod
    def expected(rom, area: int, screen: int, camera: int, state: dict, hero: tuple):
        """The converter's picture, the hero's pixels over the opaque pixels of blocks he stands behind left out (src/enemy.s behind_set, as in
        test_viewer's ladder test)."""
        import behind
        import faxanadu_maps as fm
        import st_convert as sc

        picture = sc.expected_screen(rom, area, screen, camera, state=state, hero=sc.Hero(*hero))
        a = fm.area(rom, area)
        halves = behind.halves(rom, a, screen, hero[0], hero[1])
        if halves:
            opaque = behind.opaque_screen(rom, a, screen)
            background = sc.expected_screen(rom, area, screen, camera, state=state)
            for y in range(200):
                for x in range(320):
                    if picture[y][x] != background[y][x]:
                        line, col = y + camera, x - sc.ST_LEFT
                        if 0 <= col < 256 and 32 <= line < 240 and halves & (1 << (((col - hero[0]) >> 3) & 1)) and opaque[line - 32][col]:
                            picture[y][x] = background[y][x]
        return picture

    def assert_smooth(self, seen: list, start: int, end: int) -> None:
        """The cameras shown go from `start` to `end` through every 8 lines between, each a whole picture (three frames each), nothing else."""
        step = 8 if end > start else -8
        path = list(range(start, end + step, step))
        shown = [c for _, c, _, _ in seen if c is not None]
        runs = [c for i, c in enumerate(shown) if i == 0 or shown[i - 1] != c]
        if runs[:1] != [start]:                       # (before the move he walks: the RAM is a pass ahead of the picture on show, which then matches no camera)
            self.assertEqual(seen[0][2], start, f"the camera before the move: {seen}")
            runs.insert(0, start)
        self.assertEqual(runs, path, f"cameras shown (VBL, camera, the camera variable, y): {seen}")
        first = next(i for i, s in enumerate(seen) if s[1] == path[1])
        last = max(i for i, s in enumerate(seen) if s[1] == path[-2])
        self.assertTrue(all(s[1] is not None for s in seen[first:last + 1]), f"a picture between the steps is not a whole camera's: {seen}")
        for c in path[1:-1]:
            self.assertEqual(sum(1 for s in seen if s[1] == c), 3, f"camera {c} not on show for three frames: {seen}")

    def test_a_jump_onto_a_higher_platform_keeps_the_camera(self) -> None:
        """Trunk screen 37: he stands on a ledge at 120,80 (camera 40), jumps up onto the one above (y 48) and walks on along it to the right (the
        author's report, Fax085: the old rule moved the window to camera 0 at his first step there, y under 56). His top never leaves the window
        (y 40 and more): the camera stays 40 in every frame, and the picture at the end is the converter's."""
        captures = list(range(596, 680, 4)) + [700]
        pokes = [(599, KEYS + SPACE, 1), (599, JOY, RIGHT), (640, KEYS + SPACE, 0), (655, JOY, 0)]
        base, sym, shots = self.run_scene(["AREA=1", "SCREEN=37", "CAMERA=40", "HERO=120,80,0,255,0,0,1", "VIEWER_DEFS=--defsym NO_ENEMIES=1"],
                                          pokes, captures, "shots_cam_jump")
        ys, xs = [], []
        for v, ram, _ in shots:
            word = self.reader(ram, base, sym)
            self.assertEqual(word("camera"), 40, f"VBL {v}")
            ys.append(word("hero_y"))
            xs.append(word("hero_x"))
        self.assertEqual(ys[0], 80, "standing on the lower ledge first")
        self.assertGreaterEqual(min(ys), 40, ys)
        self.assertEqual(ys[-1], 48, f"on the higher ledge: {ys}")
        landed = ys.index(48)
        self.assertGreater(xs[-1], xs[landed] + 8, f"and walked on along it: {xs}")
        late = [self.reader(ram, base, sym)("late_frames", 2) for _, ram, _ in shots]
        self.assertEqual(late[-1], late[0], f"late frames: {late}")
        seen = self.cameras_shown(1, 37, base, sym, shots[-1:], (40,))
        self.assertEqual(seen[0][1], 40, "the picture at the end")

    def test_a_flight_up_with_the_wing_boots_moves_the_camera_smoothly(self) -> None:
        """Eolis screen 1, the wing boots on: Up and A held from the floor (y 144, camera 40) fly him up a pixel a frame. When his top passes the
        window's first line (y 39) the game stands still and the window moves to camera 0 in five steps of 8 lines, each picture whole (the
        converter's at that camera with him where he is); then he flies on. No frame is late."""
        captures = list(range(690, 750))
        pokes = [(599, KEYS + SPACE, 1), (599, JOY, UP)]
        base, sym, shots = self.run_scene(["AREA=0", "SCREEN=1", "CAMERA=40", "HERO=144,144,0,255,0,0,1",
                                           "VIEWER_DEFS=--defsym NO_ENEMIES=1 --defsym WINGS=90"], pokes, captures, "shots_cam_fly")
        seen = self.cameras_shown(0, 1, base, sym, shots, (40, 32, 24, 16, 8, 0))
        self.assertTrue(seen[-1][2] == 0 and seen[-1][3] < 30, f"he flies on afterwards: {seen}")
        self.assert_smooth(seen, 40, 0)
        moving = [s[3] for s in seen if s[1] in (32, 24, 16, 8)]
        self.assertEqual(set(moving), {39}, f"he stands still while the window moves: {seen}")
        late = [self.reader(ram, base, sym)("late_frames", 2) for _, ram, _ in shots]
        self.assertEqual(late[-1], late[0], f"late frames: {late}")

    def test_walking_down_moves_the_camera_smoothly(self) -> None:
        """The demo movement (NO_PHYSICS, 2 pixels a frame) in Eolis screen 1 from y 100 with camera 0, the stick down: when his feet pass the
        window's last line (y 137 and more) the window goes to camera 40 in steps of 8, each picture whole."""
        captures = list(range(600, 660))
        pokes = [(599, JOY, DOWN), (630, JOY, 0)]
        base, sym, shots = self.run_scene(["AREA=0", "SCREEN=1", "CAMERA=0", "HERO=144,100,0,255,0,0,1", "VIEWER_DEFS=--defsym NO_PHYSICS=1"],
                                          pokes, captures, "shots_cam_down")
        seen = self.cameras_shown(0, 1, base, sym, shots, (0, 8, 16, 24, 32, 40))
        self.assert_smooth(seen, 0, 40)
        moving = {s[3] for s in seen if s[1] in (8, 16, 24, 32)}
        self.assertEqual(len(moving), 1, seen)
        self.assertGreater(moving.pop(), 136)
        word = self.reader(shots[-1][1], base, sym)
        self.assertEqual(word("camera"), 40)

    def test_a_door_to_a_high_place_picks_camera_0(self) -> None:
        """Entering a screen picks the camera from his height (camera 0 when his y is under 88, else 40), as before. Trunk: the door of
        screen 41 (block 146, no key) leads to screen 40 with him at x 208, y 48 (the ROM's door record): Up (poked) there gives camera 0, the
        picture the converter's. (The castle door of Eolis, to y 144 and camera 40, is in test_viewer.py.)"""
        import faxanadu_rom as fr
        import faxanadu_maps as fm

        rom = fr.Rom(ROM)
        a = fm.area(rom, 1)
        door = next(d for d in fm.doors(rom, a) if d.screen == 41)
        self.assertEqual((door.block, door.start, fm.door_destination(rom, a, door)[:3]), (146, 0x3D, (40, a.palette_index, 0)))
        pokes = [(599, JOY, UP), (602, JOY, 0)]
        base, sym, shots = self.run_scene(["ALL=1", "AREA=1", "SCREEN=41", "CAMERA=40", "HERO=32,144,0,255,0,0,1", "VIEWER_DEFS=--defsym NO_ENEMIES=1"],
                                          pokes, [590, 720], "shots_cam_door")
        word = self.reader(shots[0][1], base, sym)
        self.assertEqual((word("cur_screen"), word("hero_y"), word("camera")), (41, 144, 40))
        word = self.reader(shots[-1][1], base, sym)
        self.assertEqual((word("cur_screen"), word("hero_x"), word("hero_y"), word("camera")), (40, 208, 48, 0))
        seen = self.cameras_shown(1, 40, base, sym, shots[-1:], (0,))
        self.assertEqual(seen[0][1], 0, "the picture after the door")

if __name__ == "__main__":
    unittest.main()
